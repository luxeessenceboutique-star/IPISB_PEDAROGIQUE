from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated
from supabase import Client
from deps import get_current_user, get_db, CurrentUser

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
async def get_stats(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    now = datetime.now(timezone.utc).isoformat()
    unread = len(
        db.from_("notifications").select("id").eq("user_id", user.id).eq("read", False).execute().data or []
    )

    if user.is_admin():
        courses = len(db.from_("courses").select("id").execute().data or [])
        assignments = len(db.from_("assignments").select("id").execute().data or [])
        exams = len(db.from_("exams").select("id").execute().data or [])
        events = len(db.from_("calendar_events").select("id").execute().data or [])
        return {
            "courses": courses,
            "assignments": assignments,
            "exams": exams,
            "events": events,
            "unread": unread,
            "pending_grade": 0,
        }

    elif user.is_prof():
        prof_courses = db.from_("courses").select("id").eq("professor_id", user.id).execute().data or []
        course_ids = [c["id"] for c in prof_courses]
        assignments = exams = pending_grade = 0
        if course_ids:
            assignments = len(
                db.from_("assignments").select("id").in_("course_id", course_ids).execute().data or []
            )
            exams = len(
                db.from_("exams").select("id").in_("course_id", course_ids).execute().data or []
            )
            assign_ids = [
                a["id"]
                for a in (db.from_("assignments").select("id").in_("course_id", course_ids).execute().data or [])
            ]
            if assign_ids:
                pending_grade = len(
                    db.from_("submissions")
                    .select("id")
                    .in_("assignment_id", assign_ids)
                    .is_("grade", "null")
                    .execute()
                    .data or []
                )
        return {
            "courses": len(course_ids),
            "assignments": assignments,
            "exams": exams,
            "events": 0,
            "unread": unread,
            "pending_grade": pending_grade,
        }

    else:
        enrollments = (
            db.from_("course_enrollments").select("course_id").eq("student_id", user.id).execute().data or []
        )
        enrolled_ids = [e["course_id"] for e in enrollments]
        assignments = exams = 0
        if enrolled_ids:
            assignments = len(
                db.from_("assignments")
                .select("id")
                .in_("course_id", enrolled_ids)
                .gt("due_date", now)
                .execute()
                .data or []
            )
            exams = len(
                db.from_("exams")
                .select("id")
                .in_("course_id", enrolled_ids)
                .eq("is_published", True)
                .execute()
                .data or []
            )
        events = len(
            db.from_("calendar_events").select("id").gt("start_time", now).execute().data or []
        )
        return {
            "courses": len(enrolled_ids),
            "assignments": assignments,
            "exams": exams,
            "events": events,
            "unread": unread,
            "pending_grade": 0,
        }


@router.get("/admin-overview")
async def get_admin_overview(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Admin/directeur real-time overview: effectifs par classe, documents
    générés, activité récente. The frontend can subscribe to Supabase
    Realtime on these same tables to keep this live without polling."""
    if not user.is_admin():
        raise HTTPException(403, "Admin only")

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

    classes = db.from_("classes").select("id, name").execute().data or []
    memberships = db.from_("class_students").select("class_id").execute().data or []
    count_map: dict[str, int] = {}
    for m in memberships:
        count_map[m["class_id"]] = count_map.get(m["class_id"], 0) + 1
    students_by_class = [
        {"class_id": c["id"], "class_name": c["name"], "count": count_map.get(c["id"], 0)} for c in classes
    ]

    student_roles = db.from_("user_roles").select("user_id").eq("role", "student").execute().data or []
    total_students = len(student_roles)

    documents_total = len(db.from_("documents").select("id").execute().data or [])
    documents_today = len(
        db.from_("documents").select("id").gte("created_at", today_start).execute().data or []
    )

    recent_activity = (
        db.from_("audit_log")
        .select("*")
        .order("created_at", desc=True)
        .limit(10)
        .execute()
        .data or []
    )

    return {
        "total_students": total_students,
        "students_by_class": students_by_class,
        "documents_total": documents_total,
        "documents_today": documents_today,
        "recent_activity": recent_activity,
    }


@router.get("/analytics")
async def get_analytics(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """
    Professor/admin analytics: per-course breakdown of assignments and exams
    with submission counts and averages.
    """
    if not user.can_create():
        raise HTTPException(403, "Professors and admins only")

    # ── 1. Fetch courses ──────────────────────────────────────────────────────
    if user.is_admin():
        courses = db.from_("courses").select("id, title").order("title").execute().data or []
    else:
        courses = (
            db.from_("courses")
            .select("id, title")
            .eq("professor_id", user.id)
            .order("title")
            .execute()
            .data or []
        )

    if not courses:
        return []

    course_ids = [c["id"] for c in courses]

    # ── 2. Enrolled student count per course ──────────────────────────────────
    # Courses are linked to classes via class_courses; students via class_students.
    # We count unique students across all classes assigned to each course.
    class_course_rows = (
        db.from_("class_courses")
        .select("course_id, class_id")
        .in_("course_id", course_ids)
        .execute()
        .data or []
    )
    # Build course → [class_id] map
    course_to_class_ids: dict[str, list[str]] = {}
    all_class_ids: set[str] = set()
    for row in class_course_rows:
        course_to_class_ids.setdefault(row["course_id"], []).append(row["class_id"])
        all_class_ids.add(row["class_id"])

    # Build class → {student_id} map
    class_to_students: dict[str, set[str]] = {}
    if all_class_ids:
        student_rows = (
            db.from_("class_students")
            .select("class_id, student_id")
            .in_("class_id", list(all_class_ids))
            .execute()
            .data or []
        )
        for row in student_rows:
            class_to_students.setdefault(row["class_id"], set()).add(row["student_id"])

    def enrolled_count_for(course_id: str) -> int:
        unique: set[str] = set()
        for cid in course_to_class_ids.get(course_id, []):
            unique |= class_to_students.get(cid, set())
        return len(unique)

    # ── 3. Assignments ────────────────────────────────────────────────────────
    assignments = (
        db.from_("assignments")
        .select("id, title, course_id")
        .in_("course_id", course_ids)
        .execute()
        .data or []
    )
    assign_ids = [a["id"] for a in assignments]

    # All submissions for these assignments
    submissions: list[dict] = []
    if assign_ids:
        submissions = (
            db.from_("submissions")
            .select("assignment_id, grade")
            .in_("assignment_id", assign_ids)
            .execute()
            .data or []
        )

    # Group submissions by assignment_id
    sub_by_assign: dict[str, list[dict]] = {}
    for s in submissions:
        sub_by_assign.setdefault(s["assignment_id"], []).append(s)

    # ── 4. Exams ──────────────────────────────────────────────────────────────
    exams = (
        db.from_("exams")
        .select("id, title, course_id")
        .in_("course_id", course_ids)
        .execute()
        .data or []
    )
    exam_ids = [e["id"] for e in exams]

    # All exam responses for these exams
    exam_responses: list[dict] = []
    if exam_ids:
        exam_responses = (
            db.from_("exam_responses")
            .select("exam_id, score, total")
            .in_("exam_id", exam_ids)
            .execute()
            .data or []
        )

    # Group responses by exam_id
    resp_by_exam: dict[str, list[dict]] = {}
    for r in exam_responses:
        resp_by_exam.setdefault(r["exam_id"], []).append(r)

    # ── 5. Build response ─────────────────────────────────────────────────────
    # Group assignments and exams by course
    assigns_by_course: dict[str, list[dict]] = {}
    for a in assignments:
        assigns_by_course.setdefault(a["course_id"], []).append(a)

    exams_by_course: dict[str, list[dict]] = {}
    for e in exams:
        exams_by_course.setdefault(e["course_id"], []).append(e)

    result = []
    for course in courses:
        cid = course["id"]
        enrolled = enrolled_count_for(cid)

        # Assignments analytics
        assign_analytics = []
        for a in assigns_by_course.get(cid, []):
            subs = sub_by_assign.get(a["id"], [])
            submitted = len(subs)
            graded_subs = [s["grade"] for s in subs if s.get("grade") is not None]
            avg_grade = round(sum(graded_subs) / len(graded_subs), 2) if graded_subs else None
            assign_analytics.append({
                "id": a["id"],
                "title": a["title"],
                "enrolled": enrolled,
                "submitted": submitted,
                "avg_grade": avg_grade,
            })

        # Exams analytics
        exam_analytics = []
        for e in exams_by_course.get(cid, []):
            resps = resp_by_exam.get(e["id"], [])
            submitted = len(resps)
            # avg_score as a percentage (score/total * 100)
            pct_scores = [
                round(r["score"] / r["total"] * 100, 2)
                for r in resps
                if r.get("total") and r["total"] > 0
            ]
            avg_score = round(sum(pct_scores) / len(pct_scores), 2) if pct_scores else None
            exam_analytics.append({
                "id": e["id"],
                "title": e["title"],
                "enrolled": enrolled,
                "submitted": submitted,
                "avg_score": avg_score,
            })

        result.append({
            "course_id": cid,
            "course_title": course["title"],
            "enrolled_count": enrolled,
            "assignments": assign_analytics,
            "exams": exam_analytics,
        })

    return result
