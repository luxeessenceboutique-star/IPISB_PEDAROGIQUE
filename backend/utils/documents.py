import io
import secrets
from datetime import datetime, timezone
from pathlib import Path

import qrcode
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from supabase import Client

from utils import institution

DOCUMENT_LABELS = {
    "attestation_scolarite": "Certificat de Scolarité",
    "certificat": "Certificat",
    "convocation": "Convocation",
    "releve_notes": "Relevé de Notes",
}

LOGO_PATH = Path(__file__).resolve().parent.parent / "pptx_export" / "ipisb_logo.png"
_LOGO_READER: ImageReader | None = None


def _logo() -> ImageReader | None:
    global _LOGO_READER
    if _LOGO_READER is None and LOGO_PATH.exists():
        _LOGO_READER = ImageReader(str(LOGO_PATH))
    return _LOGO_READER


def new_verification_code() -> str:
    return secrets.token_hex(8)  # 16 hex chars — short enough for a URL, unguessable


def fr_date(iso: str) -> str:
    """AAAA-MM-JJ (or a full timestamptz) → JJ/MM/AAAA, blank if unparseable."""
    try:
        return datetime.strptime(iso[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return ""


def fr_year_label(year_number: int | None) -> str:
    if not year_number:
        return ""
    return f"{year_number}ère année" if year_number == 1 else f"{year_number}ème année"


def current_academic_year() -> str:
    """Morocco's school year runs Sept-June — before September, we're still
    in the year that started the previous September."""
    now = datetime.now(timezone.utc)
    start_year = now.year if now.month >= 9 else now.year - 1
    return f"{start_year}-{start_year + 1}"


def resolve_enrollment(db: Client, student_id: str) -> dict:
    """Class, filière, niveau and enrolment date, read from the student's most
    recent class. Each class carries exactly one specialty (= la filière) and
    one year number (= le niveau) — see sql/supabase_academic_extensions_
    migration.sql — so the class row is the single source of truth for all
    three, and `added_at` is when the student joined it. Shared by both
    document-generation routers (documents.py's fixed attestation/certificat/
    convocation types, document_templates.py's uploaded-template filler) so
    "which class is this student's enrolment based on" never has two answers."""
    rows = (
        db.from_("class_students")
        .select("added_at, classes(name, year_number, specialties(name))")
        .eq("student_id", student_id)
        .order("added_at", desc=True)
        .limit(1)
        .execute()
        .data or []
    )
    if not rows:
        return {"class_name": "", "filiere": "", "niveau": "", "enrollment_date": ""}

    klass = rows[0].get("classes") or {}
    specialty = klass.get("specialties") or {}
    return {
        "class_name": klass.get("name") or "",
        "filiere": specialty.get("name") or "",
        "niveau": fr_year_label(klass.get("year_number")),
        "enrollment_date": fr_date(rows[0].get("added_at") or ""),
    }


C_INK = colors.HexColor("#1C2331")
C_MUTED = colors.HexColor("#6B6976")
C_GREEN = colors.HexColor("#007842")   # same brand green as the course PDF/slide template
C_LINE = colors.HexColor("#D9D9D9")

CONTENT_LEFT, CONTENT_RIGHT = 24 * mm, 24 * mm


def _letterhead(c: canvas.Canvas, width: float, top_y: float) -> float:
    """The institution's own four-line header — one fact per line, exactly
    as given, in that order. Deliberately NOT merged onto fewer lines and
    NOT carrying the address/phone (those belong to the page footer, not
    the header — see _page_footer): this reproduces the real paper
    template's layout, not a reformatted equivalent of the same facts."""
    logo = _logo()
    logo_size = 20 * mm
    text_x = CONTENT_LEFT + (logo_size + 5 * mm if logo else 0)
    if logo:
        c.drawImage(logo, CONTENT_LEFT, top_y - logo_size, width=logo_size, height=logo_size,
                    preserveAspectRatio=True, mask="auto")

    c.setFillColor(C_INK)
    c.setFont("Helvetica-Bold", 12.5)
    c.drawString(text_x, top_y - 5 * mm, institution.NAME)
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(text_x, top_y - 10.5 * mm, f"« {institution.SHORT_NAME} » — {institution.CITY}")
    c.setFillColor(C_MUTED)
    c.setFont("Helvetica", 8.5)
    c.drawString(text_x, top_y - 15.5 * mm, institution.LEGAL_STATUS)
    c.drawString(text_x, top_y - 20 * mm, institution.AUTHORIZATION)

    rule_y = top_y - logo_size - 4 * mm
    c.setStrokeColor(C_GREEN)
    c.setLineWidth(1.1)
    c.line(CONTENT_LEFT, rule_y, width - CONTENT_RIGHT, rule_y)
    return rule_y - 12 * mm


def _page_footer(c: canvas.Canvas, width: float) -> None:
    """Address + contact line, centred at the very bottom of the page — the
    template's own footer, kept separate from the header instead of folded
    into it."""
    c.setFillColor(C_MUTED)
    c.setFont("Helvetica", 8)
    c.drawCentredString(width / 2, 16 * mm, institution.ADDRESS)
    c.drawCentredString(width / 2, 12 * mm, institution.CONTACT_LINE)


def _esc(s: str) -> str:
    """Paragraph text is parsed as mini-XML (that's how the <b> tags built
    below get their bold) — any of these characters in student-supplied
    data (a name with an ampersand, say) would otherwise break parsing or,
    worse, let arbitrary markup through since these values are interpolated
    straight into the markup string, not passed as separate arguments."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _draw_wrapped(c: canvas.Canvas, text: str, style: ParagraphStyle, x: float, top_y: float, w: float) -> float:
    """Places a Paragraph at a fixed position and returns the y just below
    it, so a run of paragraphs can be laid out top-to-bottom without
    switching this canvas-based document over to full platypus flow."""
    p = Paragraph(text, style)
    _, h = p.wrap(w, top_y)
    p.drawOn(c, x, top_y - h)
    return top_y - h


def _field_line(c: canvas.Canvas, label: str, value: str, x: float, y: float, *,
                value_x: float | None = None) -> None:
    """One "Label : valeur" row. No dotted fill-in rule when a value is
    missing — the real template just leaves the space after the colon
    empty, so an unfilled fiche prints exactly that: nothing invented."""
    c.setFillColor(C_INK)
    c.setFont("Helvetica", 10.5)
    c.drawString(x, y, label)
    if value:
        label_w = stringWidth(label, "Helvetica", 10.5)
        c.setFont("Helvetica-Bold", 10.5)
        c.drawString(value_x if value_x is not None else x + label_w + 2, y, value)


def _certificat_scolarite_body(c: canvas.Canvas, x: float, y: float, right: float, *,
                                student_name: str, date_naissance: str, enrollment_date: str,
                                matricule: str, class_name: str, filiere: str, niveau: str) -> float:
    """Reproduces the institution's own certificat de scolarité letter,
    field for field and in the order given — this is fixed content, not a
    paraphrase, so nothing here should be reworded or reordered without the
    institution supplying a revised template."""
    c.setFillColor(C_INK)
    c.setFont("Helvetica", 11)
    c.drawString(x, y, f"Je soussignée, {institution.DIRECTOR_CIVILITY} {institution.DIRECTOR_NAME}, "
                       f"{institution.DIRECTOR_TITLE} « {institution.SHORT_NAME} » {institution.CITY},")
    y -= 8 * mm

    _field_line(c, "Certifie que :", student_name, x, y)
    y -= 8 * mm
    _field_line(c, "Né(e) le :", date_naissance, x, y)
    y -= 8 * mm
    # Same line, two fields — matches the template's own layout (one row,
    # generous gap between the two label:value pairs).
    _field_line(c, "A été inscrit(e) le :", enrollment_date, x, y)
    _field_line(c, "Sous N° :", matricule, x + 85 * mm, y)
    y -= 8 * mm
    _field_line(c, "A poursuivi sa formation en classe :", class_name, x, y)
    y -= 8 * mm
    _field_line(c, "Filière de formation :", filiere, x, y)
    y -= 8 * mm
    _field_line(c, "Niveau de formation :", niveau, x, y)
    y -= 12 * mm

    c.setFont("Helvetica", 11)
    y = _draw_wrapped(
        c, "La présente attestation est délivrée à l'intéressé(e) pour servir et valoir ce que de droit.",
        ParagraphStyle("body", fontName="Helvetica", fontSize=11, textColor=C_INK, leading=16),
        x, y, right - x,
    )
    return y


def render_document_pdf(
    *,
    doc_type: str,
    student_name: str,
    verification_code: str,
    verify_url: str,
    filiere: str = "",
    niveau: str = "",
    date_naissance: str = "",
    enrollment_date: str = "",
    matricule: str = "",
    class_name: str = "",
) -> bytes:
    """Render a one-page official document. For attestation_scolarite this
    reproduces the institution's own certificat de scolarité letter exactly
    — same four-line header, same signatory clause, same field order, same
    closing and footer — with only the per-student blanks filled in from
    the fiche administrative and the student's current class assignment;
    a field with no data on file prints blank rather than inventing a
    value. certificat/convocation (no fixed wording supplied for either)
    keep the same letterhead/footer chrome with a plain identity line.

    A QR code linking to the public /verify/{code} authenticity page is
    added in the bottom-left corner — a platform feature, not part of the
    institution's own letter, kept visually separate from it."""
    label = DOCUMENT_LABELS.get(doc_type, doc_type.replace("_", " ").title())
    issued_at = datetime.now(timezone.utc).strftime("%d/%m/%Y")

    qr_img = qrcode.make(verify_url)
    qr_buf = io.BytesIO()
    qr_img.save(qr_buf, format="PNG")
    qr_buf.seek(0)

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    y = _letterhead(c, width, height - 18 * mm)

    c.setFillColor(C_GREEN)
    c.setFont("Helvetica-Bold", 17)
    c.drawCentredString(width / 2, y, label.upper())
    y -= 14 * mm

    content_w = width - CONTENT_LEFT - CONTENT_RIGHT
    if doc_type == "attestation_scolarite":
        y = _certificat_scolarite_body(
            c, CONTENT_LEFT, y, width - CONTENT_RIGHT,
            student_name=student_name, date_naissance=date_naissance, enrollment_date=enrollment_date,
            matricule=matricule, class_name=class_name, filiere=filiere, niveau=niveau,
        )
    else:
        # certificat/convocation: no specific-purpose fields exist in the
        # generation form yet (a convocation needs a date/heure/lieu/motif
        # nobody enters today) — same letterhead/footer chrome, a plain
        # identity line rather than fabricated legal wording.
        body_style = ParagraphStyle("body", fontName="Helvetica", fontSize=11, textColor=C_INK, leading=16.5)
        y = _draw_wrapped(c, f"Concerne : <b>{_esc(student_name)}</b>.", body_style, CONTENT_LEFT, y, content_w)

    y -= 14 * mm
    c.setFillColor(C_INK)
    c.setFont("Helvetica", 10.5)
    c.drawString(CONTENT_LEFT, y, f"Fait à {institution.CITY}, le {issued_at}")
    y -= 8 * mm
    c.drawString(CONTENT_LEFT, y, f"La {institution.DIRECTOR_TITLE}")

    qr_size = 20 * mm
    qr_x, qr_y = CONTENT_LEFT, 28 * mm
    c.drawImage(ImageReader(qr_buf), qr_x, qr_y, width=qr_size, height=qr_size)
    c.setFillColor(C_MUTED)
    c.setFont("Helvetica", 6.5)
    c.drawString(qr_x, qr_y - 5 * mm, f"Vérification : {verify_url}")
    c.drawString(qr_x, qr_y - 9 * mm, f"Code : {verification_code}")

    _page_footer(c, width)

    c.showPage()
    c.save()
    return buf.getvalue()
