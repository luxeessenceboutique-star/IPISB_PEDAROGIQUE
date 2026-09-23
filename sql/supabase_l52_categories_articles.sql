-- ============================================================
-- L52 — Code catégorie + catalogue d'articles par catégorie
-- ============================================================
-- Ajoute un code court à chaque catégorie comptable (ex. DIV, EQBUR) et une
-- table de catalogue « articles » rattachée à une catégorie (Code article /
-- Article / Caractéristiques / Commentaire), réutilisable pour pré-remplir
-- une Demande d'achat (les champs `article_code` / `characteristics` de
-- purchase_requests existent déjà, indépendants — aucune migration requise
-- de ce côté).

ALTER TABLE accounting_categories
  ADD COLUMN IF NOT EXISTS code text;

CREATE TABLE IF NOT EXISTS accounting_category_articles (
  id               uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  category_id      uuid        NOT NULL REFERENCES accounting_categories(id) ON DELETE CASCADE,
  code_article     text,
  article          text        NOT NULL,
  caracteristiques text,
  commentaire      text,
  created_by       uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at       timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_category_articles_category ON accounting_category_articles(category_id);

ALTER TABLE accounting_category_articles ENABLE ROW LEVEL SECURITY;
-- Pas de policy : accès exclusivement via le backend service-role, comme
-- accounting_categories et le reste du module Comptabilité.
