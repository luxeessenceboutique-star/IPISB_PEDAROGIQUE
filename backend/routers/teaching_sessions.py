import re
from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from deps import get_current_user, get_db, CurrentUser
from models import TeachingSessionStart, TeachingSessionPositionUpdate, TeachingSessionEnd
from utils.notify import notify_users
from utils.session_feedback import create_feedback_requests

router = APIRouter(prefix="/teaching-sessions", tags=["teaching-sessions"])


def _authorized(course_id: str, class_id: str, user: CurrentUser, db: Client) -> bool:
    """Admin, or a professor who (a) owns the course and (b) has that exact
    course assigned to that exact class via class_courses. Owning the course
    is deliberately not sufficient on its own — a professor is authorized to
    teach THIS class only if the course is actually scheduled there, not
    just because they authored it (see also spec §25: 'do not assume course
    owner = automatically authorized to teach every class')."""
    if user.is_admin():
        return True
    if not user.is_prof():
        return False
    course = db.from_("courses").select("professor_id").eq("id", course_id).execute().data
    if not course or course[0]["professor_id"] != user.id:
        return False
    link = (
        db.from_("class_courses")
        .select("id")
        .eq("course_id", course_id)
        .eq("class_id", class_id)
        .execute()
        .data
    )
    return bool(link)


def _parse_dt(value: str) -> datetime:
    # Postgres/PostgREST serializes fractional seconds with trailing zeros
    # stripped (e.g. ".81893" instead of ".818930"), which datetime.fromisoformat
    # can reject depending on Python version/precision expectations — pad/
    # truncate to exactly 6 digits so parsing is reliable regardless.
    value = value.replace("Z", "+00:00")
    value = re.sub(r"\.(\d+)", lambda m: "." + m.group(1)[:6].ljust(6, "0"), value)
    return datetime.fromisoformat(value)


def _enrich_sessions(rows: list[dict], db: Client) -> list[dict]:
    """Adds course/class display names, module titles for the recorded
    start/end position (spec §18 'content covered'), and feedback counts —
    everything the Phase 4 dashboard needs, batched to avoid N+1 queries."""
    if not rows:
        return []

    course_ids = list({r["course_id"] for r in rows if r.get("course_id")})
    class_ids = list({r["class_id"] for r in rows if r.get("class_id")})
    prof_ids = list({r["professor_id"] for r in rows if r.get("professor_id")})
    course_map = {c["id"]: c["title"] for c in (db.from_("courses").select("id, title").in_("id", course_ids).execute().data or [])} if course_ids else {}
    class_map = {c["id"]: c["name"] for c in (db.from_("classes").select("id, name").in_("id", class_ids).execute().data or [])} if class_ids else {}
    # Admin view needs "which professor" (spec §17); harmless/unused for a
    # professor's own list since it's always their own name.
    prof_map = {p["id"]: p["full_name"] for p in (db.from_("profiles").select("id, full_name").in_("id", prof_ids).execute().data or [])} if prof_ids else {}

    module_ids: set[str] = set()
    for r in rows:
        for key in ("start_position", "end_position"):
            pos = r.get(key)
            if pos and pos.get("module_id"):
                module_ids.add(pos["module_id"])
    module_map: dict[str, str] = {}
    if module_ids:
        mods = db.from_("course_modules").select("id, title").in_("id", list(module_ids)).execute().data or []
        module_map = {m["id"]: m["title"] for m in mods}

    session_ids = [r["id"] for r in rows]
    invited_rows = db.from_("session_feedback_requests").select("teaching_session_id").in_("teaching_session_id", session_ids).execute().data or []
    response_rows = db.from_("session_feedback_responses").select("teaching_session_id").in_("teaching_session_id", session_ids).execute().data or []
    invited_count: dict[str, int] = {}
    for x in invited_rows:
        invited_count[x["teaching_session_id"]] = invited_count.get(x["teaching_session_id"], 0) + 1
    response_count: dict[str, int] = {}
    for x in response_rows:
        response_count[x["teaching_session_id"]] = response_count.get(x["teaching_session_id"], 0) + 1

    out = []
    for r in rows:
        start_pos = r.get("start_position") or {}
        end_pos = r.get("end_position") or {}
        out.append({
            **r,
            "course_title": course_map.get(r["course_id"], "—"),
            "class_name": class_map.get(r["class_id"], "—"),
            "professor_name": prof_map.get(r["professor_id"], "—"),
            "start_module_title": module_map.get(start_pos.get("module_id")),
            "end_module_title": module_map.get(end_pos.get("module_id")),
            "feedback_invited": invited_count.get(r["id"], 0),
            "feedback_responses": response_count.get(r["id"], 0),
        })
    return out


@router.get("/active")
async def get_active_session(
    course_id: str,
    class_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Used on page load to show 'Resume Session' instead of 'Start Session'
    after a refresh/reconnect — an ACTIVE session must never silently
    disappear (spec §21)."""
    if not user.can_create():
        raise HTTPException(403, "Professor or admin only")
    rows = (
        db.from_("teaching_sessions")
        .select("*")
        .eq("professor_id", user.id)
        .eq("course_id", course_id)
        .eq("class_id", class_id)
        .eq("status", "active")
        .execute()
        .data or []
    )
    return rows[0] if rows else None


@router.get("/analytics/summary")
async def get_analytics_summary(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Admin-only institute-wide rollup (spec §17/§29 Phase 5): totals,
    response rate, overall average, and a professor/course comparison —
    the same raw per-response data as Phase 4's per-session results, just
    grouped differently, never a second copy of it."""
    if not user.is_admin():
        raise HTTPException(403, "Admin only")

    sessions = db.from_("teaching_sessions").select("id, course_id, professor_id, status").execute().data or []
    session_ids = [s["id"] for s in sessions]

    invited = (
        db.from_("session_feedback_requests").select("teaching_session_id").in_("teaching_session_id", session_ids).execute().data or []
        if session_ids else []
    )
    responses = (
        db.from_("session_feedback_responses").select("teaching_session_id, answers").in_("teaching_session_id", session_ids).execute().data or []
        if session_ids else []
    )

    # Every individual 1-5 rating, flattened per session — same raw values
    # the per-session results endpoint averages, just regrouped here by
    # professor/course instead of by question.
    session_ratings: dict[str, list[int]] = {}
    for r in responses:
        session_ratings.setdefault(r["teaching_session_id"], []).extend(r["answers"].values())
    all_ratings = [v for vals in session_ratings.values() for v in vals]

    course_ids = list({s["course_id"] for s in sessions if s.get("course_id")})
    prof_ids = list({s["professor_id"] for s in sessions if s.get("professor_id")})
    course_map = {c["id"]: c["title"] for c in (db.from_("courses").select("id, title").in_("id", course_ids).execute().data or [])} if course_ids else {}
    prof_map = {p["id"]: p["full_name"] for p in (db.from_("profiles").select("id, full_name").in_("id", prof_ids).execute().data or [])} if prof_ids else {}

    def _group_by(key: str, name_map: dict) -> list[dict]:
        groups: dict[str, dict] = {}
        for s in sessions:
            gid = s.get(key)
            if not gid:
                continue
            g = groups.setdefault(gid, {"id": gid, "name": name_map.get(gid, "—"), "session_count": 0, "ratings": []})
            g["session_count"] += 1
            g["ratings"].extend(session_ratings.get(s["id"], []))
        result = [
            {
                "id": g["id"],
                "name": g["name"],
                "session_count": g["session_count"],
                "average": (sum(g["ratings"]) / len(g["ratings"])) if g["ratings"] else None,
            }
            for g in groups.values()
        ]
        result.sort(key=lambda x: (x["average"] is None, -(x["average"] or 0)))
        return result

    total_invited = len(invited)
    total_responses = len(responses)
    return {
        "total_sessions": len(sessions),
        "completed_sessions": sum(1 for s in sessions if s["status"] == "completed"),
        "total_invited": total_invited,
        "total_responses": total_responses,
        "response_rate": (total_responses / total_invited) if total_invited else 0,
        "overall_average": (sum(all_ratings) / len(all_ratings)) if all_ratings else None,
        "by_professor": _group_by("professor_id", prof_map),
        "by_course": _group_by("course_id", course_map),
    }


@router.get("")
async def list_sessions(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
    course_id: Optional[str] = None,
):
    if not user.can_create():
        raise HTTPException(403, "Professor or admin only")
    query = db.from_("teaching_sessions").select("*")
    if not user.is_admin():
        query = query.eq("professor_id", user.id)
    if course_id:
        query = query.eq("course_id", course_id)
    rows = query.order("started_at", desc=True).execute().data or []
    return _enrich_sessions(rows, db)


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    rows = db.from_("teaching_sessions").select("*").eq("id", session_id).execute().data
    if not rows:
        raise HTTPException(404, "Séance introuvable")
    session = rows[0]
    if not user.is_admin() and session["professor_id"] != user.id:
        raise HTTPException(403, "Non autorisé")
    return _enrich_sessions([session], db)[0]


@router.post("")
async def start_session(
    body: TeachingSessionStart,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    if not user.can_create():
        raise HTTPException(403, "Professor or admin only")
    if not _authorized(body.course_id, body.class_id, user, db):
        raise HTTPException(
            403,
            "Ce cours n'est pas assigné à cette classe, ou vous n'en êtes pas le professeur",
        )

    # Resume beats duplicate: if this professor already has an active session
    # for this exact course+class, return it instead of creating a second one
    # (also enforced at the DB level by idx_teaching_sessions_one_active).
    existing = (
        db.from_("teaching_sessions")
        .select("*")
        .eq("professor_id", user.id)
        .eq("course_id", body.course_id)
        .eq("class_id", body.class_id)
        .eq("status", "active")
        .execute()
        .data
    )
    if existing:
        return existing[0]

    try:
        res = (
            db.from_("teaching_sessions")
            .insert(
                {
                    "course_id": body.course_id,
                    "class_id": body.class_id,
                    "professor_id": user.id,
                    "status": "active",
                    "start_position": body.start_position,
                    "current_position": body.start_position,
                }
            )
            .execute()
        )
    except Exception as e:
        # Most likely the unique-active-session index caught a race
        # (double-click, two tabs) — surface it as a normal conflict.
        raise HTTPException(409, str(e))
    return res.data[0]


@router.patch("/{session_id}/position")
async def update_position(
    session_id: str,
    body: TeachingSessionPositionUpdate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Live position while teaching — overwrites in place, never a new row
    per navigation (spec §7). Also what session recovery reads back."""
    rows = db.from_("teaching_sessions").select("professor_id, status").eq("id", session_id).execute().data
    if not rows:
        raise HTTPException(404, "Séance introuvable")
    if rows[0]["professor_id"] != user.id and not user.is_admin():
        raise HTTPException(403, "Non autorisé")
    if rows[0]["status"] != "active":
        raise HTTPException(400, "Cette séance n'est plus active")

    res = (
        db.from_("teaching_sessions")
        .update({"current_position": body.position})
        .eq("id", session_id)
        .execute()
    )
    return res.data[0]


@router.post("/{session_id}/end")
async def end_session(
    session_id: str,
    body: TeachingSessionEnd,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    rows = db.from_("teaching_sessions").select("*").eq("id", session_id).execute().data
    if not rows:
        raise HTTPException(404, "Séance introuvable")
    session = rows[0]
    if session["professor_id"] != user.id and not user.is_admin():
        raise HTTPException(403, "Non autorisé")
    if session["status"] != "active":
        raise HTTPException(400, "Cette séance est déjà terminée")

    ended_at = datetime.now(timezone.utc)
    started_at = _parse_dt(session["started_at"])
    duration_seconds = int((ended_at - started_at).total_seconds())
    final_position = body.end_position or session.get("current_position")

    res = (
        db.from_("teaching_sessions")
        .update(
            {
                "status": "completed",
                "ended_at": ended_at.isoformat(),
                "duration_seconds": duration_seconds,
                "current_position": final_position,
                "end_position": final_position,
            }
        )
        .eq("id", session_id)
        .execute()
    )
    completed = res.data[0]

    # Feedback questionnaire, sent to the class's real roster (spec §8,
    # §9 — class_students is the source of truth, not course_enrollments;
    # see Decision 1). Never let a feedback/notification failure undo an
    # already-recorded session — same defensive pattern as exams.py's
    # publish-notification block. Two SEPARATE try/excepts on purpose: a
    # failure creating feedback requests must not also swallow the
    # notification (they used to share one block — that's exactly what
    # silently dropped notifications while session_knowledge_questions
    # didn't exist yet, since create_feedback_requests raised before
    # notify_users ever ran).
    student_ids: list[str] = []
    try:
        members = (
            db.from_("class_students").select("student_id").eq("class_id", session["class_id"]).execute().data or []
        )
        student_ids = [m["student_id"] for m in members]
    except Exception:
        pass

    feedback_sent_to = 0
    try:
        feedback_sent_to = create_feedback_requests(db, completed, student_ids)
    except Exception:
        pass

    try:
        if student_ids:
            course = db.from_("courses").select("title").eq("id", session["course_id"]).execute().data
            course_title = course[0]["title"] if course else "ce cours"
            notify_users(
                db,
                student_ids,
                "Évaluez votre séance de cours",
                f"Vous venez de terminer une séance de {course_title}. Votre avis nous aide à améliorer la qualité des cours.",
                "info",
                f"/dashboard/session-feedback/{session_id}",
            )
    except Exception:
        pass

    return {**completed, "feedback_sent_to": feedback_sent_to}
