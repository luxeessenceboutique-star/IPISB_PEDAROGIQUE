-- ============================================================
-- IPISB Platform — Type de filière (formation initiale / continue)
-- Run this ONCE in the Supabase SQL Editor
--
-- Ajoute un champ `type` aux filières (specialties) pour piloter le
-- regroupement Formation initiale / Formation continue dans la barre
-- latérale (frontend/src/routes/dashboard.tsx). Toutes les filières
-- existantes basculent par défaut en 'formation_initiale' — à corriger
-- ensuite au cas par cas depuis Classes → Filières.
-- ============================================================

ALTER TABLE specialties
  ADD COLUMN IF NOT EXISTS type text NOT NULL DEFAULT 'formation_initiale'
    CHECK (type IN ('formation_initiale', 'formation_continue'));
