"""Export .docx du Procès-verbal de décision du jury — reproduit la feuille
« Modalité de passage de 1ère en 2ème année » de l'Excel de référence : UN
seul document pour toute la classe (pas une page par élève), avec UNE ligne
par élève (Nom, MPCC1, MPEFCFT1, MPEFCFP1, MG1, Décision), la formule de MG1
en présentation fraction (numérateur/dénominateur, lue depuis les poids réels
de la classe — `class_grade_weights`), le tally « Proposition du jury
d'examens » (nombre d'élèves par issue, 6 catégories réelles), la légende
courte, puis les lignes de signature du jury de la décision finale
(`class_jury`, 4 rôles — distinct du jury d'un Examen donné).

Réutilise directement les mêmes briques que l'Examen (utils/examen_docx.py) :
correction A4 (`_set_margins`, sans quoi python-docx produit un document au
format Letter), le bloc d'en-tête (raison sociale complète) et `_meta_line`.
Le bloc de signature (`_jury_signatures` ci-dessous) n'est PAS un tableau
bordé façon émargement d'Examen : la feuille source "Modalité de passage"
utilise de simples lignes « Rôle : Nom » + filet pointillé, reproduites
telles quelles ici. Le tableau élèves, lui, réutilise le même helper de
bordures que les autres exports de ce dossier, `_set_cell_borders`
(backend/utils/controle_continu_docx.py), plutôt que de réinventer la
bordure XML.
"""
from __future__ import annotations

import io

from docx import Document as DocxDocument
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor
from supabase import Client

from utils.controle_continu_docx import BODY_FONT, DEFAULT_FONT, _set_cell_borders
from utils.documents import fr_year_label
from utils.examen_docx import _header_block, _meta_line, _set_margins

INK = RGBColor(0x1A, 0x1A, 0x1A)

# Libellés FR des 6 statuts réels (class_student_decisions.status) + du
# sentinel "a_examiner" (jamais écrit en base, cf. grades.py::compute_class_decisions
# — un simple signal "le jury n'a pas encore tranché").
_STATUS_LABELS = {
    "admis": "Admis",
    "admis_avec_rachat": "Admis avec rachat",
    "non_admis_redouble": "Non admis — autorisé à redoubler",
    "redouble_exceptionnel": "Autorisé exceptionnellement à redoubler",
    "reoriente": "Réorienté vers une autre filière",
    "exclu": "Exclu",
    "a_examiner": "À examiner",
}

# Ordre d'affichage du tally (§ "Proposition du jury d'examens") — reproduit
# l'ordre exact des 6 lignes de la feuille source "Modalité de passage de
# 1ère TS" (lignes 40 à 45 : admis / admis avec rachat / [non admis :
# redouble / réorienté / redouble exceptionnel / exclu]).
_TALLY_ORDER = [
    "admis", "admis_avec_rachat", "non_admis_redouble",
    "reoriente", "redouble_exceptionnel", "exclu",
]

# Colonnes du tableau principal (libellé, largeur cm) — total ≈ 18,8cm,
# du même ordre de grandeur que les tableaux déjà en place dans ce dossier
# (_questions_table : 18,4cm : _jury_table de l'Examen : 18,87cm).
_TABLE_COLS: list[tuple[str, float]] = [
    ("Nom", 4.6),
    ("MPCC1", 2.3),
    ("MPEFCFT1", 2.4),
    ("MPEFCFP1", 2.4),
    ("MG1", 2.1),
    ("Décision", 5.0),
]


def _fmt_grade(value: object) -> str:
    return f"{value:.2f}" if isinstance(value, (int, float)) and not isinstance(value, bool) else "—"


def _fmt_weight(value: float) -> str:
    """3.0 -> "3", 2.5 -> "2.5" — pas de zéro décimal superflu dans la
    formule affichée."""
    return f"{value:g}"


def _decision_label(entry: dict | None) -> str:
    """Texte de la cellule « Décision » : le statut réel enregistré s'il y
    en a un (is_override=True), sinon la suggestion automatique par seuil de
    MG1 — marquée « (suggestion) » pour ne jamais faire passer un calcul pour
    une décision déjà prise par le jury. Le sentinel "a_examiner" (MG1 < 10,
    aucune décision enregistrée) n'a pas besoin de ce marqueur : « À
    examiner » dit déjà explicitement qu'aucun choix n'est encore fait."""
    entry = entry or {}
    status = entry.get("status")
    if status is None:
        return "—"
    if status == "a_examiner":
        label = _STATUS_LABELS["a_examiner"]
    else:
        label = _STATUS_LABELS.get(status, status)
        if not entry.get("is_override"):
            label += " (suggestion)"
    mention = entry.get("mention")
    return f"{label} — {mention}" if mention else label


def _class_info(db: Client, class_id: str) -> dict:
    """Nom de la classe + filière (specialties.name) + niveau (year_number,
    formaté via fr_year_label) — même source unique que resolve_enrollment
    (utils/documents.py) : une classe porte exactement une spécialité et un
    numéro d'année."""
    rows = (
        db.from_("classes").select("name, year_number, specialties(name)")
        .eq("id", class_id).execute().data or []
    )
    klass = rows[0] if rows else {}
    specialty = klass.get("specialties") or {}
    return {
        "name": klass.get("name") or "",
        "filiere": specialty.get("name") or "",
        "niveau": fr_year_label(klass.get("year_number")),
    }


def _class_students(db: Client, class_id: str) -> list[dict]:
    """Élèves de la classe, triés par nom — [{id, full_name, email}]."""
    memberships = db.from_("class_students").select("student_id").eq("class_id", class_id).execute().data or []
    student_ids = list({m["student_id"] for m in memberships})
    if not student_ids:
        return []
    profiles = db.from_("profiles").select("id, full_name, email").in_("id", student_ids).execute().data or []
    profiles.sort(key=lambda p: (p.get("full_name") or p.get("email") or "").lower())
    return profiles


def _class_weights(db: Client, class_id: str) -> tuple[float, float, float]:
    """cc_weight/efcf_th_weight/efcf_pr_weight pour la formule MG1 affichée —
    même repli 3/2/3 et même tolérance à l'absence de L69 que
    `compute_class_mg1_summary` (grades.py). Dupliqué ici à l'identique plutôt
    qu'importé : les poids ne font pas partie de sa valeur de retour, et ce
    fichier ne doit pas toucher grades.py."""
    try:
        rows = db.from_("class_grade_weights").select("*").eq("class_id", class_id).execute().data
    except Exception:
        rows = None  # L69 pas encore appliquée
    if rows:
        return rows[0]["cc_weight"], rows[0]["efcf_th_weight"], rows[0]["efcf_pr_weight"]
    return 3, 2, 3


def _class_jury_members(db: Client, class_id: str) -> list[dict]:
    """Jury de la décision finale (class_jury, L70) — toujours exactement 4
    entrées {name, role}, complétées par des entrées vides si la classe n'a
    pas encore de jury configuré (même défaut que GET /classes/{id}/jury)."""
    try:
        rows = db.from_("class_jury").select("members").eq("class_id", class_id).execute().data
    except Exception:
        rows = None  # L70 pas encore appliquée
    members = list((rows[0].get("members") if rows else None) or [])[:4]
    while len(members) < 4:
        members.append({"name": "", "role": ""})
    return members


def _title_block(doc: DocxDocument) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(12)
    run = p.add_run("Procès-verbal — Modalité de passage de 1ère en 2ème année")
    run.bold = True
    run.font.name = DEFAULT_FONT
    run.font.size = Pt(15)
    run.font.color.rgb = INK


def _student_table(doc: DocxDocument, students: list[dict], summary: dict, decisions: dict) -> None:
    table = doc.add_table(rows=1, cols=len(_TABLE_COLS))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    header_cells = table.rows[0].cells
    for ci, (label, width) in enumerate(_TABLE_COLS):
        cell = header_cells[ci]
        cell.width = Cm(width)
        _set_cell_borders(cell)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(label)
        run.bold = True
        run.font.name = DEFAULT_FONT
        run.font.size = Pt(10)
        run.font.color.rgb = INK

    for student in students:
        sid = student["id"]
        row_summary = summary.get(sid) or {}
        row_decision = decisions.get(sid)
        values = [
            student.get("full_name") or student.get("email") or sid,
            _fmt_grade(row_summary.get("mpcc1")),
            _fmt_grade(row_summary.get("mpefcft1")),
            _fmt_grade(row_summary.get("mpefcfp1")),
            _fmt_grade(row_summary.get("mg1")),
            _decision_label(row_decision),
        ]
        row_cells = table.add_row().cells
        for ci, (text, (_, width)) in enumerate(zip(values, _TABLE_COLS)):
            cell = row_cells[ci]
            cell.width = Cm(width)
            _set_cell_borders(cell)
            p = cell.paragraphs[0]
            if ci != 0:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(text)
            run.font.name = DEFAULT_FONT
            run.font.size = Pt(10)
            run.font.color.rgb = INK


def _empty_notice(doc: DocxDocument) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("Aucun élève inscrit dans cette classe.")
    run.italic = True
    run.font.name = DEFAULT_FONT
    run.font.size = Pt(12)
    run.font.color.rgb = INK


def _scale_note(doc: DocxDocument) -> None:
    """« Toutes les notes sont calculées sur une échelle de 20. » — même
    phrase, même emplacement (juste sous le tableau élèves) que la feuille
    source."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    run = p.add_run("Toutes les notes sont calculées sur une échelle de 20.")
    run.font.name = BODY_FONT
    run.font.size = Pt(10)
    run.font.color.rgb = INK


def _formula_and_legend(doc: DocxDocument, cc_w: float, th_w: float, pr_w: float) -> None:
    """Bloc « Modalités de calcul de la moyenne générale » — reproduit la
    présentation en fraction de la feuille source (numérateur « MPCC1×3 +
    MPEFCFT1×2 + MPEFCFP1×3 » au-dessus, dénominateur — la somme réelle des
    poids de la classe, jamais un 8 figé — en dessous) plutôt qu'une seule
    ligne horizontale "=  (...)/...", et les mêmes trois définitions
    (MPCC1/MPEFCFT1/MPEFCFP1) en petit texte qu'en pied de la feuille source."""
    total = cc_w + th_w + pr_w

    heading = doc.add_paragraph()
    heading.paragraph_format.space_before = Pt(18)
    heading.paragraph_format.space_after = Pt(6)
    hrun = heading.add_run("Modalités de calcul de la moyenne générale de la première année")
    hrun.bold = True
    hrun.font.name = DEFAULT_FONT
    hrun.font.size = Pt(12)
    hrun.font.color.rgb = INK

    numerator = doc.add_paragraph()
    numerator.paragraph_format.space_after = Pt(0)
    nrun = numerator.add_run(
        f"MOYENNE GENERALE MG1 =  MPCC1 × {_fmt_weight(cc_w)} + MPEFCFT1 × {_fmt_weight(th_w)} "
        f"+ MPEFCFP1 × {_fmt_weight(pr_w)}"
    )
    nrun.bold = True
    nrun.font.name = DEFAULT_FONT
    nrun.font.size = Pt(11)
    nrun.font.color.rgb = INK

    denominator = doc.add_paragraph()
    denominator.paragraph_format.left_indent = Cm(3.2)
    denominator.paragraph_format.space_after = Pt(10)
    drun = denominator.add_run(_fmt_weight(total))
    drun.font.name = DEFAULT_FONT
    drun.font.size = Pt(11)
    drun.font.color.rgb = INK

    # Définitions courtes — formulation calquée sur le ton des autres
    # documents officiels de l'établissement (cf. meta-lignes d'examen_docx.py
    # / controle_continu_docx.py : sobre, formel, une ligne par notion).
    legend_lines = [
        "MPCC1 : Moyenne pondérée des notes des contrôles continus de la "
        "1ère année (en tenant compte des coefficients d'évaluation).",
        "MPEFCFT1 : Moyenne pondérée des notes de l'EFCF Théorique de la "
        "1ère année (en tenant compte des coefficients d'évaluation).",
        "MPEFCFP1 : Moyenne pondérée des notes de l'EFCF Pratique de la "
        "1ère année (en tenant compte des coefficients d'évaluation).",
    ]
    for text in legend_lines:
        lp = doc.add_paragraph()
        lp.paragraph_format.space_after = Pt(2)
        lrun = lp.add_run(text)
        lrun.font.name = BODY_FONT
        lrun.font.size = Pt(8)
        lrun.font.color.rgb = INK


def _decision_tally(doc: DocxDocument, decisions: dict) -> None:
    """« Proposition du jury d'examens » — compte, pour la classe entière, le
    nombre d'élèves dans chacune des 6 issues réelles (même libellés, même
    ordre que la feuille source), à partir du statut EFFECTIF de chaque
    élève (décision enregistrée si elle existe, sinon la suggestion — un
    élève avec MG1 ≥ 10 et pas encore de décision compte comme "admis"
    suggéré). Les élèves encore "à examiner" (MG1 < 10, aucune décision
    enregistrée) sont comptés à part, sur une ligne ajoutée seulement si ce
    compte est non nul — jamais silencieusement absorbés dans une des 6
    catégories fixes."""
    counts = {key: 0 for key in _TALLY_ORDER}
    pending = 0
    for entry in decisions.values():
        status = (entry or {}).get("status")
        if status in counts:
            counts[status] += 1
        elif status == "a_examiner":
            pending += 1

    heading = doc.add_paragraph()
    heading.paragraph_format.space_before = Pt(14)
    heading.paragraph_format.space_after = Pt(6)
    hrun = heading.add_run("Proposition du jury d'examens")
    hrun.bold = True
    hrun.font.name = DEFAULT_FONT
    hrun.font.size = Pt(12)
    hrun.font.color.rgb = INK

    lines = [(_STATUS_LABELS[key], counts[key]) for key in _TALLY_ORDER]
    if pending:
        lines.append((_STATUS_LABELS["a_examiner"], pending))
    for label, count in lines:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        lrun = p.add_run(f"Stagiaire {label[0].lower()}{label[1:]} : ")
        lrun.font.name = BODY_FONT
        lrun.font.size = Pt(10)
        lrun.font.color.rgb = INK
        crun = p.add_run(str(count))
        crun.bold = True
        crun.font.name = DEFAULT_FONT
        crun.font.size = Pt(10)
        crun.font.color.rgb = INK


def _jury_signatures(doc: DocxDocument, members: list[dict]) -> None:
    """« Signature : » puis, pour chaque membre du jury, une ligne « Rôle :
    Nom » suivie d'un filet de signature en pointillés sur la ligne
    indentée suivante. La feuille source place le filet dans une colonne à
    part de la même ligne (table Excel) ; en paragraphes simples un tab
    stop fixe casse dès que le libellé varie en longueur (p.ex. un membre
    non encore configuré, où rôle ET nom sont tous deux vides) — deux
    lignes courtes évite ce risque de retour à la ligne imprévisible tout
    en gardant la même information."""
    heading = doc.add_paragraph()
    heading.paragraph_format.space_before = Pt(18)
    heading.paragraph_format.space_after = Pt(10)
    run = heading.add_run("Signature :")
    run.bold = True
    run.font.name = DEFAULT_FONT
    run.font.size = Pt(12)
    run.font.color.rgb = INK

    for member in members:
        role = member.get("role")
        name = member.get("name")
        label = f"{role} : {name}" if (role or name) else "……………………………………………………"

        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.keep_with_next = True
        label_run = p.add_run(label)
        label_run.font.name = BODY_FONT
        label_run.font.size = Pt(11)
        label_run.font.color.rgb = INK

        sig = doc.add_paragraph()
        sig.paragraph_format.left_indent = Cm(1)
        sig.paragraph_format.space_after = Pt(14)
        dots_run = sig.add_run("…" * 30)
        dots_run.font.name = BODY_FONT
        dots_run.font.size = Pt(11)
        dots_run.font.color.rgb = INK


def render_pv_docx(db: Client, class_id: str) -> bytes:
    """Procès-verbal de décision du jury pour `class_id` — un seul document,
    une ligne par élève. S'appuie sur grades.py::compute_class_mg1_summary
    (MPCC1/MPEFCFT1/MPEFCFP1/MG1) et compute_class_decisions (statut/mention,
    réel ou suggéré) ; importés à l'intérieur de la fonction (pas en tête de
    module) pour éviter tout import circulaire avec routers/grades.py, qui
    exposera cette fonction sur un endpoint."""
    from routers.grades import compute_class_decisions, compute_class_mg1_summary

    klass = _class_info(db, class_id)
    students = _class_students(db, class_id)
    summary = compute_class_mg1_summary(db, class_id)
    decisions = compute_class_decisions(db, class_id)
    cc_w, th_w, pr_w = _class_weights(db, class_id)
    jury_members = _class_jury_members(db, class_id)

    doc = DocxDocument()
    _set_margins(doc.sections[0])
    style = doc.styles["Normal"]
    style.font.name = DEFAULT_FONT
    style.font.size = Pt(12)

    _header_block(doc)
    _title_block(doc)
    _meta_line(doc, ("Classe", klass["name"]), ("Filière", klass["filiere"]))
    if klass["niveau"]:
        _meta_line(doc, ("Niveau", klass["niveau"]))

    doc.add_paragraph().paragraph_format.space_after = Pt(4)

    if students:
        _student_table(doc, students, summary, decisions)
        _scale_note(doc)
    else:
        _empty_notice(doc)

    _formula_and_legend(doc, cc_w, th_w, pr_w)
    _decision_tally(doc, decisions)
    _jury_signatures(doc, jury_members)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
