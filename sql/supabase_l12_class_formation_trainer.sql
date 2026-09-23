-- ============================================================
-- IPISB Connect — Rattachement classe → formation + formateur + période
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
-- ============================================================

-- 1. Catalogue des formations (programmes réutilisables)
CREATE TABLE IF NOT EXISTS formations (
  id                       uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  name                     text        NOT NULL,
  code                     text,                       -- ex. F001 (optionnel)
  default_duration_months  int,                        -- durée type, pré-remplit la classe
  description              text,
  created_by               uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at               timestamptz DEFAULT now()
);

ALTER TABLE formations ENABLE ROW LEVEL SECURITY;
-- Le backend (service key) bypasse RLS ; pas de policy (accès backend uniquement).

-- 2. Rattachements sur la classe (promo / session)
ALTER TABLE classes
  ADD COLUMN IF NOT EXISTS formation_id    uuid REFERENCES formations(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS trainer_id      uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS start_date      date,       -- date de début de la formation
  ADD COLUMN IF NOT EXISTS duration_months int;        -- durée en mois (fin = début + durée)

CREATE INDEX IF NOT EXISTS idx_classes_formation ON classes(formation_id);
CREATE INDEX IF NOT EXISTS idx_classes_trainer   ON classes(trainer_id);
