"""Turns an already-generated chapter (course_modules + its lesson's markdown)
into an initial slide deck laid out with the M101 template.

Section splitting is the same logic already proven out for the PPTX export
(utils/course_pptx.py's split_sections) — the chapter text was shaped by the
AI into heading-sized sections, so re-deriving that structure here is a
mechanical transform, not a fresh AI call. What changed is the *rendering*:
instead of a bare title + one plain text box per section, each section is
poured into the M101 layout that suits its shape (utils/slide_template_m101).

DECK LENGTH IS NOT FIXED. The template is a vocabulary of layouts, not a
13-page form. One slide is emitted per section, sections spill onto
continuation slides when they outrun a card, and the teacher can add any
number of further slides from the same layouts in the editor. A short
chapter is a short deck; a long one is a long deck.

IMPORTANT: this only ever produces the STARTING POINT for a deck the teacher
then edits by hand. It is never re-run silently over an existing hand-edited
deck (the router enforces a confirm/force flag), matching the "course is the
source of truth, not a regenerate-and-clobber pipeline" rule the whole
feature is built around. Every element it emits — including the decorative
chrome — is a normal editable object.
"""
import re

from utils import slide_template_m101 as m101
from utils.course_pptx import split_sections
from utils.slide_elements import slide

STAGE_W = 800
STAGE_H = 450

# A section longer than this gets the full-width card; shorter ones leave
# room for a visual alongside. Tuned against the card's text box at 10.5pt.
WIDE_TEXT_THRESHOLD = 520
BULLET_RE = re.compile(r"^\s*(?:[•\-*]|\d+[.)])\s+(.+)$")


def _as_bullets(text: str) -> list[str]:
    """Bullet lines already marked up in the generated markdown. Returns []
    when the text is prose, which is what selects a prose layout below."""
    return [m.group(1).strip() for line in text.splitlines() if (m := BULLET_RE.match(line))]


def _lead_in(text: str, bullets: list[str]) -> str:
    """The sentence introducing a bullet list ("L'IA se déploie dans …  :"),
    kept as its own line above the list the way the template renders it."""
    if not bullets:
        return ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not BULLET_RE.match(line):
            return stripped
    return ""


def _objective_items(objectives: str | None) -> list[str]:
    """Chapter objectives are stored as free text — one per line, sometimes
    already bulleted, sometimes a single sentence."""
    if not (objectives or "").strip():
        return []
    lines = [line.strip() for line in objectives.splitlines() if line.strip()]
    return [BULLET_RE.match(line).group(1) if BULLET_RE.match(line) else line for line in lines]


def _hours_label(hours: float | None) -> str | None:
    if not hours:
        return None
    value = int(hours) if float(hours).is_integer() else hours
    return f"{value:02d} heures" if isinstance(value, int) else f"{value} heures"


def generate_slide_deck(
    module_title: str,
    objectives: str | None,
    content: str,
    image_urls: list[str],
    *,
    chapter_number: int = 1,
    hours: float | None = None,
) -> list[dict]:
    sections = split_sections(content) if content else []
    # The kicker line repeats the chapter across every content slide, exactly
    # as the template does ("01 – S'INFORMER SUR LE MARCHÉ DU TRAVAIL").
    kicker = f"{chapter_number:02d} – {module_title.upper()}"
    tab_label = f"CHAPITRE {chapter_number}"

    slides: list[dict] = []

    # `slide_title` is the name shown in the editor's slide rail — kept
    # distinct from the layouts' own `title=` kwarg, which is course copy.
    def add(layout_id: str, slide_title: str, **kwargs) -> None:
        elements, background = m101.build(layout_id, **kwargs)
        slides.append(slide(slide_title, elements, background=background))

    # 1. Chapter opener — objectives + hours, illustrated with the chapter's
    #    own first image when the teacher already uploaded one.
    add("chapter_intro", "Intro de chapitre",
        number=chapter_number, title=module_title,
        items=_objective_items(objectives), hours=_hours_label(hours),
        src=image_urls[0] if image_urls else None)

    # 2. Chapter plan — only worth a slide once there is more than one section.
    headings: list[str] = []
    for section in sections:
        base = section["heading"]
        if "(suite)" not in base and base not in headings:
            headings.append(base)
    if len(headings) > 1:
        add("chapter_toc", "Plan du chapitre",
            number=chapter_number, title=module_title, entries=headings, active=0,
            src=image_urls[0] if image_urls else None)

    # 3. One slide per section, in the layout that fits what the section
    #    actually contains. Images left over after the opener are handed out
    #    in order, so an illustrated chapter fills its frames instead of
    #    showing empty placeholders next to real photos.
    spare_images = list(image_urls[1:])

    def take_image() -> str | None:
        return spare_images.pop(0) if spare_images else None

    for section in sections:
        heading = section["heading"]
        body = section["text"]
        bullets = _as_bullets(body)
        common = {"kicker": kicker, "subtitle": heading, "heading": heading,
                  "tab_label": tab_label, "page_num": len(slides) + 1}

        if len(bullets) >= 3:
            add("content_bullets_visuals", heading, **common,
                lead=_lead_in(body, bullets), items=bullets,
                sources=[s for s in (take_image(), take_image()) if s])
        elif bullets:
            add("content_bullets", heading, **common, lead=_lead_in(body, bullets), items=bullets)
        elif len(body) > WIDE_TEXT_THRESHOLD:
            add("content_text", heading, **common, body=body)
        else:
            add("content_text_image", heading, **common, body=body, src=take_image())

    # A chapter with no generated text still gets a usable deck rather than a
    # lone opener — the teacher writes straight onto the card.
    if not sections:
        add("content_text", "Contenu",
            kicker=kicker, subtitle=module_title, heading=module_title,
            body="", tab_label=tab_label, page_num=len(slides) + 1)

    return slides
