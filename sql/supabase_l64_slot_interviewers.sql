-- L64 — Lier les créneaux d'entretien à leurs interviewers
-- --------------------------------------------------------------
-- Demande : « Lier les créneaux aux admins et aux collaborateurs (ex.
-- Leila, Houda), avec possibilité d'ajouter ou modifier les personnes qui
-- vont entretenir les candidats. »
--
-- Jusqu'ici, interviewer_ids n'existait qu'au niveau de l'entretien
-- (interview_interviewers), assigné seulement une fois le créneau réservé
-- pour un candidat précis. On l'ajoute aussi au créneau lui-même pour
-- pouvoir décider à l'avance qui reçoit sur ce créneau, avant même qu'un
-- candidat y soit affecté.

ALTER TABLE hr_slots ADD COLUMN IF NOT EXISTS interviewer_ids uuid[] NOT NULL DEFAULT '{}';
