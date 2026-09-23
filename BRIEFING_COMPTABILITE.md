# Briefing — Module Comptabilité IPISB Connect

> **But de ce document**
> Ce fichier sert à briefer une IA (Claude) sur le projet **IPISB Connect** et sur le **besoin actuel** : concevoir/compléter la **section Comptabilité**.
>
> **Workflow prévu :**
> 1. On donne à l'IA **ce document** + le **fichier Excel du client**.
> 2. L'IA lit l'Excel + ce contexte, et produit un **cahier des besoins précis** (spec) — voir la section [« PROMPT à donner à l'IA »](#-prompt-à-donner-à-lia) et le [format de sortie attendu](#-format-de-sortie-attendu-la-spec).
> 3. On rapporte cette spec à Claude Code, qui l'implémente dans le projet.

---

## 1. Contexte projet

**IPISB Connect** est une plateforme de gestion d'un établissement scolaire (institut privé, Maroc). Elle gère cours, devoirs, examens, réunions/visios, agenda, annonces, documents, notifications, et une section **Comptabilité** (achats, fournisseurs, budgets…).

- **Langue de l'interface :** français.
- **Devise :** MAD (Dirham marocain).
- **TVA de référence :** 20 % (Maroc), modifiable par ligne.
- **Utilisateurs / rôles :** `admin`, `professor`, `student`.
  → **La comptabilité est réservée aux `admin`** (routes backend admin-only).

## 2. Stack technique

- **Frontend :** React 19 + TypeScript + Vite + **TanStack Router** + Tailwind CSS v4 + **shadcn/ui** (Radix). Recharts pour les graphes. Framer Motion pour les animations.
- **Backend :** FastAPI (Python 3.11) — dossier `backend/`. Utilise la **service key** Supabase (bypass RLS).
- **Base de données :** Supabase (PostgreSQL + Auth + Storage).
- **Auth :** Supabase Auth. Les rôles sont dans la table `user_roles` (`user_id` → `role`), le profil dans `profiles`.

**Lancer en local :**
- Backend : `cd backend && venv\Scripts\activate && uvicorn main:app --reload --port 9000` → http://localhost:9000/docs
- Frontend : `cd frontend && npm run dev` → http://localhost:5178

## 3. Design system (OBLIGATOIRE)

Toute UI doit respecter `DESIGN_SYSTEM.md` (racine) :
- **Couleurs :** variables `--pal-*` (OKLCH). Identité **teal** premium.
- **Polices :** Cormorant Garamond (titres), Manrope (UI).
- **Composants :** cartes `.dash-card` ; boutons `.btn-c-primary` / `.btn-c-ghost` / `.btn-c-soft` / `.btn-c-danger` ; badges `.chip-c` (`-green`, `-amber`, `-red`, `-blue`) ; animations `.anim-rise` / `.anim-pop` / `.anim-fade`.
- Aperçu visuel : `Système Designe ipisbe/Design System.dc.html`.

---

## 4. État ACTUEL du module Comptabilité (très important)

Le module existe déjà **partiellement** (migration « L4 Comptabilité »). Il ne faut **pas repartir de zéro** : la spec doit dire quoi **garder**, **compléter**, **modifier**, **ajouter**.

### Fichiers concernés
- SQL : `sql/supabase_l4_accounting_migration.sql`
- Backend : `backend/routers/accounting_categories.py`, `accounting_suppliers.py`, `accounting_purchases.py`
- Frontend : `frontend/src/components/accounting/Purchases.tsx`
- Stockage : bucket Supabase privé `accounting` (pièces jointes).

### Tables déjà créées

| Table | Rôle | Statut endpoints |
|---|---|---|
| `accounting_categories` | Catégories de dépenses (nom unique) | ✅ CRUD (GET/POST/DELETE) |
| `suppliers` | Fournisseurs (raison sociale, contact, email, tél, adresse, ICE/n° fiscal, notes) | ✅ CRUD (GET/POST/PATCH/DELETE) |
| `purchases` | **Achats** — n° auto `PUR-000001`, titre, catégorie, fournisseur, quantité, PU, total HT (calculé), TVA %, total TTC (calculé), devise (MAD), date, statut paiement (`pending`/`partially_paid`/`paid`), mode de paiement, demandeur, approbateur, notes | ✅ CRUD complet + pièces jointes + résumé dashboard |
| `accounting_attachments` | Pièces jointes génériques (achat/facture/devis/dépense) → bucket `accounting` | ✅ (via purchases) |
| `invoices` | **Factures** (n°, fournisseur, achat lié, dates, montant, TVA, statut) | ⚠️ Schéma seul — **PAS d'endpoints** |
| `quotations` | **Devis** (fournisseur, n°, dates, montant, statut `waiting`/`approved`/`rejected`) | ⚠️ Schéma seul — **PAS d'endpoints** |
| `expenses` | **Dépenses** (titre, catégorie, montant, date, description, employé responsable) | ⚠️ Schéma seul — **PAS d'endpoints** |
| `budgets` | **Budgets** par catégorie / année / mois (mois NULL = budget annuel) | ⚠️ Schéma seul — **PAS d'endpoints** |

### Endpoints backend existants (préfixe `/accounting`, admin-only)
- **Catégories :** `GET`, `POST`, `DELETE /{id}`
- **Fournisseurs :** `GET`, `POST`, `PATCH /{id}`, `DELETE /{id}`
- **Achats :** `GET` (liste + filtres), `GET /{id}`, `POST`, `PATCH /{id}`, `DELETE /{id}`, `POST /{id}/attachments`, `GET /attachments/{id}/download`, `DELETE /attachments/{id}`, `GET /dashboard/summary`

### Ce qui manque (à concevoir/prioriser via l'Excel + la marge créative)
- Endpoints + UI pour **factures**, **devis**, **dépenses**, **budgets**.
- **Recettes / encaissements** (frais de scolarité, inscriptions…) — pas encore modélisé.
- **Tableaux de bord financiers** enrichis (trésorerie, dépenses par catégorie, budget vs réel, échéancier des paiements).
- **Rapports & exports** (PDF/Excel), éventuellement journal comptable.
- Éventuels liens avec la **scolarité** (paiements élèves), si le client le souhaite.

### Notes techniques
- Le backend tourne sur la **service key** et **bypasse la RLS** ; les tables compta n'ont **pas de policy SELECT** (seul le backend admin lit/écrit).
- Le **journal d'audit** réutilise la table `audit_log` (colonne `meta` jsonb), pas de table dédiée.
- Montants en **`numeric`**, totaux **calculés côté DB** (colonnes générées) pour les achats.

---

## 5. Le BESOIN actuel (à faire comprendre à l'IA)

> Le **client** de la partie comptabilité **ne sait pas exactement ce qu'il veut**. Il a fourni **un fichier Excel** contenant quelques informations (structure, colonnes, exemples de données), et il **laisse une marge de créativité**.
>
> Objectif : transformer ce flou + l'Excel en une **spec claire, complète et implémentable**, cohérente avec le module existant ci-dessus et avec le design system, en **proposant** les bonnes pratiques (ce que le client devrait vouloir) sans attendre qu'il les demande.

---

## 🎯 PROMPT à donner à l'IA

> Copier-coller ce prompt à l'IA, **en joignant le fichier Excel du client** et **ce document (`BRIEFING_COMPTABILITE.md`)**.

```
Tu es analyste fonctionnel + architecte produit pour un logiciel de gestion scolaire (IPISB Connect, Maroc, devise MAD, TVA 20%).

Contexte : lis le document "BRIEFING_COMPTABILITE.md" ci-joint — il décrit le projet, le design system, et surtout le MODULE COMPTABILITÉ DÉJÀ EXISTANT (tables, endpoints, ce qui marche, ce qui manque). Ne réinvente pas ce qui existe : appuie-toi dessus.

Le client de la partie comptabilité ne sait pas exactement ce qu'il veut. Il fournit uniquement le fichier Excel ci-joint (quelques infos + exemples) et laisse une marge de créativité.

Ta mission : produire un CAHIER DES BESOINS PRÉCIS ET IMPLÉMENTABLE pour la section Comptabilité, prêt à être exécuté par un développeur (Claude Code).

Étapes :
1. Analyse l'Excel : liste chaque feuille, chaque colonne (nom, type, exemple), les relations, formules, totaux, et déduis le PROCESSUS métier réel que le client suit aujourd'hui.
2. Confronte l'Excel au module existant : ce qui correspond (mapping colonne Excel → table/champ existant), ce qui manque, ce qui doit être ajouté ou modifié.
3. Comble les zones floues par des PROPOSITIONS argumentées (bonnes pratiques compta d'un établissement scolaire marocain), en signalant clairement ce qui est "hypothèse à valider par le client".
4. Rends la spec au format défini dans la section "FORMAT DE SORTIE ATTENDU" du briefing.

Règles :
- Français. Devise MAD, TVA 20% par défaut.
- Respecte le design system (cartes .dash-card, teal OKLCH, Cormorant/Manrope).
- Réutilise les tables/endpoints existants ; propose des migrations additives (ne casse pas l'existant).
- Distingue clairement : [EXISTANT] / [À COMPLÉTER] / [NOUVEAU] / [HYPOTHÈSE À VALIDER].
- Priorise en Phase 1 / Phase 2 / Phase 3.
- Termine par une liste de QUESTIONS ouvertes à poser au client.
```

---

## 📋 FORMAT DE SORTIE ATTENDU (la spec)

La spec produite par l'IA doit contenir ces sections :

1. **Synthèse (1 paragraphe)** — ce que fait le client aujourd'hui, ce qu'on propose de construire.
2. **Analyse de l'Excel** — tableau feuille par feuille : colonne → type → exemple → interprétation.
3. **Mapping avec l'existant** — tableau : élément Excel → table/champ existant → statut ([EXISTANT]/[À COMPLÉTER]/[NOUVEAU]).
4. **Modèle de données cible** — tables & champs (existants + nouveaux), relations, colonnes calculées, contraintes. Fournir les **migrations SQL additives**.
5. **Fonctionnalités** — liste par entité (achats, fournisseurs, factures, devis, dépenses, recettes, budgets…) : opérations (CRUD, validation, statuts), règles de gestion (TVA, totaux, échéances, approbations).
6. **Écrans / UI** — liste des pages et de leurs composants (tableaux, filtres, formulaires, KPIs, graphes Recharts), cohérents avec le design system.
7. **Tableaux de bord & rapports** — KPIs, graphes, exports (PDF/Excel), journal comptable si pertinent.
8. **Rôles & permissions** — qui voit/fait quoi (admin, et éventuellement un rôle « comptable » à créer ?).
9. **Contraintes Maroc** — TVA, MAD, mentions factures (ICE, n° fiscal), numérotation légale.
10. **Découpage en phases** — Phase 1 (MVP), Phase 2, Phase 3, avec priorités.
11. **Questions ouvertes au client** — points à valider (hypothèses).

---

*Document généré pour préparer la phase Comptabilité — à joindre au fichier Excel du client.*
