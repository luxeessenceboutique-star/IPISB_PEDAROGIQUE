"""The M101 slide template, expressed as editable canvas elements.

Source of the design: the client-approved "M101 - Se situer au regard du
métier et de la démarche de formation" manual. Every colour below was
sampled from that PDF rather than eyeballed, and the geometry is the PDF's
own, converted from its 1467x825 page to the editor's 800x450 design space
(factor 0.545).

WHY THIS IS BUILT OUT OF PLAIN ELEMENTS
Reproducing M101 as a locked "theme" (a background image, a fixed frame)
would have been far less code — and would have broken the one requirement
that matters: the teacher must be able to change literally anything, down
to the decorative motifs. So the pill header, the vertical CHAPITRE tab,
the sage backdrop, the footer, the page number and the dot trames are all
ordinary text/shape/motif elements sitting on the same canvas as the
course content. Nothing is locked; the template is a *starting arrangement*,
not a chrome layer.

Two consumers share this module, which is why the layouts are parameterised
rather than hardcoded:
  * utils/course_slides.py fills them with a chapter's real content;
  * GET /api/courses/slide-layouts serves them, pre-filled with placeholder
    copy, to the editor's "Ajouter une diapositive" picker.
Both therefore stay in step from one definition.
"""
import math

from utils.slide_elements import (
    STAGE_H, STAGE_W, circle, image, line, motif, rect, text, visual,
)

# ─── Palette (sampled from the M101 PDF) ──────────────────────────────────
GREEN = "#007842"        # titres, onglet latéral, badges d'heures
GREEN_DEEP = "#006038"
BLUE = "#214D9A"         # titres du sommaire / de la page de garde
BLUE_DEEP = "#0058A1"
ORANGE = "#FF7800"       # numéros, encadrés
ORANGE_SOFT = "#FF912B"
TEAL_BAND = "#1A5D56"    # bandeau de couverture
TEAL_ACCENT = "#2AB8A7"

INK = "#3F3F3F"
MUTED = "#7E7E7E"
FAINT = "#A8A8A8"
PAPER = "#FFFFFF"

SAGE_BG = "#F2F6F0"      # fond des pages de contenu
SAGE_1 = "#E7EEE2"
SAGE_2 = "#DDEAD6"
SAGE_LINE = "#EFF4EB"

SKY_BG = "#E8F2FA"       # fond des pages d'introduction
SKY_1 = "#DCEAFB"
SKY_2 = "#C9E0FF"
ICE_BG = "#EAFCFC"

LINE = "#D9D9D9"
PILL_LINE = "#BFC7BE"
PILL_FILL = "#F4F8F2"

# Served from frontend/public/ — static assets shared by the editor canvas,
# the student viewer and any deck the generator produces. Two crops of the
# same source mark: LOGO_SRC is the icon alone (hands + caduceus + book,
# transparent) for the small corner mark that sits next to hand-drawn
# institute-name text everywhere in this file; LOGO_FULL_SRC is the
# complete lockup with the institute's name baked in, sized for use as a
# standalone mark rather than a paired icon+caption.
LOGO_SRC = "/ipisb-logo.png"
LOGO_FULL_SRC = "/ipisb-logo-full.png"
LOGO_FULL_ASPECT = 352 / 313  # height / width of the source crop

# Card geometry, reused by every content layout so headings, body copy and
# visuals line up from one slide to the next.
CARD_X, CARD_Y, CARD_W, CARD_H = 35, 94, 730, 339
BODY_X = CARD_X + 18          # 53
BODY_W = CARD_W - 36          # 694
BODY_TOP = 136                # first line under the card's own heading
BODY_BOTTOM = CARD_Y + CARD_H - 18  # 415


# ─── Shared chrome ────────────────────────────────────────────────────────
def _sage_backdrop() -> list[dict]:
    """The pale sage ground with its faint canopy shapes and column rules.
    Only the strips above and below the white card ever show, which is
    exactly how it reads in the PDF."""
    els: list[dict] = []
    for x in (383, 468, 553, 638, 723):
        els.append(rect(x, 0, 2, STAGE_H, fill=SAGE_LINE))
    els.append(circle(445, -20, 90, 110, fill=SAGE_1))
    els.append(circle(556, -34, 100, 124, fill=SAGE_1))
    els.append(circle(608, 6, 70, 92, fill=SAGE_2))
    els.append(circle(700, 28, 60, 62, fill=SAGE_1))
    els.append(circle(88, 398, 132, 92, fill=SAGE_1))
    els.append(circle(756, 378, 84, 84, fill=SAGE_1))
    return els


def _fit(value: str, max_chars: int) -> str:
    """The pill's two lines are single-line by design, and the box can't
    grow without breaking the stadium shape. M101's own kicker is a short
    part name; our module titles are arbitrarily long, and left alone they
    wrapped onto the subtitle. Truncating keeps the header legible — and the
    teacher can always retype the line, since it's an ordinary text
    element."""
    value = (value or "").strip()
    return value if len(value) <= max_chars else value[: max_chars - 1].rstrip() + "…"


def _header_pill(kicker: str, subtitle: str) -> list[dict]:
    """The stadium-shaped header. Its left rounding sits off-canvas on
    purpose — in the PDF the pill is flush to the page edge and only the
    right side is rounded."""
    return [
        rect(-30, 16, 378, 72, fill=PAPER, stroke="#C9C9C9", stroke_width=1, radius=36),
        rect(-30, 11, 372, 70, fill=PILL_FILL, stroke=PILL_LINE, stroke_width=1, radius=35),
        rect(-30, 81, 375, 2, fill="#C9C9C9"),
        # Char budgets measured against the 320px box at these sizes.
        text(17, 22, 320, 18, _fit(kicker, 44), size=12.5, bold=True, color=GREEN),
        text(17, 43, 320, 16, _fit(subtitle, 52), size=10.5, bold=True, color=GREEN),
    ]


def _side_tab(label: str) -> list[dict]:
    """Rotation is applied about the element's top-left corner, so a box of
    width 88 rotated -90° from (10, 421) occupies x 10..26, y 333..421 —
    the vertical green tab hugging the left edge."""
    return [
        rect(0, 333, 35, 88, fill=GREEN),
        text(10, 421, 88, 16, label, size=11, bold=True, align="center", color=PAPER, rotation=-90),
    ]


def _footer(page_num: int | None) -> list[dict]:
    els = [text(250, 436, 300, 12, "Copyright · Tous droits réservés · IPISB",
                size=7, align="center", color=FAINT)]
    if page_num is not None:
        els.append(text(735, 436, 30, 12, f"{page_num}", size=7, align="right", color=FAINT))
    return els


def content_chrome(kicker: str, subtitle: str, tab_label: str, page_num: int | None) -> list[dict]:
    """Everything a content slide has before its own content: backdrop, pill
    header, logo, white card, side tab, footer."""
    return [
        *_sage_backdrop(),
        *_header_pill(kicker, subtitle),
        image(655, 27, 42, 45, LOGO_SRC),
        rect(CARD_X, CARD_Y, CARD_W, CARD_H, fill=PAPER, stroke=LINE, stroke_width=1),
        *_side_tab(tab_label),
        *_footer(page_num),
    ]


def _card_heading(heading: str) -> dict:
    return text(BODY_X, 106, 500, 20, heading, size=13, bold=True, color=GREEN)


def _sky_backdrop() -> list[dict]:
    """The blue organic blob filling the left of the intro pages: a straight
    panel softened by an oversized ellipse so the right edge bulges."""
    return [
        rect(0, 0, 380, STAGE_H, fill=SKY_BG),
        circle(255, -30, 250, 510, fill=SKY_BG),
        circle(120, 150, 150, 190, fill=SKY_1, opacity=0.55),
    ]


def brand_panel(x: float, y: float, w: float, h: float, *, tone: str = SKY_1) -> list[dict]:
    """The default fill for a STRUCTURAL illustration slot (cover, splash,
    sommaire, chapter/part intro) when no photo has been supplied: a tinted
    panel carrying concentric rings, a dot trame and the full IPISB lockup
    mark, rather than a dashed "drop an image here" box. This is a genuine
    design, not a filler — M101's own equivalent slots hold stock people
    illustrations we were never given a licence or asset for (see the scope
    decision in this module's docstring), so recurring brand marks are the
    honest substitute rather than an empty page.

    CONTENT-slot illustrations (the ones inside a chapter's own material —
    content_text_image, content_bullets_visuals, content_image_strip) stay
    on the plain visual() placeholder: those are prompts for the teacher's
    own subject photo, and dressing them up would look wrong once a real
    image replaces them, and misleading before that happens (a decorated
    frame reads as "already filled" and invites nobody to add a photo)."""
    base = min(w, h)
    cx, cy = x + w * 0.82, y + h * 0.86
    els: list[dict] = [rect(x, y, w, h, fill=tone, radius=6)]
    for i, scale in enumerate((0.95, 0.68, 0.44)):
        d = base * scale
        els.append(circle(cx - d / 2, cy - d / 2, d, d, fill="transparent",
                          stroke=GREEN, stroke_width=1.4, opacity=0.16 + i * 0.05))
    els.append(motif(x + w * 0.05, y + h * 0.06, w * 0.2, h * 0.2, color=GREEN, dot=2.2, gap=11, opacity=0.3))

    logo_w = base * 0.5
    logo_h = logo_w * LOGO_FULL_ASPECT
    lx, ly = x + w / 2 - logo_w / 2, y + h / 2 - logo_h / 2 - h * 0.04
    els.append(image(lx, ly, logo_w, logo_h, LOGO_FULL_SRC))
    els.append(rect(x + w / 2 - base * 0.08, ly + logo_h + h * 0.045, base * 0.16, 2.2, fill=ORANGE))
    return els


def structure_visual(x: float, y: float, w: float, h: float, *, src: str | None = None, tone: str = SKY_1) -> list[dict]:
    """Structural-slide equivalent of visual(): a real photo when one was
    supplied, the brand panel above otherwise."""
    if src:
        return [image(x, y, w, h, src)]
    return brand_panel(x, y, w, h, tone=tone)


def _hours_badge(x: float, y: float, label: str, color: str = GREEN) -> list[dict]:
    cx, cy, d = x + 16, y + 10, 24
    return [
        rect(x, y, 145, 44, fill=color, radius=2),
        circle(cx, cy, d, d, fill="transparent", stroke=PAPER, stroke_width=1.6),
        line(cx + d / 2, cy + d / 2, 0, -7, stroke=PAPER, stroke_width=1.4),
        line(cx + d / 2, cy + d / 2, 5.5, 0, stroke=PAPER, stroke_width=1.4),
        text(x + 48, y + 11, 88, 24, label, size=15, bold=True, color=PAPER),
    ]


def _bullets(items: list[str]) -> str:
    return "\n".join(f"•  {i}" for i in items if str(i).strip())


# ─── Structure layouts ────────────────────────────────────────────────────
def cover(
    *, module_code: str = "M101", module_title: str = "Titre du module",
    filiere: str = "Soins Infirmiers et Paramédicaux", annee: str = "1ère Année",
    version: str = "2026", niveau: str = "Technicien spécialisé", src: str | None = None,
) -> list[dict]:
    """The manual cover, adapted from the PDF's portrait page to 16:9 —
    same trames, same teal band, same rotated diamonds, re-proportioned."""
    return [
        rect(0, 0, STAGE_W, STAGE_H, fill=PAPER),
        motif(28, 24, 130, 96, color="#C9D9D6", dot=2.4, gap=13),
        motif(28, 300, 130, 126, color="#C9D9D6", dot=2.4, gap=13),
        motif(600, 18, 170, 78, color="#C9D9D6", dot=2.4, gap=13),
        image(690, 22, 62, 66, LOGO_SRC),
        text(430, 30, 250, 16, "Institut Privé d'Innovation", size=10, bold=True, align="center", color=INK),
        text(430, 46, 250, 16, "en Santé et Bien-être · El Jadida", size=9, align="center", color=MUTED),
        text(430, 63, 250, 14, "Direction de la Recherche et Ingénierie de formation",
             size=7, align="center", color=MUTED),
        # Rotated diamonds with the health cross, right-hand side
        rect(548, 148, 104, 104, fill="#1E6FBF", rotation=45, opacity=0.92),
        rect(636, 108, 116, 116, fill="#17A08C", rotation=45),
        rect(648, 236, 96, 96, fill="#E58A16", rotation=45),
        # A square rotated 45° about its top-left corner centres on
        # (x, y + side/√2) — 96/√2 ≈ 67.9 — so the health cross is placed
        # against that, not against the unrotated box.
        rect(643, 288, 10, 32, fill=PAPER),
        rect(632, 299, 32, 10, fill=PAPER),
        text(196, 122, 300, 14, "Secteur : SANTÉ & BIEN-ÊTRE", size=9, bold=True, color=TEAL_ACCENT),
        text(196, 138, 300, 14, "Manuel de cours", size=9, color=INK),
        rect(196, 100, 180, 2, fill=TEAL_ACCENT),
        rect(0, 168, 470, 96, fill=TEAL_BAND),
        text(22, 182, 430, 70, f"{module_code} : {module_title}", size=19, bold=True, color=PAPER),
        text(22, 284, 300, 18, annee, size=12, color=INK),
        text(22, 306, 300, 14, "Filière :", size=8.5, color=ORANGE),
        rect(22, 322, 210, 1.5, fill=ORANGE),
        text(22, 330, 320, 50, filiere, size=15, bold=True, color=BLUE),
        rect(24, 392, 46, 46, fill=PAPER, stroke=ORANGE, stroke_width=1.5),
        *visual(30, 398, 34, 34, label="QR", src=src, fill=PAPER, stroke="#111111", caption_color=INK),
        text(330, 424, 140, 12, f"Version : {version}", size=7, align="center", color=MUTED),
        rect(624, 416, 148, 22, fill=TEAL_BAND),
        text(624, 421, 148, 14, niveau, size=8.5, align="center", color=PAPER),
    ]


def thanks(
    *, teams: list[dict] | None = None,
    note: str = "Les utilisateurs de ce document sont invités à communiquer à l'Institut toutes les "
                "remarques et suggestions afin de les prendre en considération pour l'enrichissement "
                "et l'amélioration de ce module.",
) -> list[dict]:
    teams = teams or [
        {"title": "ÉQUIPE DE CONCEPTION", "members": ["Prénom Nom, fonction, structure"]},
        {"title": "ÉQUIPE DE RÉDACTION", "members": ["Prénom Nom, fonction, structure"]},
        {"title": "ÉQUIPE DE LECTURE", "members": ["Prénom Nom, fonction, structure"]},
        {"title": "ÉQUIPE DE VALIDATION", "members": ["Direction Pédagogique — IPISB El Jadida"]},
    ]
    els: list[dict] = [
        rect(0, 0, STAGE_W, STAGE_H, fill=PAPER),
        motif(600, 12, 170, 70, color="#D6E3E1", dot=2.4, gap=13),
        image(700, 16, 42, 45, LOGO_SRC),
        text(200, 28, 400, 34, "Remerciements", size=26, align="center", color="#B9C2BE"),
        rect(345, 66, 110, 2.5, fill=TEAL_ACCENT),
        text(52, 88, 700, 26,
             "L'Institut Privé d'Innovation en Santé et Bien-être remercie les personnes qui ont "
             "contribué à l'élaboration du présent document :", size=9, color=INK),
    ]
    y = 126
    for team in teams:
        els.append(rect(52, y, 3.5, 14, fill=TEAL_ACCENT))
        els.append(text(62, y, 400, 14, team["title"], size=10, bold=True, color=INK))
        members = "\n".join(team.get("members") or [])
        h = max(16, 13 * len(team.get("members") or [1]))
        els.append(text(110, y + 18, 600, h, members, size=9, color=INK))
        y += 26 + h
    els.append(text(52, min(y + 6, 392), 700, 34, note, size=8, italic=True, color=MUTED))
    els.extend(_footer(1))
    return els


def splash(
    *, title: str = "RÉSUMÉ THÉORIQUE", subtitle: str = "M101 — Titre du module",
    hours: str = "15 heures", src: str | None = None,
) -> list[dict]:
    return [
        rect(0, 0, STAGE_W, STAGE_H, fill=ICE_BG),
        image(300, 18, 44, 47, LOGO_SRC),
        text(352, 24, 260, 18, "Institut Privé d'Innovation", size=12, bold=True, color=GREEN_DEEP),
        text(352, 42, 260, 16, "en Santé et Bien-être El Jadida", size=11, color=TEAL_ACCENT),
        *structure_visual(0, 78, STAGE_W, 232, src=src, tone="#DFF3F5"),
        rect(0, 310, STAGE_W, 140, fill=PAPER),
        text(60, 326, 680, 24, title, size=17, bold=True, align="center", color=BLUE_DEEP),
        text(60, 352, 680, 24, subtitle, size=15, bold=True, align="center", color=BLUE_DEEP),
        *_hours_badge(328, 392, hours, color=BLUE_DEEP),
    ]


def sommaire(*, parts: list[dict] | None = None, src: str | None = None) -> list[dict]:
    parts = parts or [
        {"number": "01", "title": "TITRE DE LA PREMIÈRE PARTIE",
         "items": ["Premier objectif", "Deuxième objectif"]},
        {"number": "02", "title": "TITRE DE LA SECONDE PARTIE",
         "items": ["Premier objectif", "Deuxième objectif", "Troisième objectif"]},
    ]
    els: list[dict] = [
        rect(0, 0, STAGE_W, STAGE_H, fill="#F3FAFF"),
        rect(0, 0, 400, STAGE_H, fill=SKY_1),
        circle(270, -40, 260, 530, fill=SKY_1),
        image(22, 16, 40, 43, LOGO_SRC),
        text(150, 76, 260, 40, "SOMMAIRE", size=27, bold=True, align="center", color=BLUE),
        *structure_visual(40, 150, 330, 270, src=src, tone=SKY_2),
    ]
    y = 96
    for part in parts:
        els.append(text(420, y, 350, 34, f"{part['number']} – {part['title']}",
                        size=12.5, bold=True, align="center", color=BLUE))
        y += 36
        items = part.get("items") or []
        h = max(16, 15 * len(items))
        els.append(text(420, y, 350, h, "\n".join(items), size=10, align="center", color=INK))
        y += h + 16
    return els


def modalites(*, title: str = "MODALITÉS PÉDAGOGIQUES", columns: list[dict] | None = None) -> list[dict]:
    columns = columns or [
        {"title": "LE GUIDE DE SOUTIEN", "body": "Il contient le résumé théorique et le manuel des travaux pratiques"},
        {"title": "LA VERSION PDF", "body": "Une version PDF est mise en ligne sur l'espace apprenant et formateur"},
        {"title": "DES CONTENUS TÉLÉCHARGEABLES", "body": "Les fiches de résumés et les exercices sont téléchargeables"},
        {"title": "DU CONTENU INTERACTIF", "body": "Des contenus interactifs sous forme d'exercices et de cours"},
        {"title": "DES RESSOURCES EN LIGNE", "body": "Consultables en synchrone et en asynchrone, à votre rythme"},
    ]
    els: list[dict] = [
        rect(0, 0, STAGE_W, STAGE_H, fill="#E7EFFF"),
        *_header_pill(title, ""),
        image(748, 24, 36, 39, LOGO_SRC),
        rect(115, 106, 570, 293, fill=PAPER, stroke=LINE, stroke_width=1),
    ]
    n = len(columns)
    col_w = 104
    gap = (570 - 30 - n * col_w) / max(n - 1, 1)
    for i, col in enumerate(columns):
        x = 130 + i * (col_w + gap)
        els.extend(visual(x + 22, 122, 60, 48, label="", src=None,
                          fill="#EDF4FF", stroke="#BBD3F5", caption_color="#8FAAD0"))
        els.append(circle(x + 33, 182, 38, 38, fill=PAPER, stroke=ORANGE, stroke_width=2))
        els.append(text(x + 33, 192, 38, 20, str(i + 1), size=14, bold=True, align="center", color=BLUE_DEEP))
        els.append(rect(x, 228, col_w, 158, fill=PAPER, stroke=ORANGE, stroke_width=1.5))
        els.append(text(x + 4, 236, col_w - 8, 30, col["title"], size=8, bold=True, align="center", color=BLUE_DEEP))
        els.append(text(x + 4, 268, col_w - 8, 112, col["body"], size=8, align="center", color=INK))
    els.extend(_footer(3))
    return els


def _intro(
    *, kicker: str, title: str, lead: str, items: list[str],
    hours: str | None, src: str | None,
) -> list[dict]:
    els = [
        rect(0, 0, STAGE_W, STAGE_H, fill=PAPER),
        *_sky_backdrop(),
        image(37, 22, 52, 56, LOGO_SRC),
        *structure_visual(27, 106, 352, 330, src=src),
        text(420, 40, 350, 26, kicker, size=20, bold=True, align="center", color=GREEN),
        text(410, 72, 370, 48, title, size=17, bold=True, align="center", color=GREEN),
        text(418, 158, 355, 18, lead, size=12, bold=True, color=GREEN),
        text(418, 192, 355, 130, _bullets(items), size=10.5, color=INK),
    ]
    if hours:
        els.extend(_hours_badge(525, 402, hours))
    return els


def part_intro(
    *, number: int = 1, title: str = "TITRE DE LA PARTIE",
    items: list[str] | None = None, hours: str | None = "06 heures", src: str | None = None,
) -> list[dict]:
    return _intro(
        kicker=f"PARTIE {number}", title=title, lead="Dans ce module, vous allez :",
        items=items or ["Premier objectif de la partie", "Deuxième objectif de la partie"],
        hours=hours, src=src,
    )


def chapter_intro(
    *, number: int = 1, title: str = "TITRE DU CHAPITRE",
    items: list[str] | None = None, hours: str | None = "03 heures", src: str | None = None,
) -> list[dict]:
    return _intro(
        kicker=f"CHAPITRE {number}", title=title,
        lead="Ce que vous allez apprendre dans ce chapitre :",
        items=items or ["Première notion abordée", "Deuxième notion abordée"],
        hours=hours, src=src,
    )


def chapter_toc(
    *, number: int = 1, title: str = "TITRE DU CHAPITRE",
    entries: list[str] | None = None, active: int = 0, src: str | None = None,
) -> list[dict]:
    """The chapter's own plan, with the section being opened set in bold —
    the PDF repeats this slide between sections with the highlight moved."""
    entries = entries or ["Première section du chapitre", "Deuxième section du chapitre"]
    els = [
        rect(0, 0, STAGE_W, STAGE_H, fill=PAPER),
        *_sky_backdrop(),
        image(37, 22, 52, 56, LOGO_SRC),
        *structure_visual(27, 106, 352, 330, src=src),
        text(420, 40, 350, 26, f"CHAPITRE {number}", size=20, bold=True, align="center", color=GREEN),
        text(410, 72, 370, 48, title, size=17, bold=True, align="center", color=GREEN),
    ]
    y = 178
    for i, entry in enumerate(entries):
        on = i == active
        els.append(text(418, y, 22, 20, f"{i + 1}.", size=11, bold=on, color=INK if on else MUTED))
        els.append(text(442, y, 330, 34, entry, size=11, bold=on, color=INK if on else MUTED))
        y += 38
    return els


# ─── Content layouts ──────────────────────────────────────────────────────
def content_text(
    *, kicker: str = "01 – TITRE DE LA SECTION", subtitle: str = "Sous-titre",
    heading: str = "Titre du contenu", body: str = "Rédigez votre contenu ici.",
    tab_label: str = "CHAPITRE 1", page_num: int | None = None,
) -> list[dict]:
    return [
        *content_chrome(kicker, subtitle, tab_label, page_num),
        _card_heading(heading),
        text(BODY_X, BODY_TOP, BODY_W, BODY_BOTTOM - BODY_TOP, body, size=10.5, color=INK),
    ]


def content_bullets(
    *, kicker: str = "01 – TITRE DE LA SECTION", subtitle: str = "Sous-titre",
    heading: str = "Titre du contenu", lead: str = "", items: list[str] | None = None,
    tab_label: str = "CHAPITRE 1", page_num: int | None = None,
) -> list[dict]:
    items = items or ["Premier point", "Deuxième point", "Troisième point"]
    els = [*content_chrome(kicker, subtitle, tab_label, page_num), _card_heading(heading)]
    y = BODY_TOP
    if lead:
        els.append(text(BODY_X, y, BODY_W, 20, lead, size=10.5, color=INK))
        y += 26
    els.append(text(BODY_X + 12, y, BODY_W - 12, BODY_BOTTOM - y, _bullets(items), size=10.5, color=INK))
    return els


def content_text_image(
    *, kicker: str = "01 – TITRE DE LA SECTION", subtitle: str = "Sous-titre",
    heading: str = "Titre du contenu", body: str = "Rédigez votre contenu ici.",
    src: str | None = None, tab_label: str = "CHAPITRE 1", page_num: int | None = None,
) -> list[dict]:
    return [
        *content_chrome(kicker, subtitle, tab_label, page_num),
        _card_heading(heading),
        text(BODY_X, BODY_TOP, 372, BODY_BOTTOM - BODY_TOP, body, size=10.5, color=INK),
        *visual(444, BODY_TOP, 303, 262, label="Exemple · Schéma", src=src),
    ]


def content_bullets_visuals(
    *, kicker: str = "01 – TITRE DE LA SECTION", subtitle: str = "Sous-titre",
    heading: str = "Titre du contenu", lead: str = "", items: list[str] | None = None,
    sources: list[str] | None = None, tab_label: str = "CHAPITRE 1", page_num: int | None = None,
) -> list[dict]:
    """Puces en haut, deux visuels en bas — la mise en page des pages
    « secteur » du M101."""
    items = items or ["Premier point", "Deuxième point", "Troisième point"]
    sources = sources or []
    els = [*content_chrome(kicker, subtitle, tab_label, page_num), _card_heading(heading)]
    y = BODY_TOP
    if lead:
        els.append(text(BODY_X, y, BODY_W, 20, lead, size=10.5, color=INK))
        y += 24
    els.append(text(BODY_X + 20, y, BODY_W - 20, 116, _bullets(items), size=10, color=INK))
    for i in range(2):
        els.extend(visual(96 + i * 328, 288, 300, 118,
                          label="Exemple · Illustration", src=sources[i] if i < len(sources) else None))
    return els


def content_image_strip(
    *, kicker: str = "01 – TITRE DE LA SECTION", subtitle: str = "Sous-titre",
    heading: str = "Titre du contenu", lead: str = "", items: list[str] | None = None,
    sources: list[str] | None = None, count: int = 5,
    tab_label: str = "CHAPITRE 1", page_num: int | None = None,
) -> list[dict]:
    """Texte en haut, bande de visuels en bas — la page « applications »."""
    items = items or ["Première application", "Deuxième application", "Troisième application"]
    sources = sources or []
    els = [*content_chrome(kicker, subtitle, tab_label, page_num), _card_heading(heading)]
    y = BODY_TOP
    if lead:
        els.append(text(BODY_X, y, BODY_W, 20, lead, size=10.5, color=INK))
        y += 24
    els.append(text(BODY_X + 20, y, BODY_W - 20, 108, _bullets(items), size=10, color=INK))
    gap = 10
    w = (BODY_W - gap * (count - 1)) / count
    for i in range(count):
        els.extend(visual(BODY_X + i * (w + gap), 296, w, 106,
                          label="Visuel", src=sources[i] if i < len(sources) else None))
    return els


def content_icon_grid(
    *, kicker: str = "01 – TITRE DE LA SECTION", subtitle: str = "Sous-titre",
    heading: str = "Titre du contenu", labels: list[str] | None = None,
    per_row: int = 6, tab_label: str = "CHAPITRE 1", page_num: int | None = None,
) -> list[dict]:
    """Grille de vignettes légendées — la page « secteurs d'activité »."""
    labels = labels or ["Premier", "Deuxième", "Troisième", "Quatrième", "Cinquième", "Sixième"]
    els = [*content_chrome(kicker, subtitle, tab_label, page_num), _card_heading(heading)]
    cell_w = BODY_W / per_row
    for i, label in enumerate(labels):
        row, col = divmod(i, per_row)
        cx = BODY_X + col * cell_w
        cy = 148 + row * 126
        els.append(rect(cx + cell_w / 2 - 26, cy, 52, 52, fill=PAPER, stroke="#BFD6BE", stroke_width=1, radius=3))
        els.append(text(cx + cell_w / 2 - 26, cy + 18, 52, 18, "◇", size=15, align="center", color="#63A644"))
        els.append(text(cx + 4, cy + 62, cell_w - 8, 44, label, size=9, align="center", color=MUTED))
    return els


def content_diagram(
    *, kicker: str = "01 – TITRE DE LA SECTION", subtitle: str = "Sous-titre",
    heading: str = "Titre du contenu", lead: str = "",
    node: str = "CONCEPT", satellites: list[str] | None = None,
    tab_label: str = "CHAPITRE 1", page_num: int | None = None,
) -> list[dict]:
    """Schéma en étoile : un concept central relié à ses composantes."""
    satellites = satellites or ["Composante 1", "Composante 2", "Composante 3",
                                "Composante 4", "Composante 5", "Composante 6"]
    els = [*content_chrome(kicker, subtitle, tab_label, page_num), _card_heading(heading)]
    y = BODY_TOP
    if lead:
        els.append(text(BODY_X, y, BODY_W, 30, lead, size=10, color=INK))
        y += 30
    cx, cy = 400, (y + BODY_BOTTOM) / 2
    n = max(len(satellites), 1)
    for i, label in enumerate(satellites):
        ang = -math.pi / 2 + (2 * math.pi * i) / n
        px, py = cx + 176 * math.cos(ang), cy + 104 * math.sin(ang)
        ex, ey = cx + 50 * math.cos(ang), cy + 42 * math.sin(ang)
        lx, ly = px - 26 * math.cos(ang), py - 16 * math.sin(ang)
        els.append(line(ex, ey, lx - ex, ly - ey, stroke=GREEN, stroke_width=0.8, opacity=0.7))
        els.append(text(px - 62, py - 14, 124, 28, label, size=9.5, align="center", color=INK))
    els.append(rect(cx - 45, cy - 38, 90, 76, fill=PAPER, stroke=GREEN, stroke_width=1.5, radius=10))
    els.append(text(cx - 45, cy - 9, 90, 18, node, size=12, bold=True, align="center", color=GREEN))
    return els


# ─── Catalogue ────────────────────────────────────────────────────────────
# `group` drives the picker's section headings; `background` is the slide's
# own ground colour (elements paint over it).
LAYOUTS: list[dict] = [
    {"id": "cover", "name": "Couverture", "group": "Structure",
     "description": "Couverture du manuel : trames, bandeau, filière", "build": cover, "background": PAPER},
    {"id": "thanks", "name": "Remerciements", "group": "Structure",
     "description": "Équipes de conception, rédaction, lecture, validation", "build": thanks, "background": PAPER},
    {"id": "splash", "name": "Page de garde", "group": "Structure",
     "description": "Grande illustration + titre + volume horaire", "build": splash, "background": ICE_BG},
    {"id": "sommaire", "name": "Sommaire", "group": "Structure",
     "description": "Parties numérotées et leurs objectifs", "build": sommaire, "background": "#F3FAFF"},
    {"id": "modalites", "name": "Modalités pédagogiques", "group": "Structure",
     "description": "Cinq colonnes numérotées encadrées", "build": modalites, "background": "#E7EFFF"},
    {"id": "part_intro", "name": "Intro de partie", "group": "Structure",
     "description": "PARTIE n : objectifs + volume horaire", "build": part_intro, "background": PAPER},
    {"id": "chapter_intro", "name": "Intro de chapitre", "group": "Structure",
     "description": "CHAPITRE n : ce que vous allez apprendre", "build": chapter_intro, "background": PAPER},
    {"id": "chapter_toc", "name": "Plan du chapitre", "group": "Structure",
     "description": "Sections numérotées, la section courante en gras", "build": chapter_toc, "background": PAPER},

    {"id": "content_text", "name": "Titre + texte", "group": "Contenu",
     "description": "Carte pleine largeur", "build": content_text, "background": SAGE_BG},
    {"id": "content_bullets", "name": "Titre + puces", "group": "Contenu",
     "description": "Liste à puces pleine largeur", "build": content_bullets, "background": SAGE_BG},
    {"id": "content_text_image", "name": "Texte + visuel", "group": "Contenu",
     "description": "Texte à gauche, illustration à droite", "build": content_text_image, "background": SAGE_BG},
    {"id": "content_bullets_visuals", "name": "Puces + deux visuels", "group": "Contenu",
     "description": "Puces en haut, deux illustrations en bas", "build": content_bullets_visuals, "background": SAGE_BG},
    {"id": "content_image_strip", "name": "Puces + bande de visuels", "group": "Contenu",
     "description": "Puces puis une bande de cinq vignettes", "build": content_image_strip, "background": SAGE_BG},
    {"id": "content_icon_grid", "name": "Grille de vignettes", "group": "Contenu",
     "description": "Vignettes légendées sur deux rangées", "build": content_icon_grid, "background": SAGE_BG},
    {"id": "content_diagram", "name": "Schéma en étoile", "group": "Contenu",
     "description": "Concept central relié à ses composantes", "build": content_diagram, "background": SAGE_BG},
]

_BY_ID = {layout["id"]: layout for layout in LAYOUTS}


def build(layout_id: str, **kwargs) -> tuple[list[dict], str | None]:
    """Returns (elements, background) for a layout. Unknown ids fall back to
    the plain content card rather than raising — a template id that drifts
    should degrade to a usable slide, never lose a teacher's generation."""
    layout = _BY_ID.get(layout_id) or _BY_ID["content_text"]
    return layout["build"](**kwargs), layout.get("background")


def catalogue() -> list[dict]:
    """The picker's payload: every layout pre-built with placeholder copy, so
    the editor renders real thumbnails and inserts real elements without
    duplicating a single coordinate in TypeScript."""
    return [
        {
            "id": layout["id"], "name": layout["name"],
            "description": layout["description"], "group": layout["group"],
            "background": layout.get("background"),
            "elements": layout["build"](),
        }
        for layout in LAYOUTS
    ]
