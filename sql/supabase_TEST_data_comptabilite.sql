-- ============================================================
-- IPISB Connect — JEU DE DONNÉES DE TEST · Module Comptabilité
-- Scénario : institut de formation santé (Rabat) — 6 derniers mois (2026).
-- À exécuter dans le SQL Editor de Supabase.
--
-- Objectif : peupler TOUTES les fonctionnalités (achats, dépenses, recettes,
-- factures, budgets, demandes d'achat, devis, réceptions, paiements,
-- inventaire, mouvements) pour tester et visualiser le tableau de bord.
--
-- ⚠️  TOUTES les lignes de test ont un id préfixé « 7e57… ».
--     Pour tout supprimer proprement : exécuter le fichier ROLLBACK.
--     Ré-exécution : ON CONFLICT (id) DO NOTHING → sans doublon.
-- ============================================================

BEGIN;

-- ------------------------------------------------------------
-- 1. Catégories comptables  (id 7e570001…)
-- ------------------------------------------------------------
INSERT INTO accounting_categories (id, name) VALUES
  ('7e570001-0000-4000-8000-000000000001', 'Matériel pédagogique'),
  ('7e570001-0000-4000-8000-000000000002', 'Fournitures & consommables'),
  ('7e570001-0000-4000-8000-000000000003', 'Ressources humaines'),
  ('7e570001-0000-4000-8000-000000000004', 'Loyer & charges'),
  ('7e570001-0000-4000-8000-000000000005', 'Marketing & communication'),
  ('7e570001-0000-4000-8000-000000000006', 'Maintenance & entretien')
ON CONFLICT (id) DO NOTHING;

-- ------------------------------------------------------------
-- 2. Fournisseurs  (id 7e570002…) — fiche complète (banque, forme juridique)
-- ------------------------------------------------------------
INSERT INTO suppliers (id, company_name, contact_person, email, phone, address, tax_number, legal_form, rib, bank, bank_branch, payment_terms_days) VALUES
  ('7e570002-0000-4000-8000-000000000001', 'MediSupply Maroc',        'Sanaa El Fassi',  'contact@medisupply.ma',  '+212 537 11 22 33', '12 Zone Ind. Témara', 'IF-4451220', 'SARL', '007810000123456789012345', 'Attijariwafa Bank', 'Agdal', 30),
  ('7e570002-0000-4000-8000-000000000002', 'Papeterie Atlas',         'Karim Bennani',   'ventes@papeterieatlas.ma','+212 537 44 55 66', '48 Av. Hassan II Rabat', 'IF-3320011', 'SARL', '011780000987654321098765', 'Banque Populaire', 'Hassan', 15),
  ('7e570002-0000-4000-8000-000000000003', 'TechnoLab Équipements',   'Yassine Ait Ali', 'devis@technolab.ma',      '+212 522 77 88 99', '9 Rue de Lyon Casablanca', 'IF-5567788', 'SA',   '022340000456789012345678', 'BMCE Bank', 'Maârif', 45),
  ('7e570002-0000-4000-8000-000000000004', 'Nettoyage Pro Services',  'Fatima Zahra',    'contact@nettoyagepro.ma', '+212 537 12 34 56', '3 Rue Oued Fès Rabat', 'IF-2211099', 'auto-entrepreneur', '013450000111222333444555', 'CIH Bank', 'Océan', 30)
ON CONFLICT (id) DO NOTHING;

-- ------------------------------------------------------------
-- 3. Achats  (id 7e570003…) — 10 cas, statuts et dates variés
--    total_incl_vat = colonne GÉNÉRÉE (ne pas insérer)
-- ------------------------------------------------------------
INSERT INTO purchases (id, title, description, category_id, supplier_id, quantity, unit_price, vat_percent, purchase_date, payment_status, payment_method) VALUES
  ('7e570003-0000-4000-8000-000000000001', 'Mannequins de secourisme RCP',        'Mannequins adulte pour formation premiers secours', '7e570001-0000-4000-8000-000000000001', '7e570002-0000-4000-8000-000000000001',  5, 4500, 20, '2026-02-10', 'paid',           'virement'),
  ('7e570003-0000-4000-8000-000000000002', 'Gants d''examen (boîtes de 100)',      'Gants nitrile taille M/L',                          '7e570001-0000-4000-8000-000000000002', '7e570002-0000-4000-8000-000000000001', 40,   85, 20, '2026-02-25', 'paid',           'espece'),
  ('7e570003-0000-4000-8000-000000000003', 'Vidéoprojecteur salle B',              'Projecteur Full HD 4000 lumens',                    '7e570001-0000-4000-8000-000000000001', '7e570002-0000-4000-8000-000000000003',  2, 6200, 20, '2026-03-12', 'partially_paid', 'cheque'),
  ('7e570003-0000-4000-8000-000000000004', 'Ramettes papier A4 (cartons)',         'Papier 80g blanc',                                  '7e570001-0000-4000-8000-000000000002', '7e570002-0000-4000-8000-000000000002', 60,   42, 20, '2026-03-20', 'paid',           'espece'),
  ('7e570003-0000-4000-8000-000000000005', 'Ordinateurs portables labo info',      'PC portable i5 16Go pour salle informatique',       '7e570001-0000-4000-8000-000000000001', '7e570002-0000-4000-8000-000000000003',  8, 8900, 20, '2026-04-05', 'pending',        'virement'),
  ('7e570003-0000-4000-8000-000000000006', 'Produits d''entretien',                'Détergents, désinfectants surfaces',                '7e570001-0000-4000-8000-000000000006', '7e570002-0000-4000-8000-000000000004', 30,   55, 20, '2026-04-18', 'paid',           'espece'),
  ('7e570003-0000-4000-8000-000000000007', 'Kits de perfusion (formation)',        'Consommables pratique soins infirmiers',            '7e570001-0000-4000-8000-000000000001', '7e570002-0000-4000-8000-000000000001', 20,  320, 20, '2026-05-08', 'partially_paid', 'cheque'),
  ('7e570003-0000-4000-8000-000000000008', 'Chaises salle de cours',               'Chaises empilables ergonomiques',                   '7e570001-0000-4000-8000-000000000002', '7e570002-0000-4000-8000-000000000003', 50,  380, 20, '2026-05-22', 'paid',           'virement'),
  ('7e570003-0000-4000-8000-000000000009', 'Banderoles & flyers portes ouvertes',  'Supports com. journée portes ouvertes',             '7e570001-0000-4000-8000-000000000005', '7e570002-0000-4000-8000-000000000002',  1, 7800, 20, '2026-06-10', 'paid',           'virement'),
  ('7e570003-0000-4000-8000-000000000010', 'Défibrillateur formation (DAE)',       'Défibrillateur pédagogique pour ateliers',          '7e570001-0000-4000-8000-000000000001', '7e570002-0000-4000-8000-000000000001',  1,18500, 20, '2026-07-02', 'pending',        'virement')
ON CONFLICT (id) DO NOTHING;

-- ------------------------------------------------------------
-- 4. Dépenses  (id 7e570004…) — charges récurrentes réparties sur 6 mois
-- ------------------------------------------------------------
INSERT INTO expenses (id, title, category_id, amount, expense_date, description, supplier_id, payment_method) VALUES
  ('7e570004-0000-4000-8000-000000000001', 'Salaires formateurs — février', '7e570001-0000-4000-8000-000000000003', 85000, '2026-02-28', 'Masse salariale équipe pédagogique', NULL, 'virement'),
  ('7e570004-0000-4000-8000-000000000002', 'Loyer locaux — février',        '7e570001-0000-4000-8000-000000000004', 22000, '2026-02-05', 'Loyer mensuel bâtiment formation', NULL, 'virement'),
  ('7e570004-0000-4000-8000-000000000003', 'Salaires formateurs — mars',    '7e570001-0000-4000-8000-000000000003', 85000, '2026-03-31', 'Masse salariale équipe pédagogique', NULL, 'virement'),
  ('7e570004-0000-4000-8000-000000000004', 'Facture électricité T1',        '7e570001-0000-4000-8000-000000000004',  6400, '2026-03-15', 'Consommation 1er trimestre', NULL, 'virement'),
  ('7e570004-0000-4000-8000-000000000005', 'Campagne pub réseaux sociaux',  '7e570001-0000-4000-8000-000000000005',  4500, '2026-04-20', 'Facebook / Instagram Ads recrutement', NULL, 'cheque'),
  ('7e570004-0000-4000-8000-000000000006', 'Salaires formateurs — avril',   '7e570001-0000-4000-8000-000000000003', 88000, '2026-04-30', 'Masse salariale + heures suppl.', NULL, 'virement'),
  ('7e570004-0000-4000-8000-000000000007', 'Assurance locaux annuelle',     '7e570001-0000-4000-8000-000000000004', 12000, '2026-05-10', 'Multirisque professionnelle', NULL, 'virement'),
  ('7e570004-0000-4000-8000-000000000008', 'Internet & téléphonie',         '7e570001-0000-4000-8000-000000000004',  1800, '2026-06-05', 'Abonnement fibre + lignes', NULL, 'virement'),
  ('7e570004-0000-4000-8000-000000000009', 'Salaires formateurs — juin',    '7e570001-0000-4000-8000-000000000003', 90000, '2026-06-30', 'Masse salariale équipe pédagogique', NULL, 'virement')
ON CONFLICT (id) DO NOTHING;

-- ------------------------------------------------------------
-- 5. Recettes  (id 7e570005…) — encaissées / attendues / annulée
--    total_incl_vat = colonne GÉNÉRÉE ; amount = HT
-- ------------------------------------------------------------
INSERT INTO revenues (id, title, revenue_type, amount, vat_percent, status, revenue_date, payment_method, description) VALUES
  ('7e570005-0000-4000-8000-000000000001', 'Frais scolarité promo Secourisme — tranche 1', 'tuition',  120000,  0, 'received',  '2026-02-15', 'virement', 'Encaissement 1re tranche'),
  ('7e570005-0000-4000-8000-000000000002', 'Frais d''inscription nouveaux élèves',          'tuition',   35000,  0, 'received',  '2026-02-20', 'espece',   'Session février'),
  ('7e570005-0000-4000-8000-000000000003', 'Subvention formation OFPPT',                    'subsidy',   60000,  0, 'received',  '2026-03-10', 'virement', 'Aide publique à la formation'),
  ('7e570005-0000-4000-8000-000000000004', 'Frais scolarité — tranche 2',                   'tuition',  118000,  0, 'received',  '2026-03-28', 'virement', 'Encaissement 2e tranche'),
  ('7e570005-0000-4000-8000-000000000005', 'Formation intra-entreprise (clinique privée)',  'service',   45000, 20, 'received',  '2026-04-14', 'virement', 'Formation gestes d''urgence'),
  ('7e570005-0000-4000-8000-000000000006', 'Frais scolarité — tranche 3',                   'tuition',  115000,  0, 'expected',  '2026-05-30', 'virement', 'À encaisser fin de cycle'),
  ('7e570005-0000-4000-8000-000000000007', 'Don association partenaire',                    'donation',  15000,  0, 'received',  '2026-05-18', 'cheque',   'Soutien matériel pédagogique'),
  ('7e570005-0000-4000-8000-000000000008', 'Formation continue infirmiers',                 'service',   52000, 20, 'expected',  '2026-06-20', 'virement', 'Convention hôpital régional'),
  ('7e570005-0000-4000-8000-000000000009', 'Frais scolarité promo Aide-soignant',           'tuition',   98000,  0, 'received',  '2026-06-08', 'virement', 'Nouvelle promo'),
  ('7e570005-0000-4000-8000-000000000010', 'Vente supports pédagogiques',                   'other',      8000, 20, 'cancelled', '2026-07-05', 'espece',   'Commande annulée par le client')
ON CONFLICT (id) DO NOTHING;

-- ------------------------------------------------------------
-- 6. Factures fournisseurs  (id 7e570006…) — liées aux achats
--    total_incl_vat = colonne GÉNÉRÉE ; amount = HT
-- ------------------------------------------------------------
INSERT INTO invoices (id, invoice_number, supplier_id, purchase_id, invoice_date, due_date, amount, vat_percent, payment_status) VALUES
  ('7e570006-0000-4000-8000-000000000001', 'FAC-MS-2026-014', '7e570002-0000-4000-8000-000000000001', '7e570003-0000-4000-8000-000000000001', '2026-02-12', '2026-03-13', 22500, 20, 'paid'),
  ('7e570006-0000-4000-8000-000000000002', 'FAC-TL-2026-051', '7e570002-0000-4000-8000-000000000003', '7e570003-0000-4000-8000-000000000003', '2026-03-14', '2026-04-13', 12400, 20, 'partially_paid'),
  ('7e570006-0000-4000-8000-000000000003', 'FAC-TL-2026-067', '7e570002-0000-4000-8000-000000000003', '7e570003-0000-4000-8000-000000000005', '2026-04-06', '2026-05-06', 71200, 20, 'pending'),
  ('7e570006-0000-4000-8000-000000000004', 'FAC-MS-2026-033', '7e570002-0000-4000-8000-000000000001', '7e570003-0000-4000-8000-000000000007', '2026-05-09', '2026-06-08',  6400, 20, 'partially_paid'),
  ('7e570006-0000-4000-8000-000000000005', 'FAC-MS-2026-048', '7e570002-0000-4000-8000-000000000001', '7e570003-0000-4000-8000-000000000010', '2026-07-03', '2026-08-02', 18500, 20, 'pending')
ON CONFLICT (id) DO NOTHING;

-- ------------------------------------------------------------
-- 7. Budgets annuels 2026  (id 7e570007…) — par catégorie
-- ------------------------------------------------------------
INSERT INTO budgets (id, category_id, year, month, amount) VALUES
  ('7e570007-0000-4000-8000-000000000001', '7e570001-0000-4000-8000-000000000001', 2026, NULL,  300000),
  ('7e570007-0000-4000-8000-000000000002', '7e570001-0000-4000-8000-000000000002', 2026, NULL,   60000),
  ('7e570007-0000-4000-8000-000000000003', '7e570001-0000-4000-8000-000000000003', 2026, NULL, 1100000),
  ('7e570007-0000-4000-8000-000000000004', '7e570001-0000-4000-8000-000000000004', 2026, NULL,  320000),
  ('7e570007-0000-4000-8000-000000000005', '7e570001-0000-4000-8000-000000000005', 2026, NULL,   40000),
  ('7e570007-0000-4000-8000-000000000006', '7e570001-0000-4000-8000-000000000006', 2026, NULL,   30000)
ON CONFLICT (id) DO NOTHING;

-- ------------------------------------------------------------
-- 8. Demandes d'achat (DA)  (id 7e570009…) — 3 étapes du workflow
-- ------------------------------------------------------------
INSERT INTO purchase_requests (id, company, service, requester_name, project, activity, justification, request_type, asset_category, characteristics, article_code, quantity, budget_estimate, duration, need_decision, need_decision_comment, quote_synthesis, payment_mode, payment_terms_days, quote_decision, status) VALUES
  ('7e570009-0000-4000-8000-000000000001', 'IPISB', 'Informatique', 'Y. Ait Ali', 'Labo informatique', 'Formation bureautique', 'Renouvellement parc PC vétuste', 'renouvellement', 'equipement', 'PC portables i5 16Go SSD 512', 'PC-I5-16', 8, 72000, '1 semaine', 'validation', 'Besoin validé par la direction', '3 devis reçus, TechnoLab retenu (meilleur rapport qualité/prix)', 'ov_ponctuel', 45, 'validation', 'commande_emise'),
  ('7e570009-0000-4000-8000-000000000002', 'IPISB', 'Pédagogie', 'S. El Fassi', 'Bibliothèque', 'Fonds documentaire santé', 'Enrichir la bibliothèque médicale', 'nouveau_besoin', 'consommable', 'Ouvrages médecine / soins infirmiers', 'LIV-2026', 120, 18000, '2 semaines', 'validation', 'Besoin pédagogique confirmé', NULL, NULL, NULL, 'en_attente', 'en_consultation'),
  ('7e570009-0000-4000-8000-000000000003', 'IPISB', 'Maintenance', 'F. Zahra', 'Bâtiment', 'Entretien climatisation', 'Maintenance annuelle des climatiseurs', 'renouvellement', 'service', 'Contrat entretien 6 unités', NULL, 6, 9000, 'Annuel', 'en_attente', NULL, NULL, NULL, NULL, 'en_attente', 'brouillon')
ON CONFLICT (id) DO NOTHING;

-- ------------------------------------------------------------
-- 9. Devis  (id 7e570008…) — consultation de la DA "Bibliothèque" (rang 1..3)
-- ------------------------------------------------------------
INSERT INTO quotations (id, supplier_id, quote_number, quote_date, expiration_date, amount, status, purchase_request_id, rank, currency, retenu) VALUES
  ('7e570008-0000-4000-8000-000000000001', '7e570002-0000-4000-8000-000000000002', 'DEV-PA-101', '2026-06-15', '2026-07-15', 17500, 'waiting',  '7e570009-0000-4000-8000-000000000002', 1, 'MAD', false),
  ('7e570008-0000-4000-8000-000000000002', '7e570002-0000-4000-8000-000000000001', 'DEV-MS-208', '2026-06-16', '2026-07-16', 18200, 'waiting',  '7e570009-0000-4000-8000-000000000002', 2, 'MAD', false),
  ('7e570008-0000-4000-8000-000000000003', '7e570002-0000-4000-8000-000000000003', 'DEV-TL-330', '2026-06-17', '2026-07-17', 16900, 'waiting',  '7e570009-0000-4000-8000-000000000002', 3, 'MAD', false)
ON CONFLICT (id) DO NOTHING;

-- ------------------------------------------------------------
-- 10. Réceptions & contrôle qualité  (id 7e57000a…)
-- ------------------------------------------------------------
INSERT INTO purchase_receptions (id, purchase_id, received_quantity, quality_status, qhse_checked, inclure_rapport_comptable, validation_cg, comment) VALUES
  ('7e57000a-0000-4000-8000-000000000001', '7e570003-0000-4000-8000-000000000001',  5, 'conforme',             true,  true,  true,  'Réception conforme, matériel testé.'),
  ('7e57000a-0000-4000-8000-000000000002', '7e570003-0000-4000-8000-000000000003',  2, 'non_conforme_partiel', true,  false, false, '1 projecteur avec pixel mort — SAV en cours.'),
  ('7e57000a-0000-4000-8000-000000000003', '7e570003-0000-4000-8000-000000000008', 50, 'conforme',             true,  true,  true,  'Livraison complète.'),
  ('7e57000a-0000-4000-8000-000000000004', '7e570003-0000-4000-8000-000000000006', 30, 'conforme',             false, false, false, 'Consommables rangés au local entretien.')
ON CONFLICT (id) DO NOTHING;

-- ------------------------------------------------------------
-- 11. Paiements fractionnés  (id 7e57000b…) — achats "partially_paid"
-- ------------------------------------------------------------
INSERT INTO purchase_payments (id, purchase_id, amount, payment_date, payment_method, reference) VALUES
  ('7e57000b-0000-4000-8000-000000000001', '7e570003-0000-4000-8000-000000000003', 7000, '2026-03-15', 'cheque',   'CHQ-000145'),
  ('7e57000b-0000-4000-8000-000000000002', '7e570003-0000-4000-8000-000000000003', 3000, '2026-04-20', 'ov_ponctuel', 'VIR-000212'),
  ('7e57000b-0000-4000-8000-000000000003', '7e570003-0000-4000-8000-000000000007', 4000, '2026-05-12', 'cheque',   'CHQ-000160')
ON CONFLICT (id) DO NOTHING;

-- ------------------------------------------------------------
-- 12. Inventaire / Actifs  (id 7e57000c…) — avec amortissement
--     code_unique = colonne GÉNÉRÉE (INV-xxxxxx)
-- ------------------------------------------------------------
INSERT INTO inventory_items (id, name, asset_category, purchase_id, reception_id, initial_value, purchase_date, status, amortissement_duree_annees, niveau_alerte, quantity, location) VALUES
  ('7e57000c-0000-4000-8000-000000000001', 'Mannequins de secourisme RCP', 'equipement', '7e570003-0000-4000-8000-000000000001', '7e57000a-0000-4000-8000-000000000001', 22500, '2026-02-10', 'actif',        5, 2,  5, 'Salle de simulation'),
  ('7e57000c-0000-4000-8000-000000000002', 'Vidéoprojecteur salle B',      'equipement', '7e570003-0000-4000-8000-000000000003', '7e57000a-0000-4000-8000-000000000002', 12400, '2026-03-12', 'actif',        3, 1,  2, 'Salle B'),
  ('7e57000c-0000-4000-8000-000000000003', 'Défibrillateur formation DAE', 'equipement', '7e570003-0000-4000-8000-000000000010', NULL,                                   18500, '2026-07-02', 'actif',        7, 1,  1, 'Hall principal'),
  ('7e57000c-0000-4000-8000-000000000004', 'Chaises salle de cours',       'equipement', '7e570003-0000-4000-8000-000000000008', '7e57000a-0000-4000-8000-000000000003', 19000, '2026-05-22', 'actif',       10, 5, 50, 'Salle A')
ON CONFLICT (id) DO NOTHING;

-- ------------------------------------------------------------
-- 13. Mouvements de stock  (id 7e57000d…)
-- ------------------------------------------------------------
INSERT INTO inventory_movements (id, inventory_item_id, movement_type, quantity, movement_date, description) VALUES
  ('7e57000d-0000-4000-8000-000000000001', '7e57000c-0000-4000-8000-000000000001', 'entree',      5, '2026-02-10', 'Réception initiale mannequins'),
  ('7e57000d-0000-4000-8000-000000000002', '7e57000c-0000-4000-8000-000000000001', 'sortie',      1, '2026-04-01', 'Prêt pour formation externe'),
  ('7e57000d-0000-4000-8000-000000000003', '7e57000c-0000-4000-8000-000000000002', 'entree',      2, '2026-03-12', 'Réception vidéoprojecteurs'),
  ('7e57000d-0000-4000-8000-000000000004', '7e57000c-0000-4000-8000-000000000004', 'entree',     50, '2026-05-22', 'Réception chaises'),
  ('7e57000d-0000-4000-8000-000000000005', '7e57000c-0000-4000-8000-000000000004', 'ajustement', -2, '2026-06-15', 'Inventaire : 2 chaises cassées')
ON CONFLICT (id) DO NOTHING;

COMMIT;

-- ============================================================
-- Résumé attendu sur le tableau de bord (Vue d'ensemble) :
--   • Achats               : 10   • Dépenses : 9   • Recettes : 10   • Factures : 5
--   • Fournisseurs         : 4    • Budgets 2026 : 6 catégories
--   • Trésorerie nette     ≈ recettes encaissées − (achats + dépenses)
--   • Factures impayées    = TTC des factures pending + partially_paid
--   • Graphiques           : sorties par catégorie, budget vs réel,
--                            trésorerie 6 mois (fév→juil 2026),
--                            statut paiement achats, taux d'encaissement.
--   • Demandes d'achat     : 3 (commande émise / en consultation / brouillon)
--   • Devis                : 3 (consultation bibliothèque)
--   • Réceptions           : 4   • Paiements : 3   • Inventaire : 4   • Mouvements : 5
-- ============================================================
