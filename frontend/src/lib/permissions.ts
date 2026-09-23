// Registre central des canaux de validation V1/V2 — miroir de
// backend/permissions.py. Voir le plan `we-need-to-create-imperative-quail.md`
// pour le contexte complet.
//
//   Canal 1 (SELF_VALIDATED) — V1 s'auto-valide entièrement ; V2 (admin)
//     garde un accès de supervision sur tout, sans passage obligé.
//   Canal 2 (V1_THEN_V2)     — V1 crée/agit en premier ; Annuler et
//     Supprimer sont réservés à V2 ; la validation finale n'appartient
//     qu'à V2, et la tâche reste "en attente" jusque-là.
//   Canal 3 (V2_ONLY)        — V2 exclusivement, V1 n'a aucun accès.
//
// Ce fichier ne fait QUE déclarer l'affectation (données) ; un composant
// n'utilise ce registre que s'il appelle explicitement `usePermissions()`.
// `rh.leaves` est la première entité convertie (voir components/rh/Leaves.tsx)
// et sert d'exemple de référence — les autres lignes sont des propositions
// par défaut à confirmer avant conversion.

import { useAuth } from "./auth";

export type Channel = 1 | 2 | 3;

export type Action =
  | "create" | "view" | "edit" | "export" | "import"
  | "validate_v1" | "validate_v2" | "cancel" | "delete";

type EntityConfig = { channel: Channel; v1Roles: string[] };
type AmountTier = { maxAmount: number | null; channel: Channel };

// Barème par montant — miroir de backend/permissions.py::AMOUNT_TIERED_ENTITIES.
// Remplace le canal fixe de ENTITY_CHANNELS pour les actions de décision
// (validate_v1/validate_v2) quand un montant est fourni ; la soumission/
// consultation de sa propre demande reste hors barème (ownership, gérée
// côté composant). ≤500 MAD → canal 1 (comptabilite décide seule) ;
// 500 < montant ≤ 10 000 MAD → canal 2 (admin décide en dernier ressort) ;
// >10 000 MAD → canal 3 (admin exclusivement).
const AMOUNT_TIERED_ENTITIES: Record<string, AmountTier[]> = {
  "accounting.purchase_requests": [
    { maxAmount: 500, channel: 1 },
    { maxAmount: 10000, channel: 2 },
    { maxAmount: null, channel: 3 },
  ],
};

function channelFor(entity: string, amount?: number): Channel {
  const tiers = AMOUNT_TIERED_ENTITIES[entity];
  if (tiers && amount !== undefined) {
    for (const tier of tiers) {
      if (tier.maxAmount === null || amount <= tier.maxAmount) return tier.channel;
    }
  }
  return ENTITY_CHANNELS[entity].channel;
}

export const ENTITY_CHANNELS: Record<string, EntityConfig> = {
  // ── RH ──────────────────────────────────────────────────────────────
  "rh.employees": { channel: 1, v1Roles: ["rh", "assistant_rh"] },
  "rh.employee_files": { channel: 1, v1Roles: ["rh", "assistant_rh"] },
  "rh.leaves": { channel: 2, v1Roles: ["rh", "assistant_rh"] }, // converti
  "rh.payroll": { channel: 3, v1Roles: [] },
  "rh.recruitment_ads": { channel: 1, v1Roles: ["rh", "assistant_rh"] },
  "rh.recruitment_candidates": { channel: 1, v1Roles: ["rh", "assistant_rh"] },
  "rh.recruitment_interviews": { channel: 1, v1Roles: ["rh", "assistant_rh"] },
  "rh.onboarding": { channel: 2, v1Roles: ["rh", "assistant_rh"] },
  "rh.performance_reviews": { channel: 1, v1Roles: ["rh", "assistant_rh"] },
  "rh.performance_goals": { channel: 1, v1Roles: ["rh", "assistant_rh"] },
  "rh.training": { channel: 1, v1Roles: ["rh", "assistant_rh"] },
  "rh.orgchart": { channel: 1, v1Roles: ["rh", "assistant_rh"] },
  "rh.assets": { channel: 1, v1Roles: ["rh", "assistant_rh"] },
  "rh.settings": { channel: 3, v1Roles: [] },

  // ── Comptabilité ────────────────────────────────────────────────────
  "accounting.suppliers": { channel: 1, v1Roles: ["comptabilite"] },
  "accounting.categories_budgets": { channel: 1, v1Roles: ["comptabilite"] },
  "accounting.purchase_requests": { channel: 2, v1Roles: ["comptabilite"] },
  "accounting.quotations": { channel: 2, v1Roles: ["comptabilite"] },
  "accounting.purchases": { channel: 2, v1Roles: ["comptabilite"] },
  "accounting.receptions": { channel: 1, v1Roles: ["comptabilite"] },
  "accounting.inventory": { channel: 1, v1Roles: ["comptabilite"] },
  "accounting.expenses": { channel: 1, v1Roles: ["comptabilite"] },
  "accounting.revenues": { channel: 1, v1Roles: ["comptabilite"] },
  "accounting.invoices": { channel: 1, v1Roles: ["comptabilite"] },
  "accounting.cash_journal": { channel: 2, v1Roles: ["cashier"] },
  "accounting.bank_journal": { channel: 2, v1Roles: ["comptabilite"] },
  "accounting.cash_notes": { channel: 2, v1Roles: ["cashier"] },
  "accounting.mission_notes": { channel: 2, v1Roles: ["cashier"] },
  "accounting.cheques": { channel: 2, v1Roles: ["comptabilite"] },
  "accounting.payments": { channel: 1, v1Roles: ["comptabilite"] },
  "accounting.tuition": { channel: 2, v1Roles: ["cashier"] },
  "accounting.classes_cashier_ops": { channel: 2, v1Roles: ["cashier"] },

  // ── Scolarité ───────────────────────────────────────────────────────
  "academics.courses": { channel: 1, v1Roles: ["professor"] },
  "academics.course_content": { channel: 1, v1Roles: ["professor"] },
  "academics.resources": { channel: 1, v1Roles: ["professor"] },
  "academics.library": { channel: 1, v1Roles: ["professor"] },
  "academics.document_templates": { channel: 3, v1Roles: [] },
  "academics.student_documents": { channel: 1, v1Roles: ["professor"] },
  "academics.specialties": { channel: 3, v1Roles: [] },
  "academics.classes": { channel: 1, v1Roles: ["professor"] },
  "academics.students": { channel: 3, v1Roles: [] },
  "academics.student_files": { channel: 1, v1Roles: ["professor"] },
  "academics.exams": { channel: 1, v1Roles: ["professor"] },
  "academics.grades": { channel: 1, v1Roles: ["professor"] },
  "academics.attendance": { channel: 1, v1Roles: ["professor"] },
  "academics.timetables": { channel: 2, v1Roles: ["professor"] },
  "academics.teaching_sessions": { channel: 1, v1Roles: ["professor"] },
  "academics.agenda": { channel: 1, v1Roles: ["professor"] },
  "academics.meetings": { channel: 1, v1Roles: ["professor"] },
  "academics.announcements": { channel: 3, v1Roles: [] },

  // ── Plateforme ──────────────────────────────────────────────────────
  "platform.users": { channel: 3, v1Roles: [] },

  // ── Gestion des tâches (nouveau module, page isolée) ─────────────────
  // Miroir exact de backend/permissions.py::ENTITY_CHANNELS["tasks.tasks"].
  "tasks.tasks": {
    channel: 1,
    v1Roles: ["admin", "professor", "rh", "assistant_rh", "comptabilite", "cashier", "accountant"],
  },
};

/** Autorise `action` sur `entity` selon son canal. V2 = admin, toujours.
 * `amount` affine le canal si `entity` a un barème (AMOUNT_TIERED_ENTITIES).
 * Lève une erreur si `entity` n'est pas (encore) enregistrée. */
export function canAct(roles: string[], entity: string, action: Action, amount?: number): boolean {
  const cfg = ENTITY_CHANNELS[entity];
  if (!cfg) throw new Error(`Entité inconnue dans le registre de permissions : ${entity}`);
  const isV1 = cfg.v1Roles.some((r) => roles.includes(r));
  const isV2 = roles.includes("admin");

  switch (channelFor(entity, amount)) {
    case 1:
      return isV1 || isV2;
    case 2:
      if (action === "cancel" || action === "delete" || action === "validate_v2") return isV2;
      if (action === "validate_v1") return isV1;
      return isV1 || isV2;
    case 3:
      return isV2;
  }
}

export function usePermissions() {
  const { roles } = useAuth();
  return { can: (entity: string, action: Action, amount?: number) => canAct(roles, entity, action, amount) };
}
