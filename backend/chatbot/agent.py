import os
import json
import logging
from typing import TypedDict, Literal
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from .knowledge import FAQ_SYSTEM, ADVISOR_SYSTEM, LEAD_SYSTEM, GENERAL_SYSTEM

log = logging.getLogger(__name__)

BASE_URL   = os.environ.get("OPENAI_BASE_URL", "https://toknroutertybot.tybotflow.com/")
API_KEY    = os.environ.get("OPENAI_API_KEY", "")
FAST_MODEL = "gpt-4.1-mini"
CHAT_MODEL = "gpt-4.1-mini"

# Registration stages
Stage = Literal["chat", "collect_info", "collect_docs", "review", "confirmed"]

# Required info slots (in collection order)
REQUIRED_SLOTS = ["telephone", "nom", "email", "filiere", "niveau_bac", "ville"]

# Required documents (in collection order)
REQUIRED_DOCS = ["cin", "bac", "photo", "motivation"]

DOC_LABELS = {
    "cin":        "CIN (Carte d'Identité Nationale)",
    "bac":        "Certificat Bac (Baccalauréat)",
    "photo":      "Photo d'identité récente",
    "motivation": "Lettre de Motivation (PDF ou Word)",
}

DOC_LABELS_I18N: dict[str, dict[str, str]] = {
    "fr": {
        "cin":        "CIN (Carte d'Identité Nationale)",
        "bac":        "Certificat Bac (Baccalauréat)",
        "photo":      "Photo d'identité récente",
        "motivation": "Lettre de Motivation (PDF ou Word)",
    },
    "ar": {
        "cin":        "بطاقة الهوية الوطنية (CIN)",
        "bac":        "شهادة الباكالوريا",
        "photo":      "صورة شخصية حديثة",
        "motivation": "رسالة التحفيز (PDF أو Word)",
    },
    "en": {
        "cin":        "National ID Card (CIN)",
        "bac":        "Baccalaureate Certificate",
        "photo":      "Recent identity photo",
        "motivation": "Motivation Letter (PDF or Word)",
    },
    "darija": {
        "cin":        "CIN (Carte d'Identité)",
        "bac":        "Certificat Bac",
        "photo":      "Photo d'identité récente",
        "motivation": "Lettre de Motivation (PDF wla Word)",
    },
}

SLOT_QUESTIONS = {
    "telephone":  "son numéro de téléphone (WhatsApp si possible)",
    "nom":        "son nom complet (Prénom et Nom)",
    "email":      "son adresse email",
    "filiere":    "la filière souhaitée (Infirmier Polyvalent, Infirmier Auxiliaire ou Aide-Soignant)",
    "niveau_bac": "son niveau du baccalauréat (Sciences, SVT, Lettres, Économie ou Autre)",
    "ville":      "sa ville de résidence",
}

# Hardcoded collect_info messages per language — bypasses LLM to prevent off-script responses.
SLOT_HARDCODED: dict[str, dict[str, str]] = {
    "fr": {
        "telephone": (
            "Bien sûr, je vais vous accompagner dans votre inscription ! 😊\n\n"
            "Pour commencer, pourriez-vous me communiquer votre **numéro de téléphone** "
            "(WhatsApp de préférence) ?"
        ),
        "nom":        "Merci pour votre numéro ! 😊 Quel est votre **nom complet** (Prénom et Nom) ?",
        "email":      "Quelle est votre **adresse email** ?",
        "filiere": (
            "Quelle **filière** vous intéresse ?\n\n"
            "- Infirmier Polyvalent (3 ans)\n"
            "- Infirmier Auxiliaire (2 ans)\n"
            "- Aide-Soignant (1 an)"
        ),
        "niveau_bac": "Quel est votre **niveau du baccalauréat** ?\n\nSciences · SVT · Lettres · Économie · Autre",
        "ville":      "Dans quelle **ville** résidez-vous ?",
    },
    "ar": {
        "telephone": (
            "بالتأكيد، سأرافقك في عملية التسجيل ! 😊\n\n"
            "للبدء، هل يمكنك مشاركتي **رقم هاتفك** (واتساب إن أمكن) ؟"
        ),
        "nom":        "شكراً على رقمك ! 😊 ما هو **اسمك الكامل** (الاسم الأول واللقب) ؟",
        "email":      "ما هو **بريدك الإلكتروني** ؟",
        "filiere": (
            "أي **تخصص** يهمك ؟\n\n"
            "- ممرض متعدد التخصصات (3 سنوات)\n"
            "- ممرض مساعد (سنتان)\n"
            "- مساعد رعاية (سنة واحدة)"
        ),
        "niveau_bac": "ما هو **مستواك في البكالوريا** ؟\n\nعلوم · علوم الحياة والأرض · آداب · اقتصاد · أخرى",
        "ville":      "في أي **مدينة** تقيم ؟",
    },
    "en": {
        "telephone": (
            "Of course, I'll guide you through the enrollment process! 😊\n\n"
            "To start, could you share your **phone number** (WhatsApp preferred)?"
        ),
        "nom":        "Thanks for your number! 😊 What is your **full name** (First and Last name)?",
        "email":      "What is your **email address**?",
        "filiere": (
            "Which **program** interests you?\n\n"
            "- Polyvalent Nurse (3 years)\n"
            "- Auxiliary Nurse (2 years)\n"
            "- Care Assistant (1 year)"
        ),
        "niveau_bac": "What is your **baccalaureate level**?\n\nScience · Life Sciences · Literature · Economics · Other",
        "ville":      "Which **city** do you live in?",
    },
    "darija": {
        "telephone": (
            "Wakha, ghadi n3awnek f l-inscription ! 😊\n\n"
            "Bach nbdaw, wash tqder t3tini **raqm tilifonak** (WhatsApp b l-afdal) ?"
        ),
        "nom":        "Shukran 3la raqmak ! 😊 Shno huwa **smiyatek l-kamla** (l-ism w n-nasab) ?",
        "email":      "Shno hiya **adresse email** dyalek ?",
        "filiere": (
            "Anhi **filière** t3jbek ?\n\n"
            "- Infirmier Polyvalent (3 snin)\n"
            "- Infirmier Auxiliaire (2 snin)\n"
            "- Aide-Soignant (sna wahda)"
        ),
        "niveau_bac": "Shno huwa **mustawa dyalek f bac** ?\n\nSciences · SVT · Lettres · Economie · Autre",
        "ville":      "F anhi **mdina** saken/sakna nta/nti ?",
    },
}

THANKS_WITH_NAME: dict[str, str] = {
    "fr":     "Merci, {name} ! 😊 ",
    "ar":     "شكراً، {name} ! 😊 ",
    "en":     "Thanks, {name}! 😊 ",
    "darija": "Shukran, {name} ! 😊 ",
}

DOC_REPLY_FIRST: dict[str, str] = {
    "fr":     "Parfait ! Pour compléter votre dossier, j'ai besoin de vos documents.\n\nCommençons par : **{label}**\nCliquez sur le bouton de téléversement ci-dessous.",
    "ar":     "ممتاز ! لإكمال ملفك، أحتاج إلى وثائقك.\n\nلنبدأ بـ : **{label}**\nانقر على زر الرفع أدناه.",
    "en":     "Great! To complete your file, I need your documents.\n\nLet's start with: **{label}**\nClick the upload button below.",
    "darija": "Mzyan ! Bach nkamlu dossier dyalek, khassni l-wthayeq dyalek.\n\nNbdaw b : **{label}**\nClick l-button dyal upload lta7t.",
}

DOC_REPLY_NEXT: dict[str, str] = {
    "fr":     "Merci pour **{prev}** ! ✅\n\nVeuillez maintenant téléverser : **{label}**\nCliquez sur le bouton de téléversement ci-dessous.",
    "ar":     "شكراً على **{prev}** ! ✅\n\nيرجى الآن رفع : **{label}**\nانقر على زر الرفع أدناه.",
    "en":     "Thanks for **{prev}**! ✅\n\nPlease now upload: **{label}**\nClick the upload button below.",
    "darija": "Shukran 3la **{prev}** ! ✅\n\nDaba 3afak rfe3 : **{label}**\nClick l-button dyal upload lta7t.",
}


class ChatState(TypedDict):
    messages:    list[dict]   # [{"role": "user"|"assistant", "content": str}]
    intent:      str          # faq | advisor | lead | general
    system_prompt: str
    language:    str
    # --- registration flow ---
    stage:       str          # chat | collect_info | collect_docs | review | confirmed
    slots:       dict         # collected info: nom, telephone, email, filiere, etc.
    docs:        dict         # {"cin": {"url": "...", "filename": "..."}, ...}
    session_id:  str
    airtable_record_id: str
    hardcoded_reply: str      # when set, router streams this directly without calling the LLM


def _fast_llm(max_tokens: int = 20) -> ChatOpenAI:
    return ChatOpenAI(
        model=FAST_MODEL,
        base_url=BASE_URL,
        api_key=API_KEY,
        temperature=0,
        max_tokens=max_tokens,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Classify node
# ─────────────────────────────────────────────────────────────────────────────

def classify_node(state: ChatState) -> dict:
    import re
    messages = state.get("messages", [])
    last = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    last_lower = last.lower()

    current_stage = state.get("stage", "chat")

    # Confirmed stage → allow normal follow-up questions, don't re-trigger registration
    if current_stage == "confirmed":
        return {"intent": "general"}

    # Hard-code FAQ keywords — must run BEFORE the stage guard so that explicit FAQ
    # queries (e.g. "Formations disponibles") are always answered even when a previous
    # registration session is restored from Supabase in the background.
    faq_keywords = [
        # French — programs / info queries
        "formation", "filière", "filiere", "filières", "filieres",
        "programme", "cursus",
        "quelles formations", "liste des formations", "formations disponibles",
        "available programs", "which program",
        # Arabic — برامج / تخصصات / معلومات
        "برامج", "تخصص", "تخصصات", "برنامج",
        # Darija
        "formations", "anhi filière", "anhi filiere",
        # General info
        "frais", "tarif", "prix", "coût", "durée", "duree",
        "localisation", "adresse", "campus", "horaire",
        "fees", "cost", "duration", "location",
    ]
    if any(k in last_lower for k in faq_keywords):
        # Only classify as faq if NOT also an explicit registration request
        # (e.g. "je veux m'inscrire en formation infirmier" contains both)
        reg_also = ["inscr", "candidat", "sejjel", "تسجيل", "سجل", "سجّل", "أسجل",
                    "s'inscrire", "dossier", "admission", "je veux m'inscrire",
                    "i want to enroll", "i want to register"]
        if not any(r in last_lower for r in reg_also):
            return {"intent": "faq"}

    # If already in a registration stage, keep that flow (don't re-classify).
    # Placed AFTER the FAQ check so that explicit info queries always get answered.
    if current_stage in ("collect_info", "collect_docs", "review"):
        return {"intent": "lead"}

    # Hard-code registration keywords
    reg_keywords = ["inscr", "candidat", "sejjel", "تسجيل", "سجل", "سجّل", "أسجل", "s'inscrire", "dossier", "admission"]
    if any(k in last_lower for k in reg_keywords):
        return {"intent": "lead"}

    # Auto-detect name patterns → start registration
    name_patterns = [
        r"mon nom (?:est|c['\']est|serait)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
        r"my name (?:is|'s)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
        r"^([A-Z][a-z]+\s+[A-Z][a-z]+)$",
    ]
    for pattern in name_patterns:
        if re.search(pattern, last):
            return {"intent": "lead"}

    # Context maintenance: only when actively in registration (stage != chat).
    # Skipped for "chat" stage to avoid the welcome message's "inscription" keyword
    # falsely triggering lead intent on greetings like "bonjour".
    if current_stage != "chat":
        last_assistant = next((m["content"] for m in reversed(messages) if m["role"] == "assistant"), "")
        last_assistant_lower = last_assistant.lower()
        lead_prompts = [
            # French
            "nom complet", "téléphone", "filière", "niveau du bac", "adresse email", "ville",
            "pré-inscription", "candidat", "cin", "certificat bac", "lettre de motivation",
            # Arabic
            "اسمك الكامل", "رقم هاتفك", "بريدك الإلكتروني", "تخصص", "مستواك", "مدينة",
            "بطاقة الهوية", "شهادة الباكالوريا", "رسالة التحفيز",
            # English
            "full name", "phone number", "email address", "program", "baccalaureate", "city",
            "national id", "motivation letter",
            # Darija
            "smiyatek", "raqm tilifonak", "adresse email", "filière", "mustawa", "mdina",
            "wthayeq", "lettre de motivation",
        ]
        if any(p in last_assistant_lower for p in lead_prompts):
            has_confirmed = (
                "félicitations" in last_assistant_lower
                or "enregistrée" in last_assistant_lower
                or "confirmée" in last_assistant_lower
                or "congratulations" in last_assistant_lower
                or "registered" in last_assistant_lower
                or "تهانينا" in last_assistant_lower
                or "تم تسجيل" in last_assistant_lower
                or "mbruk" in last_assistant_lower
                or "mubarak" in last_assistant_lower
            )
            if not has_confirmed:
                return {"intent": "lead"}

    # LLM classification fallback
    prompt = (
        "Classify this visitor message on IPISB's website into ONE intent.\n\n"
        "Definitions (read carefully):\n"
        "- faq     : asking WHAT programs/formations exist, WHERE the school is, HOW MUCH fees are,\n"
        "            WHEN dates/deadlines are, WHAT the platform is, or any factual question about IPISB.\n"
        "            Examples: 'Formations disponibles', 'quelles formations ?', 'c'est quoi les filières ?',\n"
        "            'البرامج المتاحة', 'available programs', 'liste des formations', 'les frais de scolarité'.\n"
        "- advisor  : asking WHICH program suits them personally, seeking personalised guidance on choosing.\n"
        "            Examples: 'quel programme me conseilles-tu ?', 'je ne sais pas quelle filière choisir'.\n"
        "- lead     : EXPLICITLY wanting to register, enroll, apply, request a callback, or submit a file.\n"
        "            Examples: 'je veux m'inscrire', 'comment s'inscrire ?', 'كيف أسجّل؟', 'I want to enroll'.\n"
        "            NOTE: asking ABOUT programs is NOT lead — it is faq.\n"
        "- general  : greeting, thank you, small talk, or completely unclear.\n\n"
        f'Message: "{last}"\n\n'
        "Reply with exactly one word (faq / advisor / lead / general):"
    )
    try:
        resp = _fast_llm().invoke([HumanMessage(content=prompt)])
        intent = resp.content.strip().lower().split()[0]
    except Exception:
        intent = "general"
    if intent not in ("faq", "advisor", "lead", "general"):
        intent = "general"
    return {"intent": intent}


# ─────────────────────────────────────────────────────────────────────────────
# FAQ / Advisor / General nodes
# ─────────────────────────────────────────────────────────────────────────────

def faq_node(state: ChatState) -> dict:
    return {"system_prompt": FAQ_SYSTEM}


def advisor_node(state: ChatState) -> dict:
    return {"system_prompt": ADVISOR_SYSTEM}


def general_node(state: ChatState) -> dict:
    return {"system_prompt": GENERAL_SYSTEM}


# ─────────────────────────────────────────────────────────────────────────────
# Slot extraction helper
# ─────────────────────────────────────────────────────────────────────────────

def _strip_markdown_json(raw: str) -> str:
    """Strip markdown code fences from an LLM JSON response."""
    raw = raw.strip()
    # Remove ```json ... ``` or ``` ... ```
    if "```json" in raw:
        raw = raw.split("```json", 1)[1]
        if "```" in raw:
            raw = raw.split("```", 1)[0]
    elif "```" in raw:
        raw = raw.split("```", 1)[1]
        if "```" in raw:
            raw = raw.split("```", 1)[0]
    raw = raw.strip()
    # Truncate at the first complete JSON object in case of trailing garbage
    brace_depth = 0
    end_pos = -1
    for i, ch in enumerate(raw):
        if ch == "{":
            brace_depth += 1
        elif ch == "}":
            brace_depth -= 1
            if brace_depth == 0:
                end_pos = i
                break
    if end_pos != -1:
        raw = raw[: end_pos + 1]
    return raw


def extract_slots_from_history(messages: list[dict]) -> dict:
    conversation = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in messages
    )
    prompt = (
        "Analyse cette conversation et extrait les informations de contact du candidat.\n"
        "Retourne UNIQUEMENT un JSON valide avec ces clés (null si non trouvé) :\n"
        '{"nom": "...", "telephone": "...", "email": "...", "filiere": "...", "ville": "...", "niveau_bac": "..."}\n\n'
        "Filières valides : Infirmier Polyvalent, Infirmier Auxiliaire, Aide-Soignant\n"
        "Niveaux bac valides : Sciences, SVT, Lettres, Economie, Autre\n\n"
        f"CONVERSATION :\n{conversation}\n\n"
        "JSON (sans markdown) :"
    )
    try:
        # Use 200 tokens — enough for a 6-key JSON object, not just 20
        resp = _fast_llm(max_tokens=200).invoke([HumanMessage(content=prompt)])
        raw = _strip_markdown_json(resp.content)
        data = json.loads(raw)
        return {k: v for k, v in data.items() if v and v not in ("null", "None", None)}
    except json.JSONDecodeError as e:
        log.warning("Slot extraction JSON parse error: %s | raw=%r", e, resp.content if 'resp' in dir() else "")
    except Exception as e:
        log.warning("Slot extraction error: %s", e)
    return {}


# ─────────────────────────────────────────────────────────────────────────────
# Lead node — orchestrates all registration stages
# ─────────────────────────────────────────────────────────────────────────────

def lead_node(state: ChatState) -> dict:
    from .airtable_client import get_candidature_by_phone, save_candidature

    messages   = state.get("messages", [])
    stage      = state.get("stage", "chat")
    slots      = dict(state.get("slots", {}))
    docs       = dict(state.get("docs", {}))
    session_id = state.get("session_id", "")
    lang = state.get("language", "fr")
    if lang not in SLOT_HARDCODED:
        lang = "fr"

    # Auto-detect language from the last user message as a safety fallback.
    # Guards against the frontend sending the wrong language field.
    last_user_content = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    if any("؀" <= c <= "ۿ" for c in last_user_content):
        # User wrote in Arabic script — keep darija if already darija, else force ar
        if lang not in ("ar", "darija"):
            lang = "ar"

    log.info("LEAD_DEBUG lang=%r stage=%r last_msg=%r", lang, stage, last_user_content[:30])
    airtable_record_id = state.get("airtable_record_id", "")

    # ── Stage: collect_info ──────────────────────────────────────────────────
    if stage in ("chat", "collect_info"):
        # Merge freshly extracted slots with previously known slots
        fresh = extract_slots_from_history(messages)
        for k, v in fresh.items():
            if v and not slots.get(k):
                slots[k] = v

        # If we just got a phone number, check Airtable for existing record
        if slots.get("telephone") and not airtable_record_id:
            existing = get_candidature_by_phone(slots["telephone"])
            if existing:
                existing_fields = existing.get("fields", {})
                airtable_record_id = existing["id"]
                # Pre-fill slots from existing Airtable record
                field_map = {
                    "Nom complet":       "nom",
                    "Email":             "email",
                    "Filiere souhaitee": "filiere",
                    "Ville":             "ville",
                    "Niveau Bac":        "niveau_bac",
                }
                for airtable_field, slot_key in field_map.items():
                    if not slots.get(slot_key) and existing_fields.get(airtable_field):
                        slots[slot_key] = existing_fields[airtable_field]
                log.info("Pre-filled slots from existing Airtable record %s", airtable_record_id)

        # Find next missing required slot
        missing_slot = next((s for s in REQUIRED_SLOTS if not slots.get(s)), None)

        if missing_slot:
            # Hardcoded reply — bypasses LLM to prevent off-script responses.
            base_reply = SLOT_HARDCODED[lang][missing_slot]
            # Personalise with name once we have it
            if missing_slot != "telephone" and missing_slot != "nom" and slots.get("nom"):
                first_name = slots["nom"].split()[0]
                prefix = THANKS_WITH_NAME.get(lang, THANKS_WITH_NAME["fr"]).format(name=first_name)
                reply = f"{prefix}{base_reply}"
            else:
                reply = base_reply
            return {
                "stage":              "collect_info",
                "slots":              slots,
                "docs":               docs,
                "system_prompt":      "",
                "hardcoded_reply":    reply,
                "airtable_record_id": airtable_record_id,
            }

        # All info collected → early-save to Airtable so the lead is captured
        # even if the user abandons before uploading documents or confirming.
        if not airtable_record_id:
            try:
                from .airtable_client import save_candidature
                record_id = save_candidature(slots)
                airtable_record_id = record_id
                log.info("Early Airtable save — record %s", record_id)
            except Exception as e:
                log.warning("Early Airtable save failed: %s", e)

        stage = "collect_docs"

    # ── Stage: collect_docs ──────────────────────────────────────────────────
    if stage == "collect_docs":
        missing_doc = next((d for d in REQUIRED_DOCS if d not in docs), None)

        if missing_doc:
            doc_labels_lang = DOC_LABELS_I18N.get(lang, DOC_LABELS_I18N["fr"])
            label = doc_labels_lang[missing_doc]
            already_uploaded = [doc_labels_lang[d] for d in REQUIRED_DOCS if d in docs]

            # Hardcoded reply — bypass LLM entirely to prevent off-script responses.
            if already_uploaded:
                tmpl = DOC_REPLY_NEXT.get(lang, DOC_REPLY_NEXT["fr"])
                reply = tmpl.format(prev=already_uploaded[-1], label=label)
            else:
                tmpl = DOC_REPLY_FIRST.get(lang, DOC_REPLY_FIRST["fr"])
                reply = tmpl.format(label=label)

            return {
                "stage":              "collect_docs",
                "slots":              slots,
                "docs":               docs,
                "system_prompt":      "",
                "hardcoded_reply":    reply,
                "airtable_record_id": airtable_record_id,
            }

        # All docs collected → move to review
        stage = "review"

    # ── Stage: review ────────────────────────────────────────────────────────
    if stage == "review":
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        last_lower = last_user.lower()

        # Check if user clicked "Confirmer"
        if any(kw in last_lower for kw in ["confirmer", "confirme", "confirm", "oui", "yes", "valider", "valide"]):
            stage = "confirmed"
        else:
            docs_summary = "\n".join(
                f"  - {DOC_LABELS.get(k, k)}: {v.get('filename', v.get('url', ''))}"
                for k, v in docs.items()
            )
            prompt = (
                "Tu es Aya, assistante d'inscription de l'IPISB.\n"
                "Voici le récapitulatif complet du dossier du candidat.\n"
                f"Informations personnelles :\n{json.dumps(slots, indent=2, ensure_ascii=False)}\n\n"
                f"Documents soumis :\n{docs_summary}\n\n"
                "Présente ce récapitulatif de manière claire et élégante.\n"
                "Demande au candidat de confirmer en cliquant sur 'Confirmer' ou de corriger en cliquant sur 'Corriger'.\n"
                "Précise que la confirmation est définitive et que son dossier sera soumis."
            )
            return {
                "stage":         "review",
                "slots":         slots,
                "docs":          docs,
                "system_prompt": prompt,
            }

    # ── Stage: confirmed ─────────────────────────────────────────────────────
    if stage == "confirmed":
        airtable_record_id = state.get("airtable_record_id", "")
        try:
            # Skip re-saving if already confirmed (prevents duplicates on follow-up messages)
            if airtable_record_id:
                record_id = airtable_record_id
            else:
                record_id = save_candidature(slots)
            airtable_record_id = record_id

            # Attach documents to the Airtable record
            from .airtable_client import attach_document_to_record, DOC_FIELD_MAP
            for doc_type, doc_info in docs.items():
                field_name = DOC_FIELD_MAP.get(doc_type)
                if field_name and doc_info.get("url"):
                    attach_document_to_record(
                        record_id=record_id,
                        field_name=field_name,
                        file_url=doc_info["url"],
                        filename=doc_info.get("filename", doc_type),
                    )

            # Persist session to Supabase
            if session_id:
                from .supabase_client import save_session
                save_session(
                    session_id=session_id,
                    phone=slots.get("telephone", ""),
                    messages=messages,
                    slots=slots,
                    stage="confirmed",
                    docs=docs,
                    airtable_record_id=record_id,
                )

            log.info("Registration confirmed — Airtable record %s, session %s", record_id, session_id)

        except Exception as e:
            log.warning("Registration save failed: %s", e)

        confirmation_prompt = (
            "Tu es Aya, assistante d'inscription de l'IPISB.\n"
            f"La candidature du candidat vient d'être enregistrée avec succès.\n"
            f"Informations enregistrées : {json.dumps(slots, ensure_ascii=False)}\n\n"
            "Félicite chaleureusement le candidat, récapitule brièvement ses informations,\n"
            "et informe-le qu'un conseiller IPISB le contactera par téléphone sous 48h ouvrables\n"
            "pour finaliser son inscription. Sois enthousiaste et positive !"
        )
        return {
            "stage":              "confirmed",
            "slots":              slots,
            "docs":               docs,
            "system_prompt":      confirmation_prompt,
            "airtable_record_id": airtable_record_id,
        }

    # Fallback
    return {"system_prompt": LEAD_SYSTEM, "stage": stage, "slots": slots, "docs": docs}


# ─────────────────────────────────────────────────────────────────────────────
# Graph routing
# ─────────────────────────────────────────────────────────────────────────────

def _route(state: ChatState) -> str:
    return state.get("intent", "general")


def build_graph():
    g = StateGraph(ChatState)
    g.add_node("classify", classify_node)
    g.add_node("faq",      faq_node)
    g.add_node("advisor",  advisor_node)
    g.add_node("lead",     lead_node)
    g.add_node("general",  general_node)

    g.add_edge(START, "classify")
    g.add_conditional_edges("classify", _route, {
        "faq":     "faq",
        "advisor": "advisor",
        "lead":    "lead",
        "general": "general",
    })
    for node in ("faq", "advisor", "lead", "general"):
        g.add_edge(node, END)

    return g.compile()


# Singleton — compiled once at import time
chat_graph = build_graph()
