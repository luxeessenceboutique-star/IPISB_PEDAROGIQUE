# PASSATION — IPISB Connect / Module Comptabilité (achats)

## Contexte projet
- Plateforme IPISB Connect. Stack : React 19 + TS + Vite + TanStack Router + Tailwind v4 (frontend/), FastAPI Python 3.14 (backend/), Supabase (PostgreSQL).
- Branche git : `dev/aymen`. Date de travail : 27/07/2026.
- Design system OBLIGATOIRE : lire `DESIGN_SYSTEM.md` + variables `--pal-*` (OKLCH), polices Cormorant/Manrope, classes `.dash-card`, `.btn-c-*`, `.chip-c`.

## Lancer en local
- Backend : `cd backend && venv\Scripts\activate && uvicorn main:app --reload --port 9000`
- Frontend : `cd frontend && npm run dev` → http://localhost:5178 | API docs :9000/docs
- Typecheck front : `cd frontend && npx tsc --noEmit -p tsconfig.json`
- Check syntaxe back : `./venv/Scripts/python.exe -c "import ast; ast.parse(open('FICHIER',encoding='utf-8').read())"`
- ⚠️ Piège récurrent : un worker uvicorn --reload devient ORPHELIN si le parent meurt → sert du code périmé et ne recharge plus. Symptôme : `{"detail":"Not Found"}` ou modif invisible. Fix : tuer les workers sur le port 9000 et relancer un uvicorn frais depuis le venv.

## Workflow achats
DA (demande d'achat / purchase_requests) → devis (quotations) → échéancier (purchase_installments) → commande (purchases) → paiements (purchase_payments).
- L'échéancier est rattaché à la DA (`purchase_installments.purchase_request_id`), éditable après choix du devis (statut `devis_valide`). Total LIBRE (peut dépasser le devis).
- Modes de paiement (chaîne achats) : `ov_permanent, ov_ponctuel, cheque, caisse_sociale, autre`. `caisse_sociale` → axe n/c = "noir" (caisse sociale).

## Migrations SQL — À APPLIQUER dans Supabase (SQL Editor), dans l'ordre
l27 → l28 → l29 → l30 → l31
- l29 `supabase_l29_installments_on_request.sql` : installments rattachés à purchase_request_id.
- l30 `supabase_l30_merge_caisse_sociale.sql` : fusion 'versement'+'espece' → 'caisse_sociale' (chaîne achats SEULEMENT ; recettes NON concernées). Ordre critique DROP contraintes → UPDATE → ADD (sinon ERROR 23514). ✅ confirmé appliqué.
- l31 `supabase_l31_quotation_delivery_included.sql` : ajoute `quotations.delivery_included` (bool) + rend `delivery_cost` nullable. (probablement appliqué — l'affichage décomposé marche.)

## Fait cette session
1. **Livraison sur devis** : `delivery_cost` NULL=inconnu / 0=gratuite / >0=payant ; `delivery_included` (incluse dans amount ou en sus). Affichage décomposé "4800 + 50" (PAS de somme) si en sus. Fichiers : models.py (QuotationCreate/Update), pdf_generators.py (bloc livraison), PurchaseRequests.tsx (Quote type, fmtNum, quoteAmountLabel, chip livraison, QuoteFormModal toggle En sus/Incluse + coût vide autorisé).
2. **Dépassement budget = pourboire livreur** : échéancier peut dépasser le devis sans blocage. "Pourboire livreur" ajouté à JALON_SUGGESTIONS ; libellé "Dépassement : X · caisse sociale" (au lieu d'une erreur). La compta RÉELLE en caisse sociale se fait au paiement effectif (onglet Paiements, mode Caisse sociale).
3. **Échéancier dans le PDF de la DA** : ajouté `installments` param à `render_purchase_request_pdf(pr, quotes, installments)` (pdf_generators.py, bloc après "Décision") + fetch des installments dans l'endpoint `GET /accounting/purchase-requests/{pr_id}/pdf` (accounting_purchase_requests.py). Syntaxe validée. ⚠️ NON VÉRIFIÉ à l'écran — le PDF testé ne montrait pas l'échéancier (voir "À vérifier").

## À VÉRIFIER EN PRIORITÉ
- Le PDF DA (bouton export) doit afficher le bloc "Mode & échéancier de paiement (prévisionnel)". Sur le dernier test il n'apparaissait pas. Vérifier : (a) backend bien rechargé sur du code frais ; (b) les rows purchase_installments de la DA existent bien avec purchase_request_id renseigné (SELECT en base).

## À FAIRE (backlog)
- Brancher recettes/dépenses/paiements achat/scolarité au JOURNAL DE CAISSE via un helper généralisé (l'échéancier reste prévisionnel, il n'alimente pas encore le journal).
- Échéance paiement scolarité : jour réglable (défaut 1, tolérance 9) + alertes J / J+5 danger / J+10 critique.

## Fichiers clés
- backend/utils/pdf_generators.py : render_purchase_request_pdf (~326), render_purchase_order_pdf (~102, a déjà l'échéancier).
- backend/routers/accounting_purchase_requests.py : endpoints installments GET/PUT + export PDF (~414).
- backend/models.py : QuotationCreate/Update (~409-435).
- frontend/src/components/accounting/PurchaseRequests.tsx : Quote type, QuoteFormModal, PaymentSchedule/ScheduleTotals, JALON_SUGGESTIONS.
