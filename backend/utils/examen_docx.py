"""Export .docx d'un Examen — reproduit fidèlement le gabarit officiel de
l'établissement (« ETEIQUE IP1 QUES.docx » fourni), mesuré directement via
python-docx (pas seulement le texte) : en-tête complet (raison sociale +
adresse), bloc métadonnées, tableau Questions/Barème à bordures visibles,
puis tableau d'émargement du jury (5 membres nommés). La page « Epreuve :
Pratique » est optionnelle — omise si `pratique_sections` est vide, comme la
partie pratique d'un examen théorique/pratique classique ne l'est pas
toujours.

Diffère du Contrôle continu (controle_continu_docx.py) par : l'en-tête
(raison sociale complète, pas juste le sigle + logo), les métadonnées
(« Epreuve » + jury au lieu de « Formateur »), l'absence de page Corrigé
type, et le tableau d'émargement. Réutilise le même parseur HTML→paragraphes
et le même principe de tableau bordé à 2 colonnes."""
from __future__ import annotations

import io

from docx import Document as DocxDocument
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.shared import Pt, Cm, RGBColor

from utils import institution
from utils.controle_continu_docx import _html_to_blocks, _set_cell_borders, DEFAULT_FONT

INK = RGBColor(0x1A, 0x1A, 0x1A)

# Largeurs mesurées sur le gabarit — 5 colonnes du tableau d'émargement (cm).
JURY_COL_WIDTHS_CM = [4.47, 3.75, 3.50, 3.40, 3.75]


def _set_margins(section) -> None:
    section.top_margin = Cm(0.75)
    section.bottom_margin = Cm(2.5)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(2.5)


def _header_block(doc: DocxDocument) -> None:
    lines = [
        f"{institution.NAME.upper()} ({institution.SHORT_NAME}-{institution.CITY.upper()})",
        "<<ETABLISSEMENT PRIVE>>",
        institution.ADDRESS.upper(),
    ]
    for text in lines:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(0)
        run = p.add_run(text)
        run.bold = True
        run.font.name = DEFAULT_FONT
        run.font.size = Pt(9)
        run.font.color.rgb = INK

    line = doc.add_paragraph()
    line.alignment = WD_ALIGN_PARAGRAPH.CENTER
    line.paragraph_format.space_before = Pt(4)
    line.paragraph_format.space_after = Pt(12)
    run = line.add_run("-" * 100)
    run.bold = True
    run.italic = True
    run.font.name = DEFAULT_FONT
    run.font.size = Pt(11)
    run.font.color.rgb = INK


def _meta_line(doc: DocxDocument, *pairs: tuple[str, str]) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    if len(pairs) == 2:
        p.paragraph_format.tab_stops.add_tab_stop(Cm(9.5), WD_TAB_ALIGNMENT.LEFT)
    for i, (label, value) in enumerate(pairs):
        if i == 1:
            p.add_run("\t")
        run = p.add_run(f"{label} : {value or '……………………………'}")
        run.bold = True
        run.font.name = DEFAULT_FONT
        run.font.size = Pt(12)
        run.font.color.rgb = INK


def _questions_table(doc: DocxDocument, sections: list[dict]) -> None:
    table = doc.add_table(rows=2, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    left_w, right_w = Cm(15.4), Cm(3.0)
    for row in table.rows:
        row.cells[0].width = left_w
        row.cells[1].width = right_w

    head_left, head_right = table.rows[0].cells
    for cell, text in ((head_left, "QUESTIONS"), (head_right, "BAREME")):
        _set_cell_borders(cell)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(text)
        run.bold = True
        run.font.name = DEFAULT_FONT
        run.font.size = Pt(12)
        run.font.color.rgb = INK

    body_left, body_right = table.rows[1].cells
    _set_cell_borders(body_left)
    _set_cell_borders(body_right)
    left_first = right_first = True

    def add_left(html: str) -> int:
        nonlocal left_first
        blocks = _html_to_blocks(html)
        for block in blocks:
            p = body_left.paragraphs[0] if left_first else body_left.add_paragraph()
            left_first = False
            if block.kind == "li":
                p.style = "List Bullet"
            for text, bold, italic in block.runs:
                run = p.add_run(text)
                run.bold = bold
                run.italic = italic
                run.font.name = DEFAULT_FONT
                run.font.size = Pt(12)
                run.font.color.rgb = INK
        return len(blocks)

    def add_right_blank(n: int) -> None:
        nonlocal right_first
        for _ in range(n):
            p = body_right.paragraphs[0] if right_first else body_right.add_paragraph()
            right_first = False

    def add_right_bareme(bareme: float) -> None:
        nonlocal right_first
        p = body_right.paragraphs[0] if right_first else body_right.add_paragraph()
        right_first = False
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        label = f"{bareme:g}pts" if float(bareme) == int(bareme) else f"{bareme}pts"
        run = p.add_run(f"({label})")
        run.bold = True
        run.font.name = DEFAULT_FONT
        run.font.size = Pt(12)
        run.font.color.rgb = INK

    for i, section in enumerate(sections, start=1):
        html = f"<p><strong>Question {i} :</strong></p>" + (section.get("consigne") or "")
        count = add_left(html)
        add_right_blank(max(0, count - 1))
        add_right_bareme(section.get("bareme") or 0)


def _jury_table(doc: DocxDocument, jury: list[dict]) -> None:
    heading = doc.add_paragraph()
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    heading.paragraph_format.space_before = Pt(14)
    heading.paragraph_format.space_after = Pt(8)
    run = heading.add_run("Emargement des membres du jury d'examen")
    run.bold = True
    run.underline = True
    run.font.name = DEFAULT_FONT
    run.font.size = Pt(14)
    run.font.color.rgb = INK

    members = list(jury or [])[:5]
    while len(members) < 5:
        members.append({"name": "", "role": ""})

    table = doc.add_table(rows=2, cols=5)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    for row in table.rows:
        for ci, cell in enumerate(row.cells):
            cell.width = Cm(JURY_COL_WIDTHS_CM[ci])

    for ci, member in enumerate(members):
        cell = table.rows[0].cells[ci]
        _set_cell_borders(cell)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        name_run = p.add_run(member.get("name") or "……………………")
        name_run.font.name = DEFAULT_FONT
        name_run.font.size = Pt(7)
        name_run.font.color.rgb = INK
        if member.get("role"):
            p2 = cell.add_paragraph()
            p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
            role_run = p2.add_run(f"({member['role']})")
            role_run.bold = True
            role_run.font.name = DEFAULT_FONT
            role_run.font.size = Pt(7)
            role_run.font.color.rgb = INK

    # Ligne de signature, vierge.
    for ci in range(5):
        cell = table.rows[1].cells[ci]
        _set_cell_borders(cell)
        cell.paragraphs[0].paragraph_format.space_before = Pt(18)


def _one_page(doc: DocxDocument, assessment: dict, *, epreuve_label: str, sections: list[dict]) -> None:
    _header_block(doc)
    _meta_line(doc, ("Unité de Formation", assessment.get("title") or ""))
    _meta_line(doc, ("Epreuve", epreuve_label))
    _meta_line(doc, ("Filière", assessment.get("filiere") or ""), ("Niveau", assessment.get("niveau") or ""))
    _meta_line(
        doc,
        ("Date de l'épreuve", assessment.get("date_evaluation") or ""),
        ("Durée de l'épreuve", assessment.get("duree_epreuve") or ""),
    )
    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    _questions_table(doc, sections)
    _jury_table(doc, assessment.get("jury") or [])


def render_examen_docx(assessment: dict) -> bytes:
    """`assessment` : dict avec title, filiere, niveau, date_evaluation (déjà
    formatée JJ/MM/AAAA), duree_epreuve, sections (épreuve théorique, générée
    par IA), pratique_sections (optionnelle, saisie manuelle), jury (liste de
    {name, role}, jusqu'à 5)."""
    doc = DocxDocument()
    _set_margins(doc.sections[0])
    style = doc.styles["Normal"]
    style.font.name = DEFAULT_FONT
    style.font.size = Pt(12)

    _one_page(doc, assessment, epreuve_label="Théorique", sections=assessment.get("sections") or [])

    pratique = assessment.get("pratique_sections") or []
    if pratique:
        doc.add_page_break()
        _one_page(doc, assessment, epreuve_label="Pratique", sections=pratique)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
