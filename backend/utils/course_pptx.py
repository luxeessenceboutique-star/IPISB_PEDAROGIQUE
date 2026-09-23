"""Builds a course-deck JSON payload and shells out to pptx_export/generate_course_deck.js
(pptxgenjs — Node) to render it, reusing the client-approved IPISB template design
verbatim rather than reimplementing it in Python. See pptx_export/README-ish notes
inside generate_course_deck.js for the exact JSON contract.
"""
import base64
import json
import re
import subprocess
import tempfile
from pathlib import Path

PPTX_EXPORT_DIR = Path(__file__).resolve().parent.parent / "pptx_export"
GENERATOR_SCRIPT = PPTX_EXPORT_DIR / "generate_course_deck.js"

_MD_STRIP_RE = [
    (re.compile(r"^#{1,6}\s*", re.MULTILINE), ""),
    (re.compile(r"\*\*(.+?)\*\*"), r"\1"),
    (re.compile(r"\*(.+?)\*"), r"\1"),
    (re.compile(r"`([^`]+)`"), r"\1"),
    (re.compile(r"^\s*[-*]\s+", re.MULTILINE), "• "),
    (re.compile(r"\[\[image:[a-f0-9-]+\]\]"), ""),  # inline-image tokens don't belong in slide text
]


def _plain_text(md: str) -> str:
    text = md
    for pattern, repl in _MD_STRIP_RE:
        text = pattern.sub(repl, text)
    return text.strip()


SLIDE_TEXT_BUDGET = 850  # ~ what the template's content-slide column fits at 10pt


def _chunk_text(text: str, max_chars: int = SLIDE_TEXT_BUDGET) -> list[str]:
    """Splits long text into slide-sized chunks on paragraph boundaries, so a
    section longer than one slide spills onto a second (third, ...) slide
    instead of being cut off. This is the actual fix for "why is it always
    the same page count" — the previous version truncated with text[:1200]
    instead of chunking, silently dropping anything past that point."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return []
    chunks: list[str] = []
    current = ""
    for p in paragraphs:
        candidate = f"{current}\n\n{p}" if current else p
        if len(candidate) > max_chars and current:
            chunks.append(current)
            current = p
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def split_sections(content: str) -> list[dict]:
    """Splits lesson markdown on ### headings into {heading, text} sections
    for one-section-per-slide layout, then chunks any section too long for
    one slide into several ("Heading", "Heading (suite)", ...). Slide count
    is therefore a direct function of how much content there actually is —
    a short chapter is a short deck, a long one is a long deck. Falls back
    to chunking the whole thing under one heading if there are no ###
    headings at all."""
    parts = re.split(r"^###\s+(.+)$", content, flags=re.MULTILINE)
    sections = []
    if len(parts) == 1:
        for i, chunk in enumerate(_chunk_text(_plain_text(content))):
            sections.append({"heading": "Contenu" if i == 0 else "Contenu (suite)", "text": chunk})
        return sections or [{"heading": "Contenu", "text": ""}]
    for i in range(1, len(parts), 2):
        heading = parts[i].strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        text = _plain_text(body)
        if not text:
            continue
        for j, chunk in enumerate(_chunk_text(text)):
            sections.append({"heading": heading if j == 0 else f"{heading} (suite)", "text": chunk})
    return sections or [{"heading": "Contenu", "text": _plain_text(content)}]


def build_deck_payload(course: dict, modules: list[dict], chapter_images: dict[str, bytes | None]) -> dict:
    """`chapter_images` maps module_id -> raw image bytes (already downloaded
    by the caller) for the first image on that chapter's lesson, or None."""
    chapters = []
    for m in modules:
        lessons = m.get("lessons") or []
        lesson = lessons[0] if lessons else None
        content = (lesson or {}).get("content") or ""
        sections = split_sections(content) if content else []

        # First chunk of each DISTINCT heading only — a long section chunked
        # into "X" / "X (suite)" / "X (suite)" shouldn't count as 3 separate
        # takeaways, just one.
        seen_headings: set[str] = set()
        takeaways = []
        for s in sections:
            if s["heading"] in seen_headings or "(suite)" in s["heading"]:
                continue
            seen_headings.add(s["heading"])
            takeaways.append({"title": s["heading"], "detail": s["text"][:220]})
            if len(takeaways) == 3:
                break

        img_bytes = chapter_images.get(m["id"])
        image_b64 = f"data:image/png;base64,{base64.b64encode(img_bytes).decode()}" if img_bytes else None

        chapters.append({
            "order": m["order_num"],
            "title": m["title"],
            "objectives": m.get("objectives") or "",
            "hoursTheory": m.get("hours_theory") or 0,
            "hoursPractice": m.get("hours_practice") or 0,
            "sections": sections,
            "keyTakeaways": takeaways,
            "imageBase64": image_b64,
        })

    return {
        "course": {
            "title": course.get("title") or "",
            "code": course.get("code") or "",
            "filiere": (course.get("semester") or "").split("·")[0].strip() if course.get("semester") else "",
            "annee": (course.get("semester") or "").split("·")[-1].strip() if course.get("semester") else "",
            "totalHours": sum((c["hoursTheory"] or 0) + (c["hoursPractice"] or 0) for c in chapters),
            "date": __import__("datetime").datetime.now().strftime("%d/%m/%Y"),
        },
        "chapters": chapters,
    }


def render_course_pptx(payload: dict) -> bytes:
    """Writes the payload to a temp file, runs the Node generator, returns
    the resulting .pptx bytes. Raises RuntimeError with the script's stderr
    on failure."""
    with tempfile.TemporaryDirectory() as tmp:
        in_path = Path(tmp) / "input.json"
        out_path = Path(tmp) / "output.pptx"
        in_path.write_text(json.dumps(payload), encoding="utf-8")

        proc = subprocess.run(
            ["node", str(GENERATOR_SCRIPT), str(in_path), str(out_path)],
            cwd=str(PPTX_EXPORT_DIR), capture_output=True, text=True, timeout=60,
        )
        if proc.returncode != 0 or not out_path.exists():
            raise RuntimeError(f"pptx generation failed: {proc.stderr or proc.stdout}")
        return out_path.read_bytes()
