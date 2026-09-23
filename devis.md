# Devis — Module Comptabilité · IPISB Connect

| | |
|---|---|
| **Client** | IPISB |
| **Projet** | IPISB Connect |
| **Objet** | Module de gestion comptable (backend + frontend + base de données) |
| **Périmètre** | **Partie comptabilité uniquement** — les autres modules de la plateforme (scolarité, utilisateurs, classes, réunions, notifications…) ne sont pas inclus dans ce devis |
| **Date** | 31/07/2026 |
| **Devise** | Dirham marocain (DH / MAD) |
| **Montant total** | **5 000,00 DH** |

---

## 1. Synthèse générale

| Volet | Nature | Montant (DH) |
|---|---|--:|
| **A — Développement réalisé** | Module comptabilité livré et opérationnel | **3 800,00** |
| **B — Provision évolutions** | Enveloppe pour les évolutions à venir (dont gestion des chèques) | **1 200,00** |
| | **TOTAL** | **5 000,00** |

---

# VOLET A — Développement réalisé · 3 800 DH

## A.1 Volume livré

| Indicateur | Quantité |
|---|--:|
| Opérations API comptables (endpoints) | 135 |
| Modules backend (routeurs Python) | 19 |
| Écrans / onglets frontend | 18 |
| Migrations base de données (l4 → l35) | 32 |
| Moteurs de génération de documents (PDF + Excel) | ~1 650 lignes |

## A.2 Répartition des 3 800 DH

| # | Partie | Prix (DH) | Part |
|--:|---|--:|--:|
| 1 | Suivi de scolarité (échéancier, alertes, reçus, export coloré) | 500,00 | 13,2 % |
| 2 | Architecture, rôles & validation N+1 (admin / caissier / comptable) | 450,00 | 11,8 % |
| 3 | Journal de caisse (auto-alimenté, pièces justificatives, export PDF) | 450,00 | 11,8 % |
| 4 | Demandes d'achat (workflow devis → commande → échéancier) | 450,00 | 11,8 % |
| 5 | Recettes (CRUD, regroupement par classe, versements bancaires) | 300,00 | 7,9 % |
| 6 | Notes de caisse (avance, approbation N+1, paiement, PDF) | 300,00 | 7,9 % |
| 7 | Dépenses & Factures (dont refonte du PDF de facture) | 250,00 | 6,6 % |
| 8 | Achats, Réceptions, Fournisseurs & Catégories | 250,00 | 6,6 % |
| 9 | Paiements, Inventaire & Budgets | 250,00 | 6,6 % |
| 10 | Notes de frais de mission (approbation, paiement, PDF) | 250,00 | 6,6 % |
| 11 | Tableau de bord, Vue d'ensemble & Analytique | 200,00 | 5,3 % |
| 12 | Moteur d'exports (PDF / Excel) & intégration design system | 150,00 | 3,9 % |
| | **SOUS-TOTAL VOLET A** | **3 800,00** | **100 %** |

---

## A.3 Détail des parties

### Partie 1 — Suivi de scolarité · **500 DH**

| Livrable | Description |
|---|---|
| Échéancier mensuel | Calcul cumulé attendu / payé par élève, mois par mois |
| Jour d'échéance réglable | Paramétrage du jour d'exigibilité et de la tolérance |
| Alertes échelonnées | Relances graduées selon l'ancienneté du retard |
| Saisie des frais mensuels | Montant de scolarité paramétrable par classe / promotion |
| Avances sur scolarité | Encaissements anticipés et imputation automatique |
| Reçus de scolarité | Génération et suivi des reçus délivrés aux élèves |
| Export Excel coloré | Couleurs de cellules, légende, ventilation par mois |
| Consolidation par promo | Statuts payé / en retard / manquant par classe |

### Partie 2 — Architecture, rôles & validation N+1 · **450 DH**

| Livrable | Description |
|---|---|
| Modèle de rôles | Admin, caissier, comptable — droits différenciés |
| Workflow N+1 | File d'opérations en attente : saisie → approbation hiérarchique |
| Endpoints d'approbation | Validation / rejet motivé, traçabilité des décisions |
| Gating backend | Contrôle des droits sur chacun des 135 endpoints |
| Gating frontend | Affichage conditionnel des onglets et actions selon le rôle |
| Écran Approbations | Interface dédiée de traitement des demandes en attente |

### Partie 3 — Journal de caisse · **450 DH**

| Livrable | Description |
|---|---|
| Journal auto-alimenté | Alimentation automatique depuis les opérations comptables sources |
| Colonne n/c | Distinction des flux selon leur nature de comptabilisation |
| Pièces justificatives | Upload, visualisation en ligne, téléchargement par ligne |
| Soldes en continu | Entrées / sorties / soldes calculés automatiquement |
| CRUD soumis à validation | Créations et corrections passant par le circuit d'approbation |
| Export PDF | Édition du journal au format officiel (en-tête, grille, signatures) |

### Partie 4 — Demandes d'achat · **450 DH**

| Livrable | Description |
|---|---|
| Expression de besoin | Formulaire multi-étapes avec justification du besoin |
| Consultation de devis | Comparaison de plusieurs devis, pièces jointes et commentaires |
| Décision sur le besoin | Arbitrage hiérarchique avant mise en concurrence |
| Sélection du devis retenu | Validation du fournisseur et du montant |
| Conformité & livraison | Contrôle de conformité et conditions de livraison |
| Mode & échéancier de paiement | Définition du mode de règlement et du calendrier, rattachés à la demande |
| Émission de la commande | Génération de la commande depuis le devis validé |
| Export PDF | Fiche de demande d'achat imprimable |

### Partie 5 — Recettes · **300 DH**

| Livrable | Description |
|---|---|
| CRUD recettes | Création, édition, suppression, pièces jointes |
| Regroupement par classe | Vue repliable : total, effectif et encaissé par promotion |
| Versements bancaires | Filtrage par mode d'encaissement |
| Déversement au journal | Report automatique dans le journal de caisse |
| Export Excel | Édition stylée des versements bancaires |

### Partie 6 — Notes de caisse · **300 DH**

| Livrable | Description |
|---|---|
| Saisie des notes | Création, modification, suppression des notes de caisse |
| Demande d'avance | Circuit d'avance sur frais |
| Approbation N+1 | Cycle en attente → approuvée / rejetée |
| Exécution du paiement | Mise en paiement et comptabilisation depuis l'onglet Paiements |
| Rattachement au journal | Liaison automatique à la ligne de journal de caisse |
| Export PDF | Édition de la note au format officiel, colonnes et totaux alignés |

### Partie 7 — Dépenses & Factures · **250 DH**

| Livrable | Description |
|---|---|
| Dépenses | Saisie, catégorisation analytique, pièces justificatives |
| Factures | Suivi, états et rattachement aux élèves / tiers |
| PDF de facture | Refonte complète : mise en page, logo, tableau multi-colonnes, totaux, montant en lettres |
| Export Excel factures | Extraction du registre des factures |

### Partie 8 — Achats, Réceptions, Fournisseurs & Catégories · **250 DH**

| Livrable | Description |
|---|---|
| Achats | Commandes, validation, rattachement comptable |
| Réceptions | Constatation des livraisons et écarts |
| Fournisseurs | Répertoire et fiches fournisseurs |
| Catégories | Nomenclature analytique paramétrable |
| Modes de règlement | Harmonisation et regroupement des modes de paiement |

### Partie 9 — Paiements, Inventaire & Budgets · **250 DH**

| Livrable | Description |
|---|---|
| Paiements | Suivi des règlements, rattachement aux échéances |
| Pièces justificatives | Upload et téléchargement par règlement |
| Inventaire | Articles, mouvements de stock, alertes de seuil |
| Budgets | Suivi budgétaire par catégorie |

### Partie 10 — Notes de frais de mission · **250 DH**

| Livrable | Description |
|---|---|
| Saisie des missions | Création et gestion des notes de frais de mission |
| Approbation N+1 | Cycle en attente → approuvée / rejetée |
| Mise en paiement | Exécution et comptabilisation du règlement |
| Export PDF | Édition de la note de frais au format officiel |

### Partie 11 — Tableau de bord, Vue d'ensemble & Analytique · **200 DH**

| Livrable | Description |
|---|---|
| Vue d'ensemble | Indicateurs clés consolidés du module comptable |
| Journal de synthèse | Vue chronologique des écritures |
| Analytique par formation | Coûts, recettes et marge par formation / classe |
| Taux formateurs | Paramétrage des taux et calcul du coût pédagogique |
| Graphiques & synthèses | Restitutions visuelles des agrégats |
| Exports analytiques | Extractions CSV et rapport PDF |

### Partie 12 — Moteur d'exports & design system · **150 DH**

| Livrable | Description |
|---|---|
| Moteur PDF réutilisable | Socle commun d'édition : en-têtes, grilles, signatures, pieds de page, coordonnées officielles |
| Moteur Excel réutilisable | Socle commun : couleurs de cellules, légendes, mises en forme |
| Design system | Application de la charte IPISB (couleurs, typographies, composants, animations) |
| Cohérence documentaire | Alignement de l'ensemble des éditions sur un modèle unique |

---

# VOLET B — Provision pour évolutions · 1 200 DH

## B.1 Objet de la provision

Le module comptable est livré et opérationnel. Des évolutions sont d'ores déjà anticipées, dont **la gestion des chèques**, ainsi que d'autres ajustements et compléments fonctionnels qui apparaîtront à l'usage.

**Ces évolutions ne sont pas encore spécifiées.** Leur contenu exact, leur nombre et leur ordre de réalisation seront définis au fur et à mesure, en concertation avec le client. La présente provision constitue une **enveloppe budgétaire prévisionnelle** destinée à les couvrir, et non le prix d'un périmètre arrêté.

## B.2 Montant

| Désignation | Montant (DH) |
|---|--:|
| Enveloppe d'évolutions du module comptabilité | 1 200,00 |
| | |
| **SOUS-TOTAL VOLET B** | **1 200,00** |

## B.3 Modalités de consommation

- L'enveloppe est **consommée au fil des demandes**, chaque évolution étant décomptée du solde disponible.
- Chaque demande fait l'objet d'un **chiffrage préalable** (charge estimée) soumis à l'accord du client avant réalisation.
- Un **état du solde** est communiqué sur demande.
- Si l'ensemble des évolutions demandées reste inférieur à l'enveloppe, **seul le montant réellement consommé est dû**.
- Si les demandes dépassent l'enveloppe, le dépassement fait l'objet d'un **avenant** avant tout démarrage.

> La gestion des chèques est citée à titre d'évolution identifiée ; elle ne préjuge ni de son périmètre définitif ni de sa part dans l'enveloppe.

---

# 2. Récapitulatif financier

| Désignation | Montant (DH) |
|---|--:|
| Volet A — Développement réalisé (module comptabilité) | 3 800,00 |
| Volet B — Provision évolutions | 1 200,00 |
| Sous-total | 5 000,00 |
| Remise | 0,00 |
| **TOTAL** | **5 000,00** |

**Dont :**

| | Montant (DH) | Statut |
|---|--:|---|
| Exigible — travaux livrés | 3 800,00 | Réalisé |
| Prévisionnel — évolutions | 1 200,00 | À consommer |

---

# 3. Conditions

- **Validité du devis :** 30 jours à compter de la date d'émission.
- **Périmètre :** strictement limité au **module comptabilité** décrit au Volet A. Les autres modules de la plateforme IPISB Connect ne sont pas couverts par ce devis.
- **Volet A :** forfaitaire, correspondant à des développements achevés et opérationnels.
- **Volet B :** prévisionnel, non forfaitaire — facturé à la consommation réelle selon les modalités du § B.3.
- **Modalités de paiement :** à convenir (ex. Volet A à réception du devis signé, Volet B à mesure de la consommation).
- **Hors périmètre :** toute demande étrangère au module comptabilité, ainsi que tout dépassement de l'enveloppe du Volet B, fera l'objet d'un avenant.

---

_Bon pour accord (date et signature) :_
