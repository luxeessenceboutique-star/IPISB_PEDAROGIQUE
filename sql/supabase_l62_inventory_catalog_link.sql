-- L62 — Lien entre l'inventaire et le catalogue d'articles (l52)
-- --------------------------------------------------------------
-- Demande : « Se référer à la liste des catégories et articles avec codes »
-- (créer un actif d'inventaire en piochant dans le catalogue Code article /
-- Article / Caractéristiques déjà géré dans Comptabilité > Catégories,
-- plutôt qu'en retapant le nom et les caractéristiques à chaque fois).
--
-- On ne touche pas à `asset_category` (les 4 grandes familles Consommable /
-- Équipement / Local / Service, gérées par L56) : `category_ref_id` est un
-- lien optionnel et distinct vers le catalogue général (accounting_categories
-- / accounting_category_articles), utilisé uniquement pour pré-remplir et
-- tracer l'origine de l'article. `code_article` copie le code du catalogue au
-- moment de la création (l'article peut ensuite être renommé/recodé dans le
-- catalogue sans réécrire l'historique de l'inventaire).

ALTER TABLE inventory_items
  ADD COLUMN IF NOT EXISTS category_ref_id uuid REFERENCES accounting_categories(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS catalog_article_id uuid REFERENCES accounting_category_articles(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS code_article text;

CREATE INDEX IF NOT EXISTS idx_inventory_items_category_ref ON inventory_items(category_ref_id);
