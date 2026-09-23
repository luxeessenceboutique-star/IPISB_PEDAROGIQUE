-- ============================================================
-- IPISB Platform — L4 Comptabilité (Accounting & Purchasing) Migration
-- Run this ONCE in the Supabase SQL Editor
--
-- Phase 1 (this build) wires up full CRUD for: categories, suppliers,
-- purchases + the dashboard summary. invoices/quotations/expenses/budgets
-- are created now (so purchases/invoices FKs are stable) but ship without
-- endpoints yet — Phase 2/3 will add those.
--
-- Audit trail reuses the existing `audit_log` table from the L2 migration
-- (utils/audit.py) rather than a second audit_logs table — old/new values
-- are stored in its `meta` jsonb column.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================
-- 1. Categories
-- ============================================================
CREATE TABLE IF NOT EXISTS accounting_categories (
  id         uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  name       text        NOT NULL UNIQUE,
  created_by uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at timestamptz DEFAULT now()
);

ALTER TABLE accounting_categories ENABLE ROW LEVEL SECURITY;
-- No SELECT policy: financial data is backend-service-key only.

-- ============================================================
-- 2. Suppliers
-- ============================================================
CREATE TABLE IF NOT EXISTS suppliers (
  id              uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  company_name    text        NOT NULL,
  contact_person  text,
  email           text,
  phone           text,
  address         text,
  tax_number      text,
  notes           text,
  created_by      uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at      timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_suppliers_company_name ON suppliers USING gin (company_name gin_trgm_ops);

ALTER TABLE suppliers ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- 3. Purchases — auto-numbered "PUR-000001", computed totals
-- ============================================================
CREATE SEQUENCE IF NOT EXISTS purchase_number_seq;

CREATE TABLE IF NOT EXISTS purchases (
  id               uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  purchase_number  text        NOT NULL UNIQUE DEFAULT ('PUR-' || lpad(nextval('purchase_number_seq')::text, 6, '0')),
  title            text        NOT NULL,
  description      text,
  category_id      uuid        REFERENCES accounting_categories(id) ON DELETE SET NULL,
  supplier_id      uuid        REFERENCES suppliers(id) ON DELETE SET NULL,
  quantity         numeric     NOT NULL DEFAULT 1,
  unit_price       numeric     NOT NULL DEFAULT 0,
  total_price      numeric     GENERATED ALWAYS AS (quantity * unit_price) STORED,
  vat_percent      numeric     NOT NULL DEFAULT 20,
  total_incl_vat   numeric     GENERATED ALWAYS AS (quantity * unit_price * (1 + vat_percent / 100)) STORED,
  currency         text        NOT NULL DEFAULT 'MAD',
  purchase_date    date        NOT NULL DEFAULT CURRENT_DATE,
  payment_status   text        NOT NULL DEFAULT 'pending' CHECK (payment_status IN ('pending', 'partially_paid', 'paid')),
  payment_method   text,
  requested_by     uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  approved_by      uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  notes            text,
  created_by       uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at       timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_purchases_category ON purchases(category_id);
CREATE INDEX IF NOT EXISTS idx_purchases_supplier ON purchases(supplier_id);
CREATE INDEX IF NOT EXISTS idx_purchases_date     ON purchases(purchase_date);
CREATE INDEX IF NOT EXISTS idx_purchases_status   ON purchases(payment_status);
CREATE INDEX IF NOT EXISTS idx_purchases_title_trgm ON purchases USING gin (title gin_trgm_ops);

ALTER TABLE purchases ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- 4. Attachments — generic, reused by purchases/invoices/quotations/expenses
-- ============================================================
CREATE TABLE IF NOT EXISTS accounting_attachments (
  id            uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  entity_type   text        NOT NULL CHECK (entity_type IN ('purchase', 'invoice', 'quotation', 'expense')),
  entity_id     uuid        NOT NULL,
  kind          text        NOT NULL DEFAULT 'document', -- 'quotation' | 'invoice' | 'receipt' | 'document'
  file_path     text        NOT NULL,
  file_name     text        NOT NULL,
  file_type     text        NOT NULL,
  file_size     integer     NOT NULL,
  uploaded_by   uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at    timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_accounting_attachments_entity ON accounting_attachments(entity_type, entity_id);

ALTER TABLE accounting_attachments ENABLE ROW LEVEL SECURITY;

INSERT INTO storage.buckets (id, name, public)
VALUES ('accounting', 'accounting', false)
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 5. Invoices (schema only — CRUD ships in a later phase)
-- ============================================================
CREATE TABLE IF NOT EXISTS invoices (
  id               uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  invoice_number   text        NOT NULL,
  supplier_id      uuid        REFERENCES suppliers(id) ON DELETE SET NULL,
  purchase_id      uuid        REFERENCES purchases(id) ON DELETE SET NULL,
  invoice_date     date        NOT NULL DEFAULT CURRENT_DATE,
  due_date         date,
  amount           numeric     NOT NULL DEFAULT 0,
  vat_percent      numeric     NOT NULL DEFAULT 20,
  payment_status   text        NOT NULL DEFAULT 'pending' CHECK (payment_status IN ('pending', 'partially_paid', 'paid')),
  created_by       uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at       timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_invoices_supplier ON invoices(supplier_id);
CREATE INDEX IF NOT EXISTS idx_invoices_purchase ON invoices(purchase_id);
CREATE INDEX IF NOT EXISTS idx_invoices_due_date  ON invoices(due_date);

ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- 6. Quotations (schema only)
-- ============================================================
CREATE TABLE IF NOT EXISTS quotations (
  id               uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  supplier_id      uuid        REFERENCES suppliers(id) ON DELETE SET NULL,
  quote_number     text        NOT NULL,
  quote_date       date        NOT NULL DEFAULT CURRENT_DATE,
  expiration_date  date,
  amount           numeric     NOT NULL DEFAULT 0,
  status           text        NOT NULL DEFAULT 'waiting' CHECK (status IN ('waiting', 'approved', 'rejected')),
  created_by       uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at       timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_quotations_supplier ON quotations(supplier_id);
CREATE INDEX IF NOT EXISTS idx_quotations_expiration ON quotations(expiration_date);

ALTER TABLE quotations ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- 7. Expenses (schema only)
-- ============================================================
CREATE TABLE IF NOT EXISTS expenses (
  id                    uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  title                 text        NOT NULL,
  category_id           uuid        REFERENCES accounting_categories(id) ON DELETE SET NULL,
  amount                numeric     NOT NULL DEFAULT 0,
  expense_date          date        NOT NULL DEFAULT CURRENT_DATE,
  description           text,
  responsible_employee  uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_by            uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at            timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category_id);
CREATE INDEX IF NOT EXISTS idx_expenses_date     ON expenses(expense_date);

ALTER TABLE expenses ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- 8. Budgets (schema only)
-- ============================================================
CREATE TABLE IF NOT EXISTS budgets (
  id           uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  category_id  uuid        REFERENCES accounting_categories(id) ON DELETE CASCADE,
  year         integer     NOT NULL,
  month        integer     CHECK (month BETWEEN 1 AND 12), -- NULL = yearly budget
  amount       numeric     NOT NULL DEFAULT 0,
  created_by   uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at   timestamptz DEFAULT now(),
  UNIQUE (category_id, year, month)
);

ALTER TABLE budgets ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- Backend runs on the service key and bypasses RLS everywhere above;
-- these tables intentionally have no SELECT policy — only the FastAPI
-- backend (admin-only routes) can read/write accounting data.
-- ============================================================
