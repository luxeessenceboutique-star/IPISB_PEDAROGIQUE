-- ============================================================
-- IPISB Connect — Mensualité SAISIE + budget dérivé (standardisation du billing)
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
-- ============================================================
--
-- Changement de modèle de facturation :
--   AVANT : la mensualité était DÉRIVÉE = (Budget − Avance) ÷ nb de mois.
--   APRÈS : la mensualité est SAISIE (standardisée, ex. 2000 pour toute la promo)
--           et le budget est DÉRIVÉ = Mensualité × nb de mois + Frais d'inscription.
--
--   Les frais d'inscription (colonne `advance`) restent un poste à part, comptés
--   comme déjà encaissés : jouer sur des réductions de frais (200 vs 300 DH)
--   n'impacte PLUS la mensualité, qui reste identique entre élèves.
--
-- La colonne `monthly_fee` existe déjà (migration l11) mais n'était pas utilisée.
-- On la renseigne ici pour les inscriptions existantes afin de conserver la même
-- mensualité qu'auparavant. `annual_budget` n'est plus la source de vérité : le
-- backend recalcule le budget à la volée (on laisse la colonne en place, ignorée).

UPDATE class_students cs
   SET monthly_fee = ROUND(
         GREATEST(0, cs.annual_budget - cs.advance)
         / GREATEST(1, COALESCE(c.installments_count, 11)),
         2)
  FROM classes c
 WHERE cs.class_id = c.id
   AND cs.monthly_fee = 0          -- ne touche pas une mensualité déjà saisie
   AND cs.annual_budget > 0;       -- uniquement les plans déjà renseignés
