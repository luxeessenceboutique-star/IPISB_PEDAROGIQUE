"""Registre central des canaux de validation V1/V2.

Voir le plan `we-need-to-create-imperative-quail.md` pour le contexte complet.
V1 = le rôle métier qui exécute une tâche (variable selon le domaine :
professeur, caissier, staff RH, comptabilité…). V2 = `admin`, toujours —
jamais un rôle "chef de domaine" traité comme équivalent.

    Canal 1 (SELF_VALIDATED) — V1 s'auto-valide entièrement, aucune
      validation V2 n'est requise pour terminer la tâche. V2 garde des
      pouvoirs de supervision (il peut tout faire aussi), sans que ce soit
      un passage obligé.
    Canal 2 (V1_THEN_V2)     — V1 crée/agit en premier ; Annuler et
      Supprimer sont réservés à V2 ; la validation finale (validate_v2)
      n'appartient qu'à V2, et la tâche reste "en attente" jusque-là.
    Canal 3 (V2_ONLY)        — V2 exclusivement, V1 n'a aucun accès à ce
      type de tâche.

Ce fichier ne fait QUE déclarer l'affectation (données), pas la logique —
la logique générique vit dans `CurrentUser.can_act()` (deps.py). Un
router n'utilise ce registre que s'il appelle explicitement `can_act()` ;
tant qu'il garde ses vérifications historiques, l'ajout d'une entité ici
n'a aucun effet de bord. Les affectations ci-dessous sont des PROPOSITIONS
par défaut (déduites des patterns déjà en place dans le code, ou du
comportement actuel faute de mieux) — à confirmer avec l'utilisateur
avant de convertir chaque router. `rh.leaves` est le premier converti
(voir routers/rh_leaves.py) et sert d'exemple de référence.
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import Optional


class Channel(IntEnum):
    SELF_VALIDATED = 1
    V1_THEN_V2 = 2
    V2_ONLY = 3


@dataclass(frozen=True)
class AmountTier:
    """Borne haute INCLUSE du palier, en MAD. `None` = tout au-delà du
    dernier palier explicite (aucune borne supérieure)."""
    max_amount: Optional[float]
    channel: Channel


# Barème par montant — remplace le canal fixe de ENTITY_CHANNELS pour les
# actions de DÉCISION (validate_v1/validate_v2) de l'entité listée ; la
# soumission/consultation (create/view/export/edit de sa propre demande)
# reste ouverte à tout auteur quel que soit le montant, gérée par
# l'ownership check du router — seule l'autorité de décision est bornée
# par le montant. Palier confirmé par l'utilisateur : ≤500 MAD → Canal 1
# (comptabilite décide seule) ; 500 < montant ≤ 10 000 MAD → Canal 2 (admin
# décide en dernier ressort) ; >10 000 MAD → Canal 3 (admin exclusivement).
AMOUNT_TIERED_ENTITIES: dict[str, list[AmountTier]] = {
    "accounting.purchase_requests": [
        AmountTier(500, Channel.SELF_VALIDATED),
        AmountTier(10000, Channel.V1_THEN_V2),
        AmountTier(None, Channel.V2_ONLY),
    ],
}


# entity_key -> (channel, [rôles V1])
# "admin" n'a pas besoin d'être listé : il est toujours V2.
ENTITY_CHANNELS: dict[str, tuple[Channel, list[str]]] = {
    # ── RH ──────────────────────────────────────────────────────────────
    "rh.employees": (Channel.SELF_VALIDATED, ["rh", "assistant_rh"]),
    "rh.employee_files": (Channel.SELF_VALIDATED, ["rh", "assistant_rh"]),
    "rh.leaves": (Channel.V1_THEN_V2, ["rh", "assistant_rh"]),  # converti
    "rh.payroll": (Channel.V2_ONLY, []),
    "rh.recruitment_ads": (Channel.SELF_VALIDATED, ["rh", "assistant_rh"]),
    "rh.recruitment_candidates": (Channel.SELF_VALIDATED, ["rh", "assistant_rh"]),
    "rh.recruitment_interviews": (Channel.SELF_VALIDATED, ["rh", "assistant_rh"]),
    "rh.onboarding": (Channel.V1_THEN_V2, ["rh", "assistant_rh"]),
    "rh.performance_reviews": (Channel.SELF_VALIDATED, ["rh", "assistant_rh"]),
    "rh.performance_goals": (Channel.SELF_VALIDATED, ["rh", "assistant_rh"]),
    "rh.training": (Channel.SELF_VALIDATED, ["rh", "assistant_rh"]),
    "rh.orgchart": (Channel.SELF_VALIDATED, ["rh", "assistant_rh"]),
    "rh.assets": (Channel.SELF_VALIDATED, ["rh", "assistant_rh"]),
    "rh.settings": (Channel.V2_ONLY, []),

    # ── Comptabilité ────────────────────────────────────────────────────
    # Réponses confirmées par l'utilisateur (questionnaire Comptabilité,
    # OMAR.xlsx, 70 actions réparties sur 7 domaines) : les 7 lignes
    # ci-dessous étaient proposées à SELF_VALIDATED par défaut ; l'utilisateur
    # a répondu Canal 2 pour les actions d'écriture (Créer/Modifier/
    # Supprimer) de chacune — la lecture (Voir) reste ouverte à V1 sous
    # Canal 2 aussi, donc aucun conflit avec le reste des réponses "1" sur
    # les mêmes domaines (Voir seul). Reste à câbler dans chaque router
    # (aucun effet de bord tant que ce n'est pas fait, cf. docstring).
    "accounting.suppliers": (Channel.V1_THEN_V2, ["comptabilite"]),          # CPR-03/04
    "accounting.categories_budgets": (Channel.V1_THEN_V2, ["comptabilite"]), # CPR-01/02/05/06
    "accounting.purchase_requests": (Channel.V1_THEN_V2, ["comptabilite"]),
    "accounting.quotations": (Channel.V1_THEN_V2, ["comptabilite"]),
    "accounting.purchases": (Channel.V1_THEN_V2, ["comptabilite"]),
    "accounting.receptions": (Channel.V1_THEN_V2, ["comptabilite"]),         # CPA-19
    "accounting.inventory": (Channel.V1_THEN_V2, ["comptabilite"]),          # CPA-20/21/22/23
    "accounting.expenses": (Channel.V1_THEN_V2, ["comptabilite"]),           # CPD-01/02/03
    "accounting.revenues": (Channel.V1_THEN_V2, ["comptabilite"]),           # CPD-04/05/06
    "accounting.invoices": (Channel.V1_THEN_V2, ["comptabilite"]),           # CPD-07/08
    "accounting.cash_journal": (Channel.V1_THEN_V2, ["cashier"]),
    "accounting.bank_journal": (Channel.V1_THEN_V2, ["comptabilite"]),
    "accounting.cash_notes": (Channel.V1_THEN_V2, ["cashier"]),
    "accounting.mission_notes": (Channel.V1_THEN_V2, ["cashier"]),
    # accounting.cheques (CPT2-11/12/13) : NON mis à jour — l'utilisateur n'a
    # répondu que CPT2-11 (Lister/Stats/Exporter le registre) = Canal 3,
    # CPT2-12 (Créer/Modifier/Supprimer une entrée) et CPT2-13 (Changer le
    # statut) restent sans réponse. Changer tout le registre en V2_ONLY sur
    # la base d'1 réponse sur 3 retirerait l'accès du comptable à la SAISIE
    # du registre sans confirmation explicite — laissé en l'état, à trancher
    # une fois CPT2-12/13 répondues.
    "accounting.cheques": (Channel.V1_THEN_V2, ["comptabilite"]),
    "accounting.payments": (Channel.V1_THEN_V2, ["comptabilite"]),          # CPT2-14/15/16
    # accounting.tuition (CPS-04/05/06 = Canal 1) : NON appliqué. Ceci est
    # littéralement LA validation N+1 déjà en place (caissier → admin) citée
    # partout comme "l'exemple de référence V1/V2" — la réponse retire cette
    # validation (paiement de scolarité auto-validé par le caissier, sans
    # passage admin). Vu l'enjeu (argent réel, workflow déjà construit et
    # documenté comme référence), laissé inchangé tant que ce n'est pas
    # confirmé explicitement plutôt qu'appliqué sur la foi d'une case cochée.
    "accounting.tuition": (Channel.V1_THEN_V2, ["cashier"]),
    "accounting.classes_cashier_ops": (Channel.V1_THEN_V2, ["cashier"]),
    # accounting.dashboard / accounting.analytics (CPX-01..06 = Canal 3) :
    # PAS ajoutées au registre. Le comptable (CPT) a accès en lecture à ces
    # tableaux de bord aujourd'hui ; Canal 3 (V2 exclusivement) le lui
    # retirerait entièrement. Changement visible et potentiellement gênant
    # au quotidien — à confirmer avant de créer ces entités et de les câbler.

    # ── Scolarité ───────────────────────────────────────────────────────
    "academics.courses": (Channel.SELF_VALIDATED, ["professor"]),
    "academics.course_content": (Channel.SELF_VALIDATED, ["professor"]),
    "academics.resources": (Channel.SELF_VALIDATED, ["professor"]),
    "academics.library": (Channel.SELF_VALIDATED, ["professor"]),
    "academics.document_templates": (Channel.V2_ONLY, []),
    "academics.student_documents": (Channel.SELF_VALIDATED, ["professor"]),
    "academics.specialties": (Channel.V2_ONLY, []),
    "academics.classes": (Channel.SELF_VALIDATED, ["professor"]),
    "academics.students": (Channel.V2_ONLY, []),
    "academics.student_files": (Channel.SELF_VALIDATED, ["professor"]),
    "academics.exams": (Channel.SELF_VALIDATED, ["professor"]),
    "academics.grades": (Channel.SELF_VALIDATED, ["professor"]),
    "academics.attendance": (Channel.SELF_VALIDATED, ["professor"]),
    "academics.timetables": (Channel.V1_THEN_V2, ["professor"]),
    "academics.teaching_sessions": (Channel.SELF_VALIDATED, ["professor"]),
    "academics.agenda": (Channel.SELF_VALIDATED, ["professor"]),
    "academics.meetings": (Channel.SELF_VALIDATED, ["professor"]),
    "academics.announcements": (Channel.V2_ONLY, []),

    # ── Plateforme ──────────────────────────────────────────────────────
    "platform.users": (Channel.V2_ONLY, []),

    # ── Gestion des tâches (nouveau module, page isolée) ─────────────────
    # V1 = tout rôle staff (admin listé aussi, sans effet indésirable : V2
    # reste déterminé séparément par is_admin() dans can_act()). Les élèves
    # n'ont pas accès à ce module (aucun rôle "student" listé ici, et la
    # page frontend ne leur est pas montrée). Canal 1 : l'assigné gère son
    # statut librement, aucune validation V2 requise pour clôturer — comme
    # dans Odoo/Jira par défaut. À rebasculer en V1_THEN_V2 si le
    # questionnaire (T6/T8) demande une validation V2 de clôture.
    "tasks.tasks": (Channel.SELF_VALIDATED, [
        "admin", "professor", "rh", "assistant_rh", "comptabilite", "cashier", "accountant",
    ]),
}


def channel_for(entity: str, amount: Optional[float] = None) -> Channel:
    """Canal applicable à `entity`, éventuellement affiné par `amount` si
    l'entité a un barème (AMOUNT_TIERED_ENTITIES). Retombe sur le canal
    fixe de ENTITY_CHANNELS sinon (ou si `amount` est inconnu)."""
    tiers = AMOUNT_TIERED_ENTITIES.get(entity)
    if tiers and amount is not None:
        for tier in tiers:
            if tier.max_amount is None or amount <= tier.max_amount:
                return tier.channel
    channel, _ = ENTITY_CHANNELS[entity]
    return channel
