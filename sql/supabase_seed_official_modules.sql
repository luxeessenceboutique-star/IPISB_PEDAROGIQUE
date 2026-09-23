-- ============================================================
-- IPISB Platform — Seed: official module catalog (Aide-Soignant,
-- Infirmier Auxiliaire, Infirmier Polyvalent)
-- Run this ONCE in the Supabase SQL Editor
--
-- Source: "Liste des Coefficients.docx" (direction-provided reference
-- document). Each row becomes a `courses` row:
--   - code     = official UF number where the source document gives one
--                (Aide-Soignant, Infirmier Auxiliaire), otherwise a
--                sequential code we assign (Infirmier Polyvalent, whose
--                source list has no UF numbering)
--   - credits  = the module's official coefficient (1-3) — this is the
--                field the platform already uses as a course's weight;
--                no new column needed
--   - semester = filière + année, shown in the UI next to the code
--   - professor_id = left to the first admin account found; reassign
--                per module to the real instructor via the existing
--                Courses page (Edit) whenever convenient — nothing here
--                is final, this just avoids 100+ empty rows
--
-- These rows are plain `courses` — after running this, use the existing
-- Courses page to rename, delete, add new modules, change a coefficient,
-- or assign a module to a real class. No new admin screen needed for any
-- of that; it's all already there.
-- ============================================================

INSERT INTO courses (title, code, credits, semester, professor_id, is_published, cover_color)
SELECT t.title, t.code, t.credits, t.semester,
       (SELECT user_id FROM user_roles WHERE role = 'admin' LIMIT 1),
       true, 'blue'
FROM (VALUES

-- ---------- Aide-Soignant · 1ère année (16 UF) ----------
('Introduction aux soins d''hygiène et du confort du malade', 'AS-101', 2, 'Aide-Soignant · 1ère année'),
('Élément de Sciences Biologiques', 'AS-102', 3, 'Aide-Soignant · 1ère année'),
('Hygiène', 'AS-103', 2, 'Aide-Soignant · 1ère année'),
('Relations et Communication / Informatique', 'AS-104', 3, 'Aide-Soignant · 1ère année'),
('Élément de Sociologie-Psychologie', 'AS-105', 2, 'Aide-Soignant · 1ère année'),
('Santé Publique', 'AS-106', 2, 'Aide-Soignant · 1ère année'),
('Droit législation', 'AS-107', 2, 'Aide-Soignant · 1ère année'),
('Éléments de Pharmacologie', 'AS-108', 3, 'Aide-Soignant · 1ère année'),
('Hygiène et Confort du Malade', 'AS-109', 3, 'Aide-Soignant · 1ère année'),
('Soins d''hygiène et confort du malade en Médecine aux Urgences', 'AS-110', 2, 'Aide-Soignant · 1ère année'),
('Soins d''hygiène et confort du malade en Chirurgie et Réanimation', 'AS-111', 2, 'Aide-Soignant · 1ère année'),
('Soins d''hygiène et confort en Pédiatrie', 'AS-112', 2, 'Aide-Soignant · 1ère année'),
('Soins d''hygiène et confort en Psychiatrie', 'AS-113', 2, 'Aide-Soignant · 1ère année'),
('Soins d''hygiène et confort en Gynéco-Obstétrique', 'AS-114', 2, 'Aide-Soignant · 1ère année'),
('Soins d''hygiène et confort en Gériatrie et Soins Palliatifs', 'AS-115', 2, 'Aide-Soignant · 1ère année'),
('Stage', 'AS-116', 3, 'Aide-Soignant · 1ère année'),

-- ---------- Infirmier Auxiliaire · 1ère année (17 UF) ----------
('Préparation aux études et méthodologie de travail', 'IA1-101', 3, 'Infirmier Auxiliaire · 1ère année'),
('L''infirmier auxiliaire et l''environnement professionnel', 'IA1-102', 3, 'Infirmier Auxiliaire · 1ère année'),
('Notion de psycho-sociologie', 'IA1-103', 3, 'Infirmier Auxiliaire · 1ère année'),
('Information éducation communication', 'IA1-104', 3, 'Infirmier Auxiliaire · 1ère année'),
('Anatomie physiologie', 'IA1-105', 3, 'Infirmier Auxiliaire · 1ère année'),
('Notions d''obstétrique', 'IA1-106', 3, 'Infirmier Auxiliaire · 1ère année'),
('Notion de puériculture et diététique', 'IA1-107', 1, 'Infirmier Auxiliaire · 1ère année'),
('Notion de pharmacologie', 'IA1-108', 3, 'Infirmier Auxiliaire · 1ère année'),
('Microbio-parasito-entomologie', 'IA1-109', 3, 'Infirmier Auxiliaire · 1ère année'),
('Nutrition et régimes alimentaires', 'IA1-110', 3, 'Infirmier Auxiliaire · 1ère année'),
('Techniques d''expression et de communication', 'IA1-111', 1, 'Infirmier Auxiliaire · 1ère année'),
('Hygiène et confort du malade', 'IA1-112', 1, 'Infirmier Auxiliaire · 1ère année'),
('Techniques de base', 'IA1-113', 1, 'Infirmier Auxiliaire · 1ère année'),
('Symptomatologie', 'IA1-114', 1, 'Infirmier Auxiliaire · 1ère année'),
('Hygiène individuelle', 'IA1-115', 2, 'Infirmier Auxiliaire · 1ère année'),
('Infrastructure et programmes d''activités sanitaires', 'IA1-116', 1, 'Infirmier Auxiliaire · 1ère année'),
('Stage', 'IA1-117', 3, 'Infirmier Auxiliaire · 1ère année'),

-- ---------- Infirmier Auxiliaire · 2ème année (17 UF) ----------
('Urgences et secours', 'IA2-201', 3, 'Infirmier Auxiliaire · 2ème année'),
('Maladies transmissibles et prophylaxie', 'IA2-202', 3, 'Infirmier Auxiliaire · 2ème année'),
('Démographie et espacement des naissances', 'IA2-203', 1, 'Infirmier Auxiliaire · 2ème année'),
('Notions de pathologie', 'IA2-204', 3, 'Infirmier Auxiliaire · 2ème année'),
('Hygiène scolaire', 'IA2-205', 1, 'Infirmier Auxiliaire · 2ème année'),
('Techniques de recherche d''emploi', 'IA2-206', 1, 'Infirmier Auxiliaire · 2ème année'),
('Programmes de lutte contre les maladies', 'IA2-207', 1, 'Infirmier Auxiliaire · 2ème année'),
('Hygiène du milieu', 'IA2-208', 3, 'Infirmier Auxiliaire · 2ème année'),
('Notion de gestion', 'IA2-209', 2, 'Infirmier Auxiliaire · 2ème année'),
('Système d''information', 'IA2-210', 3, 'Infirmier Auxiliaire · 2ème année'),
('Santé bucco-dentaire', 'IA2-211', 1, 'Infirmier Auxiliaire · 2ème année'),
('Hygiène hospitalière et l''environnement', 'IA2-212', 2, 'Infirmier Auxiliaire · 2ème année'),
('Initiation à l''informatique', 'IA2-213', 3, 'Infirmier Auxiliaire · 2ème année'),
('Notion de droit', 'IA2-214', 1, 'Infirmier Auxiliaire · 2ème année'),
('Législation du travail', 'IA2-215', 1, 'Infirmier Auxiliaire · 2ème année'),
('Langue anglaise', 'IA2-216', 2, 'Infirmier Auxiliaire · 2ème année'),
('Stage et projets', 'IA2-217', 3, 'Infirmier Auxiliaire · 2ème année'),

-- ---------- Infirmier Polyvalent · 1ère année (23 modules — no official UF numbering in source) ----------
('Préparation aux études', 'IP1-01', 2, 'Infirmier Polyvalent · 1ère année'),
('Conceptualisation et planification des soins infirmiers', 'IP1-02', 2, 'Infirmier Polyvalent · 1ère année'),
('Éthique professionnelle et profession de l''infirmier', 'IP1-03', 2, 'Infirmier Polyvalent · 1ère année'),
('Psychologie', 'IP1-04', 2, 'Infirmier Polyvalent · 1ère année'),
('Sociologie', 'IP1-05', 2, 'Infirmier Polyvalent · 1ère année'),
('Communication', 'IP1-06', 2, 'Infirmier Polyvalent · 1ère année'),
('Éléments de droit', 'IP1-07', 2, 'Infirmier Polyvalent · 1ère année'),
('Anatomie - physiologie', 'IP1-08', 3, 'Infirmier Polyvalent · 1ère année'),
('Microbiologie et parasitologie', 'IP1-09', 3, 'Infirmier Polyvalent · 1ère année'),
('Pharmacologie', 'IP1-10', 3, 'Infirmier Polyvalent · 1ère année'),
('Nutrition', 'IP1-11', 2, 'Infirmier Polyvalent · 1ère année'),
('Puériculture et diététique', 'IP1-12', 2, 'Infirmier Polyvalent · 1ère année'),
('Sémiologie', 'IP1-13', 2, 'Infirmier Polyvalent · 1ère année'),
('Soins infirmiers de base', 'IP1-14', 3, 'Infirmier Polyvalent · 1ère année'),
('Examens de laboratoire', 'IP1-15', 2, 'Infirmier Polyvalent · 1ère année'),
('Pathologie et soins infirmiers en médecine', 'IP1-16', 3, 'Infirmier Polyvalent · 1ère année'),
('Pathologie et soins infirmiers en chirurgie', 'IP1-17', 3, 'Infirmier Polyvalent · 1ère année'),
('Pathologie et soins infirmiers en pédiatrie', 'IP1-18', 2, 'Infirmier Polyvalent · 1ère année'),
('Système national de santé', 'IP1-19', 2, 'Infirmier Polyvalent · 1ère année'),
('Programme d''activité sanitaire', 'IP1-20', 3, 'Infirmier Polyvalent · 1ère année'),
('Notions d''informatique', 'IP1-21', 2, 'Infirmier Polyvalent · 1ère année'),
('Terminologie', 'IP1-22', 3, 'Infirmier Polyvalent · 1ère année'),
('Stage', 'IP1-23', 3, 'Infirmier Polyvalent · 1ère année'),

-- ---------- Infirmier Polyvalent · 2ème année (18 modules) ----------
('Économie de santé', 'IP2-01', 2, 'Infirmier Polyvalent · 2ème année'),
('Régimes alimentaires', 'IP2-02', 2, 'Infirmier Polyvalent · 2ème année'),
('Pathologie et soins infirmiers en médecine', 'IP2-03', 3, 'Infirmier Polyvalent · 2ème année'),
('Pathologie et soins infirmiers en chirurgie', 'IP2-04', 3, 'Infirmier Polyvalent · 2ème année'),
('Pathologie et soins infirmiers en réanimation médico-chirurgicale', 'IP2-05', 3, 'Infirmier Polyvalent · 2ème année'),
('Pathologie et soins infirmiers en bloc opératoire', 'IP2-06', 3, 'Infirmier Polyvalent · 2ème année'),
('Pathologie et soins infirmiers en pédiatrie', 'IP2-07', 3, 'Infirmier Polyvalent · 2ème année'),
('Gériatrie et soins infirmiers des personnes âgées', 'IP2-08', 2, 'Infirmier Polyvalent · 2ème année'),
('Obstétrique et soins infirmiers', 'IP2-09', 2, 'Infirmier Polyvalent · 2ème année'),
('Pathologie et soins infirmiers en psychiatrie', 'IP2-10', 2, 'Infirmier Polyvalent · 2ème année'),
('Santé bucco-dentaire', 'IP2-11', 2, 'Infirmier Polyvalent · 2ème année'),
('Épidémiologie', 'IP2-12', 3, 'Infirmier Polyvalent · 2ème année'),
('Maladies transmissibles', 'IP2-13', 3, 'Infirmier Polyvalent · 2ème année'),
('Programmes d''activité sanitaire', 'IP2-14', 3, 'Infirmier Polyvalent · 2ème année'),
('Statistique sanitaire', 'IP2-15', 2, 'Infirmier Polyvalent · 2ème année'),
('Démographie', 'IP2-16', 2, 'Infirmier Polyvalent · 2ème année'),
('Méthodologie de recherche', 'IP2-17', 2, 'Infirmier Polyvalent · 2ème année'),
('Stage', 'IP2-18', 3, 'Infirmier Polyvalent · 2ème année'),

-- ---------- Infirmier Polyvalent · 3ème année (11 modules) ----------
('Principe de gestion', 'IP3-01', 2, 'Infirmier Polyvalent · 3ème année'),
('Urgences et secours', 'IP3-02', 3, 'Infirmier Polyvalent · 3ème année'),
('Pathologie et soins infirmiers en gynécologie', 'IP3-03', 3, 'Infirmier Polyvalent · 3ème année'),
('Pathologie et soins infirmiers en ophtalmologie', 'IP3-04', 3, 'Infirmier Polyvalent · 3ème année'),
('Pathologie et soins infirmiers en oto-rhino-laryngologie', 'IP3-05', 3, 'Infirmier Polyvalent · 3ème année'),
('Pathologie et soins infirmiers en dermatologie', 'IP3-06', 3, 'Infirmier Polyvalent · 3ème année'),
('Diagnostic communautaire et planification des actions de santé', 'IP3-07', 2, 'Infirmier Polyvalent · 3ème année'),
('Programmes d''activité sanitaires', 'IP3-08', 3, 'Infirmier Polyvalent · 3ème année'),
('Santé au travail', 'IP3-09', 2, 'Infirmier Polyvalent · 3ème année'),
('Travaux de recherche', 'IP3-10', 2, 'Infirmier Polyvalent · 3ème année'),
('Stage', 'IP3-11', 3, 'Infirmier Polyvalent · 3ème année')

) AS t(title, code, credits, semester);
