import os
import json
import logging
from datetime import datetime
from openai import OpenAI

log = logging.getLogger(__name__)

AIRTABLE_TOKEN  = os.environ.get("AIRTABLE_TOKEN", "")
AIRTABLE_BASE   = os.environ.get("AIRTABLE_BASE_ID", "")
AIRTABLE_TABLE  = os.environ.get("AIRTABLE_TABLE_ID", "tblT7gyi0tZ51UKG4")

_BASE_URL = os.environ.get("OPENAI_BASE_URL", "")
_API_KEY  = os.environ.get("OPENAI_API_KEY", "")

# Programs offered by IPISB (used by chatbot)
FILIERES = [
    "Infirmier Polyvalent",
    "Infirmier Auxiliaire",
    "Aide-Soignant",
    "Non precise",
]

# Airtable single-select options that actually exist in the base.
# If our filiere isn't in this set we store it as text in the Message field.
_AIRTABLE_FILIERE_OPTIONS = {
    "Soins Infirmiers", "Kinesitherapie", "Sage-Femme",
    "Nutrition", "Psychologie", "Non precise",
}

# Mapping from chatbot doc_type keys to Airtable field names
DOC_FIELD_MAP = {
    "cin":        "CIN",
    "bac":        "Certificat Bac",
    "photo":      "Photo",
    "motivation": "Lettre Motivation",
}


def extract_lead(messages: list[dict]) -> dict | None:
    """
    Extract contact info from conversation using LLM + regex patterns.
    Returns a dict with keys: nom, telephone, email, filiere — or None if not enough info.
    """
    import re
    conversation = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in messages
    )

    data = {}

    # Extract email
    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', conversation)
    if email_match:
        data['email'] = email_match.group()

    # Extract phone (+212, 06, etc.)
    phone_match = re.search(r'(?:\+?212[\s\-]?|0)[6-7][\s\-]?\d{2}[\s\-]?\d{3}[\s\-]?\d{3}', conversation)
    if phone_match:
        data['telephone'] = phone_match.group().replace(' ', '').replace('-', '')

    prompt = (
        "Analyse cette conversation et extrait le NOM et la FILIÈRE du candidat.\n"
        "Retourne UNIQUEMENT un JSON valide :\n"
        '{"nom": "...", "filiere": "...", "ville": "...", "niveau_bac": "..."}\n\n'
        f"Filières valides : {', '.join(FILIERES)}\n"
        f"CONVERSATION :\n{conversation}\n\n"
        "JSON (sans markdown) :"
    )
    try:
        from chatbot.agent import _strip_markdown_json
        client = OpenAI(api_key=_API_KEY, base_url=_BASE_URL)
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=150,
        )
        raw = _strip_markdown_json(resp.choices[0].message.content)
        llm_data = json.loads(raw)
        if llm_data.get("nom"):
            data['nom'] = llm_data['nom']
        if llm_data.get("filiere"):
            data['filiere'] = llm_data['filiere']
        if llm_data.get("ville"):
            data['ville'] = llm_data['ville']
        if llm_data.get("niveau_bac"):
            data['niveau_bac'] = llm_data['niveau_bac']
    except Exception as e:
        log.warning("LLM extraction failed: %s", e)

    if data.get("nom") and data.get("telephone"):
        return data

    return None if not data else data


def _normalize_phone(phone: str) -> str:
    """Strip spaces and dashes from a phone number."""
    return phone.replace(" ", "").replace("-", "").strip()


def get_candidature_by_phone(phone: str) -> dict | None:
    """
    Look up a candidature record by phone number only.
    Returns the full Airtable record dict (with 'id' and 'fields') or None.

    Note: Airtable's phoneNumber field type does not support formula equality
    comparisons reliably, so we fetch all records and filter in Python.
    """
    from pyairtable import Api

    phone = _normalize_phone(phone)
    if not phone:
        return None

    try:
        api = Api(AIRTABLE_TOKEN)
        table = api.table(AIRTABLE_BASE, AIRTABLE_TABLE)
        records = table.all(fields=["Telephone"])
        for record in records:
            stored = _normalize_phone(record.get("fields", {}).get("Telephone", ""))
            if stored == phone:
                # Re-fetch full record so caller gets all fields
                return table.get(record["id"])
    except Exception as e:
        log.warning("Phone lookup failed: %s", e)
    return None


def save_candidature(data: dict) -> str:
    """
    Save or update a candidature record in Airtable, keyed by phone number.

    Lookup logic:
      1. Search by Telephone only.
      2. If found  → UPDATE the existing record with any new/changed fields.
      3. If not found → CREATE a new record.

    Returns the record ID (existing or new).
    """
    from pyairtable import Api

    telephone = _normalize_phone(data.get("telephone", ""))
    if not telephone:
        raise ValueError("Phone number is required")

    nom = data.get("nom", "").strip()

    filiere_raw = (data.get("filiere") or "Non precise").strip()

    # Use the Airtable-compatible option; store the real program name in Message
    if filiere_raw in _AIRTABLE_FILIERE_OPTIONS:
        filiere_select = filiere_raw
        filiere_note   = ""
    else:
        filiere_select = "Non precise"
        filiere_note   = filiere_raw  # will be appended to Message

    niveau_bac = data.get("niveau_bac") or ""
    valid_niveaux = ["Sciences", "SVT", "Lettres", "Economie", "Autre"]
    if niveau_bac not in valid_niveaux:
        niveau_bac = "Autre" if niveau_bac else ""

    api = Api(AIRTABLE_TOKEN)
    table = api.table(AIRTABLE_BASE, AIRTABLE_TABLE)

    existing = get_candidature_by_phone(telephone)

    # Build message: combine filiere note + any explicit message
    parts = []
    if filiere_note:
        parts.append(f"Filière: {filiere_note}")
    if data.get("message"):
        parts.append(data["message"])
    message_text = " | ".join(parts) if parts else ""

    fields: dict = {}
    if nom:
        fields["Nom complet"] = nom
    fields["Telephone"]        = telephone
    if data.get("email"):
        fields["Email"]        = data["email"]
    fields["Filiere souhaitee"] = filiere_select
    if data.get("ville"):
        fields["Ville"]        = data["ville"]
    if message_text:
        fields["Message"]      = message_text
    if niveau_bac:
        fields["Niveau Bac"]   = niveau_bac

    if existing:
        record_id = existing["id"]
        update_fields = {k: v for k, v in fields.items() if v}
        table.update(record_id, update_fields)
        log.info("Updated existing record %s for phone %s (filiere=%s)", record_id, telephone, filiere_raw)
        return record_id

    # New record
    fields["Statut"]          = "A contacter"
    fields["Source"]          = "Chatbot"
    fields["Date soumission"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000Z")

    record = table.create(fields)
    log.info("Created Airtable record %s for %s (%s) filiere=%s", record["id"], nom, telephone, filiere_raw)
    return record["id"]


def attach_document_to_record(
    record_id: str,
    field_name: str,
    file_url: str,
    filename: str,
) -> bool:
    """
    Append an attachment (URL + filename) to an Airtable attachment field.

    Airtable attachment fields hold a list; this function appends without
    removing existing attachments.

    field_name should be one of: "CIN", "Certificat Bac", "Photo", "Lettre Motivation"
    Returns True on success, False on failure.
    """
    from pyairtable import Api

    try:
        api = Api(AIRTABLE_TOKEN)
        table = api.table(AIRTABLE_BASE, AIRTABLE_TABLE)

        # Fetch current value so we can append rather than replace
        record = table.get(record_id)
        existing_attachments: list = record.get("fields", {}).get(field_name, [])

        new_attachment = {"url": file_url, "filename": filename}
        updated = existing_attachments + [new_attachment]

        table.update(record_id, {field_name: updated})
        log.info("Attached %s to record %s field '%s'", filename, record_id, field_name)
        return True
    except Exception as e:
        log.warning("attach_document_to_record failed: %s", e)
        return False
