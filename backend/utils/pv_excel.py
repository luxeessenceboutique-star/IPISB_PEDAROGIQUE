"""Export Excel du PV de passage (« P1 G1 » / « Modalité de passage de 1ère
TS » de l'Excel source) — UNE LIGNE PAR ÉLÈVE plutôt qu'une ligne par UF.

La feuille "P1 G1" source a une colonne Coef + 3 sous-colonnes par élève
(CC/EFCF-TH/EFCF-PR) : pour une classe de 25 élèves et ~20 UF, ça fait ~78
colonnes — un mur illisible. Ce module inverse l'orientation pour l'usage
réel : une ligne par élève, un groupe de 3 colonnes (CC / Théo / Prat) par UF
(dans l'ordre des cours de la classe), puis MPCC1 / MPEFCFT1 / MPEFCFP1 /
MG1 / Décision / Mention en colonnes finales.

Ce fichier est un IMPORTEUR pur de routers/grades.py : aucune fonction de
grades.py n'est modifiée ni dupliquée dans sa forme publique. Les moyennes
(MPCC1/MPEFCFT1/MPEFCFP1/MG1) et la décision du jury viennent directement de
compute_class_mg1_summary / compute_class_decisions — jamais recalculées ici.

Hypothèse prise sur compute_class_efcf_averages (grades.py) : cette fonction
n'expose que la moyenne Théorique/Pratique finale, déjà pondérée sur
l'ensemble des UF de la classe — pas le détail par UF, qui est pourtant ce
que la colonne "<UF> — Théo"/"<UF> — Prat" de ce PV a besoin d'afficher.
Plutôt que de changer sa signature (interdit ici — ce fichier ne doit pas
toucher grades.py, un autre agent peut l'éditer en parallèle),
`_per_uf_efcf_scores` ci-dessous rejoue la MÊME résolution exam-of-record
(_exam_of_record_map + barème `continuous_assessments` + notes
`continuous_assessment_grades`) en s'arrêtant un cran plus tôt, par UF
plutôt qu'en moyenne pondérée finale. C'est une duplication de boucle
délibérée (pas de la logique de résolution elle-même, réimportée telle
quelle) : si cette résolution change un jour dans grades.py, il faudra
répercuter le changement ici à la main.
"""
import re
import unicodedata
from typing import Optional

from supabase import Client

from routers.grades import (
    _category_average,
    _class_courses,
    _exam_of_record_map,
    compute_class_decisions,
    compute_class_mg1_summary,
    compute_course_grade,
)
from utils import institution
from utils.excel import make_xlsx

# Caractères interdits dans un nom de feuille Excel (openpyxl lève une
# ValueError sinon) — un nom de classe réel en contient ("[DEMO] …", "AS-1/2"…).
_INVALID_SHEET_CHARS = str.maketrans({c: "" for c in "[]*?:/\\"})


def _safe_sheet_name(name: str) -> str:
    cleaned = (name or "").translate(_INVALID_SHEET_CHARS).strip()
    return (cleaned or "PV")[:31]


def _ascii_filename(name: str) -> str:
    """make_xlsx() met `filename` dans l'en-tête HTTP Content-Disposition,
    que Starlette encode en Latin-1 — un nom de classe réel avec un tiret
    cadratin ("—") ou un accent fait planter la réponse (confirmé en testant
    ce module contre une vraie classe du projet). Pas de nom de fichier
    "joli" nécessaire ici (l'appelant choisira le sien), juste un nom sûr."""
    normalized = unicodedata.normalize("NFKD", name or "")
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_only = re.sub(r"[^A-Za-z0-9_.-]+", "_", ascii_only).strip("_")
    return ascii_only or "classe"


# Libellés affichés pour chaque statut — y compris le sentinel "a_examiner"
# (jamais stocké en base, seulement renvoyé par compute_class_decisions tant
# qu'aucune décision n'a été enregistrée pour un MG1 < 10).
_DECISION_LABELS = {
    "admis": "Admis(e)",
    "admis_avec_rachat": "Admis(e) avec rachat",
    "non_admis_redouble": "Non admis(e) — autorisé(e) à redoubler",
    "reoriente": "Réorienté(e) vers une autre filière",
    "exclu": "Exclu(e)",
    "a_examiner": "À examiner",
}


def _fmt20(value: Optional[float]) -> str:
    """Note /20 à 2 décimales, '' si non calculable. utils/excel.py::make_xlsx
    n'a pas de type numérique "brut" (seulement text/money/int/date — "money"
    collerait un suffixe " MAD" absurde sur une note), donc on pré-formate la
    valeur en texte et la colonne reste de type texte (aligné à droite comme
    une colonne numérique classique), plutôt que d'ajouter un type à
    make_xlsx — ce fichier ne doit toucher aucun autre fichier."""
    return "" if value is None else f"{value:.2f}"


def _per_uf_efcf_scores(
    db: Client, courses: list[dict], student_ids: list[str]
) -> dict[str, dict[str, dict]]:
    """{student_id: {course_id: {'th': val_ou_None, 'pr': val_ou_None}}} —
    même résolution exam-of-record que compute_class_efcf_averages (grades.py),
    mais gardée par UF au lieu d'être agrégée en une seule moyenne pondérée.
    Voir la note en tête de fichier."""
    out: dict[str, dict[str, dict]] = {sid: {} for sid in student_ids}
    if not courses:
        return out

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

    for c in courses:
        cid = c["id"]
        a_id = exam_of_record.get(cid)
        scale = scales.get(a_id, {}) if a_id else {}
        rows_for_course = grades_by_assessment.get(a_id, {}) if a_id else {}
        for sid in student_ids:
            row = rows_for_course.get(sid)
            th_raw = row.get("theorique_score") if row else None
            th_val = (
                _category_average([{"score": th_raw, "max": scale.get("th_scale") or 20}])
                if th_raw is not None else None
            )
            pr_raw = row.get("pratique_score") if row else None
            pr_scale = scale.get("pr_scale")
            pr_val = (
                _category_average([{"score": pr_raw, "max": pr_scale}])
                if (pr_raw is not None and pr_scale) else None
            )
            out[sid][cid] = {"th": th_val, "pr": pr_val}
    return out


def render_pv_excel(db: Client, class_id: str) -> bytes:
    """PV de passage d'une classe, au format .xlsx — une ligne par élève.

    Lève ValueError si la classe n'existe pas (à l'appelant de la traduire
    en HTTPException 404 — ce fichier n'a pas de dépendance FastAPI)."""
    cls_rows = (
        db.from_("classes").select("id, name, specialty_id, year_number")
        .eq("id", class_id).execute().data
    )
    if not cls_rows:
        raise ValueError(f"Classe introuvable : {class_id}")
    cls = cls_rows[0]

    specialty_name = None
    if cls.get("specialty_id"):
        sp_rows = db.from_("specialties").select("name").eq("id", cls["specialty_id"]).execute().data
        specialty_name = sp_rows[0]["name"] if sp_rows else None

    memberships = db.from_("class_students").select("student_id").eq("class_id", class_id).execute().data or []
    student_ids = list({m["student_id"] for m in memberships})
    profiles = (
        db.from_("profiles").select("id, full_name, email").in_("id", student_ids).execute().data or []
        if student_ids else []
    )
    name_by_student = {p["id"]: p.get("full_name") or p.get("email") or "—" for p in profiles}
    # Tri alphabétique sur le nom affiché — ordre stable pour un document imprimé (même convention que pv_docx.py).
    student_ids.sort(key=lambda sid: name_by_student.get(sid, "—").lower())

    courses = sorted(_class_courses(db, class_id), key=lambda c: c.get("title") or "")

    efcf_by_student = _per_uf_efcf_scores(db, courses, student_ids)
    mg1_summary = compute_class_mg1_summary(db, class_id)
    decisions = compute_class_decisions(db, class_id)

    columns: list[dict] = [{"key": "nom", "label": "Nom", "width": 28, "align": "left"}]
    for c in courses:
        cid, title = c["id"], c.get("title") or "UF"
        columns.append({"key": f"cc_{cid}", "label": f"{title} — CC", "width": 12, "align": "center"})
        columns.append({"key": f"th_{cid}", "label": f"{title} — Théo", "width": 12, "align": "center"})
        columns.append({"key": f"pr_{cid}", "label": f"{title} — Prat", "width": 12, "align": "center"})
    columns += [
        {"key": "mpcc1", "label": "MPCC1", "width": 10, "align": "center"},
        {"key": "mpefcft1", "label": "MPEFCFT1", "width": 10, "align": "center"},
        {"key": "mpefcfp1", "label": "MPEFCFP1", "width": 10, "align": "center"},
        {"key": "mg1", "label": "MG1", "width": 10, "align": "center"},
        {"key": "decision", "label": "Décision", "width": 32, "align": "left"},
        {"key": "mention", "label": "Mention", "width": 16, "align": "left"},
    ]

    rows: list[dict] = []
    for sid in student_ids:
        row: dict = {"nom": name_by_student.get(sid, "—")}
        for c in courses:
            cid = c["id"]
            cc_grade = compute_course_grade(db, cid, sid)["grade"]
            efcf = efcf_by_student.get(sid, {}).get(cid, {})
            row[f"cc_{cid}"] = _fmt20(cc_grade)
            row[f"th_{cid}"] = _fmt20(efcf.get("th"))
            row[f"pr_{cid}"] = _fmt20(efcf.get("pr"))

        summary = mg1_summary.get(sid, {})
        row["mpcc1"] = _fmt20(summary.get("mpcc1"))
        row["mpefcft1"] = _fmt20(summary.get("mpefcft1"))
        row["mpefcfp1"] = _fmt20(summary.get("mpefcfp1"))
        row["mg1"] = _fmt20(summary.get("mg1"))

        decision = decisions.get(sid, {})
        status = decision.get("status")
        row["decision"] = _DECISION_LABELS.get(status, status or "")
        row["mention"] = decision.get("mention") or ""

        rows.append(row)

    n = len(student_ids)
    subtitle_bits = [f"{n} élève{'s' if n != 1 else ''}"]
    if specialty_name:
        subtitle_bits.append(specialty_name)
    if cls.get("year_number"):
        subtitle_bits.append(f"Année {cls['year_number']}")

    class_name = cls.get("name") or ""
    response = make_xlsx(
        filename=f"PV_{_ascii_filename(class_name)}.xlsx",
        title=f"{institution.NAME} — PV — {class_name}".rstrip(" —"),
        subtitle=" · ".join(subtitle_bits),
        theme="blue",
        sheet_name=_safe_sheet_name(f"PV {class_name}"),
        columns=columns,
        rows=rows,
    )
    return response.body
