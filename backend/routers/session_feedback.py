from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from deps import get_current_user, get_db, CurrentUser
from models import SessionFeedbackSubmit
from utils.dt import parse_iso_dt

# Same URL namespace as teaching_sessions (spec §24: GET/POST .../feedback,
# GET .../feedback/results) — kept in its own router/file since this is a
# distinct concern (session feedback, not academic assessment — spec §10),
# not a second exam system.
#
# Each session's 5-question set is now two kinds of question, looked up
# from two different tables by id:
#   - session_feedback_questions  (global, permanent — Q1/Q2, rating 1-5)
#   - session_knowledge_questions (per-session, AI-generated from content
#     actually covered — Q3-5, QCM with a correct_index)
# question_order (on session_feedback_requests) is a flat list of ids that
# may belong to either table; every lookup below resolves against both.
router = APIRouter(prefix="/teaching-sessions", tags=["session-feedback"])

# Fixed, not configurable per session — this is 5 short questions (2
# ratings + 3 QCM), not a graded exam, so one constant is enough (~1min/
# question). Same server-authoritative start/deadline pattern as
# exams.py's /start + /submit: started_at is recorded once, the deadline
# is derived from it, and a grace window absorbs submit-request latency
# for a legitimate "timer just hit zero" auto-submit.
SESSION_FEEDBACK_DURATION_MINUTES = 5
SUBMIT_GRACE_SECONDS = 60


def _parse_dt(value: str) -> datetime:
    return parse_iso_dt(value)


def _resolve_questions(db: Client, question_ids: list[str]) -> dict[str, dict]:
    """id -> {type, text/question, ...} for every id in question_ids,
    checked against both question tables. Never exposes correct_index —
    callers that need it (results, submit-time validation) query
    session_knowledge_questions directly instead."""
    if not question_ids:
        return {}
    feedback = (
        db.from_("session_feedback_questions")
        .select("id, text_fr, text_en, scale_min, scale_max")
        .in_("id", question_ids)
        .execute()
        .data or []
    )
    knowledge = (
        db.from_("session_knowledge_questions")
        .select("id, question, options")
        .in_("id", question_ids)
        .execute()
        .data or []
    )
    q_map: dict[str, dict] = {}
    for q in feedback:
        q_map[q["id"]] = {"id": q["id"], "type": "rating", "text_fr": q["text_fr"], "text_en": q["text_en"], "scale_min": q["scale_min"], "scale_max": q["scale_max"]}
    for q in knowledge:
        q_map[q["id"]] = {"id": q["id"], "type": "knowledge", "question": q["question"], "options": q["options"]}
    return q_map


@router.get("/{session_id}/feedback")
async def get_my_feedback(
    session_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """A request row existing for (session, this student) IS the proof of
    eligibility — it's only ever created from that class's real class_students
    at session-end time, so no separate membership check is needed here."""
    if user.can_create():
        raise HTTPException(403, "Réservé aux étudiants")

    req = (
        db.from_("session_feedback_requests")
        .select("question_order")
        .eq("teaching_session_id", session_id)
        .eq("student_id", user.id)
        .execute()
        .data
    )
    if not req:
        raise HTTPException(404, "Aucune évaluation ne vous a été assignée pour cette séance")
    question_order = req[0]["question_order"]

    already_submitted = bool(
        db.from_("session_feedback_responses")
        .select("id")
        .eq("teaching_session_id", session_id)
        .eq("student_id", user.id)
        .execute()
        .data
    )

    q_map = _resolve_questions(db, question_order)
    # Re-apply this student's stored randomized order — .in_() does not
    # preserve it (spec §26: same order every time they open it).
    ordered = [q_map[qid] for qid in question_order if qid in q_map]

    course_title = None
    session = db.from_("teaching_sessions").select("course_id").eq("id", session_id).execute().data
    if session:
        course = db.from_("courses").select("title").eq("id", session[0]["course_id"]).execute().data
        course_title = course[0]["title"] if course else None

    started_at = req[0].get("started_at")
    deadline_at = (
        (_parse_dt(started_at) + timedelta(minutes=SESSION_FEEDBACK_DURATION_MINUTES)).isoformat()
        if started_at else None
    )
    return {
        "questions": ordered, "already_submitted": already_submitted, "course_title": course_title,
        "started_at": started_at, "deadline_at": deadline_at,
        "duration_minutes": SESSION_FEEDBACK_DURATION_MINUTES,
    }


@router.post("/{session_id}/feedback/start")
async def start_feedback(
    session_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Confirmed on the instructions screen, not on page load — same
    server-authoritative, idempotent pattern as exams.py's /start: the
    countdown only begins here, and re-calling after it's already set
    returns the SAME started_at rather than resetting the clock."""
    if user.can_create():
        raise HTTPException(403, "Réservé aux étudiants")

    req = (
        db.from_("session_feedback_requests")
        .select("id, started_at")
        .eq("teaching_session_id", session_id)
        .eq("student_id", user.id)
        .execute()
        .data
    )
    if not req:
        raise HTTPException(404, "Aucune évaluation ne vous a été assignée pour cette séance")

    started_at = req[0].get("started_at")
    if not started_at:
        started_at = datetime.now(timezone.utc).isoformat()
        db.from_("session_feedback_requests").update({"started_at": started_at}).eq("id", req[0]["id"]).execute()

    deadline_at = (_parse_dt(started_at) + timedelta(minutes=SESSION_FEEDBACK_DURATION_MINUTES)).isoformat()
    return {"started_at": started_at, "deadline_at": deadline_at}


@router.post("/{session_id}/feedback")
async def submit_feedback(
    session_id: str,
    body: SessionFeedbackSubmit,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    if user.can_create():
        raise HTTPException(403, "Réservé aux étudiants")

    req = (
        db.from_("session_feedback_requests")
        .select("question_order, started_at")
        .eq("teaching_session_id", session_id)
        .eq("student_id", user.id)
        .execute()
        .data
    )
    if not req:
        raise HTTPException(404, "Aucune évaluation ne vous a été assignée pour cette séance")
    question_ids = set(req[0]["question_order"])

    existing = (
        db.from_("session_feedback_responses")
        .select("id")
        .eq("teaching_session_id", session_id)
        .eq("student_id", user.id)
        .execute()
        .data
    )
    if existing:
        raise HTTPException(400, "Vous avez déjà évalué cette séance")

    # Partial is accepted, not required to equal question_ids: the
    # frontend auto-submits whatever's answered so far the instant its
    # countdown hits zero (forward-only nav means an unreached question
    # can never be answered) — same tolerance as exams.py's /submit.
    # Unknown ids are rejected; a merely-incomplete set is not.
    if not set(body.answers.keys()) <= question_ids:
        raise HTTPException(400, "Réponse invalide (question inconnue)")

    started_at = req[0].get("started_at")
    if started_at:
        deadline = _parse_dt(started_at) + timedelta(minutes=SESSION_FEEDBACK_DURATION_MINUTES, seconds=SUBMIT_GRACE_SECONDS)
        if datetime.now(timezone.utc) > deadline:
            raise HTTPException(403, "Le temps imparti pour cette évaluation est écoulé.")

    # Rating questions: 1-5. Knowledge questions: a valid option index —
    # fetch their real option counts rather than assuming exactly 4.
    knowledge = (
        db.from_("session_knowledge_questions").select("id, options").in_("id", list(question_ids)).execute().data or []
    )
    knowledge_option_count = {k["id"]: len(k["options"]) for k in knowledge}

    for qid, v in body.answers.items():
        if not isinstance(v, int):
            raise HTTPException(400, "Réponse invalide")
        if qid in knowledge_option_count:
            if not (0 <= v < knowledge_option_count[qid]):
                raise HTTPException(400, "Réponse invalide (choix hors limites)")
        elif not (1 <= v <= 5):
            raise HTTPException(400, "Réponse invalide (l'échelle va de 1 à 5)")

    try:
        db.from_("session_feedback_responses").insert(
            {"teaching_session_id": session_id, "student_id": user.id, "answers": body.answers}
        ).execute()
    except Exception:
        # Most likely UNIQUE(student_id, teaching_session_id) caught a race
        # (double submit / two tabs) — a real DB constraint, not app-level
        # check-then-insert (spec: don't copy the exam_responses pattern).
        raise HTTPException(409, "Vous avez déjà évalué cette séance")

    return {"ok": True}


@router.get("/{session_id}/feedback/results")
async def get_feedback_results(
    session_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Aggregated only — no per-student breakdown here by design (spec §16:
    'do NOT expose individual students' answers to the professor').

    Splits into two sections (feedback ratings vs. learning-check score).
    The actual question set for THIS session comes from its own requests
    (not from "currently active" questions), so older sessions created
    before the learning-check existed still show their original 5 rating
    questions correctly instead of silently losing 3 of them."""
    session = db.from_("teaching_sessions").select("professor_id").eq("id", session_id).execute().data
    if not session:
        raise HTTPException(404, "Séance introuvable")
    if not user.is_admin() and session[0]["professor_id"] != user.id:
        raise HTTPException(403, "Non autorisé")

    invited = (
        db.from_("session_feedback_requests").select("student_id, question_order").eq("teaching_session_id", session_id).execute().data or []
    )
    responses = (
        db.from_("session_feedback_responses").select("answers").eq("teaching_session_id", session_id).execute().data or []
    )
    # Every student's question_order contains the same ids (just reordered),
    # so the first row's set is the session's actual question set.
    question_ids = list(invited[0]["question_order"]) if invited else []

    feedback_rows = (
        db.from_("session_feedback_questions").select("id, order_num, text_fr").in_("id", question_ids).order("order_num").execute().data or []
    ) if question_ids else []
    knowledge_rows = (
        db.from_("session_knowledge_questions").select("id, order_num, question, correct_index, explanation").eq("teaching_session_id", session_id).order("order_num").execute().data or []
    )

    per_question = []
    overall_sum, overall_n = 0, 0
    for q in feedback_rows:
        vals = [r["answers"][q["id"]] for r in responses if q["id"] in r["answers"]]
        per_question.append({
            "question_id": q["id"],
            "text_fr": q["text_fr"],
            "average": (sum(vals) / len(vals)) if vals else None,
            "count": len(vals),
        })
        overall_sum += sum(vals)
        overall_n += len(vals)

    learning_check = []
    correct_total, graded_total = 0, 0
    for q in knowledge_rows:
        answered = [r["answers"][q["id"]] for r in responses if q["id"] in r["answers"]]
        correct = sum(1 for v in answered if v == q["correct_index"])
        learning_check.append({
            "question_id": q["id"],
            "question": q["question"],
            "explanation": q["explanation"],
            "correct_count": correct,
            "answered_count": len(answered),
            "correct_rate": (correct / len(answered)) if answered else None,
        })
        correct_total += correct
        graded_total += len(answered)

    invited_count = len(invited)
    response_count = len(responses)
    return {
        "invited": invited_count,
        "responses": response_count,
        "response_rate": (response_count / invited_count) if invited_count else 0,
        "per_question": per_question,
        "overall_average": (overall_sum / overall_n) if overall_n else None,
        "learning_check": learning_check,
        "learning_check_score": (correct_total / graded_total) if graded_total else None,
    }
