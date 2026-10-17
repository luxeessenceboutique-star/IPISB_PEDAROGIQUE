"""Export .docx du Contrôle continu — reproduit FIDÈLEMENT le modèle papier
officiel de l'établissement (gabarit « QUESTIONS-CORRIGE TYPE.docx » fourni),
d'après une inspection directe de sa structure réelle (python-docx, pas
seulement le texte) :

- en-tête : cachet d'accréditation + logo IPISB côte à côte, « I.P.I.S.B
  EL JADIDA » (10pt gras), ligne de tirets (11pt gras italique) ;
- titre « Contrôle continu (Question) » / « (Corrigé type) » ;
- bloc métadonnées (Unité de Formation / Filière+Niveau / Date+Durée /
  Formateur) ;
- un VRAI TABLEAU 2 colonnes à BORDURES VISIBLES (le gabarit n'utilise pas
  de taquets de tabulation pour aligner le barème — c'est un tableau, avec
  un en-tête « QUESTIONS »/« Barème » ou « Corrigé type »/« Barème », une
  colonne large pour le texte et une colonne étroite pour le barème) ;
- pied de page avec les deux signatures.

Les consignes/corrigés sont stockés en HTML simple (Tiptap, voir
models.py::AssessmentSection) et convertis ici en paragraphes Word."""
from __future__ import annotations

import io
from html.parser import HTMLParser
from pathlib import Path

from docx import Document as DocxDocument
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.shared import Pt, Cm, RGBColor
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

from utils import institution

ASSETS_DIR = Path(__file__).resolve().parent.parent / "pptx_export"
LOGO_PATH = ASSETS_DIR / "ipisb_logo.png"
SEAL_PATH = ASSETS_DIR / "accreditation_seal.png"
INK = RGBColor(0x1A, 0x1A, 0x1A)
DEFAULT_FONT = "Marin"  # police du gabarit d'origine — Word retombe sur une police de substitution si absente du poste, comme pour le gabarit lui-même


# ── HTML (Tiptap) → paragraphes docx ────────────────────────────────────────
class _Block:
    __slots__ = ("kind", "runs")  # kind: 'p' | 'li'

    def __init__(self, kind: str):
        self.kind = kind
        self.runs: list[tuple[str, bool, bool]] = []  # (text, bold, italic)


class _HtmlToBlocks(HTMLParser):
    """Parse le HTML borné produit par l'IA / Tiptap (<p>, <strong>, <em>,
    <ul>, <li> uniquement — cf. prompt de controle_continu_generation.py) en
    une liste de blocs, en ignorant silencieusement toute autre balise."""

    def __init__(self):
        super().__init__()
        self.blocks: list[_Block] = []
        self._bold = 0
        self._italic = 0
        self._cur: _Block | None = None

    def _ensure_block(self, kind: str):
        if self._cur is None:
            self._cur = _Block(kind)
            self.blocks.append(self._cur)

    def handle_starttag(self, tag, attrs):
        if tag == "p":
            self._cur = _Block("p")
            self.blocks.append(self._cur)
        elif tag == "li":
            self._cur = _Block("li")
            self.blocks.append(self._cur)
        elif tag in ("strong", "b"):
            self._bold += 1
        elif tag in ("em", "i"):
            self._italic += 1
        elif tag == "br":
            self._ensure_block("p")
            self._cur.runs.append(("\n", self._bold > 0, self._italic > 0))

    def handle_endtag(self, tag):
        if tag in ("strong", "b"):
            self._bold = max(0, self._bold - 1)
        elif tag in ("em", "i"):
            self._italic = max(0, self._italic - 1)
        elif tag in ("p", "li"):
            self._cur = None

    def handle_data(self, data):
        if not data:
            return
        self._ensure_block("p")
        self._cur.runs.append((data, self._bold > 0, self._italic > 0))


def _html_to_blocks(html: str) -> list[_Block]:
    parser = _HtmlToBlocks()
    parser.feed(html or "")
    return [b for b in parser.blocks if any(t.strip() for t, _, _ in b.runs)]


def _add_html(container, html: str) -> None:
    """Ajoute le contenu HTML dans un Document OU une Cell (les deux
    exposent add_paragraph)."""
    for block in _html_to_blocks(html):
        p = container.add_paragraph()
        if block.kind == "li":
            p.style = "List Bullet"
        for text, bold, italic in block.runs:
            run = p.add_run(text)
            run.bold = bold
            run.italic = italic
            run.font.name = DEFAULT_FONT
            run.font.size = Pt(12)
            run.font.color.rgb = INK


def _set_cell_borders(cell, *, sz: int = 4) -> None:
    """Bordures fines visibles sur les 4 côtés d'une cellule (le gabarit
    utilise un tableau à bordures simples 1/2pt, pas des tabulations)."""
    tcPr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(sz))
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "1A1A1A")
        borders.append(el)
    tcPr.append(borders)


# ── Mise en page ─────────────────────────────────────────────────────────────
def _set_margins(section) -> None:
    # python-docx crée un document par défaut au format Letter — le gabarit
    # (comme tous les documents officiels de l'établissement) est en A4.
    # Sans ce réglage explicite, toute la mise en page (marges en cm,
    # largeurs de colonnes de tableau) est calculée pour la mauvaise taille
    # de page et le rendu final ne ressemble pas du tout au gabarit.
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(1.0)
    section.bottom_margin = Cm(1.0)
    section.left_margin = Cm(1.25)
    section.right_margin = Cm(1.25)


def _header_block(doc: DocxDocument) -> None:
    # Cachet d'accréditation + logo côte à côte, centrés — reproduit le
    # cluster d'images du gabarit (logo + sceau « Accrédité(s) »).
    if SEAL_PATH.exists() or LOGO_PATH.exists():
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(4)
        if SEAL_PATH.exists():
            p.add_run().add_picture(str(SEAL_PATH), height=Cm(1.8))
            p.add_run("   ")
        if LOGO_PATH.exists():
            p.add_run().add_picture(str(LOGO_PATH), height=Cm(2.0))

    name = doc.add_paragraph()
    name.alignment = WD_ALIGN_PARAGRAPH.CENTER
    name.paragraph_format.space_after = Pt(2)
    run = name.add_run(f"{institution.SHORT_NAME} {institution.CITY.upper()}")
    run.bold = True
    run.font.name = DEFAULT_FONT
    run.font.size = Pt(10)
    run.font.color.rgb = INK

    # Ligne de tirets (le gabarit utilise des tirets littéraux 11pt gras
    # italique, pas une bordure de paragraphe).
    line = doc.add_paragraph()
    line.alignment = WD_ALIGN_PARAGRAPH.CENTER
    line.paragraph_format.space_after = Pt(10)
    run = line.add_run("-" * 100)
    run.bold = True
    run.italic = True
    run.font.name = DEFAULT_FONT
    run.font.size = Pt(11)
    run.font.color.rgb = INK


def _title_block(doc: DocxDocument, label: str) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(14)
    run = p.add_run(f"Contrôle continu ({label})")
    run.bold = True
    run.font.name = DEFAULT_FONT
    run.font.size = Pt(16)
    run.font.color.rgb = INK


def _meta_line(doc: DocxDocument, *pairs: tuple[str, str]) -> None:
    """Une ligne de métadonnées avec 1 ou 2 paires label/valeur, la seconde
    poussée à ~9,5cm via un taquet de tabulation — reproduit « Filière : X
    Niveau : Y » du gabarit."""
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    if len(pairs) == 2:
        p.paragraph_format.tab_stops.add_tab_stop(Cm(9.5), WD_TAB_ALIGNMENT.LEFT)
    for i, (label, value) in enumerate(pairs):
        if i == 1:
            p.add_run("\t")
        r1 = p.add_run(f"{label} : ")
        r1.bold = True
        r1.font.name = DEFAULT_FONT
        r1.font.size = Pt(12)
        r2 = p.add_run(value or "……………………………")
        r2.font.name = DEFAULT_FONT
        r2.font.size = Pt(12)


def _exercise_table(doc: DocxDocument, assessment: dict, *, header_left: str, show_corrige: bool) -> None:
    """Le tableau 2 colonnes à bordures visibles qui porte les exercices —
    c'est l'élément central du gabarit (QUESTIONS/Barème ou Corrigé
    type/Barème). Colonne gauche large (texte), colonne droite étroite
    (barème), tailles reprises des mesures du gabarit (≈16,3cm / ≈2,3cm)."""
    table = doc.add_table(rows=2, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    left_w, right_w = Cm(16.3), Cm(2.3)
    for row in table.rows:
        row.cells[0].width = left_w
        row.cells[1].width = right_w

    # En-tête
    head_left, head_right = table.rows[0].cells
    for cell, text in ((head_left, header_left), (head_right, "Barème")):
        _set_cell_borders(cell)
        cell.paragraphs[0].text = ""
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(text)
        run.bold = True
        run.font.name = DEFAULT_FONT
        run.font.size = Pt(14)
        run.font.color.rgb = INK

    body_left, body_right = table.rows[1].cells
    _set_cell_borders(body_left)
    _set_cell_borders(body_right)
    body_left.paragraphs[0].text = ""
    body_right.paragraphs[0].text = ""
    body_left_first = True
    body_right_first = True

    def left_html(html: str) -> list:
        nonlocal body_left_first
        blocks = _html_to_blocks(html)
        for block in blocks:
            p = body_left.paragraphs[0] if body_left_first else body_left.add_paragraph()
            body_left_first = False
            if block.kind == "li":
                p.style = "List Bullet"
            for text, bold, italic in block.runs:
                run = p.add_run(text)
                run.bold = bold
                run.italic = italic
                run.font.name = DEFAULT_FONT
                run.font.size = Pt(12)
                run.font.color.rgb = INK
        return blocks

    def left_blank(n: int):
        nonlocal body_left_first
        for _ in range(n):
            p = body_left.paragraphs[0] if body_left_first else body_left.add_paragraph()
            body_left_first = False

    def right_blank(n: int):
        nonlocal body_right_first
        for _ in range(n):
            p = body_right.paragraphs[0] if body_right_first else body_right.add_paragraph()
            body_right_first = False

    def right_bareme(bareme: float):
        nonlocal body_right_first
        p = body_right.paragraphs[0] if body_right_first else body_right.add_paragraph()
        body_right_first = False
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        bareme_label = f"{bareme:g}pts" if float(bareme) == int(bareme) else f"{bareme}pts"
        run = p.add_run(f"({bareme_label})")
        run.bold = True
        run.font.name = DEFAULT_FONT
        run.font.size = Pt(12)
        run.font.color.rgb = INK

    sections = assessment.get("sections") or []
    for section in sections:
        bareme = section.get("bareme") or 0
        answer_lines = 0
        if show_corrige:
            html = section.get("corrige") or ""
            blocks = left_html(html)
            gap = max(1, len(blocks))
        else:
            html = section.get("consigne") or ""
            blocks = left_html(html)
            gap = max(1, len(blocks))
            # Espace de réponse pour l'étudiant, proportionnel au barème —
            # mêmes proportions que le gabarit (plusieurs lignes blanches).
            answer_lines = max(3, min(10, int(round(float(bareme or 2) * 1.3))))
            left_blank(answer_lines)

        right_blank(max(0, gap - 1))
        right_bareme(bareme)
        if not show_corrige:
            right_blank(answer_lines)
        else:
            right_blank(1)


def _signature_footer(doc: DocxDocument) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(18)
    p.paragraph_format.tab_stops.add_tab_stop(Cm(16.5), WD_TAB_ALIGNMENT.RIGHT)
    r1 = p.add_run("Signature du formateur")
    r1.bold = True
    r1.font.name = DEFAULT_FONT
    r1.font.size = Pt(11)
    p.add_run("\t")
    directeur_label = "de la directrice" if institution.DIRECTOR_CIVILITY == "Mme" else "du directeur"
    r2 = p.add_run(f"Cachet et signature {directeur_label}")
    r2.bold = True
    r2.font.name = DEFAULT_FONT
    r2.font.size = Pt(11)


def _one_page(doc: DocxDocument, assessment: dict, *, label: str, show_corrige: bool) -> None:
    _header_block(doc)
    _title_block(doc, label)
    _meta_line(doc, ("Unité de Formation", assessment.get("title") or ""))
    _meta_line(doc, ("Filière", assessment.get("filiere") or ""), ("Niveau", assessment.get("niveau") or ""))
    _meta_line(
        doc,
        ("Date de l'évaluation", assessment.get("date_evaluation") or ""),
        ("Durée de l'épreuve", assessment.get("duree_epreuve") or ""),
    )
    _meta_line(doc, ("Formateur", assessment.get("formateur") or ""))

    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    _exercise_table(doc, assessment, header_left=("Corrigé type" if show_corrige else "QUESTIONS"), show_corrige=show_corrige)
    _signature_footer(doc)


def render_controle_continu_docx(assessment: dict) -> bytes:
    """`assessment` : dict avec title, filiere, niveau, formateur,
    date_evaluation (déjà formatée JJ/MM/AAAA), duree_epreuve, sections
    (liste de {consigne, bareme, corrige} en HTML). Retourne le .docx —
    page 1 = Questions (tableau avec espace de réponse vierge), page 2 =
    Corrigé type (même tableau, avec les réponses)."""
    doc = DocxDocument()
    _set_margins(doc.sections[0])
    style = doc.styles["Normal"]
    style.font.name = DEFAULT_FONT
    style.font.size = Pt(12)

    _one_page(doc, assessment, label="Question", show_corrige=False)
    doc.add_page_break()
    _one_page(doc, assessment, label="Corrigé type", show_corrige=True)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
