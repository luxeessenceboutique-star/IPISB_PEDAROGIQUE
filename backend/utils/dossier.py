"""
Dossier analysis — reads every file in a student's dossier (CIN, bac
certificate, CV, lettre de motivation…) and extracts the student's
information in ONE multimodal LLM call.

Extraction strategy per file kind:
  - docx and born-digital PDFs → plain text (cheap, exact).
  - images and scanned/garbled PDFs → sent as pictures to the vision model.
    Unlike template field detection, no pixel geometry is needed here — we
    only want the CONTENT — so the vision model is reliable for this job.

The structured result (resume / infos / alertes) is stored per student and
only recomputed when the admin explicitly re-runs the analysis.
"""
import base64
import io
import json
import logging
import re

from PIL import Image

from utils.templates import (
    MODEL,
    _client,
    _extract_docx_text,
    _extract_pdf_text,
    _is_garbled,
    _strip_markdown_json,
)

log = logging.getLogger(__name__)

MAX_TEXT_PER_FILE = 6000       # chars of extracted text sent per file
MAX_PAGES_PER_PDF = 3          # scanned-PDF pages rendered as images
MAX_IMAGES_TOTAL = 8           # hard cap on pictures in the LLM call
IMAGE_MAX_DIM = 1600           # px — downscale bound before base64

FILE_TYPE_HINTS = {
    "cin": "carte d'identité nationale (CIN)",
    "bac": "certificat / relevé du baccalauréat",
    "cv": "curriculum vitae",
    "motivation": "lettre de motivation",
    "autre": "document du dossier",
}

# Structured fiche fields the analysis maps onto student_details columns.
# matricule is deliberately absent: it's an internal number the institute
# assigns — never something to read off the student's own documents.
DETAIL_KEYS = (
    "nom", "prenom", "date_naissance", "lieu_naissance", "cin",
    "telephone", "email_personnel", "adresse", "bac_annee",
)

def _normalize_date(value: str) -> str | None:
    """Accept AAAA-MM-JJ or JJ/MM/AAAA → ISO AAAA-MM-JJ (what a Postgres
    date column takes). Anything else is dropped rather than guessed."""
    value = value.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return value
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", value)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return None


def _image_to_data_url(img: Image.Image) -> str:
    img = img.convert("RGB")
    if max(img.size) > IMAGE_MAX_DIM:
        img.thumbnail((IMAGE_MAX_DIM, IMAGE_MAX_DIM))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _pdf_pages_as_images(file_bytes: bytes) -> list[Image.Image]:
    import pdfplumber
    pages = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages[:MAX_PAGES_PER_PDF]:
            pages.append(page.to_image(resolution=150).original)
    return pages


def _extract_file(filename: str, file_type: str, content_type: str, data: bytes,
                  images_budget: int) -> tuple[str | None, list[Image.Image]]:
    """→ (text or None, images). Exactly one of the two carries the content."""
    if content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return _extract_docx_text(data), []
    if content_type == "application/pdf":
        text = _extract_pdf_text(data)
        if not _is_garbled(text):
            return text, []
        # Scanned or broken-font PDF — read the pages as pictures instead.
        return None, _pdf_pages_as_images(data)[:images_budget]
    if content_type in ("image/jpeg", "image/png"):
        return None, [Image.open(io.BytesIO(data))][:images_budget]
    return None, []


def analyze_dossier(files: list[dict], profile: dict) -> dict:
    """files: [{filename, type, content_type, data(bytes)}, …] — the whole
    dossier. profile: what the platform already knows (for cross-checking).
    Returns {"resume": str, "infos": [{label, valeur, source}], "alertes": [str]}.
    """
    sections: list[str] = []
    image_parts: list[dict] = []
    images_left = MAX_IMAGES_TOTAL

    for f in files:
        hint = FILE_TYPE_HINTS.get(f["type"], FILE_TYPE_HINTS["autre"])
        try:
            text, images = _extract_file(f["filename"], f["type"], f["content_type"], f["data"], images_left)
        except Exception:
            log.exception("Extraction failed for %s", f["filename"])
            sections.append(f'--- Fichier « {f["filename"]} » ({hint}) : ILLISIBLE (erreur de lecture) ---')
            continue
        if text and text.strip():
            body = text.strip()[:MAX_TEXT_PER_FILE]
            sections.append(f'--- Fichier « {f["filename"]} » ({hint}) ---\n{body}')
        elif images:
            sections.append(
                f'--- Fichier « {f["filename"]} » ({hint}) : fourni en IMAGE '
                f"({len(images)} page(s), voir les images jointes dans l'ordre) ---"
            )
            for img in images:
                image_parts.append({"type": "image_url", "image_url": {"url": _image_to_data_url(img)}})
            images_left -= len(images)
        else:
            sections.append(f'--- Fichier « {f["filename"]} » ({hint}) : aucun texte détecté ---')

    known = (
        f"- Nom complet : {profile.get('full_name') or '(inconnu)'}\n"
        f"- Email : {profile.get('email') or '(inconnu)'}"
    )

    prompt = (
        "Tu es l'assistant administratif d'un institut de formation (IPISB, "
        "El Jadida, Maroc). On te donne le dossier d'un(e) stagiaire : le "
        "contenu de chaque fichier est fourni soit en texte, soit en image "
        "(scans, cartes). Les documents peuvent mélanger français et arabe.\n\n"
        f"Ce que la plateforme sait déjà sur ce/cette stagiaire :\n{known}\n\n"
        "Ta mission : extraire TOUTES les informations sur la personne que "
        "les documents contiennent réellement. Exemples de champs utiles : "
        "nom complet, date de naissance, lieu de naissance, numéro CIN, "
        "validité de la CIN, adresse, téléphone, email, série et année du "
        "bac, mention, établissement d'origine, diplômes, niveau d'études, "
        "filière, expériences, compétences, langues… N'invente RIEN : chaque "
        "valeur doit être lisible dans un des fichiers. Si une image est "
        "trop floue pour lire une valeur, ne la devine pas.\n\n"
        "Réponds UNIQUEMENT avec un JSON valide de la forme :\n"
        "{\n"
        '  "resume": "2 à 3 phrases en français qui présentent le/la stagiaire d\'après le dossier",\n'
        '  "infos": [{"label": "Date de naissance", "valeur": "…", "source": "nom_du_fichier"}, …],\n'
        '  "alertes": ["…", …],\n'
        '  "details": {"nom": "nom de famille", "prenom": "prénom(s)", '
        '"date_naissance": "AAAA-MM-JJ", "lieu_naissance": "…", "cin": "…", '
        '"telephone": "…", "email_personnel": "…", "adresse": "…", '
        '"bac_annee": "AAAA"}\n'
        "}\n\n"
        "Règles :\n"
        "- une entrée « infos » par information, label court en français, "
        "« source » = le nom exact du fichier d'où vient la valeur ;\n"
        "- dans « alertes », signale les incohérences (ex. nom sur la CIN "
        "différent du nom de la plateforme, dates contradictoires entre "
        "documents, CIN expirée, document illisible) — liste vide si rien à "
        "signaler ;\n"
        "- n'ajoute PAS d'entrée pour une information absente des documents, "
        "et ne répète PAS ce que la plateforme sait déjà (nom, email) si "
        "aucun document ne le mentionne ;\n"
        "- chaque « valeur » est une chaîne de caractères — si plusieurs "
        "valeurs, sépare-les par des virgules (jamais de tableau) ;\n"
        "- « details » est la fiche administrative structurée : remplis "
        "chaque clé UNIQUEMENT si la valeur est lisible dans un document, "
        "sinon mets null. « email_personnel » = un email personnel trouvé "
        "dans les documents (PAS l'email de la plateforme). « bac_annee » = "
        "l'année d'obtention du bac (4 chiffres).\n\n"
        "JSON :"
    )

    content: list[dict] = [{"type": "text", "text": prompt + "\n\n" + "\n\n".join(sections)}]
    content.extend(image_parts)

    resp = _client().chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": content}],
        temperature=0,
        max_tokens=1800,
    )
    raw = _strip_markdown_json(resp.choices[0].message.content or "{}")
    data = json.loads(raw)

    infos = []
    for it in data.get("infos") or []:
        label = str(it.get("label") or "").strip()
        raw_val = it.get("valeur")
        if isinstance(raw_val, list):
            valeur = ", ".join(str(v).strip() for v in raw_val if str(v).strip())
        else:
            valeur = str(raw_val or "").strip()
        source = str(it.get("source") or "").strip()
        # Entries the model sourced from the platform's own profile (not a
        # document) are redundant — the page already shows that data.
        if not label or not valeur or source.lower() in ("plateforme", "profil"):
            continue
        infos.append({"label": label, "valeur": valeur, "source": source})

    details = {}
    raw_details = data.get("details") or {}
    if isinstance(raw_details, dict):
        for key in DETAIL_KEYS:
            val = raw_details.get(key)
            if val is None:
                continue
            val = str(val).strip()
            if not val or val.lower() in ("null", "n/a", "inconnu"):
                continue
            if key == "date_naissance":
                val = _normalize_date(val)
                if not val:
                    continue
            if key == "bac_annee" and not re.fullmatch(r"\d{4}", val):
                continue
            details[key] = val

    return {
        "resume": str(data.get("resume") or "").strip(),
        "infos": infos,
        "alertes": [str(a).strip() for a in (data.get("alertes") or []) if str(a).strip()],
        "details": details,
    }
