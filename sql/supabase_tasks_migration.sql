-- ============================================================
-- IPISB Platform — Gestion des tâches (module Task Management)
-- Run this ONCE in the Supabase SQL Editor
--
-- Tableau de tâches façon Odoo/Jira : création, assignation,
-- statut, priorité, commentaires. Page isolée, pas de découpage
-- par domaine (voir le champ `domain`, un tag optionnel).
--
-- Historique/audit : réutilise la table `audit_log` existante
-- (utils/audit.py::log_audit), pas de table dédiée — même
-- convention que le reste de la plateforme. Tout l'accès passe
-- par le backend service-role, donc RLS est activé sans policy.
-- ============================================================

CREATE TABLE IF NOT EXISTS tasks (
  id                 uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  title              text        NOT NULL,
  description        text,
  status             text        NOT NULL DEFAULT 'todo'
                        CHECK (status IN ('todo', 'in_progress', 'in_review', 'done', 'blocked', 'cancelled')),
  priority           text        NOT NULL DEFAULT 'medium'
                        CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
  domain             text        CHECK (domain IN ('rh', 'comptabilite', 'scolarite', 'general')),
  assignee_id        uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_by         uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  due_date           date,
  linked_entity_type text,
  linked_entity_id   uuid,
  parent_task_id     uuid        REFERENCES tasks(id) ON DELETE SET NULL,  -- réservé pour les sous-tâches (non exposé en v1)
  position           integer     NOT NULL DEFAULT 0,                       -- ordre d'affichage dans la colonne Kanban
  created_at         timestamptz DEFAULT now(),
  updated_at         timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks(assignee_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_created_by ON tasks(created_by);

ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
-- Pas de policy : accès exclusivement via le backend service-role (voir CurrentUser.can_act()).

DROP TRIGGER IF EXISTS trg_tasks_updated_at ON tasks;
CREATE TRIGGER trg_tasks_updated_at
  BEFORE UPDATE ON tasks
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ============================================================
-- Commentaires de tâche (calqué sur candidate_comments)
-- ============================================================
CREATE TABLE IF NOT EXISTS task_comments (
  id          uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  task_id     uuid        NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  author_id   uuid        NOT NULL REFERENCES auth.users(id),
  text        text        NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_task_comments_task ON task_comments(task_id);

ALTER TABLE task_comments ENABLE ROW LEVEL SECURITY;
-- Pas de policy : accès exclusivement via le backend service-role.
