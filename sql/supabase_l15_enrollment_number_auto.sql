-- ============================================================
-- IPISB Connect — N° d'inscription automatique (class_students.enrollment_number)
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
-- Nécessite l14 (table reference_counters + fonctions de référence).
-- ============================================================
--
-- Objectif : le n° d'inscription de chaque élève est généré automatiquement à
-- l'inscription (ajout à une promo), au format 001/IP/2026 (compteur 3 chiffres
-- réinitialisé chaque année, suffixe /IP/AAAA). Il n'est plus saisi à la main.

-- Sécurité : s'assure que le compteur partagé existe (créé en l14).
CREATE TABLE IF NOT EXISTS reference_counters (
  prefix  text NOT NULL,
  year    int  NOT NULL,
  counter int  NOT NULL DEFAULT 0,
  PRIMARY KEY (prefix, year)
);

-- Générateur dédié : réutilise reference_counters (préfixe interne « INS »)
-- mais renvoie le format institutionnel NNN/IP/AAAA au lieu de PRÉFIXE-AAAA-NNNN.
CREATE OR REPLACE FUNCTION next_enrollment_number(p_year int DEFAULT NULL) RETURNS text AS $$
DECLARE y int := COALESCE(p_year, EXTRACT(year FROM now())::int); n int;
BEGIN
  INSERT INTO reference_counters(prefix, year, counter) VALUES ('INS', y, 1)
  ON CONFLICT (prefix, year) DO UPDATE SET counter = reference_counters.counter + 1
  RETURNING counter INTO n;
  RETURN lpad(n::text, 3, '0') || '/IP/' || y::text;
END; $$ LANGUAGE plpgsql;

-- Backfill chronologique des inscriptions sans numéro (par année de added_at).
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT class_id, student_id, added_at FROM class_students
           WHERE enrollment_number IS NULL OR enrollment_number = ''
           ORDER BY added_at NULLS LAST LOOP
    UPDATE class_students
       SET enrollment_number = next_enrollment_number(EXTRACT(year FROM COALESCE(r.added_at, now()))::int)
     WHERE class_id = r.class_id AND student_id = r.student_id;
  END LOOP;
END $$;

-- Génération automatique à l'INSERT (ajout d'un élève à une promo).
ALTER TABLE class_students ALTER COLUMN enrollment_number SET DEFAULT next_enrollment_number();
