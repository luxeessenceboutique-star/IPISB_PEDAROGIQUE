"""Génération IA du « Contrôle continu » — un module de cours de ce
secteur paramédical, sur le modèle papier officiel de l'établissement
(Question / Corrigé type, avec barème par exercice).

Contrairement à exam_generation.py (QCM, un seul cours), ceci produit des
questions ouvertes (dissertation/définitions/études de cas), potentiellement
groupées sur PLUSIEURS cours sélectionnés ensemble — le cas réel d'un
contrôle continu qui porte sur une unité de formation regroupant plusieurs
modules enseignés par le même formateur.
"""
import json
import logging
import os
import re

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from supabase import Client

log = logging.getLogger(__name__)

BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://toknroutertybot.tybotflow.com/")
API_KEY  = os.environ.get("OPENAI_API_KEY", "")
MODEL    = "gpt-4.1-mini"

# Grounding : extrait RÉEL d'un contrôle continu de l'établissement (UF
# Microbio-parasito-entomologie, Infirmier Auxiliaire 1ère année) — calibre
# le registre, la structure en exercices notés, et le niveau de détail
# attendu du corrigé type, sur le modèle papier fourni par l'établissement.
FEW_SHOT_REFERENCE = """
--- Exemple réel (UF Microbio-parasito-entomologie, Infirmier Auxiliaire 1ère année) ---
Exercice 1 (06pts) — Consigne : "Définir les termes suivants : La microbiologie.
Une bactérie. L'immunité."
Corrigé : "Microbiologie : c'est la science qui étudie les microorganismes, cette
science est divisée en plusieurs branches, en fonction du type de « microbe »
étudié. Une bactérie : Des organismes unicellulaires procaryotes. Elles n'ont pas
de noyau et leur génome est le plus petit des cellules vivantes. L'immunité : est
l'ensemble des mécanismes de défense de l'organisme qui le protègent contre les
agents infectieux et les substances étrangères."

Exercice 2 (04pts) — Consigne : "Décrire deux groupes de bactéries selon leur
fonction ou leur interaction avec le milieu, avec des exemples ?"
Corrigé : "Bactéries ubiquitaires : colonisent tous les milieux (air, eau, sol,
être vivant), certaines vivent même dans des conditions extrêmes. Bactéries
commensales : vivent sur/dans un organisme sans lui porter préjudice, contribuent
à sa défense ou à son fonctionnement. [...]"

Exercice 3 (04pts) — Consigne : "Citer les deux groupes principaux identifiés
par la coloration de Gram ?"
Corrigé : "Les bactéries Gram positives (Gram+) : apparaissent violettes après la
coloration. Les bactéries Gram négatives (Gram-) : apparaissent roses ou rouges
après la coloration."

Exercice 4 (06pts) — Consigne : "Décrire une infection bactérienne, en précisant
la bactérie responsable, le traitement et les moyens de prévention ?"
Corrigé : "La tuberculose : Bactérie responsable : Mycobacterium tuberculose.
Traitement : association de plusieurs antibiotiques pendant au moins 6 mois,
selon la prescription médicale. Prévention : Vaccination par le BCG. Dépistage
précoce des cas. Port du masque et isolement des patients contagieux. Bonne
hygiène et aération des locaux."
""".strip()


def gather_course_content(db: Client, course_ids: list[str]) -> list[dict]:
    """Contenu RÉELLEMENT enseigné (leçons publiées, pas la bibliothèque de
    référence générale) pour chacun des cours sélectionnés — c'est ce sur
    quoi le contrôle continu doit être « basé », au sens le plus direct :
    ce que les stagiaires ont effectivement reçu comme cours."""
    courses = db.from_("courses").select("id, title").in_("id", course_ids).execute().data or []
    course_by_id = {c["id"]: c for c in courses}

    modules = (
        db.from_("course_modules").select("id, course_id, title, order_num")
        .in_("course_id", course_ids).eq("status", "published")
        .order("order_num").execute().data or []
    )
    module_ids = [m["id"] for m in modules]

    lessons = []
    if module_ids:
        lessons = (
            db.from_("course_lessons").select("module_id, title, content, order_num")
            .in_("module_id", module_ids).eq("status", "published")
            .order("order_num").execute().data or []
        )
    lessons_by_module: dict[str, list[dict]] = {}
    for l in lessons:
        lessons_by_module.setdefault(l["module_id"], []).append(l)

    out = []
    for cid in course_ids:
        course = course_by_id.get(cid)
        if not course:
            continue
        parts = []
        for m in [m for m in modules if m["course_id"] == cid]:
            for l in lessons_by_module.get(m["id"], []):
                if l.get("content"):
                    parts.append(f"## {m['title']} — {l['title']}\n{l['content']}")
        out.append({"id": cid, "title": course["title"], "content": "\n\n".join(parts)})
    return out


def _client(temperature: float = 0.5) -> ChatOpenAI:
    return ChatOpenAI(model=MODEL, base_url=BASE_URL, api_key=API_KEY, temperature=temperature)


def _extract_json_array(text: str) -> list:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON array found in model output")
    return json.loads(match.group(0))


def generate_assessment_sections(
    courses: list[dict],
    filiere: str | None,
    niveau: str | None,
    total_points: float = 20,
    instructions: str | None = None,
) -> list[dict]:
    """Génère les exercices (consigne + barème + corrigé) d'un contrôle
    continu, à partir du contenu réellement enseigné des cours sélectionnés.
    Chaque exercice est rendu en HTML simple (<p>, <strong>, <ul>/<li>) —
    directement éditable dans l'éditeur riche du formateur et convertible
    en paragraphes Word à l'export.

    Lève ValueError si aucun des cours sélectionnés n'a de contenu publié
    (rien de concret à évaluer) ou si la génération échoue."""
    grounding_parts = [f"=== Cours : {c['title']} ===\n{c['content']}" for c in courses if c.get("content")]
    if not grounding_parts:
        raise ValueError(
            "Aucun des cours sélectionnés n'a de contenu publié (leçons) — "
            "publiez au moins une leçon avant de générer un contrôle continu."
        )
    grounding = "\n\n".join(grounding_parts)
    # Un prompt système devient peu fiable au-delà de quelques dizaines de
    # milliers de caractères de contexte — plusieurs cours entiers peuvent
    # largement dépasser ce budget.
    if len(grounding) > 24000:
        grounding = grounding[:24000] + "\n[...contenu tronqué...]"

    course_titles = ", ".join(c["title"] for c in courses)
    filiere_line = f"Filière : {filiere}\n" if filiere else ""
    niveau_line = f"Niveau : {niveau}\n" if niveau else ""
    instructions_line = f"Consigne du formateur pour cette génération : {instructions}\n" if instructions else ""

    system = (
        "Tu es un formateur expérimenté dans un institut de formation paramédicale privé au Maroc "
        "(filières Aide-Soignant, Infirmier Auxiliaire, Infirmier Polyvalent), qui rédige un "
        "« Contrôle continu » — une évaluation à questions ouvertes (définitions, questions de "
        "cours, études de cas courtes), PAS un QCM.\n\n"
        "Voici un exemple RÉEL tiré des archives de contrôles continus de cet institut, pour "
        "calibrer le registre, le découpage en exercices notés et le niveau de détail attendu du "
        "corrigé :\n\n"
        f"{FEW_SHOT_REFERENCE}\n\n"
        f"Cours sur lesquels baser ce contrôle continu : {course_titles}\n"
        f"{filiere_line}{niveau_line}{instructions_line}\n"
        "CONTENU RÉELLEMENT ENSEIGNÉ (base exclusive des questions — n'invente rien qui n'y figure "
        "pas, et ne pose aucune question hors de ce contenu) :\n\n"
        f"{grounding}\n\n"
        "RÈGLES STRICTES :\n"
        "- Réponds UNIQUEMENT avec un tableau JSON valide, sans texte avant/après, sans balises "
        "markdown.\n"
        "- Chaque élément : {\"consigne\": str (HTML), \"bareme\": number, \"corrige\": str (HTML)}.\n"
        "- consigne et corrige sont du HTML SIMPLE UNIQUEMENT : <p>, <strong>, <ul>, <li> — jamais "
        "de <h1-6>, <table>, <img>, class ou style.\n"
        "- consigne = l'énoncé de l'exercice tel qu'il serait imprimé pour l'étudiant (peut contenir "
        "plusieurs sous-questions dans une liste <ul>). corrige = le modèle de réponse complet et "
        "précis attendu du correcteur, dans le même registre que l'exemple ci-dessus.\n"
        "- 4 à 7 exercices, qui couvrent des sujets DIFFÉRENTS et RÉPARTIS sur l'ensemble du contenu "
        "fourni (pas tous concentrés sur la même leçon) — et, si plusieurs cours sont fournis, "
        f"répartis entre eux plutôt que concentrés sur un seul.\n"
        f"- Le barème de chaque exercice est un nombre entier ou demi-entier de points, et la somme "
        f"de tous les barèmes doit être EXACTEMENT {total_points}.\n"
        "- Français clair, registre professionnel, adapté à des stagiaires en formation "
        "paramédicale.\n"
    )
    resp = _client().invoke([SystemMessage(content=system), HumanMessage(content="Génère le contrôle continu.")])
    raw = resp.content if isinstance(resp.content, str) else str(resp.content)

    try:
        items = _extract_json_array(raw)
    except Exception as e:
        log.error("Continuous assessment generation: failed to parse model output: %s\nRaw: %s", e, raw)
        raise ValueError("La génération IA a échoué (réponse invalide). Réessayez.")

    cleaned = []
    for i, it in enumerate(items):
        if not it.get("consigne"):
            continue
        cleaned.append({
            "id": f"s{i + 1}",
            "consigne": str(it["consigne"]),
            "bareme": float(it.get("bareme") or 0),
            "corrige": str(it.get("corrige") or ""),
        })
    if not cleaned:
        raise ValueError("La génération IA n'a produit aucun exercice valide. Réessayez.")

    # Recale le total sur total_points si l'arrondi du modèle dérive un peu,
    # plutôt que de rejeter une génération par ailleurs utilisable.
    current_total = sum(s["bareme"] for s in cleaned)
    if current_total > 0 and abs(current_total - total_points) > 0.01:
        factor = total_points / current_total
        for s in cleaned:
            s["bareme"] = round(s["bareme"] * factor * 2) / 2  # arrondi au demi-point

    return cleaned


def edit_html_with_ai(html: str, instruction: str) -> str:
    """Réécrit UN bloc HTML (une consigne ou un corrigé) selon l'instruction
    libre du formateur — le pendant HTML de
    course_generation.py::edit_text_with_ai (qui produit du texte brut pour
    une diapositive, pas adapté ici car l'éditeur de contrôle continu est un
    éditeur riche Tiptap qui a besoin de vraies balises)."""
    system = (
        "Tu es un assistant pédagogique qui aide un formateur à modifier UN bloc de texte (consigne "
        "ou corrigé) d'un contrôle continu, formation paramédicale au Maroc, selon son instruction.\n\n"
        "RÈGLES STRICTES :\n"
        "- Réponds UNIQUEMENT avec le nouveau HTML, sans aucun commentaire ni texte d'introduction.\n"
        "- HTML SIMPLE UNIQUEMENT : <p>, <strong>, <em>, <ul>, <li> — jamais de <h1-6>, <table>, "
        "<img>, class ou style, ni de balises <html>/<body> englobantes.\n"
        "- Registre professionnel, français clair, adapté à des stagiaires en formation "
        "paramédicale au Maroc.\n"
    )
    human = f"Texte actuel :\n\"\"\"\n{html}\n\"\"\"\n\nInstruction : {instruction}"
    resp = _client().invoke([SystemMessage(content=system), HumanMessage(content=human)])
    result = resp.content if isinstance(resp.content, str) else str(resp.content)
    result = result.strip()
    if result.startswith("```"):
        result = re.sub(r"^```[a-z]*\n?|```$", "", result).strip()
    if not result:
        raise ValueError("La génération IA n'a produit aucun texte. Réessayez.")
    return result
