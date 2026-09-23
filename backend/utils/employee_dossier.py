"""
Employee dossier analysis — reads every file in an employee's dossier (CIN,
diplôme, contrat, CV…) and extracts the employee's information in ONE
multimodal LLM call. Mirrors utils/dossier.py's strategy exactly (same file
extraction, same "detect once, no re-approval" philosophy for the fiche
administrative) — the prompt and field vocabulary are employee-specific.

Everything the analysis can read off a document gets applied straight to
the employees row (DETAIL_KEYS below) — matricule/status/email are the only
exclusions (matricule is an internal number HR assigns, never read off a
document; status is a workflow state; email is login-linked). Each field is
applied independently, so one unreadable value never blocks the rest.
"""
import json
import logging
import re

from utils.dossier import _extract_file, _image_to_data_url
from utils.templates import MODEL, _client, _strip_markdown_json

log = logging.getLogger(__name__)

MAX_TEXT_PER_FILE = 6000
MAX_IMAGES_TOTAL = 8

FILE_TYPE_HINTS = {
    "cin": "carte d'identité nationale (CIN)",
    "diplome": "diplôme",
    "cv": "curriculum vitae",
    "contrat": "contrat de travail",
    "photo": "photo d'identité",
    "autre": "document du dossier",
}

# Fields the analysis maps onto employees columns. matricule is deliberately
# absent — it's an internal number HR assigns, never something to read off
# the employee's own documents.
DETAIL_KEYS = (
    "cin", "birth_date", "address", "city", "nationality", "phone", "cnss_number", "bank_account",
    "position", "department", "manager", "contract_type", "contract_start", "contract_end", "salary",
    "gender", "place_of_birth", "marital_status", "dependents_count", "blood_type", "postal_code",
    "country", "personal_email", "cin_issue_date", "cin_expiry_date", "passport_number",
    "emergency_contact_name", "emergency_contact_phone", "emergency_contact_relation",
    "grade", "work_location", "weekly_hours", "bank_name", "amo_number", "tax_id", "cimr_number",
)
DATE_KEYS = {"birth_date", "contract_start", "contract_end", "cin_issue_date", "cin_expiry_date"}
FLOAT_KEYS = {"salary", "weekly_hours"}
INT_KEYS = {"dependents_count"}


def _normalize_date(value: str) -> str | None:
    value = value.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return value
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", value)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return None


def analyze_employee_dossier(files: list[dict], employee: dict) -> dict:
    """files: [{filename, type, content_type, data(bytes)}, …] — the whole
    dossier. employee: what the platform already knows (for cross-checking).
    Returns {"resume": str, "infos": [{label, valeur, source}], "alertes": [str], "details": {...}}.
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
        f"- Nom complet : {employee.get('full_name') or '(inconnu)'}\n"
        f"- Poste : {employee.get('position') or '(inconnu)'}\n"
        f"- Email : {employee.get('email') or '(inconnu)'}"
    )

    prompt = (
        "Tu es l'assistant RH de l'IPISB (El Jadida, Maroc). On te donne le "
        "dossier d'un(e) employé(e) : le contenu de chaque fichier est fourni "
        "soit en texte, soit en image (scans, cartes, contrats). Les documents "
        "peuvent mélanger français et arabe.\n\n"
        f"Ce que la plateforme sait déjà sur cet(te) employé(e) :\n{known}\n\n"
        "Ta mission : extraire TOUTES les informations que les documents "
        "contiennent réellement, et le plus précisément possible. Exemples de "
        "champs utiles :\n"
        "- identité : numéro CIN, date/lieu de naissance, sexe, situation "
        "familiale, nombre de personnes à charge, groupe sanguin, adresse, "
        "code postal, ville, pays, nationalité, téléphone, email personnel ;\n"
        "- pièce d'identité : date de délivrance et de validité de la CIN, "
        "numéro de passeport ;\n"
        "- contact d'urgence : nom, téléphone, lien de parenté ;\n"
        "- poste : département, manager / responsable hiérarchique, échelon "
        "/ niveau, lieu de travail (site), horaires hebdomadaires, type de "
        "contrat (CDI/CDD/Stage…), date de début et de fin de contrat, "
        "salaire ;\n"
        "- administratif / paie : numéro CNSS, numéro AMO / mutuelle, "
        "identifiant fiscal (IF), numéro CIMR, RIB / compte bancaire, nom de "
        "la banque ;\n"
        "- parcours : diplômes, expériences, compétences, langues.\n\n"
        "N'invente RIEN : chaque valeur doit être lisible dans un des "
        "fichiers. Si une image est trop floue pour lire une valeur, ne la "
        "devine pas.\n\n"
        "Réponds UNIQUEMENT avec un JSON valide de la forme :\n"
        "{\n"
        '  "resume": "2 à 3 phrases en français qui présentent l\'employé(e) d\'après le dossier",\n'
        '  "infos": [{"label": "Diplôme", "valeur": "…", "source": "nom_du_fichier"}, …],\n'
        '  "alertes": ["…", …],\n'
        '  "details": {"cin": "…", "birth_date": "AAAA-MM-JJ", "place_of_birth": "…", '
        '"gender": "M ou F", "marital_status": "…", "dependents_count": "…", '
        '"blood_type": "…", "address": "…", "postal_code": "…", "city": "…", '
        '"country": "…", "nationality": "…", "phone": "…", "personal_email": "…", '
        '"cin_issue_date": "AAAA-MM-JJ", "cin_expiry_date": "AAAA-MM-JJ", '
        '"passport_number": "…", "emergency_contact_name": "…", '
        '"emergency_contact_phone": "…", "emergency_contact_relation": "…", '
        '"position": "…", "department": "…", "manager": "…", "grade": "…", '
        '"work_location": "…", "weekly_hours": "…", "contract_type": "…", '
        '"contract_start": "AAAA-MM-JJ", "contract_end": "AAAA-MM-JJ", '
        '"salary": "…", "cnss_number": "…", "amo_number": "…", "tax_id": "…", '
        '"cimr_number": "…", "bank_account": "…", "bank_name": "…"}\n'
        "}\n\n"
        "Règles :\n"
        "- « details » couvre TOUT ce qui va directement dans la fiche de "
        "l'employé (identité, poste, contrat, salaire inclus) — remplis "
        "chaque clé UNIQUEMENT si la valeur est lisible dans un document, "
        "sinon mets null. « salary » = montant seul, sans devise ni texte ;\n"
        "- une entrée « infos » pour tout ce qui n'a pas sa place dans "
        "« details » (diplômes, expériences, compétences, langues…), label "
        "court en français, « source » = le nom exact du fichier d'où vient "
        "la valeur ;\n"
        "- dans « alertes », signale les incohérences (ex. nom sur la CIN "
        "différent du nom de la plateforme, dates contradictoires entre "
        "documents, CIN expirée, document illisible) — liste vide si rien à "
        "signaler ;\n"
        "- n'ajoute PAS d'entrée pour une information absente des documents ;\n"
        "- chaque « valeur » est une chaîne de caractères — si plusieurs "
        "valeurs, sépare-les par des virgules (jamais de tableau).\n\n"
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
        if not label or not valeur or source.lower() in ("plateforme", "profil"):
            continue
        infos.append({"label": label, "valeur": valeur, "source": source})

    details: dict[str, str | float | int] = {}
    raw_details = data.get("details") or {}
    if isinstance(raw_details, dict):
        for key in DETAIL_KEYS:
            val = raw_details.get(key)
            if val is None:
                continue
            val = str(val).strip()
            if not val or val.lower() in ("null", "n/a", "inconnu"):
                continue
            if key in DATE_KEYS:
                normalized = _normalize_date(val)
                if not normalized:
                    continue
                details[key] = normalized
                continue
            if key in FLOAT_KEYS or key in INT_KEYS:
                numeric = re.sub(r"[^\d.,]", "", val).replace(",", ".")
                try:
                    details[key] = int(float(numeric)) if key in INT_KEYS else float(numeric)
                except ValueError:
                    continue
                continue
            details[key] = val

    return {
        "resume": str(data.get("resume") or "").strip(),
        "infos": infos,
        "alertes": [str(a).strip() for a in (data.get("alertes") or []) if str(a).strip()],
        "details": details,
    }
