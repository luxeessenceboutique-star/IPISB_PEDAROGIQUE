from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException
from supabase import Client
from deps import get_current_user, get_db, CurrentUser
from models import CourseGradeWeightsUpdate

router = APIRouter(tags=["grades"])


def _check_course_access(db: Client, user: CurrentUser, course_id: str) -> dict:
    rows = db.from_("courses").select("*").eq("id", course_id).execute().data
    if not rows:
        raise HTTPException(404, "Cours introuvable")
    course = rows[0]
    if not user.is_admin() and course.get("professor_id") != user.id:
        raise HTTPException(403, "Non autorisé")
    return course


def _category_average(items: list[dict]) -> Optional[float]:
    """Sum(score)/Sum(max) normalized to /20 — items = [{'score': x, 'max': y}]. None if empty."""
    total_max = sum(i["max"] for i in items if i.get("max"))
    if total_max <= 0:
        return None
    total_score = sum(i["score"] for i in items if i.get("max"))
    return round((total_score / total_max) * 20, 2)


def compute_course_grade(db: Client, course_id: str, student_id: str) -> dict:
    """Weighted continuous-assessment grade for one student in one course.

    Weights come from `course_grade_weights` if configured; otherwise falls
    back to an equal split across whichever categories (Examens/Devoirs/Quiz)
    actually have graded items for this student. If a configured weight
    covers a category the student has no grades in yet, the remaining
    weights are renormalized to 100% rather than capping the achievable
    grade below 20 mid-term.

    Évaluations « Note directe » (page Notes, is_quick_grade=true) : comptent
    dans devoir_avg comme n'importe quel devoir noté, SAUF celles catégorisées
    quick_grade_category='exam', qui rejoignent exam_avg aux côtés des vrais
    examens QCM (exam_responses) — un professeur peut ainsi saisir une note
    d'examen à la main sans qu'un vrai examen QCM existe.
    """
    try:
        # is_quick_grade (l47) / quick_grade_category (l48) : si l48 n'a pas
        # encore été exécutée côté Supabase, on retombe sur le comportement
        # d'avant ces migrations (tous les devoirs comptent en devoir_avg)
        # plutôt que de faire planter tout calcul de note en attendant.
        assignments = db.from_("assignments").select("id, max_grade, is_quick_grade, quick_grade_category").eq("course_id", course_id).execute().data or []
    except Exception:
        assignments = db.from_("assignments").select("id, max_grade").eq("course_id", course_id).execute().data or []
    max_grade_map = {a["id"]: a.get("max_grade") or 20 for a in assignments}
    devoir_assignment_ids = [a["id"] for a in assignments if not (a.get("is_quick_grade") and a.get("quick_grade_category") == "exam")]
    quick_exam_assignment_ids = [a["id"] for a in assignments if a.get("is_quick_grade") and a.get("quick_grade_category") == "exam"]

    def _submission_items(assignment_ids: list[str]) -> list[dict]:
        if not assignment_ids:
            return []
        subs = (
            db.from_("submissions").select("assignment_id, grade")
            .eq("student_id", student_id).in_("assignment_id", assignment_ids)
            .execute().data or []
        )
        return [
            {"score": s["grade"], "max": max_grade_map.get(s["assignment_id"], 20)}
            for s in subs if s.get("grade") is not None
        ]

    devoir_items = _submission_items(devoir_assignment_ids)
    quick_exam_items = _submission_items(quick_exam_assignment_ids)
    devoir_avg = _category_average(devoir_items)

    exams = db.from_("exams").select("id, type").eq("course_id", course_id).execute().data or []
    exam_ids = [e["id"] for e in exams if e.get("type", "examen") == "examen"]
    quiz_ids = [e["id"] for e in exams if e.get("type") == "quiz"]

    def _exam_category_avg(exam_ids_: list[str], extra_items: Optional[list[dict]] = None) -> Optional[float]:
        items = list(extra_items or [])
        if exam_ids_:
            responses = (
                db.from_("exam_responses").select("exam_id, score, total")
                .eq("student_id", student_id).in_("exam_id", exam_ids_)
                .execute().data or []
            )
            items += [{"score": r["score"], "max": r["total"]} for r in responses if r.get("total")]
        return _category_average(items) if items else None

    exam_avg = _exam_category_avg(exam_ids, quick_exam_items)
    quiz_avg = _exam_category_avg(quiz_ids)

    category_avgs = {"exam": exam_avg, "devoir": devoir_avg, "quiz": quiz_avg}
    present = {k: v for k, v in category_avgs.items() if v is not None}

    if not present:
        return {
            "course_id": course_id, "student_id": student_id, "grade": None,
            "exam_avg": exam_avg, "devoir_avg": devoir_avg, "quiz_avg": quiz_avg, "weights_used": None,
        }

    configured = db.from_("course_grade_weights").select("*").eq("course_id", course_id).execute().data
    if configured:
        raw_weights = {
            "exam": configured[0]["exam_weight"],
            "devoir": configured[0]["devoir_weight"],
            "quiz": configured[0]["quiz_weight"],
        }
        total_w = sum(raw_weights[k] for k in present)
        weights = (
            {k: raw_weights[k] / total_w * 100 for k in present}
            if total_w > 0 else {k: 100 / len(present) for k in present}
        )
    else:
        weights = {k: 100 / len(present) for k in present}

    grade = sum(present[k] * weights.get(k, 0) / 100 for k in present)
    return {
        "course_id": course_id, "student_id": student_id, "grade": round(grade, 2),
        "exam_avg": exam_avg, "devoir_avg": devoir_avg, "quiz_avg": quiz_avg, "weights_used": weights,
    }


@router.get("/courses/{course_id}/grade-weights")
async def get_grade_weights(
    course_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    _check_course_access(db, user, course_id)
    rows = db.from_("course_grade_weights").select("*").eq("course_id", course_id).execute().data
    if rows:
        return rows[0]
    return {"course_id": course_id, "exam_weight": 50, "devoir_weight": 30, "quiz_weight": 20, "configured": False}


@router.put("/courses/{course_id}/grade-weights")
async def set_grade_weights(
    course_id: str,
    body: CourseGradeWeightsUpdate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    _check_course_access(db, user, course_id)
    total = body.exam_weight + body.devoir_weight + body.quiz_weight
    if total != 100:
        raise HTTPException(400, f"Les pourcentages doivent totaliser 100 (actuellement {total})")

    res = db.from_("course_grade_weights").upsert({
        "course_id": course_id,
        "exam_weight": body.exam_weight,
        "devoir_weight": body.devoir_weight,
        "quiz_weight": body.quiz_weight,
        "updated_by": user.id,
    }).execute()
    return res.data[0]


@router.get("/courses/{course_id}/students/{student_id}/grade")
async def get_student_course_grade(
    course_id: str,
    student_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    _check_course_access(db, user, course_id)
    return compute_course_grade(db, course_id, student_id)


def compute_overall_average(db: Client, student_id: str, class_id: Optional[str] = None) -> dict:
    """Coefficient-weighted average across a student's courses.

    Each course's `credits` field doubles as its official coefficient
    (per `Liste des Coefficients`, e.g. a 3-coefficient module like Anatomie
    counts 3x as much as a 1-coefficient module in the overall average).
    Courses with no grade yet are excluded rather than counted as zero.
    """
    if class_id:
        class_ids = [class_id]
    else:
        memberships = db.from_("class_students").select("class_id").eq("student_id", student_id).execute().data or []
        class_ids = [m["class_id"] for m in memberships]
    if not class_ids:
        return {"student_id": student_id, "average": None, "courses": []}

    cc_rows = db.from_("class_courses").select("course_id").in_("class_id", class_ids).execute().data or []
    course_ids = list({r["course_id"] for r in cc_rows})
    if not course_ids:
        return {"student_id": student_id, "average": None, "courses": []}

    courses = db.from_("courses").select("id, title, credits").in_("id", course_ids).execute().data or []
    course_map = {c["id"]: c for c in courses}

    results = []
    weighted_sum = 0.0
    total_weight = 0.0
    for cid in course_ids:
        course = course_map.get(cid, {})
        coefficient = course.get("credits") or 1
        grade_info = compute_course_grade(db, cid, student_id)
        results.append({
            "course_id": cid,
            "title": course.get("title"),
            "coefficient": coefficient,
            "grade": grade_info["grade"],
        })
        if grade_info["grade"] is not None:
            weighted_sum += grade_info["grade"] * coefficient
            total_weight += coefficient

    average = round(weighted_sum / total_weight, 2) if total_weight > 0 else None
    return {"student_id": student_id, "average": average, "courses": results}


@router.get("/students/{student_id}/overall-grade")
async def get_student_overall_grade(
    student_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
    class_id: Optional[str] = None,
):
    if not user.is_admin() and not user.is_prof():
        raise HTTPException(403, "Non autorisé")
    return compute_overall_average(db, student_id, class_id)
