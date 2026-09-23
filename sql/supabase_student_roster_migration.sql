-- ============================================================
-- IPISB Platform — Student Roster ("Effectifs des stagiaires") Migration
-- Mirrors the "Canevas privé" Excel roster (Département, Région,
-- Établissement, Filière, Année, identité, CIN, Id massar…) as a real,
-- importable/exportable table — a reference roster, NOT tied to login
-- accounts (no auth.users row per line; unlike `students`, which is a
-- profile with role='student').
-- ============================================================

CREATE TABLE IF NOT EXISTS student_roster (
  id                        uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  academic_year             text        NOT NULL DEFAULT '2025-2026',
  departement               text,
  region                    text,
  province                  text,
  milieu                    text,       -- Urbain / Rural
  etablissement             text,
  mode_formation            text,       -- Résidentiel / Alterné
  niveau_formation          text,       -- S/Q/T/TS
  secteur                   text,
  filiere                   text,
  annee_formation           text,       -- 1°A / 2°A / 3°A
  nom                       text        NOT NULL,
  prenom                    text        NOT NULL,
  genre                     text,       -- M / F
  besoins_specifiques       boolean     DEFAULT false,
  type_handicap             text,
  cin                       text,
  id_massar                 text,
  date_naissance            date,
  nationalite               text,
  etranger_migrant_refugie  text,
  pays_origine              text,
  niveau_scolaire           text,
  date_dernier_niveau       date,
  created_by                uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at                timestamptz DEFAULT now(),
  updated_at                timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_student_roster_academic_year ON student_roster(academic_year);
CREATE INDEX IF NOT EXISTS idx_student_roster_filiere ON student_roster(filiere);

ALTER TABLE student_roster ENABLE ROW LEVEL SECURITY;
-- No policies: only the backend (service key) reads/writes — same pattern
-- as student_details/student_files (admin-only via API-level checks).
