"""Renders a course's PUBLISHED modules/lessons into a single multi-page PDF,
using the M101 manual's own visual language — the same palette and chrome
vocabulary as the slide editor (utils/slide_template_m101.py): the teal
cover band, the health-cross diamonds, the sage content pages with their
pill header and vertical CHAPITRE tab, the orange hours badge.

Colours are imported from slide_template_m101 rather than redefined, so the
PDF, the slide canvas and the editor's picker can never drift onto three
different greens. Geometry is NOT shared — the slide canvas is a fixed
800x450 (16:9) design space, this is a paginated A4 portrait document, and
mapping one onto the other would just be wrong in both directions. The
proportions here are redrawn for the page they actually live on, following
the same visual grammar (pill → card → sidebar tab → footer) rather than
the same pixel coordinates.

Body text still runs on reportlab's platypus (flowables) engine, unchanged
from before — a "Manuel de cours" pages a chapter's markdown across as many
pages as it needs, with tables/lists/images/diagrams handled the same way
they always were. What's new is everything AROUND that flow: a
BaseDocTemplate with distinct PageTemplates for the cover, the sommaire,
each chapter's divider and its content pages, each with its own onPage
chrome-drawing callback.

Pure rendering only — no network/storage I/O. Callers that want lesson
images embedded must pre-download them and attach as
lesson["images"] = [{"caption": str, "data": bytes}, ...] before calling
render_course_pdf (see routers/course_generation.py).
"""
import io
import re
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

import markdown
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate, Flowable, Frame, HRFlowable, Image, ListFlowable,
    ListItem, NextPageTemplate, PageBreak, PageTemplate, Paragraph, Spacer,
    Table, TableStyle,
)

from utils.slide_template_m101 import (
    BLUE, BLUE_DEEP, FAINT, GREEN, GREEN_DEEP, INK, LINE, MUTED, ORANGE,
    PAPER, SAGE_1, SAGE_2, SAGE_BG, SKY_1, SKY_BG, TEAL_BAND,
)

# ─── Palette — reportlab Color objects, built once from the shared hex
# constants above (single source of truth is slide_template_m101.py). ─────
C_GREEN = colors.HexColor(GREEN)
C_GREEN_DEEP = colors.HexColor(GREEN_DEEP)
C_BLUE = colors.HexColor(BLUE)
C_BLUE_DEEP = colors.HexColor(BLUE_DEEP)
C_ORANGE = colors.HexColor(ORANGE)
C_TEAL_BAND = colors.HexColor(TEAL_BAND)
C_INK = colors.HexColor(INK)
C_MUTED = colors.HexColor(MUTED)
C_FAINT = colors.HexColor(FAINT)
C_PAPER = colors.HexColor(PAPER)
C_SAGE_BG = colors.HexColor(SAGE_BG)
C_SAGE_1 = colors.HexColor(SAGE_1)
C_SAGE_2 = colors.HexColor(SAGE_2)
C_SKY_BG = colors.HexColor(SKY_BG)
C_SKY_1 = colors.HexColor(SKY_1)
C_LINE = colors.HexColor(LINE)
C_SHADOW = colors.Color(0, 0, 0, alpha=0.08)

LOGO_PATH = Path(__file__).resolve().parent.parent / "pptx_export" / "ipisb_logo.png"
_LOGO_READER: ImageReader | None = None


def _logo() -> ImageReader | None:
    """Lazy + cached: most renders happen inside a request, no reason to hit
    disk more than once per process."""
    global _LOGO_READER
    if _LOGO_READER is None and LOGO_PATH.exists():
        _LOGO_READER = ImageReader(str(LOGO_PATH))
    return _LOGO_READER


INLINE_TAG_MAP = {"strong": "b", "em": "i"}

PAGE_W, PAGE_H = A4

# Content-page card geometry (mm from page edges) — the vertical green tab
# sits left of the card, the pill header sits above it, matching the slide
# template's chrome vocabulary at portrait-page proportions rather than its
# exact pixel layout.
SIDEBAR_X, SIDEBAR_W = 8 * mm, 9 * mm
CARD_X = SIDEBAR_X + SIDEBAR_W + 6 * mm
CARD_RIGHT = PAGE_W - 16 * mm
CARD_TOP_Y = PAGE_H - 40 * mm      # top edge of the card, in reportlab's bottom-left-origin space
CARD_BOTTOM_Y = 24 * mm
CARD_W = CARD_RIGHT - CARD_X
CARD_H = CARD_TOP_Y - CARD_BOTTOM_Y


def _y(mm_from_top: float) -> float:
    """This whole module is authored top-down (mm from the page's top edge),
    matching how every other design surface in this codebase (the slide
    canvas, the PPTX generator) is authored — but reportlab's canvas origin
    is bottom-left. Converting at this one boundary keeps every drawing
    function below written the intuitive way."""
    return PAGE_H - mm_from_top * mm


# ─── Minimal HTML tree (html.parser gives events, not a tree — build one) ──
class _Node:
    __slots__ = ("tag", "attrs", "children")

    def __init__(self, tag: str, attrs: dict | None = None):
        self.tag = tag
        self.attrs = attrs or {}
        self.children: list = []  # list[_Node | str]


class _TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("root")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = _Node(tag, dict(attrs))
        self.stack[-1].children.append(node)
        if tag not in ("br", "hr", "img"):
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(_Node(tag, dict(attrs)))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _inline_text(node: _Node) -> str:
    """Render a node's descendants as ReportLab's mini-markup (b/i/br)."""
    parts = []
    for child in node.children:
        if isinstance(child, str):
            parts.append(_esc(child))
            continue
        if child.tag in INLINE_TAG_MAP:
            parts.append(f"<{INLINE_TAG_MAP[child.tag]}>{_inline_text(child)}</{INLINE_TAG_MAP[child.tag]}>")
        elif child.tag == "br":
            parts.append("<br/>")
        elif child.tag == "code":
            parts.append(f"<font face='Courier'>{_inline_text(child)}</font>")
        elif child.tag == "p":
            # markdown emits nested <p> inside "loose" <li> items — flatten
            # it into the same run rather than starting a new flowable.
            parts.append(_inline_text(child) + "<br/><br/>")
        else:
            parts.append(_inline_text(child))
    return "".join(parts).strip()


def _raw_text(node: _Node) -> str:
    """Plain-text content, no mini-markup — for parsing (not displaying) a
    fenced code block's contents."""
    parts = []
    for child in node.children:
        parts.append(child if isinstance(child, str) else _raw_text(child))
    return "".join(parts)


def _table_flowable(table_node: _Node, styles: dict) -> list:
    rows: list[list] = []
    header_idx = None
    for section in table_node.children:
        if isinstance(section, str):
            continue
        if section.tag == "thead":
            for tr in section.children:
                if isinstance(tr, str) or tr.tag != "tr":
                    continue
                rows.append([Paragraph(_inline_text(c), styles["th"]) for c in tr.children if not isinstance(c, str)])
                header_idx = len(rows) - 1
        elif section.tag == "tbody":
            for tr in section.children:
                if isinstance(tr, str) or tr.tag != "tr":
                    continue
                rows.append([Paragraph(_inline_text(c), styles["td"]) for c in tr.children if not isinstance(c, str)])
    if not rows:
        return []
    ncols = max(len(r) for r in rows)
    for r in rows:
        while len(r) < ncols:
            r.append(Paragraph("", styles["td"]))

    t = Table(rows, hAlign="LEFT", repeatRows=1 if header_idx == 0 else 0)
    cmds = [
        ("GRID", (0, 0), (-1, -1), 0.4, C_LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header_idx is not None:
        cmds.append(("BACKGROUND", (0, header_idx), (-1, header_idx), C_SAGE_BG))
    t.setStyle(TableStyle(cmds))
    return [t, Spacer(1, 3 * mm)]


def _parse_diagram_dsl(text: str) -> dict | None:
    """Parses the ```diagram fenced-block mini-DSL the generation prompt
    asks the model for:
        TITLE: <title>
        CATEGORIE: <name>
        - <item>
        - <item>
        CATEGORIE: <name>
        - <item>
    Defensive: malformed input just yields fewer/empty categories rather
    than raising — a diagram that renders oddly beats one that 500s the PDF.
    """
    title = ""
    categories: list[dict] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.upper().startswith("TITLE:"):
            title = line.split(":", 1)[1].strip()
        elif line.upper().startswith("CATEGORIE:") or line.upper().startswith("CATÉGORIE:"):
            categories.append({"name": line.split(":", 1)[1].strip(), "items": []})
        elif line.startswith("-") and categories:
            categories[-1]["items"].append(line.lstrip("-").strip())
    if not categories:
        return None
    return {"title": title, "categories": categories}


def _diagram_flowable(spec: dict, styles: dict) -> list:
    """A classification/typology rendered as a row of headed cards — a real
    visual break from body text, and far more robust across page widths
    than freehand box/line drawing would be."""
    cats = spec["categories"][:4]  # keep it to what actually fits a page width
    cells = []
    for cat in cats:
        items_html = "<br/>".join(f"• {_esc(it)}" for it in cat["items"][:8])
        cell = Paragraph(f"<b>{_esc(cat['name'])}</b><br/><br/>{items_html}", styles["diagram_cell"])
        cells.append(cell)

    t = Table([cells], colWidths=[CARD_W / len(cells)] * len(cells), hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, C_ORANGE),
        ("INNERGRID", (0, 0), (-1, -1), 0.6, C_ORANGE),
        ("BACKGROUND", (0, 0), (-1, -1), C_SAGE_1),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))

    flowables = []
    if spec.get("title"):
        flowables.append(Paragraph(_esc(spec["title"]), styles["diagram_title"]))
    flowables += [t, Spacer(1, 3 * mm)]
    return flowables


def _image_flowables(images: list[dict], styles: dict) -> list:
    flowables = []
    for img in images:
        data = img.get("data")
        if not data:
            continue
        try:
            with PILImage.open(io.BytesIO(data)) as pi:
                w, h = pi.size
        except Exception:
            continue  # corrupt/unsupported file — skip rather than crash the whole PDF
        max_w, max_h = CARD_W, 95 * mm
        scale = min(max_w / w, max_h / h, 1.0)
        flowables.append(Spacer(1, 2 * mm))
        flowables.append(Image(io.BytesIO(data), width=w * scale, height=h * scale))
        if img.get("caption"):
            flowables.append(Paragraph(_esc(img["caption"]), styles["caption"]))
        flowables.append(Spacer(1, 3 * mm))
    return flowables


def _block_flowables(root: _Node, styles: dict) -> list:
    flowables = []
    for node in root.children:
        if isinstance(node, str):
            continue
        if node.tag == "h2":
            flowables += [Spacer(1, 5 * mm), Paragraph(_inline_text(node), styles["h2"])]
        elif node.tag == "h3":
            flowables += [Spacer(1, 4 * mm), Paragraph(_inline_text(node), styles["h3"])]
        elif node.tag == "h4":
            flowables += [Spacer(1, 3 * mm), Paragraph(_inline_text(node), styles["h4"])]
        elif node.tag == "p":
            txt = _inline_text(node)
            if txt:
                flowables += [Paragraph(txt, styles["body"]), Spacer(1, 2 * mm)]
        elif node.tag in ("ul", "ol"):
            items = [
                ListItem(Paragraph(_inline_text(li), styles["body"]), spaceAfter=2 * mm)
                for li in node.children if not isinstance(li, str) and li.tag == "li"
            ]
            if items:
                flowables += [
                    ListFlowable(items, bulletType="bullet" if node.tag == "ul" else "1", leftIndent=6 * mm),
                    Spacer(1, 2 * mm),
                ]
        elif node.tag == "hr":
            flowables += [Spacer(1, 2 * mm), HRFlowable(width="100%", thickness=0.5, color=C_LINE), Spacer(1, 2 * mm)]
        elif node.tag == "table":
            flowables += _table_flowable(node, styles)
        elif node.tag == "pre":
            code = next((c for c in node.children if not isinstance(c, str) and c.tag == "code"), None)
            lang = (code.attrs.get("class") or "") if code else ""
            raw = _raw_text(code) if code else _raw_text(node)
            if "diagram" in lang:
                spec = _parse_diagram_dsl(raw)
                if spec:
                    flowables += _diagram_flowable(spec, styles)
                # malformed diagram block: drop it silently rather than dump
                # the raw DSL as visible text in a student-facing PDF
            else:
                flowables += [Paragraph(f"<font face='Courier' size='8'>{_esc(raw)}</font>", styles["body"]), Spacer(1, 2 * mm)]
        elif node.tag in ("div", "root"):
            flowables += _block_flowables(node, styles)  # our own tbl-wrap-style wrappers, if any
    return flowables


def _styles() -> dict:
    return {
        "toc_h":         ParagraphStyle("toc_h", fontName="Helvetica-Bold", fontSize=10, textColor=colors.white, spaceAfter=6, tracking=1),
        "toc_item":      ParagraphStyle("toc_item", fontName="Helvetica", fontSize=10.5, textColor=C_INK, leading=15),
        "toc_num":       ParagraphStyle("toc_num", fontName="Helvetica-Bold", fontSize=10.5, textColor=C_ORANGE, leading=15),
        "eyebrow":       ParagraphStyle("eyebrow", fontName="Helvetica-Bold", fontSize=9, textColor=C_ORANGE, spaceAfter=2, leading=12),
        "chap_title":    ParagraphStyle("chap_title", fontName="Helvetica-Bold", fontSize=19, textColor=C_GREEN, leading=23, spaceAfter=3),
        "chap_lead":     ParagraphStyle("chap_lead", fontName="Helvetica-Bold", fontSize=10, textColor=C_GREEN, spaceAfter=3),
        "objective":     ParagraphStyle("objective", fontName="Helvetica", fontSize=10, textColor=C_INK, spaceAfter=2, leading=15, bulletIndent=0, leftIndent=4 * mm),
        "hours":         ParagraphStyle("hours", fontName="Helvetica-Bold", fontSize=11, textColor=colors.white, alignment=TA_CENTER),
        "kicker":        ParagraphStyle("kicker", fontName="Helvetica-Bold", fontSize=11.5, textColor=C_GREEN, leading=14),
        "subtitle":      ParagraphStyle("subtitle", fontName="Helvetica-Bold", fontSize=9.5, textColor=C_GREEN, leading=12),
        "card_heading":  ParagraphStyle("card_heading", fontName="Helvetica-Bold", fontSize=13.5, textColor=C_GREEN, spaceAfter=4),
        "h2":            ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=14.5, textColor=C_GREEN, leading=18, spaceAfter=3),
        "h3":            ParagraphStyle("h3", fontName="Helvetica-Bold", fontSize=12.5, textColor=C_GREEN_DEEP, leading=16, spaceAfter=3),
        "h4":            ParagraphStyle("h4", fontName="Helvetica-Bold", fontSize=10, textColor=C_MUTED, leading=13, spaceAfter=3),
        "body":          ParagraphStyle("body", fontName="Times-Roman", fontSize=10.5, textColor=C_INK, leading=15.5, alignment=TA_JUSTIFY),
        "th":            ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=8.5, textColor=C_GREEN_DEEP),
        "td":            ParagraphStyle("td", fontName="Times-Roman", fontSize=9.5, textColor=C_INK, leading=13),
        "diagram_title": ParagraphStyle("diagram_title", fontName="Helvetica-Bold", fontSize=9.5, textColor=C_ORANGE, spaceAfter=3, alignment=TA_CENTER),
        "diagram_cell":  ParagraphStyle("diagram_cell", fontName="Helvetica", fontSize=8.5, textColor=C_INK, leading=12.5),
        "caption":       ParagraphStyle("caption", fontName="Helvetica-Oblique", fontSize=8, textColor=C_MUTED, alignment=TA_CENTER),
        "cover_inst":    ParagraphStyle("cover_inst", fontName="Helvetica-Bold", fontSize=10.5, textColor=C_INK, leading=13),
        "cover_sub":     ParagraphStyle("cover_sub", fontName="Helvetica", fontSize=8, textColor=C_MUTED, leading=10.5),
        "cover_secteur": ParagraphStyle("cover_secteur", fontName="Helvetica-Bold", fontSize=9.5, textColor=C_GREEN, leading=13),
        "cover_manuel":  ParagraphStyle("cover_manuel", fontName="Helvetica", fontSize=9.5, textColor=C_INK, leading=13),
        "cover_title":   ParagraphStyle("cover_title", fontName="Helvetica-Bold", fontSize=20, textColor=colors.white, leading=25),
        "cover_niveau":  ParagraphStyle("cover_niveau", fontName="Helvetica", fontSize=11, textColor=C_INK, leading=14),
        "cover_filiere_label": ParagraphStyle("cover_filiere_label", fontName="Helvetica", fontSize=9, textColor=C_ORANGE, leading=12),
        "cover_filiere": ParagraphStyle("cover_filiere", fontName="Helvetica-Bold", fontSize=17, textColor=C_BLUE, leading=21),
        "cover_foot":    ParagraphStyle("cover_foot", fontName="Helvetica-Oblique", fontSize=8, textColor=C_MUTED),
    }


# ─── Drawing helpers shared across chrome callbacks ────────────────────────
def _draw_para(canvas: Canvas, text: str, style: ParagraphStyle, x_mm: float, top_mm: float, w_mm: float, max_h_mm: float = 40) -> None:
    """Places a Paragraph at a fixed top-down position rather than flowing
    it — used for chrome text (kickers, cover blocks, chapter-divider
    titles) that's short enough to size itself, so it doesn't need a real
    Frame. `text` is plain and gets escaped; pass pre-built markup only from
    trusted call sites."""
    if not text:
        return
    p = Paragraph(_esc(text), style)
    w, h = p.wrap(w_mm * mm, max_h_mm * mm)
    p.drawOn(canvas, x_mm * mm, _y(top_mm) - h)


def _dot_grid(canvas: Canvas, x_mm: float, top_mm: float, w_mm: float, h_mm: float, gap_mm: float = 4.4, r_mm: float = 0.5, color=C_LINE) -> None:
    canvas.setFillColor(color)
    cols = int(w_mm / gap_mm)
    rows = int(h_mm / gap_mm)
    for row in range(rows):
        for col in range(cols):
            cx = (x_mm + col * gap_mm) * mm
            cy = _y(top_mm + row * gap_mm)
            canvas.circle(cx, cy, r_mm * mm, fill=1, stroke=0)


def _diamond(canvas: Canvas, cx_mm: float, cy_top_mm: float, side_mm: float, color) -> None:
    """A square rotated 45° about its own centre — reportlab's rotate()
    pivots around whatever point translate() last moved to, so centring
    first sidesteps the top-left-anchor correction the same shape needed
    on the Konva canvas (utils/slide_template_m101.py)."""
    canvas.saveState()
    canvas.translate(cx_mm * mm, _y(cy_top_mm))
    canvas.rotate(45)
    canvas.setFillColor(color)
    canvas.rect(-side_mm * mm / 2, -side_mm * mm / 2, side_mm * mm, side_mm * mm, fill=1, stroke=0)
    canvas.restoreState()


def _health_cross(canvas: Canvas, cx_mm: float, cy_top_mm: float, size_mm: float) -> None:
    canvas.setFillColor(colors.white)
    canvas.rect((cx_mm - size_mm * 0.14) * mm, _y(cy_top_mm + size_mm * 0.5), size_mm * 0.28 * mm, size_mm * mm, fill=1, stroke=0)
    canvas.rect((cx_mm - size_mm * 0.5) * mm, _y(cy_top_mm + size_mm * 0.14), size_mm * mm, size_mm * 0.28 * mm, fill=1, stroke=0)


def _sage_backdrop(canvas: Canvas) -> None:
    """Faint canopy blobs behind the card — only the strips above/below/
    beside the white card are ever visible, exactly as in the PDF."""
    canvas.setFillColor(C_SAGE_BG)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    canvas.setFillColor(C_SAGE_1)
    for cx, cy, r in [(PAGE_W * 0.62, PAGE_H + 4 * mm, 22 * mm), (PAGE_W * 0.85, PAGE_H - 6 * mm, 16 * mm),
                      (18 * mm, 28 * mm, 20 * mm), (PAGE_W - 22 * mm, 30 * mm, 14 * mm)]:
        canvas.circle(cx, cy, r, fill=1, stroke=0)
    canvas.setFillColor(C_SAGE_2)
    canvas.circle(PAGE_W * 0.74, PAGE_H - 20 * mm, 12 * mm, fill=1, stroke=0)


def _card(canvas: Canvas) -> None:
    canvas.setFillColor(C_SHADOW)
    canvas.roundRect(CARD_X + 0.6 * mm, CARD_BOTTOM_Y - 0.6 * mm, CARD_W, CARD_H, 2 * mm, fill=1, stroke=0)
    canvas.setFillColor(C_PAPER)
    canvas.setStrokeColor(C_LINE)
    canvas.setLineWidth(0.6)
    canvas.roundRect(CARD_X, CARD_BOTTOM_Y, CARD_W, CARD_H, 2 * mm, fill=1, stroke=1)


def _fit_line(text: str, max_chars: int) -> str:
    """The pill's two lines are single-line by construction — the box can't
    grow without breaking the stadium shape. Module titles run arbitrarily
    long where the PDF's own kicker was a short part name, so truncate
    rather than let it wrap into the card underneath."""
    text = (text or "").strip()
    return text if len(text) <= max_chars else text[: max_chars - 1].rstrip() + "…"


def _pill_header(canvas: Canvas, kicker: str, subtitle: str) -> None:
    # Plain mm floats throughout, like every sibling chrome function —
    # _y()/_draw_para() each do their own ×mm conversion, so pre-multiplying
    # here double-converts and sends the shape miles off-page (the bug that
    # made the pill invisible while its text still drew at the wrong spot).
    x, top, w, h = -6, 10, 128, 22
    canvas.setFillColor(C_PAPER)
    canvas.setStrokeColor(colors.HexColor("#C9C9C9"))
    canvas.setLineWidth(0.7)
    canvas.roundRect(x * mm, _y(top + h), w * mm, h * mm, h * mm / 2, fill=1, stroke=1)
    _draw_para(canvas, _fit_line(kicker, 50), _styles()["kicker"], 6, top + 3.4, w - 12, max_h_mm=8)
    _draw_para(canvas, _fit_line(subtitle, 58), _styles()["subtitle"], 6, top + 12.6, w - 12, max_h_mm=8)


def _sidebar_tab(canvas: Canvas, label: str) -> None:
    canvas.setFillColor(C_GREEN)
    canvas.roundRect(SIDEBAR_X, CARD_BOTTOM_Y, SIDEBAR_W, CARD_H, 1.5 * mm, fill=1, stroke=0)
    canvas.saveState()
    canvas.translate(SIDEBAR_X + SIDEBAR_W / 2, CARD_BOTTOM_Y + CARD_H / 2)
    canvas.rotate(90)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 9.5)
    canvas.drawCentredString(0, -3, label.upper())
    canvas.restoreState()


def _footer(canvas: Canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(C_LINE)
    canvas.setLineWidth(0.4)
    canvas.line(SIDEBAR_X, _y(PAGE_H / mm - 14), CARD_RIGHT, _y(PAGE_H / mm - 14))
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(C_MUTED)
    canvas.drawCentredString(PAGE_W / 2, 10 * mm, "Copyright · Tous droits réservés · IPISB")
    canvas.setFillColor(C_GREEN)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawRightString(CARD_RIGHT, 10 * mm, str(doc.page))
    canvas.restoreState()


def _logo_at(canvas: Canvas, x_mm: float, top_mm: float, size_mm: float) -> None:
    logo = _logo()
    if logo:
        canvas.drawImage(logo, x_mm * mm, _y(top_mm + size_mm), size_mm * mm, size_mm * mm,
                          preserveAspectRatio=True, mask="auto")


# ─── Zero-size flowables that stash per-chapter chrome data on the shared
# canvas — every page a chapter spans reuses the same Python canvas object
# across showPage() calls, so what's stashed here is still readable by the
# NEXT page's onPage callback without threading state through doc.build(). ──
class _ChapterMarker(Flowable):
    def __init__(self, number: int, title: str):
        super().__init__()
        self.number, self.title = number, title
        self.width = self.height = 0

    def wrap(self, aw, ah):
        return (0, 0)

    def draw(self):
        self.canv._m101_chapter_num = self.number
        self.canv._m101_chapter_title = self.title


def _chapter_ctx(canvas: Canvas) -> tuple[int, str]:
    return getattr(canvas, "_m101_chapter_num", 1), getattr(canvas, "_m101_chapter_title", "")


# ─── Page templates ─────────────────────────────────────────────────────────
def _make_cover_page(course: dict, filiere: str, annee: str):
    def on_page(canvas: Canvas, doc):
        canvas.saveState()
        canvas.setFillColor(C_PAPER)
        canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
        _dot_grid(canvas, 12, 14, 30, 24)
        _dot_grid(canvas, 12, 66, 30, 30)
        _logo_at(canvas, PAGE_W / mm - 34, 12, 20)
        _draw_para(canvas, "Institut Privé d'Innovation en Santé et Bien-être", _styles()["cover_inst"], 60, 14, 108)
        _draw_para(canvas, "El Jadida · Direction de la Recherche et Ingénierie de formation", _styles()["cover_sub"], 60, 21, 108)

        canvas.setStrokeColor(colors.HexColor("#2AB8A7"))
        canvas.setLineWidth(1.1)
        canvas.line(20 * mm, _y(46), 62 * mm, _y(46))
        _draw_para(canvas, "Secteur : SANTÉ & BIEN-ÊTRE", _styles()["cover_secteur"], 20, 52, 100)
        _draw_para(canvas, "Manuel de cours", _styles()["cover_manuel"], 20, 58.5, 100)

        # Rotated diamonds, health-cross on the last — mirrors the slide
        # cover's motif at page-appropriate scale.
        _diamond(canvas, 148, 82, 34, colors.HexColor("#1E6FBF"))
        _diamond(canvas, 168, 68, 38, colors.HexColor("#17A08C"))
        _diamond(canvas, 172, 96, 30, C_ORANGE)
        _health_cross(canvas, 172, 96, 11)

        # Band height follows the title's actual wrapped height rather than
        # a fixed guess — a one-line module title and a four-line one both
        # need to fit without either clipping text or leaving a half-empty
        # band, and course titles here are never as short as M101's own.
        code = (course.get("code") or "").strip()
        title = course.get("title") or ""
        cover_line = f"{code} : {title}" if code else title
        title_para = Paragraph(_esc(cover_line), _styles()["cover_title"])
        title_w, title_h = title_para.wrap(116 * mm, 200 * mm)
        pad_top, pad_bottom = 8 * mm, 8 * mm
        band_top_mm, band_h = 92, title_h + pad_top + pad_bottom
        canvas.setFillColor(C_TEAL_BAND)
        canvas.rect(0, _y(band_top_mm) - band_h, 128 * mm, band_h, fill=1, stroke=0)
        title_para.drawOn(canvas, 8 * mm, _y(band_top_mm) - pad_top - title_h)

        # "mm from top" increases going DOWN the page, so the band's bottom
        # edge is band_top_mm PLUS its height, not minus — a little
        # clearance is added below wherever that lands.
        after_band_mm = band_top_mm + band_h / mm + 8
        _draw_para(canvas, annee or "1ère Année", _styles()["cover_niveau"], 20, max(160, after_band_mm), 90)
        line_y = max(173, after_band_mm + 13)
        canvas.setStrokeColor(C_ORANGE)
        canvas.setLineWidth(0.9)
        canvas.line(20 * mm, _y(line_y), 74 * mm, _y(line_y))
        _draw_para(canvas, "Filière :", _styles()["cover_filiere_label"], 20, line_y - 5, 60)
        _draw_para(canvas, filiere or "—", _styles()["cover_filiere"], 20, line_y + 5, 130, max_h_mm=24)

        canvas.setFillColor(C_MUTED)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(20 * mm, 16 * mm, f"Document généré le {datetime.now().strftime('%d/%m/%Y')}")
        canvas.restoreState()

    # A near-empty Frame — BaseDocTemplate requires at least one per
    # PageTemplate, but the cover is drawn entirely by on_page above.
    frame = Frame(PAGE_W - 2 * mm, PAGE_H - 2 * mm, 1, 1, id="cover")
    return PageTemplate(id="cover", frames=[frame], onPage=on_page)


def _make_sommaire_page():
    def on_page(canvas: Canvas, doc):
        canvas.saveState()
        canvas.setFillColor(C_PAPER)
        canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
        canvas.setFillColor(C_TEAL_BAND)
        canvas.rect(0, 0, 62 * mm, PAGE_H, fill=1, stroke=0)
        canvas.setFillColor(colors.Color(1, 1, 1, alpha=0.06))
        canvas.circle(10 * mm, PAGE_H - 20 * mm, 42 * mm, fill=1, stroke=0)
        _logo_at(canvas, 14, 16, 16)
        _draw_para(canvas, "SOMMAIRE", _styles()["toc_h"], 14, 48, 46)
        canvas.restoreState()

    frame = Frame(74 * mm, 20 * mm, PAGE_W - 74 * mm - 20 * mm, PAGE_H - 55 * mm, id="sommaire", topPadding=0, leftPadding=0, rightPadding=0)
    return PageTemplate(id="sommaire", frames=[frame], onPage=on_page)


def _make_divider_page():
    def on_page(canvas: Canvas, doc):
        num, title = _chapter_ctx(canvas)
        canvas.saveState()
        canvas.setFillColor(C_PAPER)
        canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
        canvas.setFillColor(C_SKY_BG)
        canvas.rect(0, 0, 70 * mm, PAGE_H, fill=1, stroke=0)
        canvas.setFillColor(C_SKY_1)
        canvas.circle(70 * mm, PAGE_H * 0.4, 50 * mm, fill=1, stroke=0)
        _logo_at(canvas, 12, 14, 16)
        _draw_para(canvas, f"CHAPITRE {num:02d}", _styles()["eyebrow"], 78, 30, 112)
        _draw_para(canvas, title, _styles()["chap_title"], 78, 40, 112, max_h_mm=32)
        canvas.restoreState()

    frame = Frame(78 * mm, 26 * mm, PAGE_W - 78 * mm - 16 * mm, PAGE_H - 100 * mm, id="divider", topPadding=0, leftPadding=0, rightPadding=0)
    return PageTemplate(id="divider", frames=[frame], onPage=on_page)


def _make_content_page():
    def on_page(canvas: Canvas, doc):
        num, title = _chapter_ctx(canvas)
        canvas.saveState()
        _sage_backdrop(canvas)
        _pill_header(canvas, f"CHAPITRE {num:02d}", title[:70])
        _logo_at(canvas, PAGE_W / mm - 30, 12, 15)
        _card(canvas)
        _sidebar_tab(canvas, f"Chapitre {num}")
        canvas.restoreState()
        _footer(canvas, doc)

    frame = Frame(CARD_X + 4 * mm, CARD_BOTTOM_Y + 4 * mm, CARD_W - 8 * mm, CARD_H - 8 * mm,
                   id="content", topPadding=0, leftPadding=0, rightPadding=0, bottomPadding=0)
    return PageTemplate(id="content", frames=[frame], onPage=on_page)


# A professor places an image mid-chapter by leaving one of these tokens in
# the lesson text (the "Insérer ici" button in the editor writes it at the
# cursor position — see dashboard.courses.tsx). Markdown doesn't treat [[ ]]
# as anything special, so it survives the markdown→HTML pass as plain text
# inside a <p>; we split the RAW text on it before that pass instead, so it
# never has to round-trip through HTML at all.
IMAGE_TOKEN_RE = re.compile(r"\[\[image:([a-f0-9-]+)\]\]")


def _render_lesson_body(content: str, images: list[dict], styles: dict) -> list:
    """Splits the chapter's markdown on [[image:ID]] tokens and interleaves
    the referenced image at that exact point. Any image NOT referenced by a
    token (uploaded before this feature existed, or a token got deleted by
    accident) falls back to appearing after the text, so nothing silently
    disappears from the PDF."""
    images_by_id = {img["id"]: img for img in images if img.get("data")}
    used_ids: set[str] = set()
    flowables: list = []

    pieces = IMAGE_TOKEN_RE.split(content)  # [text, id, text, id, text, ...]
    for i, piece in enumerate(pieces):
        if i % 2 == 1:  # odd indices are captured image ids
            img = images_by_id.get(piece)
            if img:
                flowables += _image_flowables([img], styles)
                used_ids.add(piece)
            continue
        if not piece.strip():
            continue
        html = markdown.markdown(piece, extensions=["tables", "fenced_code"])
        tree = _TreeBuilder()
        tree.feed(html)
        flowables += _block_flowables(tree.root, styles)

    leftover = [img for img in images if img.get("id") not in used_ids]
    if leftover:
        flowables += _image_flowables(leftover, styles)
    return flowables


def _hours_line(m: dict) -> str:
    parts = []
    if m.get("hours_theory"):
        parts.append(f"{m['hours_theory']:g}h théorie")
    if m.get("hours_practice"):
        parts.append(f"{m['hours_practice']:g}h pratique")
    return " · ".join(parts)


def render_course_pdf(course: dict, modules: list[dict]) -> bytes:
    """`modules` must already be filtered to status == 'published', each with
    its `lessons` list attached (see routers/course_generation.py list_modules
    for the shape) — this function doesn't filter, it just renders every
    published chapter it's given, in order, cover to last page. A lesson may
    optionally carry `images`: [{"caption": str, "data": bytes}, ...],
    pre-downloaded by the caller (this module does no I/O)."""
    styles = _styles()
    buf = io.BytesIO()

    semester = course.get("semester") or ""
    filiere = semester.split("·")[0].strip() if semester else ""
    annee = semester.split("·")[-1].strip() if semester and "·" in semester else ""

    doc = BaseDocTemplate(
        buf, pagesize=A4,
        title=course.get("title") or "Cours", author="IPISB",
        pageTemplates=[
            _make_cover_page(course, filiere, annee),
            _make_sommaire_page(),
            _make_divider_page(),
            _make_content_page(),
        ],
    )

    # No leading PageBreak here — BaseDocTemplate already opens page 1 on
    # pageTemplates[0] ("cover"), so an immediate break would just render
    # that same template a second time before ever reaching the sommaire.
    story: list = []

    # ── Sommaire ──
    story += [NextPageTemplate("sommaire"), PageBreak()]
    for i, m in enumerate(modules, start=1):
        story.append(Paragraph(
            f'<font color="{ORANGE}"><b>{i:02d}</b></font>&nbsp;&nbsp;{_esc(m["title"])}',
            styles["toc_item"],
        ))
        story.append(Spacer(1, 3 * mm))

    # ── Chapters: a divider page, then as many content pages as the text needs ──
    for i, m in enumerate(modules, start=1):
        story += [_ChapterMarker(i, m["title"])]
        story += [NextPageTemplate("divider"), PageBreak()]
        if m.get("objectives"):
            story.append(Paragraph("Ce que vous allez apprendre dans ce chapitre :", styles["chap_lead"]))
            story.append(Spacer(1, 2 * mm))
            obj_items = [line.strip("•- ").strip() for line in (m["objectives"] or "").splitlines() if line.strip()]
            if obj_items:
                story.append(ListFlowable(
                    [ListItem(Paragraph(_esc(o), styles["objective"]), spaceAfter=1.5 * mm) for o in obj_items],
                    bulletType="bullet", leftIndent=4 * mm,
                ))
        hours = _hours_line(m)
        if hours:
            story.append(Spacer(1, 6 * mm))
            badge = Table([[Paragraph(hours, styles["hours"])]], colWidths=[52 * mm], rowHeights=[9 * mm])
            badge.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), C_GREEN),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("ROUNDEDCORNERS", [4, 4, 4, 4]),
            ]))
            story.append(badge)

        story += [NextPageTemplate("content"), PageBreak(), _ChapterMarker(i, m["title"])]
        story.append(Paragraph(_esc(m["title"]), styles["card_heading"]))

        lessons = m.get("lessons") or []
        lesson = lessons[0] if lessons else None
        content = lesson.get("content") if lesson else None
        images = (lesson or {}).get("images") or []
        if content:
            story += _render_lesson_body(content, images, styles)
        else:
            story.append(Paragraph("(Contenu non disponible pour ce chapitre.)", styles["body"]))

    doc.build(story)
    return buf.getvalue()
