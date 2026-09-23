-- ============================================================
-- IPISB Platform — L4 Comptabilité · Phase 1 Migration
-- Run this ONCE in the Supabase SQL Editor, AFTER
-- supabase_l4_accounting_migration.sql.
--
-- Phase 1 wires up full CRUD for: invoices, expenses, budgets and the
-- new `revenues` table, plus an aggregated accounting dashboard. This
-- migration only touches what those endpoints need:
--   • suppliers  → banking / legal-form fields
--   • expenses   → supplier link + payment method
--   • invoices   → computed total_incl_vat (mirrors purchases)
--   • revenues   → NEW table (auto-numbered "REC-", computed TTC)
--
-- Column names stay in English to match the existing accounting schema
-- (amount / vat_percent / total_incl_vat / payment_method / category_id).
-- French only appears in the UI labels.
--
-- Every statement is idempotent (IF NOT EXISTS / ADD COLUMN IF NOT EXISTS)
-- so re-running is safe.
-- ============================================================

-- ============================================================
-- 1. Suppliers — extended fiche (banking + legal form)
-- ============================================================
ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS legal_form         text;      -- SARL, SA, auto-entrepreneur…
ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS rib                text;      -- Relevé d'Identité Bancaire (24 digits)
ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS bank               text;
ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS bank_branch        text;      -- agence
ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS payment_terms_days integer;   -- délai de paiement (jours)
-- NB: `contact_person` already exists — it covers the "personne de contact".

-- ============================================================
-- 2. Expenses — supplier link + payment method
-- ============================================================
ALTER TABLE expenses ADD COLUMN IF NOT EXISTS supplier_id    uuid REFERENCES suppliers(id) ON DELETE SET NULL;
ALTER TABLE expenses ADD COLUMN IF NOT EXISTS payment_method text;

CREATE INDEX IF NOT EXISTS idx_expenses_supplier ON expenses(supplier_id);

-- ============================================================
-- 3. Invoices — computed TTC (treats existing `amount` as HT)
-- ============================================================
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS total_incl_vat numeric
  GENERATED ALWAYS AS (amount * (1 + vat_percent / 100)) STORED;

-- ============================================================
-- 4. Revenues — NEW · auto-numbered "REC-000001", computed TTC
-- ============================================================
CREATE SEQUENCE IF NOT EXISTS revenue_number_seq;

CREATE TABLE IF NOT EXISTS revenues (
  id              uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  revenue_number  text        NOT NULL UNIQUE DEFAULT ('REC-' || lpad(nextval('revenue_number_seq')::text, 6, '0')),
  title           text        NOT NULL,
  revenue_type    text        NOT NULL DEFAULT 'other'
                                CHECK (revenue_type IN ('tuition', 'subsidy', 'donation', 'service', 'other')),
  category_id     uuid        REFERENCES accounting_categories(id) ON DELETE SET NULL,
  amount          numeric     NOT NULL DEFAULT 0,          -- HT
  vat_percent     numeric     NOT NULL DEFAULT 0,
  total_incl_vat  numeric     GENERATED ALWAYS AS (amount * (1 + vat_percent / 100)) STORED,
  payment_method  text,
  status          text        NOT NULL DEFAULT 'received'
                                CHECK (status IN ('expected', 'received', 'cancelled')),
  revenue_date    date        NOT NULL DEFAULT CURRENT_DATE,
  description     text,
  created_by      uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at      timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_revenues_category ON revenues(category_id);
CREATE INDEX IF NOT EXISTS idx_revenues_date     ON revenues(revenue_date);
CREATE INDEX IF NOT EXISTS idx_revenues_status   ON revenues(status);

ALTER TABLE revenues ENABLE ROW LEVEL SECURITY;
-- No SELECT policy: like the rest of the accounting schema, revenues are
-- readable/writable only by the FastAPI backend (service key, admin routes).

-- ============================================================
-- Done. Backend runs on the service key and bypasses RLS everywhere above.
-- ============================================================
