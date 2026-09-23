        # Plan de travail — Module Comptabilité IPISB Connect

        > Document de suivi de l'implémentation. Basé sur le cahier des besoins validé.
        > **Devise** MAD · **TVA** 20 % par défaut · **UI** française · **Accès** admin-only.
        > Approche : **additive** (on ne casse pas l'existant), **phasée** (1 → 2 → 3).

        ---

        ## 0. État actuel (rappel)

        | Entité | Base | API | UI | Statut |
        |---|---|---|---|---|
        | Catégories | ✅ | ✅ CRUD | ✅ | **Fait** |
        | Fournisseurs | ✅ | ✅ CRUD | ✅ | **Fait** (à enrichir) |
        | Achats (`purchases`) | ✅ | ✅ CRUD + PJ + résumé | ✅ | **Fait** (à lier DA) |
        | Pièces jointes | ✅ | ✅ (via achats) | ✅ | **Fait** |
        | Factures (`invoices`) | ✅ | ✅ CRUD | ✅ onglet | **Fait (P1 code)** |
        | Dépenses (`expenses`) | ✅ | ✅ CRUD | ✅ onglet | **Fait (P1 code)** |
        | Budgets (`budgets`) | ✅ | ✅ CRUD | ✅ onglet | **Fait (P1 code)** |
        | Devis (`quotations`) | ✅ schéma | ❌ | ❌ | **Phase 2** |
        | Recettes (`revenues`) | ✅ migration P1 | ✅ CRUD | ✅ onglet | **Fait (P1 code)** |
        | Demandes d'achat (`purchase_requests`) | ❌ | ❌ | ❌ | **Phase 2** (nouveau) |
        | Réceptions / Paiements / Inventaire | ✅ | ✅ | ✅ | **Phase 3** (fait, L10 appliquée) |

        ---

        ## Conventions repo à respecter

        **Backend** (`backend/`)
        - Router : `APIRouter(prefix="/accounting/<name>", tags=["accounting"])`, inclus dans `main.py` (import ~l.10 + `app.include_router(x.router, prefix="/api")` ~l.67). Chemin final `/api/accounting/<name>`.
        - Auth : DI `user: Depends(get_current_user)` + `db: Depends(get_db)` ; copier le helper `_require_admin(user)` (cf. `accounting_purchases.py:18`) et l'appeler en 1re ligne de chaque handler. `get_db` = client **service key** (bypass RLS).
        - Modèles : `<Entity>Create` / `<Entity>Update` (Optional) dans `models.py`, `BaseModel` simple, pas de `response_model` → on renvoie les dicts Supabase. Enums validés dans le router (`HTTPException(400)`).
        - Listes : `.select("*, fk(col)", count="exact")`, pagination `page`/`page_size` (défaut 25, 1–100), retour `{"items","total","page","page_size"}`.
        - Mutations : insert `data["created_by"]=user.id` ; update `model_dump(exclude_unset=True)` filtré, 404 si vide ; delete = guard intégrité puis `{"ok":True}`. **Toujours** `log_audit(db, user.id, "<entity>.<verb>", "<entity>", id, meta)` après mutation.
        - Pièces jointes : `BUCKET="accounting"`, table `accounting_attachments`, `validate_and_read` (PDF/JPEG/PNG, 20 Mo).

        **SQL** — migrations manuelles dans le **Supabase SQL Editor** (projet `zftnvydmjypmcjdsczjb`), fichiers `sql/supabase_<feature>_migration.sql` dans l'ordre. RLS activée **sans policy SELECT**. Colonnes : `id uuid DEFAULT gen_random_uuid() PK`, `created_by → auth.users(id) ON DELETE SET NULL`, `created_at timestamptz DEFAULT now()`, totaux `GENERATED ALWAYS AS (...) STORED`, numéros via `SEQUENCE` + `DEFAULT`.

        **Frontend** (`frontend/src/`)
        - Routes plates dot-notation (`dashboard.invoices.tsx` → `/dashboard/invoices`), auto-registrées (ne pas éditer `routeTree.gen.ts`). Garde admin = copier `beforeLoad` de `dashboard.accounting.tsx:12-21`. Nav admin dans `dashboard.tsx:98-104` + clé i18n.
        - Composants sous `components/accounting/`. Onglets = pattern custom `useState<Tab>` (pas shadcn Tabs, absent).
        - Données : `@/lib/api` (`api.get/post/patch/delete`), `try/catch` → `toast.error`. Upload = `fetch` + `FormData` + `authHeaders()`.
        - UI : listes `.dash-card` + `.row-c` ; **formulaires = modal plain `useState`** (`FormModal` dans `Purchases.tsx`, inputs `.u-input`) — pas de RHF/zod. Réutiliser `PageHead`/`SectionLabel`/`EmptyHint`/`ProgressBar`, `CountUp`, `fmtMAD`, `.btn-c-*`, `.chip-c-*`.
        - Rôle : `useAuth().roles.includes("admin")`.
        - **2 patterns net-new** : (a) graphes **Recharts** réutilisables (couleurs `--chart-1..5`/`--pal-*`, police Manrope) ; (b) formulaire multi-étapes DA + comparateur de devis → rester en plain `useState`.

        ---

        ## PHASE 1 — MVP : compléter le socle (dépenses / recettes / factures / budgets)

        > **Statut : code terminé** (compile back + build front OK). **Reste 1.4** : exécuter la
        > migration dans Supabase puis tester en réel. Écarts assumés vs plan initial :
        > colonnes en **anglais** (cohérence schéma existant), frontend en **onglets** de la page
        > Comptabilité (pas de routes séparées → sidebar propre), summary agrégé dans un router
        > dédié `accounting_dashboard.py` (`/api/accounting/dashboard/summary`).

        ### 1.1 Migration `sql/supabase_l4_accounting_phase1_migration.sql`
        - [x] `ALTER TABLE suppliers` : `legal_form`, `rib`, `bank`, `bank_branch`, `payment_terms_days` (`contact_person` réutilisé)
        - [x] `ALTER TABLE expenses` : `supplier_id → suppliers(id)`, `payment_method`
        - [x] `ALTER TABLE invoices` : `total_incl_vat` généré (cohérent avec `purchases`)
        - [x] `CREATE TABLE revenues` : n° auto `REC-`, `revenue_type`, `category_id`, `amount` (HT), `vat_percent`, `total_incl_vat` (généré), `payment_method`, `status`, `revenue_date`

        ### 1.2 Backend
        - [x] `routers/accounting_invoices.py` — CRUD + list paginée + audit
        - [x] `routers/accounting_expenses.py` — idem (+ `supplier_id`, `payment_method`)
        - [x] `routers/accounting_budgets.py` — idem (budget par catégorie/année/mois, garde UNIQUE)
        - [x] `routers/accounting_revenues.py` — idem (+ validation `revenue_type`/`status`)
        - [x] `models.py` — modèles Create/Update + `SupplierCreate/Update` étendus
        - [x] `main.py` — imports + `include_router` (5 nouveaux routers, 36 routes accounting)
        - [x] `GET /accounting/dashboard/summary` (nouveau router) : trésorerie nette, sorties/catégorie, budget vs réel, factures impayées, série trésorerie 6 mois

        ### 1.3 Frontend
        - [x] Fiche fournisseur étendue (`Suppliers.tsx` : forme juridique, RIB, banque, agence, délai paiement)
        - [x] Onglet **Factures** (`components/accounting/Invoices.tsx`, alerte échéance dépassée)
        - [x] Onglet **Dépenses** (`Expenses.tsx`)
        - [x] Onglet **Budgets** (`Budgets.tsx`, sélecteur d'exercice)
        - [x] Onglet **Recettes** (`Revenues.tsx`)
        - [x] Dashboard enrichi : KPIs `.dash-card` + graphes Recharts (camembert sorties/catégorie, barres budget vs réel, aires trésorerie)
        - [x] Onglets ajoutés dans `dashboard.accounting.tsx` (pas de nouvelles entrées sidebar → i18n inchangé)

        ### 1.4 Vérification Phase 1 — **À FAIRE (nécessite Supabase + serveurs lancés)**
        - [ ] Migration exécutée dans Supabase SQL Editor (tables/colonnes créées)
        - [ ] Chaque endpoint testé via `/docs` (créer/lister/modifier/supprimer, `audit_log` alimenté, TTC calculé, pagination)
        - [ ] Chaque onglet testé en admin (`admin1@ipisb.ma`) sur `:5178`
        - [ ] Non-régression Achats/Fournisseurs/Catégories

        ---

        ## PHASE 2 — Workflow Demande d'Achat (DA)

        ### 2.1 Migration `..._phase2_migration.sql`
        - [ ] Enums `purchase_request_type`, `asset_category`, `approval_decision`
        - [ ] `CREATE TABLE purchase_requests` (n° `DA-`, statut multi-étapes, décision besoin)
        - [ ] `ALTER quotations` (`purchase_request_id`, ordre 1–5, devise, `retenu`, synthèse)
        - [ ] `ALTER purchases` (`purchase_request_id`, `edite_par`, `valide_responsable_*`, `valide_comptable_*`, `mode_paiement`)

        ### 2.2 Backend
        - [ ] `routers/accounting_purchase_requests.py` (CRUD + transitions statut + décisions → audit)
        - [ ] `routers/accounting_quotations.py` (CRUD filtré par DA ; « retenu » verrouille les autres)
        - [ ] Étendre `purchases` : double validation (responsable → comptable) avant `commande_emise` ; lien DA + devis retenu ; garde-fou « pas de commande sans DA validée + devis retenu » (sauf seuil hors-procédure — à trancher)

        ### 2.3 Frontend
        - [ ] Liste DA (badges statut `.chip-c-*`)
        - [ ] Formulaire **multi-étapes (stepper)** reproduisant le circuit Excel
        - [ ] **Comparateur de devis** côte à côte (≤ 5)
        - [ ] Colonnes de validation sur la table Achats
        - [ ] Journal comptable = vue sur `audit_log`

        ### 2.4 Rôles (selon décision produit)
        - [ ] `admin` seul **OU** introduire `accountant` (+ approbateurs) via `user_roles` + helpers `deps.py` / `auth.tsx`

        ---

        ## PHASE 3 — Réception, Inventaire, Paiements, Contrôle qualité

        > **Statut : code terminé et vérifié** (`tsc -b` OK, `py_compile` OK, routes live sur :9000).
        > Migration `L10` **appliquée** dans Supabase. Écarts assumés vs plan initial :
        > - Migration nommée `sql/supabase_l10_phase3_reception_payments_inventory.sql` (idempotente).
        > - **Réception intégrée au détail d'un Achat** (section « Réceptions & QHSE », visible uniquement
        >   si la commande est validée par le comptable) — pas de formulaire/page dédié.
        > - **Inventaire = un seul onglet** avec filtre par `asset_category` (pas 4 onglets séparés) ;
        >   la fiche actif calcule l'amortissement linéaire (VNC, %, dotation annuelle) côté backend.
        > - **Édition de réception** ajoutée après coup (`PATCH /accounting/receptions/{id}`) pour régler
        >   les contrôles QHSE / CG / rapport comptable et le statut qualité (crayon dans la liste).
        > - **Exports corrigés** : les boutons utilisaient `window.open()` qui ne transmet pas le token
        >   Bearer → 403. Remplacés par `api.download()` (fetch authentifié + blob).
        > - « Excel » = export **CSV** (`;`, BOM UTF-8, ouvrable dans Excel), pas un `.xlsx` natif.

        ### 3.1 Migration `sql/supabase_l10_phase3_reception_payments_inventory.sql`
        - [x] `purchase_receptions` (conformité qté/qualité, QHSE, retour, contrôle qualité + `inclure_rapport_comptable`, validation CG)
        - [x] `purchase_payments` (paiement fractionné → statut `purchases` calculé)
        - [x] `inventory_items` (table unique paramétrée par `asset_category`, valeur, amortissement, `niveau_alerte`, `code_unique`)
        - [x] `inventory_movements` (entrée/sortie/ajustement)
        - [x] Étendre CHECK `accounting_attachments.entity_type` (`purchase_request`, `reception`, `inventory_item`)

        ### 3.2 Backend
        - [x] Router réceptions (`accounting_receptions.py`) : list/create/**update**/delete ; crée auto `inventory_items` + `inventory_movements` si conforme
        - [x] Router paiements (`accounting_payments.py`) : list/create/delete + recalcul auto du `payment_status` de l'achat
        - [x] Router inventaire (`accounting_inventory.py`) : CRUD + mouvements + alertes stock ≤ seuil + amortissement linéaire

        ### 3.3 Frontend
        - [x] Onglet **Inventaire** (`Inventory.tsx`) : liste filtrable par catégorie + fiche actif (amortissement, mouvements, alertes)
        - [x] Onglet **Paiements** (`Payments.tsx`) par achat (solde dû)
        - [x] **Réception + contrôle qualité** intégrée au détail Achat (`Purchases.tsx`) + édition QHSE
        - [x] Exports PDF (bon de commande, fiche DA, rapport comptable) + CSV — via `api.download()` authentifié

        ---

        ## Décisions produit ouvertes (à trancher avec le client — n'empêchent pas la Phase 1)
        1. **Modèle de rôles** : `admin` seul vs nouveau `accountant` + approbateurs → **défaut retenu : `admin` seul en Phase 1**
        2. Seuil « hors procédure » (commande sans DA complète)
        3. Recettes liées à un élève (passerelle Scolarité) ou globales → **défaut : globales en Phase 1**
        4. Méthode / durée d'amortissement
        5. Périmètre du dashboard (compta pure vs pilotage global)

        ---

        ## Fichiers clés
        - **Créer** : `sql/supabase_l4_accounting_phase{1,2,3}_migration.sql` ; `backend/routers/accounting_{invoices,expenses,budgets,revenues,purchase_requests,quotations,receptions,payments,inventory}.py` ; `frontend/src/components/accounting/*` + `frontend/src/routes/dashboard.*.tsx`
        - **Modifier** : `backend/main.py`, `backend/models.py`, `backend/routers/accounting_purchases.py`, `frontend/src/routes/dashboard.tsx` (nav), dashboard compta, `deps.py` / `auth.tsx` (si nouveaux rôles)

        ---

        *Réf. plan validé : `~/.claude/plans/cahier-des-besoins-cached-kahan.md` · Briefing : `BRIEFING_COMPTABILITE.md`*
