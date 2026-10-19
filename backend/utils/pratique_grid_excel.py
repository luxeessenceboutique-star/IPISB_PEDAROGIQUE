"""Export Excel de la grille des Examens pratiques de fin de cursus de
formation (EFCF Pratique) d'une classe — sœur de utils/cc_grid_excel.py :
même mise en page (bandeau institutionnel, en-tête à 3 lignes, pied de
tableau "Moyenne de la classe", bloc signature du jury), mais une source de
données différente (notes d'EFCF Pratique par UF + note de Stage, pas le
Contrôle Continu) et une colonne de plus (STAGE, avant la colonne de moyenne
finale).

Convention délibérée de ce fichier (établie par pv_docx.py/pv_excel.py puis
reprise par cc_grid_excel.py cette session, cf. son propre docstring) : les
petits helpers de lecture DB et le bandeau institutionnel sont DUPLIQUÉS
depuis cc_grid_excel.py plutôt qu'importés — ce fichier ne touche jamais
cc_grid_excel.py (déjà vérifié et utilisé en prod, risque de régression réel
si on le modifie pour ce 2e export) et cc_grid_excel.py ne doit pas non plus
dépendre de celui-ci. Toute correction faite ici (ex. un bug de mise en page
repéré sur le rendu réel) qui s'appliquerait aussi à cc_grid_excel.py doit
être répercutée là-bas À LA MAIN, pas par un import partagé.

Même garde-fou d'import circulaire que cc_grid_excel.py : ce fichier importe
`_class_courses` / `_category_average` / `_exam_of_record_map` /
`compute_class_efcf_averages` depuis routers.grades, qui elle-même doit
importer `render_pratique_grid_excel` depuis CE fichier seulement DANS LE
CORPS de son endpoint (import différé), jamais en tête de module.
"""
import io
from pathlib import Path
from typing import Optional

from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from supabase import Client

from utils import institution
from utils.documents import current_academic_year, fr_year_label
from utils.excel import _THEMES

# Même logo que tous les autres exports de l'app — dupliqué depuis
# cc_grid_excel.py (cf. note en tête de fichier).
LOGO_PATH = Path(__file__).resolve().parent.parent / "pptx_export" / "ipisb_logo.png"

_INVALID_SHEET_CHARS = str.maketrans({c: "" for c in "[]*?:/\\"})

_GREY_FILL = PatternFill("solid", fgColor=_THEMES["grey"]["header"])  # D5DBDB
# Même seuil "<10 = échec" que cc_grid_excel.py, appliqué ici à MPEFCFP1 au
# lieu de MPCC — cf. judgment call dans le rapport de vérification.
_RED_FILL = PatternFill("solid", fgColor="C0392B")
_WHITE = "FFFFFF"
_THIN = Side(style="thin", color="BFC9CA")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)

_JURY_LABELS = [
    "PRESIDENT DE JURY D'EXAMEN",
    "Membre professionnel",
    "Membre formateur 1",
    "Membre formateur 2",
]


def _safe_sheet_name(name: str) -> str:
    cleaned = (name or "").translate(_INVALID_SHEET_CHARS).strip()
    return (cleaned or "EFCFP")[:31]


def _class_info(db: Client, class_id: str) -> dict:
    """Nom + filière + niveau — dupliqué depuis cc_grid_excel.py::_class_info
    (lui-même dupliqué de pv_docx.py), même requête, même comportement."""
    rows = (
        db.from_("classes").select("name, year_number, specialties(name)")
        .eq("id", class_id).execute().data or []
    )
    if not rows:
        raise ValueError(f"Classe introuvable : {class_id}")
    klass = rows[0]
    specialty = klass.get("specialties") or {}
    return {
        "name": klass.get("name") or class_id,
        "filiere": specialty.get("name") or "",
        "niveau": fr_year_label(klass.get("year_number")),
    }


def _class_students(db: Client, class_id: str) -> list[dict]:
    """Dupliqué depuis cc_grid_excel.py::_class_students (lui-même dupliqué
    de pv_docx.py) — [{id, full_name, email}], triés par nom."""
    memberships = db.from_("class_students").select("student_id").eq("class_id", class_id).execute().data or []
    student_ids = list({m["student_id"] for m in memberships})
    if not student_ids:
        return []
    profiles = db.from_("profiles").select("id, full_name, email").in_("id", student_ids).execute().data or []
    profiles.sort(key=lambda p: (p.get("full_name") or p.get("email") or "").lower())
    return profiles


def _class_jury_members(db: Client, class_id: str) -> list[dict]:
    """Dupliqué depuis cc_grid_excel.py::_class_jury_members — toujours 4
    entrées {name, role}, dégradées en vide si class_jury (L70) n'existe pas
    encore ou n'est pas configurée pour cette classe."""
    try:
        rows = db.from_("class_jury").select("members").eq("class_id", class_id).execute().data
    except Exception:
        rows = None  # L70 pas encore appliquée
    members = list((rows[0].get("members") if rows else None) or [])[:4]
    while len(members) < 4:
        members.append({"name": "", "role": ""})
    return members


def _class_stage_grades(db: Client, class_id: str) -> dict[str, dict]:
    """Note(s) de Stage de la classe (class_stage_grades, L68) —
    {student_id: {grade, coefficient}}. Try/except comme partout ailleurs
    dans ces fichiers d'export frères : dégrade en dict vide si la table
    n'existe pas encore sur ce projet Supabase, plutôt que de faire planter
    l'export entier pour une seule colonne optionnelle."""
    try:
        rows = (
            db.from_("class_stage_grades").select("student_id, grade, coefficient")
            .eq("class_id", class_id).execute().data or []
        )
    except Exception:
        rows = []  # L68 pas encore appliquée
    return {r["student_id"]: r for r in rows}


def _per_uf_efcf_scores(
    db: Client, courses: list[dict], student_ids: list[str],
    *, _exam_of_record_map, _category_average,
) -> dict[str, dict[str, dict]]:
    """{student_id: {course_id: {'th': val_ou_None, 'pr': val_ou_None}}} —
    DUPLIQUÉ depuis pv_excel.py::_per_uf_efcf_scores (même logique de
    résolution que grades.py::compute_class_efcf_averages, mais gardée par
    UF au lieu d'être agrégée en une seule moyenne pondérée). Ce fichier n'a
    besoin que de 'pr' (EFCF Pratique), mais on duplique la fonction entière
    telle quelle plutôt que de n'en garder qu'une moitié — moins de risque
    de divergence silencieuse si la résolution exam-of-record change un jour
    (cf. la note déjà écrite dans pv_excel.py à ce sujet).

    `_exam_of_record_map`/`_category_average` sont passées en paramètres
    (pas importées ici en tête de fonction) : routers.grades ne peut être
    importé qu'à l'intérieur de render_pratique_grid_excel (import différé,
    cf. note en tête de fichier) — cette fonction, appelée PAR
    render_pratique_grid_excel, reçoit donc ces deux références déjà
    résolues plutôt que de refaire son propre import différé."""
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


def _style_range(ws, cell_range: str, *, fill=None, font=None, alignment=None, border=None) -> None:
    """Dupliqué depuis cc_grid_excel.py::_style_range — applique
    fill/font/alignment/border à chaque cellule d'une plage fusionnée (les
    cellules non-ancres d'une plage fusionnée n'héritent pas automatiquement
    du style de la cellule en haut à gauche)."""
    for row in ws[cell_range]:
        for cell in row:
            if fill is not None:
                cell.fill = fill
            if font is not None:
                cell.font = font
            if alignment is not None:
                cell.alignment = alignment
            if border is not None:
                cell.border = border


def _write_letterhead(ws, ncol: int, filiere: str, niveau: str) -> int:
    """Bandeau institutionnel — dupliqué depuis cc_grid_excel.py::
    _write_letterhead (même logo-au-dessus-du-texte, même plancher de
    largeur pour éviter le débordement sur une classe à peu d'UF, cf. son
    propre docstring pour le détail du bug déjà rencontré et corrigé
    là-bas), AVEC UN AJOUT propre à cette feuille : une mention "Année
    scolaire : AAAA/AAAA" sur la même ligne que "Filière", alignée à droite
    — confirmée présente dans la feuille source réelle de cet export (pas
    dans celle du CC grid). Aucune colonne par-classe pour l'année scolaire
    dans ce schéma (vérifié : la table `classes` n'en a pas) — on utilise
    `current_academic_year()` (année scolaire EN COURS, reformatée avec "/"
    pour matcher le séparateur de la feuille source), PAS l'année réelle de
    la cohorte de cette classe, qui n'est stockée nulle part. Approximation
    assumée, à corriger si un jour une vraie colonne apparaît.

    Retourne le numéro de ligne où la grille (en-tête à 3 lignes) doit
    commencer."""
    row = 1
    # Plancher de largeur un peu plus généreux que cc_grid_excel.py (6) : ce
    # fichier partage la ligne Filière avec "Année scolaire" en plus, donc a
    # besoin d'un peu plus de place pour que les deux zones restent lisibles
    # sur une classe à très peu d'UF.
    text_ncol = max(ncol, 8)

    if LOGO_PATH.exists():
        try:
            img = XLImage(str(LOGO_PATH))
            target_h = 90
            orig_w, orig_h = img.width, img.height
            img.height = target_h
            img.width = int(target_h * orig_w / orig_h) if orig_h else target_h
            ws.add_image(img, f"A{row}")
            ws.row_dimensions[row].height = 70
            row += 1
        except Exception:
            pass  # logo illisible/corrompu : on dégrade sans faire planter l'export

    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=text_ncol)
    name_cell = ws.cell(
        row=row, column=1,
        value=f"{institution.NAME.upper()} -{institution.LEGAL_STATUS}-",
    )
    name_cell.font = Font(bold=True, size=11)
    name_cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[row].height = 48
    row += 1

    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=text_ncol)
    auth_cell = ws.cell(row=row, column=1, value=institution.AUTHORIZATION)
    auth_cell.font = Font(size=10)
    auth_cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[row].height = 20
    row += 1

    # "Filière : X (niveau)" à gauche + "Année scolaire : AAAA/AAAA" à
    # droite, sur la MÊME ligne — zone de droite fixée à 3 colonnes
    # (largeur suffisante pour le texte le plus court des deux, cf. essais).
    # Toujours affichée (contrairement à la ligne Filière seule de
    # cc_grid_excel.py, qu'on saute entièrement si filiere est vide) : Année
    # scolaire a toujours une valeur, donc la ligne garde un sens même sans
    # filière connue.
    annee_label = f"Année scolaire : {current_academic_year().replace('-', '/')}"
    split_col = max(2, text_ncol - 3)

    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=split_col)
    fil_label = (f"Filière : {filiere}" + (f" ({niveau})" if niveau else "")) if filiere else ""
    fil_cell = ws.cell(row=row, column=1, value=fil_label)
    fil_cell.font = Font(bold=True, size=10)
    fil_cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)

    ws.merge_cells(start_row=row, start_column=split_col + 1, end_row=row, end_column=text_ncol)
    annee_cell = ws.cell(row=row, column=split_col + 1, value=annee_label)
    annee_cell.font = Font(bold=True, size=10)
    annee_cell.alignment = Alignment(horizontal="right", vertical="center", wrap_text=True)

    ws.row_dimensions[row].height = 22
    row += 1

    row += 1  # ligne vide de séparation avant la grille
    return row


def render_pratique_grid_excel(db: Client, class_id: str) -> bytes:
    """Grille des Examens pratiques de fin de cursus de formation (EFCF
    Pratique) d'une classe — une ligne par élève, une colonne par UF
    (titre+coefficient en en-tête) avec la note EFCF Pratique de l'élève
    dans cette UF, puis une colonne STAGE (titre+coefficient), puis MPEFCFP1
    (moyenne pondérée EFCF Pratique + Stage, déjà calculée par
    grades.py::compute_class_efcf_averages — PAS recalculée ici, cf. note
    plus bas) en dernière colonne. Lève ValueError si la classe n'existe
    pas (à l'appelant de la traduire en HTTPException 404)."""
    from routers.grades import (  # import différé : cf. note en tête de fichier
        _category_average, _class_courses, _exam_of_record_map, compute_class_efcf_averages,
    )

    info = _class_info(db, class_id)
    class_name, filiere, niveau = info["name"], info["filiere"], info["niveau"]
    # Même ordre stable que cc_grid_excel.py (et que le PV) : fixé une fois
    # via ce seul appel, réutilisé pour les en-têtes ET pour indexer les
    # notes de chaque élève.
    courses = sorted(_class_courses(db, class_id), key=lambda c: c.get("title") or "")
    students = _class_students(db, class_id)
    jury_members = _class_jury_members(db, class_id)
    student_ids = [s["id"] for s in students]

    per_uf = _per_uf_efcf_scores(
        db, courses, student_ids,
        _exam_of_record_map=_exam_of_record_map, _category_average=_category_average,
    )
    stage_by_student = _class_stage_grades(db, class_id)
    # Un seul appel groupé pour toute la classe (pas par élève) — même
    # convention que compute_class_mg1_summary (grades.py) : cette fonction
    # fait déjà ses propres requêtes batched en interne. `mpefcfp1` qu'elle
    # renvoie inclut DÉJÀ la note de Stage dans sa pondération (cf. son
    # propre docstring dans grades.py) : la colonne STAGE de cette grille
    # n'est affichée qu'à titre d'information brute, elle n'est jamais
    # réincorporée dans un recalcul local de la moyenne.
    efcf_summary = compute_class_efcf_averages(db, class_id, student_ids)
    mpefcfp1_by_student: dict[str, Optional[float]] = {
        sid: efcf_summary.get(sid, {}).get("mpefcfp1") for sid in student_ids
    }

    # "Moyenne de la classe" (pied de tableau) — même amélioration
    # délibérée que cc_grid_excel.py (la feuille source la laisse vide) :
    # moyenne simple par colonne, en excluant les élèves sans note (jamais
    # compté comme 0).
    course_ids = [c["id"] for c in courses]
    course_class_avg: dict[str, Optional[float]] = {}
    for cid in course_ids:
        vals = [
            per_uf.get(sid, {}).get(cid, {}).get("pr")
            for sid in student_ids
            if per_uf.get(sid, {}).get(cid, {}).get("pr") is not None
        ]
        course_class_avg[cid] = round(sum(vals) / len(vals), 2) if vals else None

    stage_vals = [
        stage_by_student[sid]["grade"] for sid in student_ids
        if stage_by_student.get(sid) and stage_by_student[sid].get("grade") is not None
    ]
    stage_class_avg = round(sum(stage_vals) / len(stage_vals), 2) if stage_vals else None

    mpefcfp1_vals = [v for v in mpefcfp1_by_student.values() if v is not None]
    class_mpefcfp1_avg = round(sum(mpefcfp1_vals) / len(mpefcfp1_vals), 2) if mpefcfp1_vals else None

    # Coefficient affiché en en-tête de la colonne STAGE (ligne 3 de l'en-
    # tête, comme pour chaque UF) — JUDGMENT CALL (cf. rapport) : la table
    # class_stage_grades a un coefficient PAR ÉLÈVE (défaut 3, cf. L68), pas
    # un coefficient de classe unique. On affiche la valeur commune si tous
    # les élèves ayant une note de Stage partagent le même coefficient ;
    # blanc s'ils divergent (un seul nombre serait trompeur) ; et par défaut
    # 3 (le même repli que compute_class_efcf_averages elle-même applique en
    # interne, `coefficient or 3`) si aucune note de Stage n'existe encore
    # pour cette classe — c'est la valeur qui s'appliquerait dès qu'une note
    # serait saisie sans coefficient explicite.
    stage_coeffs = {
        stage_by_student[sid].get("coefficient")
        for sid in stage_by_student
        if stage_by_student[sid].get("coefficient") is not None
    }
    if not stage_by_student:
        stage_header_coeff: Optional[float] = 3
    elif len(stage_coeffs) == 1:
        stage_header_coeff = next(iter(stage_coeffs))
    else:
        stage_header_coeff = None

    n_courses = len(courses)
    ncol = n_courses + 3  # col 1 = Nom, cols 2..n+1 = UF, n+2 = STAGE, n+3 = MPEFCFP1*
    col_stage = n_courses + 2
    col_total = ncol

    wb = Workbook()
    ws = wb.active
    ws.title = _safe_sheet_name(f"Prat {class_name}")

    bold = Font(bold=True)
    small_italic = Font(italic=True, size=9)
    wrap_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    center = Alignment(horizontal="center", vertical="center")
    left = Alignment(horizontal="left", vertical="center")

    hr = _write_letterhead(ws, ncol, filiere, niveau)

    ws.row_dimensions[hr].height = 40
    ws.row_dimensions[hr + 1].height = 42
    ws.row_dimensions[hr + 2].height = 16

    # ── Colonne 1 "Nom & Prénom" — fusion verticale sur les 3 lignes d'en-tête ─
    ws.merge_cells(start_row=hr, start_column=1, end_row=hr + 2, end_column=1)
    ws.cell(row=hr, column=1, value="Nom & Prénom")
    _style_range(ws, f"A{hr}:A{hr + 2}", font=bold, alignment=left, border=_BORDER)

    # ── Dernière colonne "MPEFCFP1*" — fusion verticale sur les 3 lignes
    #    d'en-tête, même fond gris que les colonnes UF/STAGE. Le libellé du
    #    vrai tableur source dit "MPEFCFT1*" ici — une coquille confirmée
    #    (son PROPRE pied de page dit "MPEFCFP1", correctement) : on corrige
    #    plutôt que de reproduire l'incohérence interne de la source (cf.
    #    rapport de vérification). ─────────────────────────────────────────
    last_col_letter = get_column_letter(col_total)
    ws.merge_cells(start_row=hr, start_column=col_total, end_row=hr + 2, end_column=col_total)
    ws.cell(row=hr, column=col_total, value="MPEFCFP1*")
    _style_range(
        ws, f"{last_col_letter}{hr}:{last_col_letter}{hr + 2}",
        fill=_GREY_FILL, font=bold, alignment=center, border=_BORDER,
    )

    # ── Bandeau titre (UF + STAGE, toujours au moins 1 colonne — STAGE —
    #    contrairement à cc_grid_excel.py où ce bloc pouvait être vide) ─────
    first_band_col, last_band_col = 2, col_stage
    first_letter, last_letter = get_column_letter(first_band_col), get_column_letter(last_band_col)
    ws.merge_cells(start_row=hr, start_column=first_band_col, end_row=hr, end_column=last_band_col)
    ws.cell(row=hr, column=first_band_col, value="Examens pratiques de fin de cursus de formation")
    _style_range(
        ws, f"{first_letter}{hr}:{last_letter}{hr}",
        fill=_GREY_FILL, font=bold, alignment=wrap_center, border=_BORDER,
    )

    for j, c in enumerate(courses, start=2):
        title_cell = ws.cell(row=hr + 1, column=j, value=c.get("title") or "UF")
        title_cell.fill, title_cell.font, title_cell.alignment, title_cell.border = (
            _GREY_FILL, bold, wrap_center, _BORDER,
        )
        coeff_cell = ws.cell(row=hr + 2, column=j, value=c.get("credits"))
        coeff_cell.fill, coeff_cell.font, coeff_cell.alignment, coeff_cell.border = (
            _GREY_FILL, Font(size=9), center, _BORDER,
        )

    # ── Colonne STAGE (titre + coefficient, même style que les UF) ─────────
    stage_title_cell = ws.cell(row=hr + 1, column=col_stage, value="STAGE")
    stage_title_cell.fill, stage_title_cell.font, stage_title_cell.alignment, stage_title_cell.border = (
        _GREY_FILL, bold, wrap_center, _BORDER,
    )
    stage_coeff_cell = ws.cell(row=hr + 2, column=col_stage, value=stage_header_coeff)
    stage_coeff_cell.fill, stage_coeff_cell.font, stage_coeff_cell.alignment, stage_coeff_cell.border = (
        _GREY_FILL, Font(size=9), center, _BORDER,
    )

    # ── Lignes élèves ────────────────────────────────────────────────────────
    first_data_row = hr + 3
    for i, s in enumerate(students):
        r = first_data_row + i
        sid = s["id"]
        name = s.get("full_name") or s.get("email") or "—"
        mpefcfp1 = mpefcfp1_by_student.get(sid)
        is_fail = mpefcfp1 is not None and mpefcfp1 < 10  # seuil "<10 = échec" — même convention que cc_grid_excel.py

        name_cell = ws.cell(row=r, column=1, value=name)
        name_cell.alignment, name_cell.border = left, _BORDER

        for j, c in enumerate(courses, start=2):
            pr = per_uf.get(sid, {}).get(c["id"], {}).get("pr")
            cell = ws.cell(row=r, column=j, value=pr)
            cell.number_format, cell.alignment, cell.border = "0.00", center, _BORDER

        stage_row = stage_by_student.get(sid)
        stage_grade = stage_row.get("grade") if stage_row else None
        stage_cell = ws.cell(row=r, column=col_stage, value=stage_grade)
        stage_cell.number_format, stage_cell.alignment, stage_cell.border = "0.00", center, _BORDER

        total_cell = ws.cell(row=r, column=col_total, value=mpefcfp1)
        total_cell.number_format, total_cell.font, total_cell.alignment, total_cell.border = (
            "0.00", bold, center, _BORDER,
        )

        if is_fail:
            for j in range(1, ncol + 1):
                cell = ws.cell(row=r, column=j)
                cell.fill = _RED_FILL
                cell.font = Font(color=_WHITE, bold=cell.font.bold if cell.font else False)

    if students:
        footer_row = first_data_row + len(students)
    else:
        ws.merge_cells(start_row=first_data_row, start_column=1, end_row=first_data_row, end_column=ncol)
        notice = ws.cell(row=first_data_row, column=1, value="Aucun élève inscrit dans cette classe.")
        notice.font, notice.alignment = Font(italic=True), center
        footer_row = first_data_row + 1

    # ── Pied de tableau : "Moyenne de la classe" (UF + STAGE + MPEFCFP1*) ──
    label_cell = ws.cell(row=footer_row, column=1, value="Moyenne de la classe")
    label_cell.font, label_cell.alignment, label_cell.border = bold, left, _BORDER

    for j, c in enumerate(courses, start=2):
        cell = ws.cell(row=footer_row, column=j, value=course_class_avg.get(c["id"]))
        cell.number_format, cell.font, cell.alignment, cell.border = "0.00", bold, center, _BORDER

    stage_avg_cell = ws.cell(row=footer_row, column=col_stage, value=stage_class_avg)
    stage_avg_cell.number_format, stage_avg_cell.font, stage_avg_cell.alignment, stage_avg_cell.border = (
        "0.00", bold, center, _BORDER,
    )

    avg_cell = ws.cell(row=footer_row, column=col_total, value=class_mpefcfp1_avg)
    avg_cell.number_format, avg_cell.font, avg_cell.alignment, avg_cell.border = "0.00", bold, center, _BORDER

    # ── Largeurs de colonnes ────────────────────────────────────────────────
    ws.column_dimensions["A"].width = 32
    for j in range(2, ncol):
        ws.column_dimensions[get_column_letter(j)].width = 14
    ws.column_dimensions[get_column_letter(col_total)].width = 12

    # ── Note de bas de tableau — texte réel de la source, qui dit bien
    #    "MPEFCFP1" ici (contrairement à son en-tête de colonne, cf. plus
    #    haut) ───────────────────────────────────────────────────────────────
    r = footer_row + 2
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=ncol)
    footnote = ws.cell(row=r, column=1, value=(
        "** MPEFCFP1 : Moyenne pondérée des notes de l'Examen de Fin de Cursus "
        "de Formation pratique de la 1ère année (en tenant compte des "
        "coefficients d'évaluation Ci)"
    ))
    footnote.font, footnote.alignment = small_italic, left

    # ── Bloc signature — identique à cc_grid_excel.py ───────────────────────
    r += 2
    sig_heading = ws.cell(row=r, column=1, value="Signature :")
    sig_heading.font = Font(bold=True, underline="single")
    sig_heading.alignment = left

    r += 1
    label_row, name_row = r, r + 1
    ws.row_dimensions[label_row].height = 30
    ws.row_dimensions[name_row].height = 24
    zone_cols = max(ncol, 4)
    base, rem = divmod(zone_cols, 4)
    col_cursor = 1
    for i, label in enumerate(_JURY_LABELS):
        span = base + (1 if i < rem else 0)
        start_col, end_col = col_cursor, col_cursor + span - 1
        col_cursor = end_col + 1

        if end_col > start_col:
            ws.merge_cells(start_row=label_row, start_column=start_col, end_row=label_row, end_column=end_col)
            ws.merge_cells(start_row=name_row, start_column=start_col, end_row=name_row, end_column=end_col)

        lbl_cell = ws.cell(row=label_row, column=start_col, value=label)
        lbl_cell.font, lbl_cell.alignment = Font(bold=True, size=10), wrap_center

        member = jury_members[i] if i < len(jury_members) else {}
        name_cell = ws.cell(row=name_row, column=start_col, value=member.get("name") or "")
        name_cell.font, name_cell.alignment = Font(italic=True, size=10), wrap_center

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
