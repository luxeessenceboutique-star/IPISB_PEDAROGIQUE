"""CV extraction — reads an uploaded CV (pdf/docx/image) and returns
structured fields via one LLM call, mirroring utils/dossier.py's
born-digital-text-first / vision-fallback strategy."""
import io
import json
import logging

from PIL import Image

from utils.dossier import _image_to_data_url, _pdf_pages_as_images
from utils.templates import _extract_docx_text, _extract_pdf_text, _is_garbled, _strip_markdown_json

log = logging.getLogger(__name__)

MAX_TEXT_CHARS = 8000
MAX_PAGES = 3


def extract_cv_content(content_type: str, data: bytes) -> tuple[str | None, list[str]]:
    """CPU-bound — call via run_in_threadpool. Returns (text, image_data_urls);
    exactly one of the two carries the content."""
    if content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return _extract_docx_text(data)[:MAX_TEXT_CHARS], []
    if content_type == "application/pdf":
        text = _extract_pdf_text(data)
        if not _is_garbled(text):
            return text[:MAX_TEXT_CHARS], []
        pages = _pdf_pages_as_images(data)[:MAX_PAGES]
        return None, [_image_to_data_url(img) for img in pages]
    if content_type in ("image/jpeg", "image/png"):
        return None, [_image_to_data_url(Image.open(io.BytesIO(data)))]
    return None, []


CV_EXTRACTION_PROMPT = (
    "Tu es l'assistant recrutement de l'IPISB (El Jadida, Maroc). Voici le CV "
    "d'un(e) candidat(e), fourni en texte ou en image ci-dessous. Extrais "
    "UNIQUEMENT ce qui est réellement écrit — n'invente rien, ne devine pas "
    "une valeur illisible. Le but est de permettre aux RH de juger le profil "
    "sans ouvrir le CV, donc sois précis et complet sur l'expérience et les "
    "compétences.\n\n"
    "Réponds UNIQUEMENT avec un JSON valide :\n"
    "{\n"
    '  "education_summary": "2 à 4 lignes : diplômes, établissements, années",\n'
    '  "experience_summary": "2 à 4 lignes : postes, entreprises, durées, missions",\n'
    '  "years_experience": nombre total d\'années d\'expérience professionnelle '
    "(calculé à partir des dates des postes occupés ; nombre décimal ou entier, "
    "null si non déterminable),\n"
    '  "skills": "compétences techniques et métier séparées par des virgules",\n'
    '  "languages": "langues parlées/écrites séparées par des virgules (avec niveau si mentionné)",\n'
    '  "education_details": [{"degree": "…", "institution": "…", "year": "…"}],\n'
    '  "experience_details": [{"title": "…", "company": "…", "period": "…", "description": "…"}],\n'
    '  "city": "ville de résidence du/de la candidat(e), si mentionnée, sinon null",\n'
    '  "address": "adresse complète du/de la candidat(e), si mentionnée, sinon null",\n'
    '  "detected_name": "… ou null", "detected_email": "… ou null", "detected_phone": "… ou null"\n'
    "}\n\nMets null (jamais une chaîne vide) pour tout champ absent.\n\nJSON :"
)


def build_cv_extraction_messages(text: str | None, image_urls: list[str]) -> list[dict]:
    content: list[dict] = [{"type": "text", "text": CV_EXTRACTION_PROMPT + "\n\n" + (text or "(voir image ci-jointe)")}]
    for url in image_urls:
        content.append({"type": "image_url", "image_url": {"url": url}})
    return [{"role": "user", "content": content}]


def _as_text(v) -> str | None:
    if isinstance(v, list):
        v = ", ".join(str(x).strip() for x in v if str(x).strip())
    v = str(v or "").strip()
    return v or None


def _as_number(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_cv_extraction_response(raw: str) -> dict:
    """Returns {} on any parse failure — extraction is best-effort and must
    never block the application from being saved."""
    try:
        data = json.loads(_strip_markdown_json(raw))
    except Exception:
        log.exception("CV extraction: could not parse LLM response")
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        "education": _as_text(data.get("education_summary")),
        "experience_summary": _as_text(data.get("experience_summary")),
        "skills": _as_text(data.get("skills")),
        "languages": _as_text(data.get("languages")),
        "years_experience": _as_number(data.get("years_experience")),
        "city": _as_text(data.get("city")),
        "address": _as_text(data.get("address")),
        "raw": data,
    }
