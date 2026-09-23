import io
import os
from datetime import datetime, timedelta, timezone
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors as rl_colors
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
from reportlab.lib.utils import ImageReader
from utils.dt import parse_iso_dt

CONFORMITY_LABELS = {
    "frais": "Produit frais",
    "congele": "Produit congelé",
    "scelle": "Emballage scellé / fermé",
    "peremption": "Date de péremption valide",
    "certificat": "Certificat / norme de conformité",
    "qhse": "Contrôle QHSE effectué",
}

PAY_MODE_LABELS = {
    "ov_permanent": "OV permanent",
    "ov_ponctuel": "OV ponctuel",
    "cheque": "Chèque",
    "caisse_sociale": "Caisse sociale",
}

# Coordonnées de l'établissement émetteur (éditez librement).
# Les lignes vides ne sont pas rendues.
COMPANY = {
    "name": "IPISB",
    "subtitle": "Institut Privé d'Innovation en Santé et Bien-être",
    "mention": "Établissement de Formation Professionnelle Privé",
    "ofppt": "Autorisé par l'OFPPT sous N° 3/02/3/2024",
    "address": "24, 3ème étage, Lotissement Ennajd, El Jadida, Maroc",
    "phone": "00 212 6 32 82 28 98",
    "email": "ipisbj.infirmiers@gmail.com",
    "website": "www.ipisb.com",
    "rc": "22325 à El Jadida",
    "if": "66003179",
    "ice": "003540784000092",
    "rib": "007 170 0006433000000500 27",
}

# Logo de l'établissement — déposez le fichier ici : backend/assets/logo.png
# S'il est absent, les en-têtes basculent sur un repli textuel/placeholder.
_LOGO_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "logo.png"
)
_LOGO_CACHE: dict = {}


def _get_logo():
    """ImageReader du logo IPISB (mis en cache), ou None si absent/illisible."""
    if "img" not in _LOGO_CACHE:
        try:
            _LOGO_CACHE["img"] = ImageReader(_LOGO_PATH) if os.path.exists(_LOGO_PATH) else None
        except Exception:
            _LOGO_CACHE["img"] = None
    return _LOGO_CACHE["img"]


def _draw_logo(c, x_mm: float, top_y_pts: float, max_w_mm: float, max_h_mm: float,
               align: str = "left") -> bool:
    """Dessine le logo dans une boîte (largeur/hauteur max en mm) en conservant le
    ratio. `x_mm` = bord gauche (align='left') ou bord droit (align='right') ;
    `top_y_pts` = bord haut en points. Retourne False si aucun logo n'est disponible."""
    img = _get_logo()
    if img is None:
        return False
    iw, ih = img.getSize()
    ratio = min((max_w_mm * mm) / iw, (max_h_mm * mm) / ih)
    w, h = iw * ratio, ih * ratio
    x = x_mm * mm - (w if align == "right" else 0)
    c.drawImage(img, x, top_y_pts - h, width=w, height=h, mask="auto", preserveAspectRatio=True)
    return True


def _legal_line() -> str:
    """Ligne compacte des identifiants légaux (RC · IF · ICE)."""
    parts = []
    if COMPANY.get("rc"):
        parts.append(f"RC : {COMPANY['rc']}")
    if COMPANY.get("if"):
        parts.append(f"IF : {COMPANY['if']}")
    if COMPANY.get("ice"):
        parts.append(f"ICE : {COMPANY['ice']}")
    return "   ·   ".join(parts)

# Palette (RGB 0..1)
_TEAL = (0.0, 0.62, 0.71)
_ORANGE = (0.95, 0.62, 0.13)
_INK = (0.13, 0.13, 0.13)
_MUTED = (0.42, 0.42, 0.42)
_LIGHT = (0.949, 0.949, 0.949)


def _draw_conformity(c, pr: dict, y: float, x_mm: float = 20) -> float:
    """Dessine le bloc « Conformité » (texte libre + critères) et retourne le nouveau y."""
    conf_note = (pr.get("conformity_note") or "").strip()
    conf_crit = pr.get("conformity_criteria") or []
    if not (conf_note or conf_crit):
        return y
    y -= 12 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x_mm * mm, y, "Conformité :")
    c.setFont("Helvetica", 9)
    if conf_note:
        for line in [conf_note[i:i+80] for i in range(0, len(conf_note), 80)][:2]:
            y -= 5 * mm
            c.drawString(x_mm * mm, y, line)
    if conf_crit:
        crit_text = ", ".join(CONFORMITY_LABELS.get(k, k) for k in conf_crit)
        for line in [crit_text[i:i+80] for i in range(0, len(crit_text), 80)][:3]:
            y -= 5 * mm
            c.drawString(x_mm * mm, y, line)
    return y


def fmt_mad(value) -> str:
    try:
        val = float(value or 0)
        return f"{val:,.2f} MAD".replace(",", " ").replace(".", ",")
    except Exception:
        return "0,00 MAD"

def draw_header(c, title: str):
    width, height = A4
    # Logo à gauche (si présent) ; le bloc texte se décale à sa droite.
    has_logo = _draw_logo(c, 20, height - 10 * mm, 22, 24)
    tx = 46 if has_logo else 20

    c.setFillColorRGB(*_INK)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(tx * mm, height - 20 * mm, "IPISB")
    c.setFillColorRGB(*_MUTED)
    c.setFont("Helvetica", 8.5)
    c.drawString(tx * mm, height - 25 * mm, COMPANY["subtitle"])
    c.drawString(tx * mm, height - 29 * mm, COMPANY["address"])

    c.setFillColorRGB(*_INK)
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(width - 20 * mm, height - 20 * mm, title)

    # Horizontal line
    c.setLineWidth(0.5)
    c.setStrokeColorRGB(0.7, 0.7, 0.7)
    c.line(20 * mm, height - 40 * mm, width - 20 * mm, height - 40 * mm)

def draw_footer(c, page_num: int = 1):
    width, height = A4
    c.setLineWidth(0.5)
    c.setStrokeColorRGB(0.7, 0.7, 0.7)
    c.line(20 * mm, 20 * mm, width - 20 * mm, 20 * mm)
    # Identifiants légaux de l'établissement (centrés).
    c.setFillColorRGB(*_MUTED)
    c.setFont("Helvetica", 7)
    legal = _legal_line()
    if legal:
        c.drawCentredString(width / 2, 15.5 * mm, legal)
    if COMPANY.get("rib"):
        c.drawCentredString(width / 2, 12 * mm, f"RIB : {COMPANY['rib']}")
    c.setFont("Helvetica-Oblique", 7)
    c.drawString(20 * mm, 8 * mm, f"Document généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}")
    c.drawRightString(width - 20 * mm, 8 * mm, f"Page {page_num}")
    c.setFillColorRGB(*_INK)

def _wrap(text: str, width: int, limit: int) -> list[str]:
    text = (text or "").strip()
    return [text[i:i + width] for i in range(0, len(text), width)][:limit] if text else []


def render_purchase_order_pdf(purchase: dict, supplier: dict, pr: dict | None = None, quote: dict | None = None, installments: list | None = None) -> bytes:
    """Bon de commande — toutes les informations proviennent de l'expression de
    besoin (DA) liée ; les montants proviennent du devis retenu (purchase)."""
    pr = pr or {}
    supplier = supplier or {}
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    def L(x, y, s, font="Helvetica", size=9, color=_INK):
        c.setFont(font, size); c.setFillColorRGB(*color); c.drawString(x * mm, y, str(s) if s is not None else "")

    def R(x, y, s, font="Helvetica", size=9, color=_INK):
        c.setFont(font, size); c.setFillColorRGB(*color); c.drawRightString(x * mm, y, str(s) if s is not None else "")

    # ── En-tête : titre + logo + filet teal ──
    c.setFillColorRGB(*_TEAL); c.setFont("Helvetica-Bold", 30)
    c.drawString(20 * mm, height - 28 * mm, "Bon de commande")
    # Logo réel à droite (repli : pastille orange « Logo » si le fichier est absent).
    if not _draw_logo(c, width / mm - 20, height - 6 * mm, 28, 30, align="right"):
        c.setFillColorRGB(*_ORANGE); c.circle(width - 32 * mm, height - 24 * mm, 11 * mm, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1); c.setFont("Helvetica", 10)
        c.drawCentredString(width - 32 * mm, height - 25.5 * mm, "Logo")
    c.setStrokeColorRGB(*_TEAL); c.setLineWidth(2)
    c.line(20 * mm, height - 38 * mm, width - 20 * mm, height - 38 * mm)

    # ── Émetteur (société de la DA / IPISB) ──
    y = height - 50 * mm
    L(20, y, pr.get("company") or COMPANY["name"], "Helvetica-Bold", 11)
    for line in [COMPANY.get("subtitle"), COMPANY.get("address"),
                 f"Service : {pr['service']}" if pr.get("service") else None,
                 f"Demandeur : {pr['requester_name']}" if pr.get("requester_name") else None]:
        if line:
            y -= 4.6 * mm; L(20, y, line, "Helvetica-Oblique", 8.5, _MUTED)

    # ── Destinataire (fournisseur retenu) ──
    yd = height - 66 * mm
    L(120, yd, "Destinataire", "Helvetica", 9, _MUTED)
    yd -= 5.5 * mm; L(120, yd, supplier.get("company_name") or "—", "Helvetica-Bold", 10.5)
    for line in [supplier.get("contact_person"), supplier.get("address"),
                 supplier.get("phone"), supplier.get("email"),
                 f"ICE : {supplier['tax_number']}" if supplier.get("tax_number") else None]:
        if line:
            yd -= 4.6 * mm; L(120, yd, line, "Helvetica-Oblique", 8.5, _MUTED)

    # ── Encadré gris : métadonnées (issues de la DA) ──
    rows = [
        ("Date", purchase.get("purchase_date") or "—"),
        ("Bon de commande N°", purchase.get("purchase_number") or "—"),
        ("N° demande (DA)", pr.get("request_number") or "—"),
        ("N° devis", (quote or {}).get("quote_number") or "—"),
    ]
    box_top = height - 96 * mm
    row_h = 6 * mm
    box_h = row_h * len(rows) + 6 * mm
    c.setFillColorRGB(*_LIGHT); c.rect(20 * mm, box_top - box_h, 90 * mm, box_h, fill=1, stroke=0)
    ry = box_top - 6 * mm
    for label, val in rows:
        L(24, ry, f"{label} :", "Helvetica", 8.5, _MUTED)
        L(63, ry, val, "Helvetica-Bold", 8.5, _INK)
        ry -= row_h

    # ── Tableau produit ──
    # Colonnes (mm) : Réf | Description | Qté | Unité | PU HT | %TVA | Total TVA | Total TTC(droite)
    CX = {"ref": 20, "desc": 42, "qte": 92, "unite": 106, "pu": 120, "tva": 143, "ttva": 156, "ttc": 190}
    ty = box_top - box_h - 18 * mm
    L(CX["ref"], ty, "Réf. produit", "Helvetica-Bold", 8, _INK)
    L(CX["desc"], ty, "Description", "Helvetica-Bold", 8, _INK)
    L(CX["qte"], ty, "Quantité", "Helvetica-Bold", 8, _INK)
    L(CX["unite"], ty, "Unité", "Helvetica-Bold", 8, _INK)
    L(CX["pu"], ty, "Prix unit. HT", "Helvetica-Bold", 8, _INK)
    L(CX["tva"], ty, "% TVA", "Helvetica-Bold", 8, _INK)
    L(CX["ttva"], ty, "Total TVA", "Helvetica-Bold", 8, _INK)
    R(CX["ttc"], ty, "Total TTC", "Helvetica-Bold", 8, _INK)
    c.setStrokeColorRGB(0.8, 0.8, 0.8); c.setLineWidth(0.5)
    c.line(20 * mm, ty - 2 * mm, width - 20 * mm, ty - 2 * mm)

    # Montants : total depuis le devis retenu ; quantité depuis la DA.
    qty = float(pr.get("quantity") or purchase.get("quantity") or 1) or 1
    total_ht = float(purchase.get("unit_price") or 0) * float(purchase.get("quantity") or 1)
    if total_ht == 0:
        total_ht = float(purchase.get("total_incl_vat") or 0)
    unit_ht = total_ht / qty if qty else total_ht
    vat_percent = float(purchase.get("vat_percent") or 0)
    total_tva = total_ht * vat_percent / 100
    total_ttc = float(purchase.get("total_incl_vat") or (total_ht + total_tva))

    ty -= 8 * mm
    desc = (pr.get("justification") or purchase.get("title") or "—")
    desc = desc[:38] + "…" if len(desc) > 39 else desc
    L(CX["ref"], ty, pr.get("article_code") or "—", "Helvetica", 8, _INK)
    L(CX["desc"], ty, desc, "Helvetica", 8, _INK)
    L(CX["qte"], ty, f"{qty:g}", "Helvetica", 8, _INK)
    L(CX["unite"], ty, "u", "Helvetica", 8, _INK)
    L(CX["pu"], ty, fmt_mad(unit_ht), "Helvetica", 8, _INK)
    L(CX["tva"], ty, f"{vat_percent:g} %", "Helvetica", 8, _INK)
    L(CX["ttva"], ty, fmt_mad(total_tva), "Helvetica", 8, _INK)
    R(CX["ttc"], ty, fmt_mad(total_ttc), "Helvetica", 8, _INK)

    fy = 42 * mm  # y du filet de pied de page — défini tôt, utilisé aussi par l'échéancier/la signature ci-dessous.

    # ── Totaux (colonne droite) — Total HT, Livraison, Total TVA, Total TTC :
    # la livraison vient juste après le HT dont elle fait partie (base avant
    # application de la TVA), avant TVA/TTC. ──
    # Colonne de 40 mm (150→190) : « Total TTC » en 10 pt gras touchait sa
    # valeur (label + montant ne tiennent pas côte à côte à cette taille) —
    # ramené à 9 pt comme les autres lignes, qui laisse une marge suffisante.
    totals_top = ty - 7 * mm  # rapproché du tableau produit (était 12 mm, jugé trop éloigné)
    ty = totals_top
    L(150, ty, "Total HT", "Helvetica", 9, _MUTED); R(190, ty, fmt_mad(total_ht), "Helvetica-Bold", 9, _INK)

    # ── Livraison (issue du devis retenu) ──
    # Le qualificatif « (en sus)/(incluse) » accolé au montant pouvait dépasser
    # la largeur de colonne et se superposer au label « Livraison » — affiché
    # sur sa propre ligne, plus petit, plutôt qu'accolé au montant.
    if quote and quote.get("delivery_required"):
        raw_cost = quote.get("delivery_cost")
        included = bool(quote.get("delivery_included"))
        qualifier = "incluse" if included else "en sus"
        if raw_cost is None:  # coût inconnu / à préciser
            d_txt = "À préciser"; d_col = _INK
        else:
            d_cost = float(raw_cost)
            if d_cost <= 0:  # gratuite
                d_txt = "Gratuite"; d_col = (0.0, 0.55, 0.30); qualifier = None
            else:
                d_txt = fmt_mad(d_cost); d_col = _INK  # fmt_mad() ajoute déjà « MAD »
        ty -= 6 * mm
        L(150, ty, "Livraison", "Helvetica", 9, _MUTED)
        R(190, ty, d_txt, "Helvetica-Bold", 9, d_col)
        if qualifier:
            ty -= 3.6 * mm
            R(190, ty, f"({qualifier})", "Helvetica-Oblique", 7.5, _MUTED)

    ty -= 6 * mm
    L(150, ty, "Total TVA", "Helvetica", 9, _MUTED); R(190, ty, fmt_mad(total_tva), "Helvetica-Bold", 9, _INK)
    ty -= 7 * mm
    L(150, ty, "Total TTC", "Helvetica-Bold", 9, _TEAL); R(190, ty, fmt_mad(total_ttc), "Helvetica-Bold", 9, _TEAL)
    right_bottom = ty

    # ── Échéancier de paiement prévisionnel (colonne gauche) ──
    # Un pas de ligne fixe (confortable, jamais compressé jusqu'à l'illisible)
    # — s'il n'y a pas la place pour toutes les échéances au-dessus de
    # `safe_bottom`, l'échéancier bascule intégralement en page 2 plutôt que
    # de chevaucher la signature/le pied de page.
    _PAY_LABEL = {
        "ov_permanent": "OV permanent", "ov_ponctuel": "OV ponctuel", "cheque": "Chèque",
        "caisse_sociale": "Caisse comptable",
    }
    ROW_STEP = 4.6 * mm
    HEADER_MM = 5.5 + 1.5 + 4.2   # titre + en-têtes de colonnes + filet
    TAIL_MM = 4.8                  # ligne « Total planifié » + marge
    safe_bottom = fy + 14 * mm      # marge au-dessus du filet de pied de page

    def _draw_installments(top_y, rows, right_x=140):
        """Dessine le tableau Échéancier à partir de `top_y`. `right_x` est
        la limite droite de la colonne Montant — 140 mm sur la page 1 (garde
        une marge avec la colonne Totaux qui commence à 150 mm), 190 mm sur
        une page 2 dédiée (pleine largeur). Retourne le y juste sous la
        dernière ligne (pour y placer la signature)."""
        ey = top_y
        L(20, ey, "Échéancier de paiement", "Helvetica-Bold", 9.5, _INK)
        ey -= 5.5 * mm
        L(20, ey, "Échéance", "Helvetica-Bold", 7, _MUTED)
        L(66, ey, "Règlement", "Helvetica-Bold", 7, _MUTED)
        L(100, ey, "Date", "Helvetica-Bold", 7, _MUTED)
        R(right_x, ey, "Montant", "Helvetica-Bold", 7, _MUTED)
        ey -= 1.5 * mm
        c.setStrokeColorRGB(0.85, 0.85, 0.85); c.setLineWidth(0.4)
        c.line(20 * mm, ey, right_x * mm, ey)
        ey -= 4.2 * mm
        planned = 0.0
        for it in rows:
            amt = float(it.get("amount") or 0); planned += amt
            label = (it.get("label") or "—")[:26]
            mode = _PAY_LABEL.get(it.get("payment_mode"), it.get("payment_mode") or "—")
            raw = it.get("due_date")
            due = "—"
            if raw:
                # Année sur 2 chiffres : laisse assez de place avant la colonne Montant.
                parts = str(raw)[:10].split("-")
                due = f"{parts[2]}/{parts[1]}/{parts[0][2:]}" if len(parts) == 3 else str(raw)[:10]
            L(20, ey, label, "Helvetica", 7.5, _INK)
            L(66, ey, mode[:24], "Helvetica", 7, _MUTED)
            L(100, ey, due, "Helvetica", 7.5, _MUTED)
            R(right_x, ey, fmt_mad(amt), "Helvetica", 7.5, _INK)
            ey -= ROW_STEP
        c.setStrokeColorRGB(0.85, 0.85, 0.85); c.setLineWidth(0.4)
        c.line(20 * mm, ey + 2.2 * mm, right_x * mm, ey + 2.2 * mm)
        L(20, ey, "Total planifié", "Helvetica-Bold", 8, _INK)
        R(right_x, ey, fmt_mad(planned), "Helvetica-Bold", 8, _INK)
        ey -= TAIL_MM * mm
        return ey

    left_bottom = totals_top
    overflow_to_p2 = False
    if installments:
        needed_mm = HEADER_MM + TAIL_MM + (ROW_STEP / mm) * len(installments)
        if (totals_top - safe_bottom) / mm >= needed_mm:
            # Calé en bas de la zone disponible (juste au-dessus de la
            # signature/du pied de page) plutôt qu'en haut, juste après le
            # tableau produit — l'espace libre reste en haut, pas en bas.
            top_y = safe_bottom + needed_mm * mm
            left_bottom = _draw_installments(top_y, installments)
        else:
            overflow_to_p2 = True
            L(20, totals_top, "Échéancier de paiement", "Helvetica-Bold", 9.5, _INK)
            L(20, totals_top - 5.5 * mm, "→ Détail en page suivante.", "Helvetica-Oblique", 8.5, _MUTED)

    # ── Signature (page 1, sauf si l'échéancier a basculé en page 2 — elle y
    # est alors redessinée sous l'échéancier complet). ──
    if not overflow_to_p2:
        L(145, max(min(right_bottom, left_bottom) - 10 * mm, safe_bottom), "Signature :", "Helvetica", 9, _INK)

    # ── Pied de page : 3 colonnes ──
    def _draw_footer():
        c.setStrokeColorRGB(0.8, 0.8, 0.8); c.setLineWidth(0.5)
        c.line(20 * mm, fy + 4 * mm, width - 20 * mm, fy + 4 * mm)

        def _footer_col(x, title, lines):
            yy = fy
            L(x, yy, title, "Helvetica-Bold", 7.5, _INK)
            for ln in lines:
                if ln:
                    yy -= 3.8 * mm; L(x, yy, ln, "Helvetica", 7.5, _MUTED)

        _footer_col(20, "IPISB — Identifiants",
                    [COMPANY.get("address"),
                     f"RC : {COMPANY['rc']}" if COMPANY.get("rc") else None,
                     f"IF : {COMPANY['if']}" if COMPANY.get("if") else None,
                     f"ICE : {COMPANY['ice']}" if COMPANY.get("ice") else None,
                     f"RIB : {COMPANY['rib']}" if COMPANY.get("rib") else None])
        _footer_col(105, "Détails bancaires (fournisseur)",
                    [supplier.get("bank"), supplier.get("bank_branch"),
                     f"RIB : {supplier['rib']}" if supplier.get("rib") else None])

    _draw_footer()

    if overflow_to_p2:
        c.showPage()
        c.setFillColorRGB(*_TEAL); c.setFont("Helvetica-Bold", 13)
        c.drawString(20 * mm, height - 20 * mm,
                     f"Bon de commande {purchase.get('purchase_number') or ''} — Échéancier (suite)")
        c.setStrokeColorRGB(*_TEAL); c.setLineWidth(1.2)
        c.line(20 * mm, height - 24 * mm, width - 20 * mm, height - 24 * mm)
        p2_bottom = _draw_installments(height - 35 * mm, installments, right_x=190)
        L(145, p2_bottom - 10 * mm, "Signature :", "Helvetica", 9, _INK)
        _draw_footer()

    c.showPage()
    c.save()
    return buf.getvalue()

def render_purchase_request_pdf(pr: dict, quotes: list, installments: list | None = None) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    
    draw_header(c, "DEMANDE D'ACHAT")
    
    # Request Info
    c.setFont("Helvetica-Bold", 10)
    c.drawString(20 * mm, height - 50 * mm, "Informations de la demande :")
    c.setFont("Helvetica", 9)
    c.drawString(20 * mm, height - 56 * mm, f"N° DA : {pr.get('request_number', 'N/A')}")
    c.drawString(20 * mm, height - 61 * mm, f"Statut : {pr.get('status', 'N/A').replace('_', ' ').upper()}")
    c.drawString(20 * mm, height - 66 * mm, f"Demandeur : {pr.get('requester_name', 'N/A') or '—'}")
    c.drawString(20 * mm, height - 71 * mm, f"Service : {pr.get('service', 'N/A') or '—'}")

    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(width - 20 * mm, height - 50 * mm, "Détail Budget :")
    c.setFont("Helvetica", 9)
    c.drawRightString(width - 20 * mm, height - 56 * mm, f"Type : {pr.get('request_type', 'N/A').replace('_', ' ').title()}")
    c.drawRightString(width - 20 * mm, height - 61 * mm, f"Catégorie : {pr.get('asset_category', 'N/A').title()}")
    c.drawRightString(width - 20 * mm, height - 66 * mm, f"Est. Budgétaire : {fmt_mad(pr.get('budget_estimate', 0))}")

    # Justification
    y = height - 85 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(20 * mm, y, "Justification du besoin :")
    c.setFont("Helvetica", 9)
    just = pr.get("justification", "—")
    # Wrap text simple
    lines = [just[i:i+80] for i in range(0, len(just), 80)]
    for line in lines[:3]:
        y -= 5 * mm
        c.drawString(20 * mm, y, line)

    # Conformité (texte libre + critères standard)
    y = _draw_conformity(c, pr, y)

    # Devis comparatifs
    y -= 12 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(20 * mm, y, "Synthèse des devis comparatifs :")
    
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(20 * mm, y, "Rang")
    c.drawString(35 * mm, y, "Fournisseur")
    c.drawString(95 * mm, y, "N° Devis")
    c.drawString(135 * mm, y, "Montant")
    c.drawRightString(width - 20 * mm, y, "Retenu ?")
    
    c.setLineWidth(0.5)
    c.line(20 * mm, y - 2 * mm, width - 20 * mm, y - 2 * mm)
    
    c.setFont("Helvetica", 9)
    for q_item in quotes[:5]:
        y -= 7 * mm
        c.drawString(20 * mm, y, f"Devis {q_item.get('rank', 1)}")
        c.drawString(35 * mm, y, q_item.get("supplier_name", "—") or "—")
        c.drawString(95 * mm, y, q_item.get("quote_number", "—"))
        c.drawString(135 * mm, y, fmt_mad(q_item.get("amount", 0)))
        c.drawRightString(width - 20 * mm, y, "OUI" if q_item.get("retenu") else "Non")

    # Décisions
    y -= 20 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(20 * mm, y, "Décision Expression de besoin :")
    c.setFont("Helvetica", 9)
    dec = pr.get("need_decision", "En attente")
    comment = pr.get("need_decision_comment", "")
    c.drawString(20 * mm, y - 6 * mm, f"Décision : {dec.upper()} {f'({comment})' if comment else ''}")

    # ── Mode & échéancier de paiement prévisionnel (rattaché à la DA) ──
    # Tous les modes de règlement (dont Caisse comptable) sont rattachés au
    # journal comptable — plus de distinction « caisse sociale/comptable ».
    if installments:
        _PAY_LABEL = {
            "ov_permanent": "OV permanent", "ov_ponctuel": "OV ponctuel", "cheque": "Chèque",
            "caisse_sociale": "Caisse comptable",
        }
        y -= 20 * mm
        c.setFont("Helvetica-Bold", 10)
        c.drawString(20 * mm, y, "Mode & échéancier de paiement (prévisionnel) :")
        y -= 8 * mm
        # Colonnes alignées sur le tableau à l'écran : Jalon | Règlement | Date prévue | Montant
        c.setFont("Helvetica-Bold", 9)
        c.drawString(20 * mm, y, "Jalon")
        c.drawString(70 * mm, y, "Règlement")
        c.drawString(120 * mm, y, "Date prévue")
        c.drawRightString(width - 20 * mm, y, "Montant")
        c.setLineWidth(0.5)
        c.line(20 * mm, y - 2 * mm, width - 20 * mm, y - 2 * mm)
        c.setFont("Helvetica", 9)
        planned = 0.0
        for it in installments:
            amt = float(it.get("amount") or 0); planned += amt
            label = (it.get("label") or "—")[:28]
            mode = _PAY_LABEL.get(it.get("payment_mode"), it.get("payment_mode") or "—")
            raw = it.get("due_date")
            due = "—"
            if raw:
                parts = str(raw)[:10].split("-")
                due = f"{parts[2]}/{parts[1]}/{parts[0]}" if len(parts) == 3 else str(raw)[:10]
            y -= 7 * mm
            c.drawString(20 * mm, y, label)
            c.drawString(70 * mm, y, mode[:24])
            c.drawString(120 * mm, y, due)
            c.drawRightString(width - 20 * mm, y, fmt_mad(amt))
        y -= 3 * mm
        c.setLineWidth(0.5)
        c.line(20 * mm, y, width - 20 * mm, y)
        y -= 6 * mm
        c.setFont("Helvetica-Bold", 9)
        c.drawString(20 * mm, y, "Total planifié :")
        c.drawRightString(width - 20 * mm, y, fmt_mad(planned))
        y -= 6 * mm
        c.setFont("Helvetica", 8.5)
        retenu = next((q for q in quotes if q.get("retenu")), None)
        if retenu:
            y -= 5 * mm
            devis_total = float(retenu.get("amount") or 0)
            c.drawString(20 * mm, y, f"Devis retenu : {fmt_mad(devis_total)}")
            ecart = planned - devis_total
            if abs(ecart) >= 0.01:
                sign = "+" if ecart > 0 else "-"
                c.drawRightString(width - 20 * mm, y, f"Écart : {sign}{fmt_mad(abs(ecart))}")

    draw_footer(c)
    c.showPage()
    c.save()
    return buf.getvalue()

def render_accounting_report_pdf(summary: dict) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    
    draw_header(c, "SYNTHÈSE COMPTABLE & FINANCIÈRE")
    
    y = height - 55 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(20 * mm, y, "Indicateurs Clés (KPIs)")
    
    y -= 10 * mm
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y, "Trésorerie nette :")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(65 * mm, y, fmt_mad(summary.get("net_treasury", 0)))
    
    y -= 8 * mm
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y, "Recettes encaissées :")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(65 * mm, y, fmt_mad(summary.get("total_revenues_received", 0)))
    
    y -= 8 * mm
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y, "Total sorties (Achats + Dépenses) :")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(65 * mm, y, fmt_mad(summary.get("total_outflow", 0)))
    
    y -= 8 * mm
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y, "Factures clients impayées :")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(65 * mm, y, fmt_mad(summary.get("unpaid_invoices", 0)))

    # Outflow by category
    y -= 18 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(20 * mm, y, "Répartition des Sorties par Catégorie")
    
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(20 * mm, y, "Catégorie")
    c.drawRightString(width - 20 * mm, y, "Montant")
    c.setLineWidth(0.5)
    c.line(20 * mm, y - 2 * mm, width - 20 * mm, y - 2 * mm)
    
    c.setFont("Helvetica", 9)
    for cat in (summary.get("expenses_by_category") or [])[:8]:
        y -= 6 * mm
        c.drawString(20 * mm, y, cat.get("name", "—"))
        c.drawRightString(width - 20 * mm, y, fmt_mad(cat.get("value", 0)))

    draw_footer(c)
    c.showPage()
    c.save()
    return buf.getvalue()


DAY_NAMES_FR = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi"]


def _fmt_hm(value: str) -> str:
    """Postgres 'time' comes back as 'HH:MM:SS' (or 'HH:MM') — render French-style ('10h' or '10h30')."""
    h, m = value.split(":")[0], value.split(":")[1]
    return f"{int(h)}h{m if m != '00' else ''}"


def render_timetable_pdf(timetable: dict, slots: list[dict], class_name: str) -> bytes:
    """Renders the official weekly 'Emploi du temps' matching the institute's signed template:
    letterhead + Filière/Année/Semaine header, a Jours×Horaire×Séquence×Formateurs×Salle grid
    (day cells merged across their slots, gray '-' for empty slots, yellow highlight for
    'Contrôle continue' exam slots), and a directrice signature footer."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    week_start = datetime.fromisoformat(str(timetable["week_start"])).date()
    week_end = datetime.fromisoformat(str(timetable["week_end"])).date()

    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(width / 2, height - 20 * mm, "Institut Privé d'Innovation en Santé et Bien-être El Jadida")
    c.setFont("Helvetica", 8)
    c.drawCentredString(width / 2, height - 25 * mm, "Etablissement de Formation Professionnelle Privé")
    c.drawCentredString(width / 2, height - 29 * mm, "Autorisé sous N° 3/02/3/2024 Du 09/07/2024")

    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(width / 2, height - 40 * mm, f"Filière : {class_name}")
    c.drawCentredString(width / 2, height - 45 * mm, f"Année scolaire : {timetable['academic_year']}")
    c.drawCentredString(
        width / 2, height - 50 * mm,
        f"Semaine du {week_start.strftime('%d/%m/%Y')} au {week_end.strftime('%d/%m/%Y')}",
    )

    by_day: dict[int, list[dict]] = {i: [] for i in range(5)}
    for s in slots:
        by_day.setdefault(s["day_of_week"], []).append(s)
    for d in by_day:
        by_day[d].sort(key=lambda s: s["start_time"])

    header = ["Jours", "Horaire", "Séquence (Matière)", "Formateurs(trices)", "Salle"]
    data = [header]
    row_kinds: list[tuple[int, str]] = []   # (row_index, 'empty' | 'exam')
    day_spans: list[tuple[int, int]] = []   # (start_row, end_row) inclusive

    row_idx = 1  # row 0 is the header
    for day_idx in range(5):
        day_slots = by_day.get(day_idx, [])
        day_date = week_start + timedelta(days=day_idx)
        day_label = f"{DAY_NAMES_FR[day_idx]}\n{day_date.strftime('%d/%m/%Y')}"

        if not day_slots:
            data.append([day_label, "—", "-", "", ""])
            row_kinds.append((row_idx, "empty"))
            day_spans.append((row_idx, row_idx))
            row_idx += 1
            continue

        start_row = row_idx
        for s in day_slots:
            horaire = f"{_fmt_hm(s['start_time'])}-{_fmt_hm(s['end_time'])}"
            if not s.get("subject"):
                data.append([day_label, horaire, "-", "", ""])
                row_kinds.append((row_idx, "empty"))
            elif s.get("slot_type") == "exam":
                data.append([day_label, horaire, f"Contrôle continue : {s['subject']}", s.get("professor_name") or "", s.get("room") or ""])
                row_kinds.append((row_idx, "exam"))
            else:
                data.append([day_label, horaire, s["subject"], s.get("professor_name") or "", s.get("room") or ""])
            row_idx += 1
        day_spans.append((start_row, row_idx - 1))

    col_widths = [30 * mm, 22 * mm, 65 * mm, 40 * mm, 20 * mm]
    table = Table(data, colWidths=col_widths, repeatRows=1)

    TEAL = rl_colors.Color(0.10, 0.42, 0.40)
    ORANGE = rl_colors.Color(0.98, 0.85, 0.65)
    GRAY = rl_colors.Color(0.85, 0.85, 0.85)
    YELLOW = rl_colors.Color(1.0, 0.95, 0.4)

    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), TEAL),
        ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.6, rl_colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (1, -1), "CENTER"),
        ("ALIGN", (4, 0), (4, -1), "CENTER"),
    ]
    for start_r, end_r in day_spans:
        style_cmds.append(("SPAN", (0, start_r), (0, end_r)))
        style_cmds.append(("BACKGROUND", (0, start_r), (0, end_r), ORANGE))
        style_cmds.append(("FONTNAME", (0, start_r), (0, end_r), "Helvetica-Bold"))
    for r, kind in row_kinds:
        if kind == "empty":
            style_cmds.append(("BACKGROUND", (1, r), (-1, r), GRAY))
        elif kind == "exam":
            style_cmds.append(("BACKGROUND", (2, r), (2, r), YELLOW))
            style_cmds.append(("FONTNAME", (2, r), (2, r), "Helvetica-Bold"))

    table.setStyle(TableStyle(style_cmds))

    table_width, table_height = table.wrapOn(c, width, height)
    table_x = (width - table_width) / 2
    table_y = height - 60 * mm - table_height
    table.drawOn(c, table_x, table_y)

    validated_at = timetable.get("validated_at")
    try:
        validated_date = parse_iso_dt(str(validated_at)).strftime("%d/%m/%Y")
    except Exception:
        validated_date = datetime.now().strftime("%d/%m/%Y")

    footer_y = table_y - 15 * mm
    c.setFont("Helvetica", 9)
    c.drawRightString(width - 20 * mm, footer_y, f"Fait à El Jadida : {validated_date}")
    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(width - 20 * mm, footer_y - 6 * mm, "La directrice de l'établissement")

    c.setFont("Helvetica-Oblique", 7)
    c.drawString(20 * mm, 15 * mm, "Sise au 24, 3ème étage, Lotissement Ennajd, El Jadida MAROC")
    c.drawString(20 * mm, 11 * mm, "Tél : 06 32 82 28 98 · www.ipisb.ma · E-mail : ipisbj.infirmiers@gmail.com")
# ── Facture scolarité (générée au paiement d'un étudiant) ─────────────────────

_FR_UNITS = ["", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf",
             "dix", "onze", "douze", "treize", "quatorze", "quinze", "seize",
             "dix-sept", "dix-huit", "dix-neuf"]
_FR_TENS = {2: "vingt", 3: "trente", 4: "quarante", 5: "cinquante", 6: "soixante"}


def _fr_2(n: int) -> str:
    """0..99 en toutes lettres (français)."""
    if n < 20:
        return _FR_UNITS[n]
    t, u = divmod(n, 10)
    if t in _FR_TENS:                       # 20..69
        w = _FR_TENS[t]
        if u == 1:
            return f"{w} et un"
        return w + (f"-{_FR_UNITS[u]}" if u else "")
    if t == 7:                              # 70..79
        return "soixante et onze" if u == 1 else f"soixante-{_FR_UNITS[10 + u]}"
    if t == 8:                              # 80..89
        return "quatre-vingts" if u == 0 else f"quatre-vingt-{_FR_UNITS[u]}"
    return f"quatre-vingt-{_FR_UNITS[10 + u]}"   # 90..99


def _fr_3(n: int) -> str:
    """0..999 en toutes lettres."""
    if n < 100:
        return _fr_2(n)
    h, r = divmod(n, 100)
    hw = "cent" if h == 1 else f"{_FR_UNITS[h]} cent"
    if r == 0:
        return hw + ("s" if h > 1 else "")   # deux cents, mais « cent »
    return f"{hw} {_fr_2(r)}"


def _fr_int(n: int) -> str:
    """Entier ≥ 0 en toutes lettres."""
    if n == 0:
        return "zéro"
    parts = []
    for value, name, plural in ((1_000_000_000, "milliard", "milliards"),
                                (1_000_000, "million", "millions")):
        q, n = divmod(n, value)
        if q:
            parts.append(f"{_fr_3(q)} {plural if q > 1 else name}")
    milliers, unites = divmod(n, 1000)
    if milliers:
        parts.append("mille" if milliers == 1 else f"{_fr_3(milliers)} mille")
    if unites:
        parts.append(_fr_3(unites))
    return " ".join(p for p in parts if p)


def montant_en_lettres(amount) -> str:
    """Montant MAD en toutes lettres, ex. « Mille deux cents dirhams et cinquante centimes »."""
    try:
        amount = float(amount or 0)
    except Exception:
        amount = 0.0
    dh = int(amount)
    cent = int(round((amount - dh) * 100))
    if cent >= 100:                          # bord d'arrondi
        dh += 1
        cent -= 100
    txt = f"{_fr_int(dh)} {'dirham' if dh == 1 else 'dirhams'}"
    if cent:
        txt += f" et {_fr_int(cent)} {'centime' if cent == 1 else 'centimes'}"
    return txt.capitalize()


def render_tuition_invoice_pdf(payment: dict, student_name: str,
                               class_name: str | None = None,
                               enrollment_number: str | None = None,
                               period_label: str | None = None) -> bytes:
    """Facture IPISB d'un versement de scolarité, calquée sur le modèle bébleo
    « Facture IPISB » : fond blanc, logo, encadrés aux couleurs du thème (teal),
    tableau multi-colonnes, bloc totaux + montant en lettres, bandeau de pied.
    `payment` = ligne tuition_payments (amount, paid_on, method, reference, id)."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    W, H = width / mm, height / mm  # dimensions en mm (210 × 297)

    # Palette dérivée du thème IPISB (teal), fond blanc.
    TEAL = _TEAL
    TEAL_DARK = (0.0, 0.44, 0.51)
    TEAL_PALE = (0.902, 0.961, 0.969)
    WHITE = (1, 1, 1)
    INK = _INK
    MUTED = _MUTED
    GRID = (0.82, 0.82, 0.82)

    MARGIN = 18.0
    RIGHT = W - MARGIN  # 192

    def L(x, y, s, font="Helvetica", size=9, color=INK):
        c.setFont(font, size); c.setFillColorRGB(*color)
        c.drawString(x * mm, y * mm, "" if s is None else str(s))

    def R(x, y, s, font="Helvetica", size=9, color=INK):
        c.setFont(font, size); c.setFillColorRGB(*color)
        c.drawRightString(x * mm, y * mm, "" if s is None else str(s))

    def CC(x, y, s, font="Helvetica", size=9, color=INK):
        c.setFont(font, size); c.setFillColorRGB(*color)
        c.drawCentredString(x * mm, y * mm, "" if s is None else str(s))

    def fill_rect(x, y, w, h, color):
        c.setFillColorRGB(*color); c.rect(x * mm, y * mm, w * mm, h * mm, fill=1, stroke=0)

    def stroke_rect(x, y, w, h, color, lw=0.6):
        c.setStrokeColorRGB(*color); c.setLineWidth(lw)
        c.rect(x * mm, y * mm, w * mm, h * mm, fill=0, stroke=1)

    def hline(x1, x2, y, color, lw=0.5):
        c.setStrokeColorRGB(*color); c.setLineWidth(lw); c.line(x1 * mm, y * mm, x2 * mm, y * mm)

    def vline(x, y1, y2, color, lw=0.5):
        c.setStrokeColorRGB(*color); c.setLineWidth(lw); c.line(x * mm, y1 * mm, x * mm, y2 * mm)

    def nb(v):
        """Nombre au format marocain, sans suffixe (pour cellules du tableau)."""
        try:
            return f"{float(v or 0):,.2f}".replace(",", " ").replace(".", ",")
        except Exception:
            return "0,00"

    def ell(s, n):
        s = "" if s is None else str(s)
        return s if len(s) <= n else s[: n - 1] + "…"

    def wrap_words(s, maxchars, limit=3):
        """Retour à la ligne sur les espaces (évite de couper un mot)."""
        out, cur = [], ""
        for word in str(s).split():
            if cur and len(cur) + 1 + len(word) > maxchars:
                out.append(cur); cur = word
            else:
                cur = word if not cur else f"{cur} {word}"
            if len(out) >= limit:
                break
        if cur and len(out) < limit:
            out.append(cur)
        return out

    # ── Données ──
    amount = float(payment.get("amount") or 0)
    number = payment.get("reference") or f"FAC-{str(payment.get('id') or '')[:8]}"
    date = _fmt_date_fr(payment.get("paid_on") or (str(payment.get("created_at") or "")[:10]))
    method = payment.get("method") or "—"
    obj_parts = ["Frais de scolarité"]
    if period_label:
        obj_parts.append(period_label)
    if class_name:
        obj_parts.append(class_name)
    objet = " — ".join(obj_parts)

    # ── En-tête : logo (avec identité) à gauche + identifiants légaux à droite ──
    _draw_logo(c, MARGIN, height - 10 * mm, 34, 26)
    ly = H - 13
    for lab, val in [("RC", COMPANY.get("rc")), ("IF", COMPANY.get("if")),
                     ("ICE", COMPANY.get("ice")), ("RIB", COMPANY.get("rib"))]:
        if val:
            R(RIGHT, ly, f"{lab} : {val}", "Helvetica", 7.2, MUTED)
            ly -= 4.2
    hline(MARGIN, RIGHT, H - 40, TEAL, 1.2)

    # ── Deux encadrés : Facture (gauche) / Client (droite) ──
    box_top = H - 44
    gap = 6.0
    bw = (174 - gap) / 2  # 84
    lx, rx = MARGIN, MARGIN + bw + gap  # 18, 108
    hh = 6.5
    rh = 6.0
    body_h = rh * 4 + 3
    left_rows = [
        ("N° de Facture", number),
        ("Date de la Facture", date),
        ("Bon de Commande N°", "—"),
        ("Objet de commande", ell(objet, 34)),
    ]
    right_rows = [
        ("Client", ell(student_name or "—", 34)),
        ("Référence Client", enrollment_number or "—"),
        ("Promotion", ell(class_name or "—", 34)),
        ("ICE Client", "—"),
    ]

    def draw_box(x, title, rows):
        fill_rect(x, box_top - hh, bw, hh, TEAL)
        L(x + 2.5, box_top - hh + 2, title, "Helvetica-Bold", 8.5, WHITE)
        fill_rect(x, box_top - hh - body_h, bw, body_h, TEAL_PALE)
        stroke_rect(x, box_top - hh - body_h, bw, hh + body_h, TEAL_DARK, 0.7)
        yy = box_top - hh - 4
        for lab, val in rows:
            L(x + 2.5, yy, f"{lab} :", "Helvetica", 7.2, MUTED)
            L(x + 33, yy, val, "Helvetica-Bold", 7.5, INK)
            yy -= rh

    draw_box(lx, "Facture", left_rows)
    draw_box(rx, "Client", right_rows)
    boxes_bottom = box_top - hh - body_h

    # ── Titre « Facture » centré ──
    ty = boxes_bottom - 10
    CC(W / 2, ty, "Facture", "Helvetica-Bold", 20, TEAL)
    CC(W / 2, ty - 5, "Montants exprimés en Dirham (MAD)", "Helvetica-Oblique", 8, MUTED)

    # ── Tableau des désignations ──
    cols = [("N°", 10), ("Désignation", 62), ("Quantité", 18), ("PU HT", 26),
            ("%TVA", 16), ("Total HT", 21), ("Total TTC", 21)]
    xb = [MARGIN]
    for _, w in cols:
        xb.append(xb[-1] + w)
    head_align = ["c", "l", "c", "c", "c", "c", "c"]
    head_h = 8.0
    row_h = 7.2
    thead_top = ty - 12
    header_bottom = thead_top - head_h

    fill_rect(MARGIN, header_bottom, 174, head_h, TEAL)
    for i, (label, w) in enumerate(cols):
        if head_align[i] == "l":
            L(xb[i] + 2, header_bottom + 2.6, label, "Helvetica-Bold", 7.3, WHITE)
        else:
            CC(xb[i] + w / 2, header_bottom + 2.6, label, "Helvetica-Bold", 7.3, WHITE)

    items = [{"n": "1", "desig": objet, "qte": "1", "pu": nb(amount),
              "tva": "0 %", "ht": nb(amount), "ttc": nb(amount)}]
    n_rows = max(len(items), 4)
    body_bottom = header_bottom - row_h * n_rows
    fill_rect(MARGIN, body_bottom, 174, row_h * n_rows, WHITE)
    for r in range(n_rows):
        ry = header_bottom - row_h * (r + 1) + 2.2
        if r < len(items):
            it = items[r]
            CC(xb[0] + cols[0][1] / 2, ry, it["n"], "Helvetica", 7.6, INK)
            L(xb[1] + 2, ry, ell(it["desig"], 48), "Helvetica", 7.6, INK)
            CC(xb[2] + cols[2][1] / 2, ry, it["qte"], "Helvetica", 7.6, INK)
            R(xb[4] - 2, ry, it["pu"], "Helvetica", 7.6, INK)
            CC(xb[4] + cols[4][1] / 2, ry, it["tva"], "Helvetica", 7.6, INK)
            R(xb[6] - 2, ry, it["ht"], "Helvetica", 7.6, INK)
            R(xb[7] - 2, ry, it["ttc"], "Helvetica", 7.6, INK)
        hline(MARGIN, RIGHT, header_bottom - row_h * (r + 1), GRID, 0.4)
    for x in xb:
        vline(x, body_bottom, header_bottom, GRID, 0.4)
    stroke_rect(MARGIN, body_bottom, 174, thead_top - body_bottom, TEAL_DARK, 0.7)

    # ── Bas de page : montant en lettres (gauche) + totaux (droite) ──
    sec_top = body_bottom - 10

    # Totaux (droite)
    tw = 74.0
    tx = RIGHT - tw  # 118
    trows = [("Total HT", nb(amount)), ("Total TVA", nb(0)), ("Total TTC", nb(amount)),
             ("RAS", nb(0)), ("Total à Payer (MAD)*", nb(amount))]
    trh = 6.6
    for i, (lab, val) in enumerate(trows):
        yy = sec_top - trh * (i + 1)
        if i == len(trows) - 1:
            fill_rect(tx, yy, tw, trh, TEAL)
            L(tx + 3, yy + 2, lab, "Helvetica-Bold", 8.2, WHITE)
            R(tx + tw - 3, yy + 2, val, "Helvetica-Bold", 8.6, WHITE)
        else:
            L(tx + 3, yy + 2, lab, "Helvetica", 8, MUTED)
            R(tx + tw - 3, yy + 2, val, "Helvetica-Bold", 8, INK)
            hline(tx, tx + tw, yy, GRID, 0.4)
    stroke_rect(tx, sec_top - trh * len(trows), tw, trh * len(trows), TEAL_DARK, 0.7)
    totals_bottom = sec_top - trh * len(trows)

    # Montant en lettres (gauche)
    lw_box = 92.0
    fill_rect(MARGIN, sec_top - hh, lw_box, hh, TEAL)
    L(MARGIN + 3, sec_top - hh + 2, "Total à payer en lettres*", "Helvetica-Bold", 8, WHITE)
    lines = wrap_words(montant_en_lettres(amount) + " (TTC).", 44, 3)
    lbody = max(len(lines), 2) * 4.6 + 4
    fill_rect(MARGIN, sec_top - hh - lbody, lw_box, lbody, TEAL_PALE)
    stroke_rect(MARGIN, sec_top - hh - lbody, lw_box, hh + lbody, TEAL_DARK, 0.7)
    yy = sec_top - hh - 5
    for ln in lines:
        L(MARGIN + 3, yy, ln, "Helvetica-Oblique", 8, INK); yy -= 4.6

    # ── Mentions ──
    note_y = min(totals_bottom, sec_top - hh - lbody) - 8
    L(MARGIN, note_y, f"Mode de règlement : {method}", "Helvetica", 8, MUTED)
    L(MARGIN, note_y - 4.6, "Formation professionnelle exonérée de TVA.", "Helvetica-Oblique", 7.5, MUTED)

    # ── Bandeau de pied de page (teal) ──
    band_h = 15.0
    fill_rect(0, 0, W, band_h, TEAL)
    CC(W / 2, band_h - 5.5, COMPANY.get("subtitle") or "IPISB", "Helvetica-Bold", 7.6, WHITE)
    legal = _legal_line()
    if legal:
        CC(W / 2, band_h - 9.5, legal, "Helvetica", 6.6, (0.9, 0.98, 1.0))
    if COMPANY.get("rib"):
        CC(W / 2, band_h - 12.8, f"RIB : {COMPANY['rib']}", "Helvetica", 6.6, (0.9, 0.98, 1.0))
    R(RIGHT, band_h + 2.5, f"Généré le {datetime.now().strftime('%d/%m/%Y')}",
      "Helvetica-Oblique", 6.5, MUTED)

    c.showPage()
    c.save()
    return buf.getvalue()


MONTH_NAMES_FR = [
    "", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
]


def compute_moroccan_payroll(base: float, bonuses: float = 0, deductions: float = 0) -> dict:
    """Approximate Moroccan CNSS + IR (progressive income tax) monthly calculation."""
    gross = base + bonuses

    # CNSS employee part ~= 4.48%, capped at a 6 000 MAD/month contribution base
    cnss_base = min(gross, 6000)
    cnss = round(cnss_base * 0.0448, 2)

    # Taxable income = gross - CNSS - professional deduction (20%, capped at 2 500)
    prof_deduction = min(gross * 0.20, 2500)
    taxable = gross - cnss - prof_deduction

    # 2024 Moroccan IR brackets (monthly)
    if taxable <= 2500:
        ir = 0.0
    elif taxable <= 4166:
        ir = taxable * 0.10 - 250
    elif taxable <= 5000:
        ir = taxable * 0.20 - 666.67
    elif taxable <= 6666:
        ir = taxable * 0.30 - 1166.67
    elif taxable <= 15000:
        ir = taxable * 0.34 - 1433.33
    else:
        ir = taxable * 0.38 - 2033.33
    ir = max(round(ir, 2), 0.0)

    net_salary = round(gross - cnss - ir - deductions, 2)
    return {"cnss": cnss, "ir": ir, "gross_salary": round(gross, 2), "net_salary": net_salary}


def render_payslip_pdf(record: dict, employee: dict) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    month_label = MONTH_NAMES_FR[record.get("month") or 0] or str(record.get("month"))
    draw_header(c, f"BULLETIN DE PAIE — {month_label} {record.get('year', '')}")

    c.setFont("Helvetica-Bold", 10)
    c.drawString(20 * mm, height - 50 * mm, "Employé :")
    c.setFont("Helvetica", 9)
    c.drawString(20 * mm, height - 56 * mm, f"Nom : {employee.get('full_name', 'N/A')}")
    c.drawString(20 * mm, height - 61 * mm, f"Poste : {employee.get('position', 'N/A') or '—'}")
    c.drawString(20 * mm, height - 66 * mm, f"Département : {employee.get('department', 'N/A') or '—'}")
    c.drawString(20 * mm, height - 71 * mm, f"N° CNSS : {employee.get('cnss_number', 'N/A') or '—'}")

    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(width - 20 * mm, height - 50 * mm, "Statut :")
    c.setFont("Helvetica", 9)
    c.drawRightString(width - 20 * mm, height - 56 * mm, (record.get("status") or "draft").upper())

    y = height - 85 * mm
    rows = [
        ("Salaire de base", record.get("base_salary", 0), None),
        ("Primes", record.get("bonuses", 0), None),
        ("Salaire brut", record.get("gross_salary", 0), None),
        ("Cotisation CNSS", None, record.get("cnss", 0)),
        ("Impôt sur le revenu (IR)", None, record.get("ir", 0)),
        ("Autres retenues", None, record.get("deductions", 0)),
    ]

    c.setFont("Helvetica-Bold", 9)
    c.drawString(20 * mm, y, "Désignation")
    c.drawRightString(120 * mm, y, "Gains")
    c.drawRightString(width - 20 * mm, y, "Retenues")
    c.setLineWidth(0.5)
    c.line(20 * mm, y - 2 * mm, width - 20 * mm, y - 2 * mm)

    c.setFont("Helvetica", 9)
    for label, gain, deduction in rows:
        y -= 8 * mm
        c.drawString(20 * mm, y, label)
        if gain is not None:
            c.drawRightString(120 * mm, y, fmt_mad(gain))
        if deduction is not None:
            c.drawRightString(width - 20 * mm, y, fmt_mad(deduction))

    y -= 14 * mm
    c.setLineWidth(0.8)
    c.line(20 * mm, y + 5 * mm, width - 20 * mm, y + 5 * mm)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(20 * mm, y, "NET À PAYER")
    c.drawRightString(width - 20 * mm, y, fmt_mad(record.get("net_salary", 0)))

    y -= 30 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(20 * mm, y, "Signature Employeur")
    c.drawRightString(width - 20 * mm, y, "Signature Employé")

    draw_footer(c)
    c.showPage()
    c.save()
    return buf.getvalue()


def _mention(grade: float) -> str:
    if grade >= 16:
        return "Excellent"
    if grade >= 14:
        return "Bien"
    if grade >= 12:
        return "Assez bien"
    if grade >= 10:
        return "Passable"
    return "Insuffisant"


def render_transcript_pdf(student: dict, courses: list[dict], period_label: str = "") -> bytes:
    """Relevé de notes — one row per course (contrôle continu grade /20 +
    mention), with a credit-weighted overall average at the bottom."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    draw_header(c, "RELEVÉ DE NOTES")

    c.setFont("Helvetica-Bold", 10)
    c.drawString(20 * mm, height - 50 * mm, f"Étudiant : {student.get('full_name', 'N/A')}")
    c.setFont("Helvetica", 9)
    c.drawString(20 * mm, height - 56 * mm, f"Classe : {student.get('class_name', 'N/A') or '—'}")
    if period_label:
        c.drawRightString(width - 20 * mm, height - 50 * mm, period_label)

    y = height - 70 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(20 * mm, y, "Cours")
    c.drawString(120 * mm, y, "Coeff.")
    c.drawString(140 * mm, y, "Note / 20")
    c.drawRightString(width - 20 * mm, y, "Mention")
    c.setLineWidth(0.5)
    c.line(20 * mm, y - 2 * mm, width - 20 * mm, y - 2 * mm)

    c.setFont("Helvetica", 9)
    total_weighted, total_credits = 0.0, 0
    for course in courses:
        y -= 8 * mm
        title = course.get("title", "—")
        if len(title) > 45:
            title = title[:42] + "..."
        c.drawString(20 * mm, y, title)
        credits = course.get("credits") or 1
        c.drawString(120 * mm, y, str(credits))
        grade = course.get("grade")
        if grade is None:
            c.drawString(140 * mm, y, "—")
            c.drawRightString(width - 20 * mm, y, "Non évalué")
        else:
            c.drawString(140 * mm, y, f"{grade:.2f}")
            c.drawRightString(width - 20 * mm, y, _mention(grade))
            total_weighted += grade * credits
            total_credits += credits

    y -= 14 * mm
    c.setLineWidth(0.8)
    c.line(20 * mm, y + 5 * mm, width - 20 * mm, y + 5 * mm)
    overall = round(total_weighted / total_credits, 2) if total_credits else None
    c.setFont("Helvetica-Bold", 12)
    c.drawString(20 * mm, y, "MOYENNE GÉNÉRALE")
    c.drawRightString(width - 20 * mm, y, f"{overall:.2f} / 20" if overall is not None else "—")

    y -= 30 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(20 * mm, y, "Signature Direction")
    c.drawRightString(width - 20 * mm, y, "Cachet de l'établissement")

    draw_footer(c)
# ── Note de caisse (module de saisie) ────────────────────────────────────────

def _fmt_date_fr(iso) -> str:
    """ISO 'AAAA-MM-JJ' → 'JJ/MM/AAAA' ; None → '—'."""
    if not iso:
        return "—"
    parts = str(iso)[:10].split("-")
    return f"{parts[2]}/{parts[1]}/{parts[0]}" if len(parts) == 3 else str(iso)[:10]


def render_cash_note_pdf(note: dict) -> bytes:
    """Note de caisse (modèle bébleo « Note de Caisse »). `note` = ligne cash_notes
    (reference, note_date, beneficiary_name, beneficiary_cin, objet, period_from,
    period_to, accorded_by, items[], total)."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    def L(x, y, s, font="Helvetica", size=9, color=_INK):
        c.setFont(font, size); c.setFillColorRGB(*color)
        c.drawString(x * mm, y, str(s) if s is not None else "")

    def R(x, y, s, font="Helvetica", size=9, color=_INK):
        c.setFont(font, size); c.setFillColorRGB(*color)
        c.drawRightString(x * mm, y, str(s) if s is not None else "")

    items = note.get("items") or []
    total = float(note.get("total") or sum(float(it.get("montant") or 0) for it in items))
    number = note.get("reference") or f"NDC-{str(note.get('id') or '')[:8]}"

    draw_header(c, "NOTE DE CAISSE")

    # ── Lieu / date + N° (sous l'en-tête, à droite) ──
    R(width / mm - 20, height - 47 * mm, f"El Jadida, le : {_fmt_date_fr(note.get('note_date'))}",
      "Helvetica", 9, _MUTED)
    R(width / mm - 20, height - 52 * mm, f"Note de Caisse N° : {number}", "Helvetica-Bold", 10, _INK)

    # ── Bloc bénéficiaire ──
    y = height - 62 * mm
    L(20, y, "Nom et Prénom :", "Helvetica-Bold", 9.5, _INK)
    L(53, y, note.get("beneficiary_name") or "—", "Helvetica", 9.5, _INK)
    L(140, y, "CIN :", "Helvetica-Bold", 9.5, _INK)
    L(152, y, note.get("beneficiary_cin") or "—", "Helvetica", 9.5, _INK)

    y -= 7 * mm
    L(20, y, "Objet de la note de caisse :", "Helvetica-Bold", 9.5, _INK)
    oy = y
    for line in (_wrap(note.get("objet"), 95, 2) or ["—"]):
        oy -= 5 * mm
        L(20, oy, line, "Helvetica", 9.5, _INK)

    y = oy - 7 * mm
    L(20, y, "Du", "Helvetica-Bold", 9.5, _INK)
    L(28, y, _fmt_date_fr(note.get("period_from")), "Helvetica", 9.5, _INK)
    L(70, y, "au", "Helvetica-Bold", 9.5, _INK)
    L(78, y, _fmt_date_fr(note.get("period_to")), "Helvetica", 9.5, _INK)

    y -= 7 * mm
    L(20, y, "Accordée par :", "Helvetica-Bold", 9.5, _INK)
    L(50, y, note.get("accorded_by") or "—", "Helvetica", 9.5, _INK)

    # ── Tableau Article / Prestataire / Montant ──
    # Bornes de colonnes (mm) : gauche, séparateurs, droite + padding interne.
    # En-tête, valeurs et bordures verticales partagent les MÊMES repères.
    X_L, X_S1, X_S2, X_R, PAD = 20.0, 88.0, 152.0, 190.0, 4.0
    ty = y - 12 * mm
    c.setFillColorRGB(*_TEAL); c.rect(X_L * mm, ty, (X_R - X_L) * mm, 8 * mm, fill=1, stroke=0)
    L(X_L + PAD, ty + 2.5 * mm, "Article", "Helvetica-Bold", 9, (1, 1, 1))
    L(X_S1 + PAD, ty + 2.5 * mm, "Prestataire", "Helvetica-Bold", 9, (1, 1, 1))
    R(X_R - PAD, ty + 2.5 * mm, "Montant", "Helvetica-Bold", 9, (1, 1, 1))

    c.setStrokeColorRGB(0.85, 0.85, 0.85); c.setLineWidth(0.5)
    ry = ty
    # Lignes réelles, complétées jusqu'à 5 lignes pour un tableau lisible.
    rows = list(items) + [{}] * max(0, 5 - len(items))
    for it in rows:
        ry -= 8 * mm
        art = (it.get("article") or "")[:44]
        presta = (it.get("prestataire") or "")[:36]
        montant = it.get("montant")
        L(X_L + PAD, ry + 2.5 * mm, art, "Helvetica", 9, _INK)
        L(X_S1 + PAD, ry + 2.5 * mm, presta, "Helvetica", 9, _INK)
        if montant is not None and str(montant) != "":
            R(X_R - PAD, ry + 2.5 * mm, fmt_mad(montant), "Helvetica", 9, _INK)
        c.line(X_L * mm, ry, X_R * mm, ry)
    # Bordures verticales du tableau (gauche, séparateurs, droite).
    for vx in (X_L, X_S1, X_S2, X_R):
        c.line(vx * mm, ty + 8 * mm, vx * mm, ry)

    # ── Total Global (montant aligné sous la colonne Montant) ──
    ty2 = ry - 9 * mm
    c.setFillColorRGB(*_LIGHT); c.rect(X_L * mm, ty2 - 1 * mm, (X_R - X_L) * mm, 9 * mm, fill=1, stroke=0)
    L(X_L + PAD, ty2 + 1.5 * mm, "Total Global", "Helvetica-Bold", 9.5, _INK)
    R(X_R - PAD, ty2 + 1.5 * mm, fmt_mad(total), "Helvetica-Bold", 10, _TEAL)

    # ── Montant en toutes lettres (ligne dédiée) ──
    ly = ty2 - 8 * mm
    L(X_L + PAD, ly, "Arrêtée la présente note à la somme de :", "Helvetica-Bold", 8.5, _MUTED)
    lettres = montant_en_lettres(total)
    L(X_L + PAD, ly - 5 * mm, (lettres[:88] + "…") if len(lettres) > 89 else lettres,
      "Helvetica-Oblique", 9, _INK)

    # ── Visas (3 colonnes) ──
    vy = ty2 - 20 * mm
    box_w = (width - 40 * mm - 12 * mm) / 3
    labels = ["Visa Intéressé(e)", "Visa Responsable N+1", "Visa Responsable Comptabilité"]
    for i, lab in enumerate(labels):
        bx = 20 * mm + i * (box_w + 6 * mm)
        c.setStrokeColorRGB(0.8, 0.8, 0.8); c.setLineWidth(0.5)
        c.rect(bx, vy - 22 * mm, box_w, 22 * mm, fill=0, stroke=1)
        c.setFillColorRGB(*_MUTED); c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(bx + box_w / 2, vy - 5 * mm, lab)

    draw_footer(c)
    c.showPage()
    c.save()
    return buf.getvalue()


# ── Journal de la Caisse (modèle bébleo) ─────────────────────────────────────

def render_cash_journal_pdf(rows: list[dict], meta: dict | None = None) -> bytes:
    """Journal de la Caisse / Journal des Comptes (modèle bébleo).
    `rows` = lignes cash_journal triées chronologiquement, chacune :
    {entry_date, type ('entree'|'sortie'), amount, justificatif, created_at, balance}.
    `meta` (optionnel) : {journal_no, holder, poste, date_from, date_to, generated_on,
    title, signatory, signature_col, signature2_col} — `title` bascule l'export sur
    le journal des comptes (banque : virement / OV / chèque), `signatory` le premier
    visa, `signature_col` / `signature2_col` les deux colonnes de signature de la
    grille (format « Ligne 1|Ligne 2 »).
    Multi-pages : l'en-tête d'identité est répété, la grille reprend à chaque page."""
    meta = meta or {}
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    W, H = width / mm, height / mm

    TEAL = _TEAL
    TEAL_DARK = (0.0, 0.44, 0.51)
    WHITE = (1, 1, 1)
    INK = _INK
    MUTED = _MUTED
    GRID = (0.72, 0.72, 0.72)

    MARGIN = 12.0
    RIGHT = W - MARGIN  # 198

    def L(x, y, s, font="Helvetica", size=8, color=INK):
        c.setFont(font, size); c.setFillColorRGB(*color)
        c.drawString(x * mm, y * mm, "" if s is None else str(s))

    def R(x, y, s, font="Helvetica", size=8, color=INK):
        c.setFont(font, size); c.setFillColorRGB(*color)
        c.drawRightString(x * mm, y * mm, "" if s is None else str(s))

    def CC(x, y, s, font="Helvetica", size=8, color=INK):
        c.setFont(font, size); c.setFillColorRGB(*color)
        c.drawCentredString(x * mm, y * mm, "" if s is None else str(s))

    def fill_rect(x, y, w, h, color):
        c.setFillColorRGB(*color); c.rect(x * mm, y * mm, w * mm, h * mm, fill=1, stroke=0)

    def stroke_rect(x, y, w, h, color, lw=0.5):
        c.setStrokeColorRGB(*color); c.setLineWidth(lw)
        c.rect(x * mm, y * mm, w * mm, h * mm, fill=0, stroke=1)

    def hline(x1, x2, y, color, lw=0.4):
        c.setStrokeColorRGB(*color); c.setLineWidth(lw); c.line(x1 * mm, y * mm, x2 * mm, y * mm)

    def vline(x, y1, y2, color, lw=0.4):
        c.setStrokeColorRGB(*color); c.setLineWidth(lw); c.line(x * mm, y1 * mm, x * mm, y2 * mm)

    def nb(v):
        try:
            f = float(v or 0)
            return "" if f == 0 else f"{f:,.2f}".replace(",", " ").replace(".", ",")
        except Exception:
            return ""

    def ell(s, n):
        s = "" if s is None else str(s)
        return s if len(s) <= n else s[: n - 1] + "…"

    def heure(iso):
        s = str(iso or "")
        return s.split("T", 1)[1][:5] if "T" in s else ""

    # Colonnes (largeurs mm, somme = 186 = usable avec MARGIN=12)
    cols = [18, 12, 22, 20, 22, 20, 20, 20, 16, 16]
    xb = [MARGIN]
    for w in cols:
        xb.append(xb[-1] + w)  # xb[-1] = 198

    dates = [r.get("entry_date") for r in rows if r.get("entry_date")]
    date_from = meta.get("date_from") or (min(dates) if dates else "")
    date_to = meta.get("date_to") or (max(dates) if dates else "")

    def dotted(x, y, w):
        c.setStrokeColorRGB(*MUTED); c.setLineWidth(0.4); c.setDash(1, 2)
        c.line(x * mm, y * mm, (x + w) * mm, y * mm); c.setDash()

    def draw_identity(page_no):
        """En-tête d'identité. Retourne y (mm) du haut de la grille."""
        _draw_logo(c, MARGIN, height - 8 * mm, 26, 22)
        tx = MARGIN + 30
        L(tx, H - 12, f"{COMPANY['subtitle']} El Jadida", "Helvetica-Bold", 11, TEAL)
        L(tx, H - 16.5, COMPANY.get("mention") or "", "Helvetica", 8, MUTED)
        L(tx, H - 20.5, COMPANY.get("ofppt") or "", "Helvetica", 8, MUTED)
        R(RIGHT, H - 27, f"El Jadida, le : {_fmt_date_fr(meta.get('generated_on'))}", "Helvetica", 8.5, INK)
        hline(MARGIN, RIGHT, H - 30, TEAL, 1.0)
        CC(W / 2, H - 38,
           f"{meta.get('title') or 'Journal de la Caisse'} N° : {meta.get('journal_no') or '—'}",
           "Helvetica-Bold", 15, INK)
        y = H - 45
        L(MARGIN, y, "Nom et Prénom :", "Helvetica-Bold", 8.5, INK)
        if meta.get("holder"):
            L(MARGIN + 26, y, meta["holder"], "Helvetica", 8.5, INK)
        else:
            dotted(MARGIN + 26, y - 0.5, 55)
        L(MARGIN + 90, y, "Poste :", "Helvetica-Bold", 8.5, INK)
        if meta.get("poste"):
            L(MARGIN + 103, y, meta["poste"], "Helvetica", 8.5, INK)
        else:
            dotted(MARGIN + 103, y - 0.5, RIGHT - (MARGIN + 103))
        y -= 5
        # Un journal tenu au jour le jour s'annonce comme une journée, pas comme
        # une plage « du 07/08 au 07/08 ».
        if date_from and date_from == date_to:
            L(MARGIN, y, "Journée du", "Helvetica-Bold", 8.5, INK)
            L(MARGIN + 19, y, _fmt_date_fr(date_from), "Helvetica", 8.5, INK)
        else:
            L(MARGIN, y, "Suivi du", "Helvetica-Bold", 8.5, INK)
            L(MARGIN + 15, y, _fmt_date_fr(date_from), "Helvetica", 8.5, INK)
            L(MARGIN + 42, y, "au", "Helvetica-Bold", 8.5, INK)
            L(MARGIN + 49, y, _fmt_date_fr(date_to), "Helvetica", 8.5, INK)
        if page_no > 1:
            R(RIGHT, y, f"Page {page_no}", "Helvetica-Oblique", 7.5, MUTED)
        return y - 5

    def draw_table_header(top):
        """En-tête de tableau à 2 niveaux. Retourne y (mm) du haut des lignes."""
        h1 = 6.0
        th = 12.0
        fill_rect(MARGIN, top - th, 186, th, TEAL)
        groups = [
            ("Mise à jour", 0, 2, [("Date", 0), ("Heure", 1)]),
            ("Entrées", 2, 4, [("Montant (M1)", 2), ("Référence", 3)]),
            ("Sortie", 4, 6, [("Montant (M2)", 4), ("Référence", 5)]),
        ]
        for title, a, b, subs in groups:
            CC((xb[a] + xb[b]) / 2, top - h1 + 1.7, title, "Helvetica-Bold", 7.6, WHITE)
            hline(xb[a], xb[b], top - h1, WHITE, 0.5)
            for lab, ci in subs:
                CC((xb[ci] + xb[ci + 1]) / 2, top - h1 - 3.5, lab, "Helvetica-Bold", 6.2, WHITE)
        # Les deux dernières colonnes restent VIDES sur toute la hauteur de la
        # grille : ce sont les cases de visa, signées à la main ligne par ligne.
        singles = [
            (6, "Solde Journalier|(SJ = M1-M2)"),
            (7, "Solde Cumulé|(SC = ∑ SJ)"),
            (8, meta.get("signature_col") or "Signature 1|resp. caisse"),
            (9, meta.get("signature2_col") or "Signature 2|resp. comptabilité *"),
        ]
        for ci, lab in singles:
            parts = lab.split("|")
            yy = top - th / 2 + 1.2
            for k, p in enumerate(parts):
                CC((xb[ci] + xb[ci + 1]) / 2, yy - k * 2.7, p, "Helvetica-Bold", 6.1, WHITE)
        return top - th

    def draw_grid(top, bottom):
        for x in xb:
            vline(x, bottom, top, GRID, 0.4)
        stroke_rect(MARGIN, bottom, 186, top - bottom, TEAL_DARK, 0.7)

    def footer_band():
        band_h = 12.0
        fill_rect(0, 0, W, band_h, TEAL)
        bits = []
        if COMPANY.get("phone"):
            bits.append(f"Tél : {COMPANY['phone']}")
        if COMPANY.get("website"):
            bits.append(COMPANY["website"])
        if COMPANY.get("email"):
            bits.append(COMPANY["email"])
        CC(W / 2, band_h - 5, COMPANY.get("address") or "", "Helvetica-Bold", 6.8, WHITE)
        CC(W / 2, band_h - 8.6, "   ·   ".join(bits), "Helvetica", 6.6, (0.9, 0.98, 1.0))

    row_h = 8.0
    total = len(rows)
    idx = 0
    page_no = 0
    while True:
        page_no += 1
        top_grid = draw_identity(page_no)
        head_bottom = draw_table_header(top_grid)
        avail = head_bottom - 20
        per_page = max(1, int(avail // row_h))
        page_rows = rows[idx: idx + per_page]
        y = head_bottom
        for r in page_rows:
            is_in = r.get("type") == "entree"
            amt = float(r.get("amount") or 0)
            ry = y - row_h + 2.8
            L(xb[0] + 1.5, ry, _fmt_date_fr(r.get("entry_date")), "Helvetica", 7, INK)
            CC((xb[1] + xb[2]) / 2, ry, heure(r.get("created_at")), "Helvetica", 7, INK)
            # Référence : n° de chèque / d'OV quand il existe (journal des comptes),
            # sinon le type de pièce justificative (journal de caisse).
            ref = r.get("payment_ref") or r.get("justificatif")
            if is_in:
                R(xb[3] - 1.5, ry, nb(amt), "Helvetica", 7, (0.0, 0.45, 0.2))
                L(xb[3] + 1.5, ry, ell(ref, 12), "Helvetica", 6.2, MUTED)
            else:
                R(xb[5] - 1.5, ry, nb(amt), "Helvetica", 7, (0.66, 0.12, 0.12))
                L(xb[5] + 1.5, ry, ell(ref, 12), "Helvetica", 6.2, MUTED)
            sj = amt if is_in else -amt
            R(xb[7] - 1.5, ry, nb(sj), "Helvetica", 7, INK)
            R(xb[8] - 1.5, ry, nb(r.get("balance")), "Helvetica-Bold", 7, TEAL_DARK)
            hline(MARGIN, RIGHT, y - row_h, GRID, 0.4)
            y -= row_h
        draw_grid(head_bottom, y)
        idx += len(page_rows)
        if idx >= total:
            ny = y - 8
            L(MARGIN, ny, "* Validation après révision et vérification des justifications "
              "(notes de frais, notes de caisse…).", "Helvetica-Oblique", 7, MUTED)
            sy = max(ny - 16, 22)
            third = 186 / 3
            for i, lab in enumerate([meta.get("signatory") or "Signature Responsable de Caisse",
                                     "Visa Responsable Comptabilité",
                                     "Validation Comité de Gestion"]):
                cx = MARGIN + third * i + third / 2
                CC(cx, sy, lab, "Helvetica-Bold", 7.4, INK)
                hline(MARGIN + third * i + 6, MARGIN + third * (i + 1) - 6, sy - 10, MUTED, 0.5)
            footer_band()
            break
        footer_band()
        c.showPage()

    c.showPage()
    c.save()
    return buf.getvalue()


# ── Note des Frais de Mission (modèle bébleo) ────────────────────────────────

# Catalogue FIXE des thèmes / articles de la note de frais de mission, dans
# l'ordre du modèle Word. Clés stables partagées avec le backend (validation +
# stockage) et le frontend (formulaire matriciel). Format : [(thème, [(clé, libellé)])].
MISSION_CATALOG = [
    ("Transport", [
        ("taxi", "Taxi / Bus / Car"),
        ("vehicule", "Véhicule personnel"),
        ("location", "Location de voiture"),
        ("train", "Train"),
    ]),
    ("Hébergement", [
        ("hotel", "Hôtels"),
        ("heb_forfait", "Forfait"),
    ]),
    ("Repas", [
        ("repas_justif", "Justificatifs"),
        ("repas_forfait", "Forfait"),
    ]),
    ("Divers", [
        ("telephone", "Téléphone"),
        ("peage", "Péage Autoroute"),
        ("gardiennage", "Gardiennage"),
        ("autres", "Autres"),
    ]),
]


def render_mission_note_pdf(note: dict) -> bytes:
    """Note des Frais de Mission (modèle bébleo « Note des frais de mission »).
    `note` = ligne mission_notes (reference, note_date, beneficiary_name,
    beneficiary_cin, accompanied_by, objet, mission_from, mission_to, accorded_by,
    days[], amounts{clé:[montants]}, total). La matrice reproduit la grille
    Thème/Article × jours (J1..J10) avec totaux journaliers et total global."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    W, H = width / mm, height / mm  # dimensions en mm (210 × 297)

    TEAL = _TEAL
    TEAL_DARK = (0.0, 0.44, 0.51)
    WHITE = (1, 1, 1)
    INK = _INK
    MUTED = _MUTED
    GRID = (0.72, 0.72, 0.72)

    MARGIN = 12.0
    RIGHT = W - MARGIN  # 198

    def L(x, y, s, font="Helvetica", size=8, color=INK):
        c.setFont(font, size); c.setFillColorRGB(*color)
        c.drawString(x * mm, y * mm, "" if s is None else str(s))

    def R(x, y, s, font="Helvetica", size=8, color=INK):
        c.setFont(font, size); c.setFillColorRGB(*color)
        c.drawRightString(x * mm, y * mm, "" if s is None else str(s))

    def CC(x, y, s, font="Helvetica", size=8, color=INK):
        c.setFont(font, size); c.setFillColorRGB(*color)
        c.drawCentredString(x * mm, y * mm, "" if s is None else str(s))

    def fill_rect(x, y, w, h, color):
        c.setFillColorRGB(*color); c.rect(x * mm, y * mm, w * mm, h * mm, fill=1, stroke=0)

    def stroke_rect(x, y, w, h, color, lw=0.6):
        c.setStrokeColorRGB(*color); c.setLineWidth(lw)
        c.rect(x * mm, y * mm, w * mm, h * mm, fill=0, stroke=1)

    def hline(x1, x2, y, color, lw=0.4):
        c.setStrokeColorRGB(*color); c.setLineWidth(lw); c.line(x1 * mm, y * mm, x2 * mm, y * mm)

    def vline(x, y1, y2, color, lw=0.4):
        c.setStrokeColorRGB(*color); c.setLineWidth(lw); c.line(x * mm, y1 * mm, x * mm, y2 * mm)

    def nb(v):
        try:
            f = float(v or 0)
            return "" if f == 0 else f"{f:,.2f}".replace(",", " ").replace(".", ",")
        except Exception:
            return ""

    def ell(s, n):
        s = "" if s is None else str(s)
        return s if len(s) <= n else s[: n - 1] + "…"

    def day_short(d):
        if not d:
            return ""
        p = str(d)[:10].split("-")
        return f"{p[2]}/{p[1]}" if len(p) == 3 else str(d)[:5]

    # ── Données ──
    number = note.get("reference") or f"NFM-{str(note.get('id') or '')[:8]}"
    days = list(note.get("days") or [])
    if not days:
        days = [""]                        # au moins une colonne pour la grille
    n = min(len(days), 10)  # doit rester égal à MAX_DAYS (accounting_mission_notes.py)
    days = days[:n]
    amounts = note.get("amounts") or {}
    day_totals = [0.0] * n
    for _, articles in MISSION_CATALOG:
        for key, _lbl in articles:
            row = amounts.get(key) or []
            for i in range(min(n, len(row))):
                try:
                    day_totals[i] += float(row[i] or 0)
                except Exception:
                    pass
    grand_total = note.get("total")
    if grand_total is None:
        grand_total = sum(day_totals)
    grand_total = float(grand_total or 0)

    # ── En-tête : identité + logo ──
    _draw_logo(c, MARGIN, height - 8 * mm, 26, 22)
    tx = MARGIN + 30
    L(tx, H - 12, f"{COMPANY['subtitle']} El Jadida", "Helvetica-Bold", 11, TEAL)
    L(tx, H - 16.5, COMPANY.get("mention") or "", "Helvetica", 8, MUTED)
    L(tx, H - 20.5, COMPANY.get("ofppt") or "", "Helvetica", 8, MUTED)
    R(RIGHT, H - 27, f"El Jadida, le : {_fmt_date_fr(note.get('note_date'))}", "Helvetica", 8.5, INK)
    hline(MARGIN, RIGHT, H - 30, TEAL, 1.0)
    CC(W / 2, H - 38, f"Note des Frais de Mission N° : {number}", "Helvetica-Bold", 15, INK)

    # ── Bloc bénéficiaire / mission ──
    y = H - 46
    L(MARGIN, y, "Nom et Prénom :", "Helvetica-Bold", 8.5, INK)
    L(MARGIN + 28, y, note.get("beneficiary_name") or "—", "Helvetica", 8.5, INK)
    L(MARGIN + 112, y, "CIN :", "Helvetica-Bold", 8.5, INK)
    L(MARGIN + 124, y, note.get("beneficiary_cin") or "—", "Helvetica", 8.5, INK)

    y -= 6
    L(MARGIN, y, "Accompagné par :", "Helvetica-Bold", 8.5, INK)
    acc = _wrap(note.get("accompanied_by"), 78, 2) or ["—"]
    L(MARGIN + 30, y, acc[0], "Helvetica", 8.5, INK)
    for extra in acc[1:]:
        y -= 4.4
        L(MARGIN + 30, y, extra, "Helvetica", 8.5, INK)

    y -= 6
    L(MARGIN, y, "Objet de mission :", "Helvetica-Bold", 8.5, INK)
    obj = _wrap(note.get("objet"), 78, 2) or ["—"]
    L(MARGIN + 30, y, obj[0], "Helvetica", 8.5, INK)
    for extra in obj[1:]:
        y -= 4.4
        L(MARGIN + 30, y, extra, "Helvetica", 8.5, INK)

    y -= 6
    L(MARGIN, y, "Mission du", "Helvetica-Bold", 8.5, INK)
    L(MARGIN + 20, y, _fmt_date_fr(note.get("mission_from")), "Helvetica", 8.5, INK)
    L(MARGIN + 55, y, "au", "Helvetica-Bold", 8.5, INK)
    L(MARGIN + 62, y, _fmt_date_fr(note.get("mission_to")), "Helvetica", 8.5, INK)
    L(MARGIN + 112, y, "Accordée par :", "Helvetica-Bold", 8.5, INK)
    L(MARGIN + 138, y, ell(note.get("accorded_by") or "—", 24), "Helvetica", 8.5, INK)

    # ── Matrice Thème / Article × jours ──
    C_THEME, C_ART, C_DAYS = MARGIN, MARGIN + 24, MARGIN + 58   # 12, 36, 70
    dw = (RIGHT - C_DAYS) / n
    header_h = 10.0
    row_h = 7.0
    th_top = y - 5
    head_bottom = th_top - header_h

    fill_rect(MARGIN, head_bottom, RIGHT - MARGIN, header_h, TEAL)
    CC((C_THEME + C_ART) / 2, head_bottom + 3.4, "Thème", "Helvetica-Bold", 7.5, WHITE)
    CC((C_ART + C_DAYS) / 2, head_bottom + 3.4, "Article", "Helvetica-Bold", 7.5, WHITE)
    for i in range(n):
        cx = C_DAYS + dw * i + dw / 2
        CC(cx, head_bottom + header_h - 3.6, f"J{i + 1}", "Helvetica-Bold", 6.6, WHITE)
        CC(cx, head_bottom + 1.8, day_short(days[i]), "Helvetica", 6.0, WHITE)

    # Lignes d'articles, regroupées par thème.
    yy = head_bottom
    for theme, articles in MISSION_CATALOG:
        grp_top = yy
        for key, label in articles:
            ry = yy - row_h
            L(C_ART + 2, ry + 2.3, ell(label, 26), "Helvetica", 6.8, INK)
            vals = amounts.get(key) or []
            for i in range(n):
                v = vals[i] if i < len(vals) else 0
                if v:
                    R(C_DAYS + dw * (i + 1) - 1.5, ry + 2.3, nb(v), "Helvetica", 6.6, INK)
            hline(C_ART, RIGHT, ry, GRID, 0.3)     # séparateur léger inter-articles
            yy = ry
        grp_bottom = yy
        CC((C_THEME + C_ART) / 2, (grp_top + grp_bottom) / 2 - 1.0, theme, "Helvetica-Bold", 7, TEAL_DARK)
        hline(MARGIN, RIGHT, grp_bottom, TEAL_DARK, 0.6)   # séparateur fort inter-thèmes

    # Ligne « Total Journalier ».
    tj_top = yy
    tj_bottom = yy - row_h
    fill_rect(MARGIN, tj_bottom, RIGHT - MARGIN, row_h, _LIGHT)
    L(C_THEME + 2, tj_bottom + 2.3, "Total Journalier", "Helvetica-Bold", 7, INK)
    for i in range(n):
        if day_totals[i]:
            R(C_DAYS + dw * (i + 1) - 1.5, tj_bottom + 2.3, nb(day_totals[i]), "Helvetica-Bold", 6.8, TEAL_DARK)
    yy = tj_bottom

    # Bordures verticales : C_ART s'arrête au-dessus de la ligne de total (fusion Thème+Article).
    vline(C_ART, tj_top, th_top, GRID, 0.4)
    vline(C_DAYS, yy, th_top, GRID, 0.4)
    for i in range(1, n):
        vline(C_DAYS + dw * i, yy, th_top, GRID, 0.4)
    stroke_rect(MARGIN, yy, RIGHT - MARGIN, th_top - yy, TEAL_DARK, 0.7)

    # ── Total Globale + montant en lettres ──
    gy = yy - 9
    fill_rect(MARGIN, gy, RIGHT - MARGIN, 9, _LIGHT)
    stroke_rect(MARGIN, gy, RIGHT - MARGIN, 9, TEAL_DARK, 0.6)
    L(MARGIN + 3, gy + 3, "Total Globale", "Helvetica-Bold", 9.5, INK)
    R(RIGHT - 3, gy + 3, fmt_mad(grand_total), "Helvetica-Bold", 10.5, TEAL)

    gy -= 6
    L(MARGIN, gy, "Arrêtée la présente note à la somme de :", "Helvetica-Bold", 8, MUTED)
    gy -= 5
    lettres = montant_en_lettres(grand_total)
    L(MARGIN + 2, gy, (lettres[:95] + "…") if len(lettres) > 96 else lettres, "Helvetica-Oblique", 8.5, INK)

    # ── Visas (3 colonnes) ──
    vy = gy - 10
    box_w = (RIGHT - MARGIN - 12) / 3
    for i, lab in enumerate(["Visa Intéressé(e)", "Visa Responsable N+1", "Visa Responsable Comptabilité"]):
        bx = MARGIN + i * (box_w + 6)
        stroke_rect(bx, vy - 22, box_w, 22, (0.8, 0.8, 0.8), 0.5)
        CC(bx + box_w / 2, vy - 5, lab, "Helvetica-Bold", 7.5, MUTED)

    # ── Bandeau de pied de page (teal) ──
    band_h = 12.0
    fill_rect(0, 0, W, band_h, TEAL)
    bits = []
    if COMPANY.get("phone"):
        bits.append(f"Tél : {COMPANY['phone']}")
    if COMPANY.get("website"):
        bits.append(COMPANY["website"])
    if COMPANY.get("email"):
        bits.append(COMPANY["email"])
    CC(W / 2, band_h - 5, COMPANY.get("address") or "", "Helvetica-Bold", 6.8, WHITE)
    CC(W / 2, band_h - 8.6, "   ·   ".join(bits), "Helvetica", 6.6, (0.9, 0.98, 1.0))
    R(RIGHT, band_h + 2.5, f"Généré le {datetime.now().strftime('%d/%m/%Y')}", "Helvetica-Oblique", 6.5, MUTED)

    c.showPage()
    c.save()
    return buf.getvalue()
