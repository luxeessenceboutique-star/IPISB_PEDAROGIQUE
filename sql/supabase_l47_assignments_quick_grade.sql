-- L47 — Marqueur du devoir canonique « Note directe » (raccourci de saisie)
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
--
-- Contexte : la page Notes (professeur) permet désormais de saisir une note
-- par élève directement pour un module, sans passer par la création d'un
-- vrai devoir ni exiger de remise préalable — cela réutilise le pipeline
-- devoir/soumission/notation existant via UN devoir auto-créé par cours,
-- repéré par ce marqueur (plutôt que par son titre, pour éviter toute
-- collision avec un devoir réel que le professeur nommerait pareil).

ALTER TABLE public.assignments
  ADD COLUMN IF NOT EXISTS is_quick_grade boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.assignments.is_quick_grade IS
  'Devoir canonique auto-créé par le raccourci « Note directe » (page Notes, professeur) — un seul par cours ; permet de saisir une note par élève sans créer un vrai devoir ni exiger de remise.';
