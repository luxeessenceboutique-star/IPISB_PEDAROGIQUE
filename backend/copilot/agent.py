import os
import logging
from typing import TypedDict, Literal
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from .knowledge import sections_for_role, render_sections, ROLE_LABEL

log = logging.getLogger(__name__)

BASE_URL   = os.environ.get("OPENAI_BASE_URL", "https://toknroutertybot.tybotflow.com/")
API_KEY    = os.environ.get("OPENAI_API_KEY", "")
FAST_MODEL = "gpt-4.1-mini"
CHAT_MODEL = "gpt-4.1-mini"

# Reply language — spoken/written by the copilot regardless of the platform's
# own UI language, same 4 options offered by the public Aya assistant.
LANG_SYSTEM: dict[str, str] = {
    "fr":     "Tu réponds UNIQUEMENT en français, avec un ton clair et pédagogue.",
    "en":     "You respond ONLY in English, with a clear and helpful tone.",
    "ar":     "تجيب فقط باللغة العربية الفصحى، بأسلوب واضح ومفيد.",
    "darija": (
        "Katjaweb GHIR b-darija maghribiya (l-lahja lmaghribiya). "
        "Kteb b-7roof latinia (style Franco-arabe) aw b-3arabia. Koun wdoud o mfahem."
    ),
}

Intent = Literal["howto", "explain", "troubleshoot", "general"]


class CopilotState(TypedDict):
    messages: list[dict]        # [{"role": "user"|"assistant", "content": str}]
    role: str                   # admin | professor | student
    language: str
    intent: str
    system_prompt: str


def _fast_llm(max_tokens: int = 10) -> ChatOpenAI:
    return ChatOpenAI(model=FAST_MODEL, base_url=BASE_URL, api_key=API_KEY, temperature=0, max_tokens=max_tokens)


def classify_node(state: CopilotState) -> dict:
    messages = state.get("messages", [])
    last = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")

    prompt = (
        "Classify this message from a logged-in user of an internal school-management "
        "web app (IPISB Connect) into ONE intent.\n\n"
        "- howto        : asking HOW to perform a specific action on the platform "
        "(e.g. 'comment ajouter un contrôle continu ?', 'how do I approve a leave request?').\n"
        "- explain      : asking WHAT a feature/module/term does or means "
        "(e.g. 'c'est quoi le module RH ?', 'what is the 9-box grid?').\n"
        "- troubleshoot : reporting something broken, missing, or not working as expected.\n"
        "- general      : greeting, thanks, small talk, or unclear.\n\n"
        f'Message: "{last}"\n\n'
        "Reply with exactly one word (howto / explain / troubleshoot / general):"
    )
    try:
        resp = _fast_llm().invoke([HumanMessage(content=prompt)])
        intent = resp.content.strip().lower().split()[0]
    except Exception as e:
        log.warning("Copilot classify failed: %s", e)
        intent = "general"
    if intent not in ("howto", "explain", "troubleshoot", "general"):
        intent = "general"
    return {"intent": intent}


def _base_prompt(state: CopilotState) -> str:
    role = state.get("role", "student")
    sections = sections_for_role(role)
    knowledge = render_sections(sections)
    role_label = ROLE_LABEL.get(role, role)
    return (
        "Tu es le Copilote IPISB Connect, l'assistant intégré à la plateforme qui aide les "
        f"utilisateurs à s'en servir. Tu parles à un utilisateur avec le rôle **{role_label}**.\n\n"
        "MODULES ACCESSIBLES À CET UTILISATEUR (ne mentionne jamais un module hors de cette liste, "
        "il n'y a pas accès) :\n\n"
        f"{knowledge}\n\n"
        "RÈGLES :\n"
        "- Ne réponds qu'à propos d'IPISB Connect (navigation, fonctionnalités, où trouver quoi).\n"
        "- N'invente jamais un bouton, un onglet ou un champ qui n'est pas dans la liste ci-dessus.\n"
        "- Si la question concerne un module auquel l'utilisateur n'a pas accès selon son rôle, "
        "dis-le clairement et oriente-le vers un administrateur si besoin.\n"
        "- Si tu ne sais pas, dis-le honnêtement plutôt que d'inventer.\n"
    )


def howto_node(state: CopilotState) -> dict:
    prompt = _base_prompt(state) + (
        "\nSTYLE DE RÉPONSE : donne des étapes numérotées, courtes et actionnables, en citant le "
        "nom exact de l'onglet ou du bouton à cliquer et le chemin de navigation "
        "(ex. « Dashboard → Ressources humaines → Congés »)."
    )
    return {"system_prompt": prompt}


def explain_node(state: CopilotState) -> dict:
    prompt = _base_prompt(state) + (
        "\nSTYLE DE RÉPONSE : donne une explication concise (3-5 phrases) de ce à quoi sert le "
        "module ou la fonctionnalité, avec un exemple concret d'usage."
    )
    return {"system_prompt": prompt}


def troubleshoot_node(state: CopilotState) -> dict:
    prompt = _base_prompt(state) + (
        "\nSTYLE DE RÉPONSE : pose une ou deux questions de clarification courtes si le problème "
        "n'est pas assez précis, propose les vérifications de base les plus probables (recharger la "
        "page, vérifier les filtres, vérifier les droits d'accès), et si le problème dépasse une "
        "simple erreur d'usage, invite l'utilisateur à contacter un administrateur de la plateforme."
    )
    return {"system_prompt": prompt}


def general_node(state: CopilotState) -> dict:
    prompt = _base_prompt(state) + (
        "\nSTYLE DE RÉPONSE : sois bref et chaleureux. Si c'est une salutation, présente-toi en une "
        "phrase et propose 2-3 exemples de questions que tu peux aider à résoudre, adaptées au rôle "
        "de l'utilisateur."
    )
    return {"system_prompt": prompt}


def _route(state: CopilotState) -> str:
    return state.get("intent", "general")


def build_graph():
    g = StateGraph(CopilotState)
    g.add_node("classify",     classify_node)
    g.add_node("howto",        howto_node)
    g.add_node("explain",      explain_node)
    g.add_node("troubleshoot", troubleshoot_node)
    g.add_node("general",      general_node)

    g.add_edge(START, "classify")
    g.add_conditional_edges("classify", _route, {
        "howto":        "howto",
        "explain":      "explain",
        "troubleshoot": "troubleshoot",
        "general":      "general",
    })
    for node in ("howto", "explain", "troubleshoot", "general"):
        g.add_edge(node, END)

    return g.compile()


# Singleton — compiled once at import time
copilot_graph = build_graph()
