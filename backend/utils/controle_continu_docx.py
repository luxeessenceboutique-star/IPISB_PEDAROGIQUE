"""Export .docx du Contrôle continu — reproduit le modèle papier officiel de
l'établissement (voir le gabarit « QUESTIONS-CORRIGE TYPE.docx » fourni) :
en-tête I.P.I.S.B EL JADIDA, bloc métadonnées (Unité de Formation / Filière /
Niveau / Date / Durée / Formateur), exercices numérotés avec barème, puis —
sur une seconde page du MÊME fichier — la version Corrigé type avec les
réponses. Les consignes/corrigés sont stockés en HTML simple (Tiptap, voir
models.py::AssessmentSection) et convertis ici en paragraphes Word."""
from __future__ import annotations

import io
from html.parser import HTMLParser
from pathlib import Path

from docx import Document as DocxDocument
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.shared import Pt, Cm, RGBColor
from docx.oxml.ns import qn

from utils import institution

LOGO_PATH = Path(__file__).resolve().parent.parent / "pptx_export" / "ipisb_logo.png"
INK = RGBColor(0x1A, 0x1A, 0x1A)


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


def _add_html(doc: DocxDocument, html: str, *, indent_li: bool = True) -> None:
    for block in _html_to_blocks(html):
        p = doc.add_paragraph()
        if block.kind == "li":
            p.style = "List Bullet" if indent_li else p.style
        for text, bold, italic in block.runs:
            run = p.add_run(text)
            run.bold = bold
            run.italic = italic
            run.font.size = Pt(11)
            run.font.color.rgb = INK


# ── Mise en page ─────────────────────────────────────────────────────────────
def _set_margins(section) -> None:
    for attr in ("top_margin", "bottom_margin", "left_margin", "right_margin"):
        setattr(section, attr, Cm(2.0))


def _header_block(doc: DocxDocument) -> None:
    if LOGO_PATH.exists():
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run()
        run.add_picture(str(LOGO_PATH), width=Cm(2.2))

    name = doc.add_paragraph()
    name.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = name.add_run(f"{institution.SHORT_NAME} {institution.CITY.upper()}")
    run.bold = True
    run.font.size = Pt(13)
    run.font.color.rgb = INK

    line = doc.add_paragraph()
    line.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf = line.paragraph_format
    pf.space_before = Pt(2)
    pf.space_after = Pt(10)
    border = line._p.get_or_add_pPr()
    bottom = border.makeelement(qn("w:pBdr"), {})
    edge = border.makeelement(qn("w:bottom"), {
        qn("w:val"): "single", qn("w:sz"): "6", qn("w:space"): "1", qn("w:color"): "1A1A1A",
    })
    bottom.append(edge)
    border.append(bottom)


def _title_block(doc: DocxDocument, label: str) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(f"Contrôle continu ({label})")
    run.bold = True
    run.font.size = Pt(14)
    run.font.color.rgb = INK
    p.paragraph_format.space_after = Pt(14)


def _meta_line(doc: DocxDocument, *pairs: tuple[str, str]) -> None:
    """Une ligne de métadonnées avec 1 ou 2 paires label/valeur, la seconde
    poussée à ~9cm via un taquet de tabulation (reproduit la mise en page du
    modèle papier : « Filière : X    Niveau : Y »)."""
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    if len(pairs) == 2:
        p.paragraph_format.tab_stops.add_tab_stop(Cm(9.5), WD_TAB_ALIGNMENT.LEFT)
    for i, (label, value) in enumerate(pairs):
        if i == 1:
            p.add_run("\t")
        r1 = p.add_run(f"{label} : ")
        r1.bold = True
        r1.font.size = Pt(11)
        r2 = p.add_run(value or "……………………………")
        r2.font.size = Pt(11)


def _section_header(doc: DocxDocument, left: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.tab_stops.add_tab_stop(Cm(16.5), WD_TAB_ALIGNMENT.RIGHT)
    r1 = p.add_run(left)
    r1.bold = True
    r1.underline = True
    r1.font.size = Pt(12)
    p.add_run("\t")
    r2 = p.add_run("Barème")
    r2.bold = True
    r2.underline = True
    r2.font.size = Pt(12)


def _exercise(doc: DocxDocument, num: int, section: dict, *, show_corrige: bool) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.tab_stops.add_tab_stop(Cm(16.5), WD_TAB_ALIGNMENT.RIGHT)
    r1 = p.add_run(f"Exercice {num}")
    r1.bold = True
    r1.font.size = Pt(11)
    p.add_run("\t")
    bareme = section.get("bareme") or 0
    bareme_label = f"{bareme:g}pts" if float(bareme) == int(bareme) else f"{bareme}pts"
    r2 = p.add_run(f"({bareme_label})")
    r2.bold = True
    r2.font.size = Pt(11)

    _add_html(doc, section.get("consigne") or "")

    if show_corrige:
        corrige_label = doc.add_paragraph()
        corrige_label.paragraph_format.space_before = Pt(4)
        r = corrige_label.add_run("Réponse attendue :")
        r.italic = True
        r.font.size = Pt(10.5)
        _add_html(doc, section.get("corrige") or "")
    else:
        # Espace pour la réponse de l'étudiant — mêmes proportions que le
        # modèle papier (plusieurs lignes blanches, longueur ~ barème).
        blank_lines = max(3, min(10, int(round(float(bareme or 2) * 1.3))))
        for _ in range(blank_lines):
            doc.add_paragraph()


def _signature_footer(doc: DocxDocument, formateur: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(24)
    p.paragraph_format.tab_stops.add_tab_stop(Cm(16.5), WD_TAB_ALIGNMENT.RIGHT)
    r1 = p.add_run("Signature du formateur")
    r1.font.size = Pt(10.5)
    p.add_run("\t")
    directeur_label = "de la directrice" if institution.DIRECTOR_CIVILITY == "Mme" else "du directeur"
    r2 = p.add_run(f"Cachet et signature {directeur_label}")
    r2.font.size = Pt(10.5)


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

    _section_header(doc, "Corrigé type" if show_corrige else "QUESTIONS")
    for i, section in enumerate(assessment.get("sections") or [], start=1):
        _exercise(doc, i, section, show_corrige=show_corrige)

    _signature_footer(doc, assessment.get("formateur") or "")


def render_controle_continu_docx(assessment: dict) -> bytes:
    """`assessment` : dict avec title, filiere, niveau, formateur,
    date_evaluation (déjà formatée JJ/MM/AAAA), duree_epreuve, sections
    (liste de {consigne, bareme, corrige} en HTML). Retourne le .docx —
    page 1 = Questions (espace de réponse vierge), page 2 = Corrigé type."""
    doc = DocxDocument()
    _set_margins(doc.sections[0])
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    _one_page(doc, assessment, label="Question", show_corrige=False)
    doc.add_page_break()
    _one_page(doc, assessment, label="Corrigé type", show_corrige=True)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
