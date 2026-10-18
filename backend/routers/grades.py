from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException
from supabase import Client
from deps import get_current_user, get_db, CurrentUser
from models import CourseGradeWeightsUpdate, StageGradesUpsert, ClassGradeWeightsUpdate

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


def _weighted_average(items: list[tuple[Optional[float], float]]) -> Optional[float]:
    """Coefficient-weighted average of (value, coefficient) pairs, excluding
    any item whose value is None ENTIRELY — not counted as zero. Same
    null-exclusion semantics `compute_overall_average` already applies to
    per-course grades (a course with no grade yet doesn't drag the average
    down to 0, it's simply not counted yet). Shared by MPCC1 (via
    compute_overall_average), MPEFCFT1, MPEFCFP1 and MG1."""
    weighted_sum = 0.0
    total_weight = 0.0
    for value, coefficient in items:
        if value is not None:
            weighted_sum += value * coefficient
            total_weight += coefficient
    return round(weighted_sum / total_weight, 2) if total_weight > 0 else None


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


def _class_courses(db: Client, class_id: str) -> list[dict]:
    """UF (cours) assignées à une classe, avec leur coefficient (`credits`) —
    [{id, title, credits}]. Factorisé depuis compute_overall_average pour
    être réutilisé par compute_class_efcf_averages/compute_class_mg1_summary."""
    cc_rows = db.from_("class_courses").select("course_id").eq("class_id", class_id).execute().data or []
    course_ids = list({r["course_id"] for r in cc_rows})
    if not course_ids:
        return []
    return db.from_("courses").select("id, title, credits").in_("id", course_ids).execute().data or []


def compute_overall_average(db: Client, student_id: str, class_id: Optional[str] = None) -> dict:
    """Coefficient-weighted average across a student's courses — this is
    MPCC1 (Moyenne pondérée des notes des Contrôles Continus) when scoped to
    one class_id.

    Each course's `credits` field doubles as its official coefficient
    (per `Liste des Coefficients`, e.g. a 3-coefficient module like Anatomie
    counts 3x as much as a 1-coefficient module in the overall average).
    Courses with no grade yet are excluded rather than counted as zero.
    """
    if class_id:
        courses = _class_courses(db, class_id)
    else:
        memberships = db.from_("class_students").select("class_id").eq("student_id", student_id).execute().data or []
        class_ids = [m["class_id"] for m in memberships]
        if not class_ids:
            courses = []
        else:
            cc_rows = db.from_("class_courses").select("course_id").in_("class_id", class_ids).execute().data or []
            course_ids = list({r["course_id"] for r in cc_rows})
            courses = db.from_("courses").select("id, title, credits").in_("id", course_ids).execute().data or [] if course_ids else []
    if not courses:
        return {"student_id": student_id, "average": None, "courses": []}

    results = []
    for course in courses:
        cid = course["id"]
        coefficient = course.get("credits") or 1
        grade_info = compute_course_grade(db, cid, student_id)
        results.append({
            "course_id": cid,
            "title": course.get("title"),
            "coefficient": coefficient,
            "grade": grade_info["grade"],
        })

    average = _weighted_average([(r["grade"], r["coefficient"]) for r in results])
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


# ── EFCF (Examen de fin de cursus Théorique/Pratique) + Stage + MG1 ────────
# Réplique les feuilles "T F C" / "P F C V" / "P1 G1" de l'Excel de
# référence — cf. plan "Remplacer l'Excel de gestion des notes" (Phase 1).

def _exam_of_record_map(db: Client, course_ids: list[str]) -> dict[str, str]:
    """Pour chaque UF (cours), l'Examen (continuous_assessments,
    doc_type='examen') le plus récent qui la cible — en pratique un Examen
    cible un seul cours à la fois (cf. le gabarit Word : une Unité de
    Formation par épreuve). S'il y a plusieurs Examens pour la même UF (ex.
    une reprise), le plus récent compte. Lu en Python : course_ids est un
    uuid[], aucune requête de ce code ne filtre sur un tableau Postgres."""
    if not course_ids:
        return {}
    try:
        rows = (
            db.from_("continuous_assessments").select("id, course_ids, created_at")
            .eq("doc_type", "examen").order("created_at", desc=True).execute().data or []
        )
    except Exception:
        return {}  # doc_type (L66) pas encore appliquée — aucun Examen exploitable
    wanted, out = set(course_ids), {}
    for r in rows:
        for cid in (r.get("course_ids") or []):
            if cid in wanted and cid not in out:
                out[cid] = r["id"]
    return out


def compute_class_efcf_averages(db: Client, class_id: str, student_ids: list[str]) -> dict[str, dict]:
    """MPEFCFT1 (Théorique) et MPEFCFP1 (Pratique + Stage) pour toute une
    cohorte en une passe groupée — pas une boucle par élève × par UF (qui
    ferait des centaines de requêtes pour une classe de 25 élèves × 20 UF)."""
    courses = _class_courses(db, class_id)
    if not courses:
        return {sid: {"mpefcft1": None, "mpefcfp1": None} for sid in student_ids}

    course_ids = [c["id"] for c in courses]
    exam_of_record = _exam_of_record_map(db, course_ids)
    assessment_ids = list({v for v in exam_of_record.values()})

    scales: dict[str, dict] = {}
    if assessment_ids:
        try:
            a_rows = (
                db.from_("continuous_assessments").select("id, total_points, pratique_sections")
                .in_("id", assessment_ids).execute().data or []
            )
        except Exception:
            a_rows = []
        for a in a_rows:
            pr_sections = a.get("pratique_sections") or []
            pr_scale = sum((s.get("bareme") or 0) for s in pr_sections)
            scales[a["id"]] = {"th_scale": a.get("total_points") or 20, "pr_scale": pr_scale or None}

    grades_by_assessment: dict[str, dict[str, dict]] = {}
    if assessment_ids:
        try:
            g_rows = (
                db.from_("continuous_assessment_grades")
                .select("assessment_id, student_id, theorique_score, pratique_score")
                .in_("assessment_id", assessment_ids).in_("student_id", student_ids)
                .execute().data or []
            )
        except Exception:
            g_rows = []  # L67 pas encore appliquée
        for g in g_rows:
            grades_by_assessment.setdefault(g["assessment_id"], {})[g["student_id"]] = g

    try:
        stage_rows = (
            db.from_("class_stage_grades").select("student_id, grade, coefficient")
            .eq("class_id", class_id).execute().data or []
        )
    except Exception:
        stage_rows = []  # L68 pas encore appliquée
    stage_by_student = {r["student_id"]: r for r in stage_rows}

    out: dict[str, dict] = {}
    for sid in student_ids:
        th_items: list[tuple[Optional[float], float]] = []
        pr_items: list[tuple[Optional[float], float]] = []
        for c in courses:
            coeff = c.get("credits") or 1
            a_id = exam_of_record.get(c["id"])
            row = grades_by_assessment.get(a_id, {}).get(sid) if a_id else None
            scale = scales.get(a_id, {}) if a_id else {}

            th_raw = row.get("theorique_score") if row else None
            th_val = _category_average([{"score": th_raw, "max": scale.get("th_scale") or 20}]) if th_raw is not None else None
            th_items.append((th_val, coeff))

            pr_raw = row.get("pratique_score") if row else None
            pr_scale = scale.get("pr_scale")
            pr_val = _category_average([{"score": pr_raw, "max": pr_scale}]) if (pr_raw is not None and pr_scale) else None
            pr_items.append((pr_val, coeff))

        stage = stage_by_student.get(sid)
        if stage and stage.get("grade") is not None:
            pr_items.append((stage["grade"], stage.get("coefficient") or 3))

        out[sid] = {"mpefcft1": _weighted_average(th_items), "mpefcfp1": _weighted_average(pr_items)}
    return out


def compute_class_mg1_summary(db: Client, class_id: str) -> dict[str, dict]:
    """MPCC1 + MPEFCFT1 + MPEFCFP1 + MG1 pour toute la classe — réplique les
    feuilles "P1 G1" / "Modalité de passage" de l'Excel pour CETTE cohorte.
    MG1 = pondération des 3 moyennes déjà agrégées (pas des notes brutes),
    poids class_grade_weights (défaut 3/2/3 — somme réelle, pas 100)."""
    memberships = db.from_("class_students").select("student_id").eq("class_id", class_id).execute().data or []
    student_ids = list({m["student_id"] for m in memberships})
    if not student_ids:
        return {}

    mpcc1_by_student = {sid: compute_overall_average(db, sid, class_id)["average"] for sid in student_ids}
    efcf = compute_class_efcf_averages(db, class_id, student_ids)

    try:
        configured = db.from_("class_grade_weights").select("*").eq("class_id", class_id).execute().data
    except Exception:
        configured = None  # L69 pas encore appliquée
    if configured:
        cc_w, th_w, pr_w = configured[0]["cc_weight"], configured[0]["efcf_th_weight"], configured[0]["efcf_pr_weight"]
    else:
        cc_w, th_w, pr_w = 3, 2, 3

    out = {}
    for sid in student_ids:
        mpcc1 = mpcc1_by_student.get(sid)
        mpefcft1 = efcf.get(sid, {}).get("mpefcft1")
        mpefcfp1 = efcf.get(sid, {}).get("mpefcfp1")
        out[sid] = {
            "mpcc1": mpcc1, "mpefcft1": mpefcft1, "mpefcfp1": mpefcfp1,
            "mg1": _weighted_average([(mpcc1, cc_w), (mpefcft1, th_w), (mpefcfp1, pr_w)]),
        }
    return out


@router.get("/classes/{class_id}/mg1-summary")
async def get_class_mg1_summary(
    class_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    if not user.is_admin() and not user.is_prof():
        raise HTTPException(403, "Non autorisé")
    return compute_class_mg1_summary(db, class_id)


@router.get("/classes/{class_id}/stage-grades")
async def get_stage_grades(
    class_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    if not user.is_admin() and not user.is_prof():
        raise HTTPException(403, "Non autorisé")
    try:
        rows = db.from_("class_stage_grades").select("*").eq("class_id", class_id).execute().data or []
    except Exception:
        rows = []  # L68 pas encore appliquée
    return {r["student_id"]: r for r in rows}


@router.put("/classes/{class_id}/stage-grades")
async def set_stage_grades(
    class_id: str,
    body: StageGradesUpsert,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    if not user.is_admin() and not user.is_prof():
        raise HTTPException(403, "Non autorisé")
    existing = (
        db.from_("class_stage_grades").select("id, student_id")
        .eq("class_id", class_id).in_("student_id", list(body.grades.keys()))
        .execute().data or []
    )
    by_student = {r["student_id"]: r["id"] for r in existing}
    to_insert = []
    for student_id, entry in body.grades.items():
        payload = {"grade": entry.grade, "coefficient": entry.coefficient, "graded_by": user.id}
        if student_id in by_student:
            db.from_("class_stage_grades").update(payload).eq("id", by_student[student_id]).execute()
        else:
            to_insert.append({"class_id": class_id, "student_id": student_id, **payload})
    if to_insert:
        db.from_("class_stage_grades").insert(to_insert).execute()
    return {"ok": True}


@router.get("/classes/{class_id}/grade-weights")
async def get_class_grade_weights(
    class_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    if not user.is_admin() and not user.is_prof():
        raise HTTPException(403, "Non autorisé")
    try:
        rows = db.from_("class_grade_weights").select("*").eq("class_id", class_id).execute().data
    except Exception:
        rows = None  # L69 pas encore appliquée
    if rows:
        return rows[0]
    return {"class_id": class_id, "cc_weight": 3, "efcf_th_weight": 2, "efcf_pr_weight": 3, "configured": False}


@router.put("/classes/{class_id}/grade-weights")
async def set_class_grade_weights(
    class_id: str,
    body: ClassGradeWeightsUpdate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    if not user.is_admin():
        raise HTTPException(403, "Réservé aux administrateurs")
    if body.cc_weight <= 0 or body.efcf_th_weight <= 0 or body.efcf_pr_weight <= 0:
        raise HTTPException(400, "Les poids doivent être strictement positifs")
    res = db.from_("class_grade_weights").upsert({
        "class_id": class_id,
        "cc_weight": body.cc_weight,
        "efcf_th_weight": body.efcf_th_weight,
        "efcf_pr_weight": body.efcf_pr_weight,
        "updated_by": user.id,
    }).execute()
    return res.data[0]
