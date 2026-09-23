# IPISB Connect — Plateforme de gestion pédagogique

---

## C'est quoi ce projet ? (Explication pour quelqu'un qui n'a aucune idée)

Imagine une école d'infirmiers. Les étudiants doivent suivre des cours, rendre des devoirs, passer des examens. Les professeurs doivent gérer leurs classes, corriger les travaux, planifier des réunions. Le directeur doit gérer tout le monde.

Avant ce projet, tout ça se faisait probablement par WhatsApp, email, papier. **IPISB Connect** remplace tout ça par une plateforme web moderne — comme un mélange entre Moodle (la plateforme scolaire) et Google Classroom, mais fait sur mesure pour l'Institut Privé Infirmier Spécialisé de Beni Mellal au Maroc.

En plus de la gestion pédagogique, le projet intègre un **chatbot d'admission intelligent** qui répond aux questions des futurs étudiants en français, anglais, arabe et darija (dialecte marocain), et collecte automatiquement leurs dossiers de candidature.

---

## A quoi sert concrètement l'application ?

### Pour les étudiants
- Consulter les cours auxquels ils sont inscrits
- Télécharger les ressources pédagogiques (PDF, vidéos, liens)
- Rendre des devoirs en ligne (upload de fichiers)
- Passer des examens QCM directement sur la plateforme
- Voir leurs notes et feedbacks
- Consulter leur emploi du temps et les réunions planifiées
- Recevoir des notifications en temps réel (devoir noté, examen publié, etc.)

### Pour les professeurs
- Créer et gérer des cours (titre, description, code, semestre, crédits)
- Ajouter des ressources à un cours (fichiers, vidéos YouTube, liens externes)
- Créer des devoirs avec date limite et note maximale
- Corriger les rendus des étudiants et laisser un feedback
- Créer des examens QCM avec correction automatique
- Planifier des réunions/séances pour leurs classes
- Gérer leurs classes (créer, ajouter des étudiants)
- Créer des comptes pour leurs étudiants

### Pour les administrateurs
- Tout ce que fait un professeur, plus :
- Gérer tous les utilisateurs (créer des professeurs)
- Voir les statistiques globales de la plateforme
- Gérer toutes les classes et tous les cours

### Pour les futurs étudiants (candidats)
- Sur la page publique du site, un chatbot nommé **Aya** répond à leurs questions sur l'école
- Aya guide le candidat pour remplir son dossier de candidature en conversant
- Le dossier est automatiquement enregistré dans un CRM (Airtable) pour le service admission

---

## Architecture du projet — Les 3 grandes parties

Le projet est divisé en 3 dossiers principaux :

```
IPISB-CONNECT/
├── frontend/    → Ce que l'utilisateur voit dans son navigateur (React)
├── backend/     → Le serveur qui traite les données (Python/FastAPI)
└── sql/         → Les scripts de création de la base de données
```

### Comment les 3 parties communiquent

```
[Navigateur de l'utilisateur]
         │
         │  HTTP/HTTPS (requêtes API)
         ▼
[Backend FastAPI — Railway]  ◄──► [Base de données Supabase PostgreSQL]
         │                                    │
         │                         [Stockage de fichiers Supabase]
         │
         ▼
[Services externes]
  ├── Supabase Auth (connexion/déconnexion)
  ├── Resend (emails automatiques)
  ├── Airtable (CRM candidatures)
  └── OpenAI (IA pour le chatbot)
```

---

## Le Frontend (ce que voit l'utilisateur)

**Technologie :** React 19 + TypeScript + Vite + Tailwind CSS

Le frontend est une **SPA (Single Page Application)** — ça veut dire que toute l'application charge une seule fois et ensuite navigue sans recharger la page, comme une app mobile.

### Pages publiques (accessibles sans connexion)

| Route | Description |
|---|---|
| `/` | Page d'accueil avec présentation de l'école, fonctionnalités, témoignages, actualités |
| `/plateforme` | Présentation détaillée de la plateforme |
| `/formations` | Détail des formations proposées |
| `/a-propos` | Page "À propos" de l'institution |
| `/actualites` | Actualités et articles de l'école |
| `/temoignages` | Témoignages d'anciens étudiants |
| `/contact` | Formulaire de contact |
| `/auth` | Page de connexion |

Sur toutes les pages publiques, un **widget chatbot flottant** (Aya) est disponible en bas à droite.

### Dashboard (espace privé après connexion)

| Route | Qui peut y accéder | Description |
|---|---|---|
| `/dashboard` | Tous | Vue d'ensemble avec statistiques personnalisées |
| `/dashboard/courses` | Tous | Liste des cours + gestion des ressources |
| `/dashboard/assignments` | Tous | Devoirs + soumission/correction |
| `/dashboard/exams` | Tous | Examens + interface de passage |
| `/dashboard/agenda` | Tous | Calendrier personnel |
| `/dashboard/meetings` | Tous | Réunions et séances planifiées |
| `/dashboard/classes` | Admin, Professeur | Gestion des classes |
| `/dashboard/users` | Admin, Professeur | Gestion des utilisateurs |
| `/dashboard/notifications` | Tous | Centre de notifications |
| `/dashboard/profile` | Tous | Profil utilisateur |

### Composants notables

- **ChatWidget.tsx** — Le chatbot d'admission Aya, avec sélecteur de langue (FR/EN/AR/Darija)
- **SiteNav.tsx** — Barre de navigation des pages publiques
- **Skeletons.tsx** — Placeholders de chargement (évite les écrans vides)
- **dashboard/ui.tsx** — Composants réutilisables du dashboard
- **landing/** — Toutes les sections de la page d'accueil (Hero, Features, Programs, etc.)

### Bibliothèques UI

Le projet utilise **shadcn/ui** — une collection de composants accessibles construits sur **Radix UI**. Ça veut dire que tous les boutons, formulaires, dialogues, tableaux, etc. viennent de cette librairie et ont un design cohérent.

---

## Le Backend (le serveur)

**Technologie :** Python 3.11 + FastAPI + Supabase

Le backend est une **API REST** — il reçoit des requêtes HTTP, traite les données, et renvoie des réponses JSON. Il tourne sur Railway (hébergeur cloud).

### Fichiers principaux

| Fichier | Rôle |
|---|---|
| `main.py` | Point d'entrée de l'app, configure CORS, inclut tous les routers |
| `deps.py` | Dépendances partagées : connexion DB, authentification, récupération de l'utilisateur connecté |
| `models.py` | Schémas de données Pydantic (validation des requêtes/réponses) |
| `requirements.txt` | Liste des bibliothèques Python nécessaires |
| `seed_admins.py` | Script pour créer les premiers comptes administrateurs |

### Les 11 modules de routes (routers/)

Chaque fichier dans `routers/` gère un groupe de fonctionnalités :

#### `courses.py` — Gestion des cours
- Lister les cours (filtré selon le rôle)
- Créer, modifier, supprimer un cours
- Associer un cours à une classe
- Publier un cours

#### `assignments.py` — Devoirs
- Lister les devoirs avec leurs soumissions
- Créer un devoir
- Soumettre un rendu (avec upload de fichier)
- Corriger une soumission (note + feedback) → déclenche un email automatique
- Supprimer un devoir

#### `exams.py` — Examens
- Lister les examens disponibles
- Créer un examen avec ses questions QCM
- Publier un examen
- Soumettre les réponses → correction automatique
- Consulter les résultats

#### `meetings.py` — Réunions et séances
- Lister les réunions (selon la classe de l'utilisateur)
- Planifier, modifier, supprimer une réunion

#### `agenda.py` — Calendrier
- Ajouter, modifier, supprimer des événements au calendrier
- Vue personnelle des événements

#### `classes.py` — Classes
- Créer une classe (groupe d'étudiants)
- Lister les étudiants d'une classe
- Ajouter un étudiant à une classe
- Supprimer une classe

#### `users.py` — Utilisateurs
- Lister tous les utilisateurs
- Créer un utilisateur (admin crée prof → prof crée étudiant)
- Modifier le rôle d'un utilisateur

#### `notifications.py` — Notifications
- Lister les notifications non lues
- Marquer comme lu (une ou toutes)
- Supprimer une notification

#### `dashboard.py` — Statistiques
- Renvoie des stats personnalisées selon le rôle
  - Admin : nombre total d'utilisateurs, cours, devoirs, examens
  - Professeur : ses cours, étudiants, devoirs en attente de correction
  - Étudiant : ses cours, devoirs rendus, prochains examens

#### `resources.py` — Ressources de cours
- Lister les ressources d'un cours (fichiers, vidéos, liens)
- Uploader un fichier vers Supabase Storage
- Ajouter un lien ou vidéo YouTube
- Supprimer une ressource

#### `chatbot.py` — Chatbot d'admission
- Endpoint SSE (Server-Sent Events) pour le streaming en temps réel
- Le texte apparaît mot par mot comme ChatGPT

### Le Chatbot d'admission (chatbot/)

C'est la partie la plus avancée du backend. Il utilise **LangGraph** pour créer un agent conversationnel à états.

#### Comment ça marche

Le chatbot suit un **parcours en 5 étapes** :

```
[1] chat          → Conversation libre : répond aux questions sur l'école
         │
         ▼ (si le candidat est intéressé)
[2] collect_info  → Collecte 6 informations : nom, téléphone, email, filière, niveau bac, ville
         │
         ▼
[3] collect_docs  → Collecte 4 documents : CIN, Bac, photo, lettre de motivation
         │
         ▼
[4] review        → Récapitulatif de la candidature pour confirmation
         │
         ▼
[5] confirmed     → Enregistre dans Airtable + envoie un email de confirmation
```

#### Fichiers du chatbot

| Fichier | Rôle |
|---|---|
| `agent.py` | Machine à états LangGraph — logique des 5 étapes |
| `knowledge.py` | Base de connaissances sur l'école + prompts système (4 modes : FAQ, conseiller, collecte, général) |
| `airtable_client.py` | Extrait les infos de la conversation et les sauvegarde dans Airtable (CRM) |
| `supabase_client.py` | Sauvegarde les sessions de conversation dans Supabase |

#### Langues supportées
- Français (fr)
- Anglais (en)
- Arabe (ar)
- Darija marocain (darija) — en caractères latins

### Utilitaires (utils/)

| Fichier | Rôle |
|---|---|
| `email.py` | Envoie des emails via Resend (notifications de notes, confirmations) |
| `notify.py` | Insère des notifications dans la base de données pour l'utilisateur concerné |

---

## La Base de Données (sql/)

**Technologie :** PostgreSQL hébergé sur Supabase

Supabase est un "Backend as a Service" — il gère la base de données, l'authentification, le stockage de fichiers, et la sécurité au niveau des lignes (RLS).

### Scripts SQL à exécuter dans l'ordre

| Ordre | Fichier | Ce qu'il crée |
|---|---|---|
| 1 | `supabase_migration.sql` | Tables `profiles` et `user_roles` + politiques RLS |
| 2 | `supabase_classes_migration.sql` | Tables `classes` et `class_students` + RLS |
| 3 | `supabase_migration_class_courses.sql` | Table de jointure `class_courses` |
| 4 | `supabase_migration_meetings_class.sql` | Ajoute `class_id` à la table meetings |
| 5 | `supabase_meetings_rls.sql` | Politiques de sécurité complexes pour les meetings |
| 6 | `supabase_storage_submissions.sql` | Bucket de stockage pour les rendus d'étudiants + RLS |
| 7 | `supabase_notifications_migration.sql` | Table `notifications` + RLS |

### Schéma des tables principales

```
auth.users (géré par Supabase)
    │
    ├── profiles          (id, full_name, email, created_by, created_at)
    └── user_roles        (user_id, role: 'admin'|'professor'|'student')

classes                   (id, name, created_by)
    ├── class_students    (class_id, student_id)
    └── class_courses     (class_id, course_id)

courses                   (id, title, description, code, semester, credits, professor_id)

assignments               (id, title, description, due_date, max_grade, course_id)
    └── submissions       (id, student_id, assignment_id, file_url, grade, feedback)

exams                     (id, title, duration_minutes, start_time, is_published, course_id)
    ├── exam_questions    (id, exam_id, question_text, options JSON, correct_index)
    └── exam_responses    (id, student_id, exam_id, answers JSON, score)

meetings                  (id, title, scheduled_at, duration_minutes, class_id, course_id)
calendar_events           (id, user_id, title, start_date, end_date, color)
notifications             (id, user_id, title, message, type, read, link, created_at)
```

### C'est quoi le RLS (Row Level Security) ?

C'est une sécurité intégrée dans la base de données qui dit : "tel utilisateur ne peut voir que ses propres données". Par exemple, un étudiant ne peut pas voir les rendus d'un autre étudiant — même si quelqu'un essaie de le pirater directement via l'API. C'est une couche de sécurité en plus du contrôle dans le backend.

### Stockage de fichiers

Supabase Storage (équivalent de AWS S3) est utilisé pour deux types de fichiers :

| Bucket | Contenu | Limite |
|---|---|---|
| `submissions` | Rendus des étudiants (`{user_id}/{assignment_id}/fichier`) | 25 MB par fichier |
| `course-materials` | Ressources de cours (`{course_id}/fichier`) | Variable |

---

## Technologies utilisées — Récapitulatif complet

### Frontend

| Technologie | Version | Pourquoi |
|---|---|---|
| React | 19.0.0 | Bibliothèque UI, composants réutilisables |
| TypeScript | 5.8.3 | JavaScript avec types, moins de bugs |
| Vite | 6.3.5 | Bundler ultra-rapide pour le développement |
| TanStack Router | 1.169.1 | Routing basé sur fichiers, type-safe |
| Tailwind CSS | 4.1.7 | CSS utilitaire, styles sans écrire de CSS |
| shadcn/ui | 4.6.0 | Composants accessibles et stylés |
| Radix UI | Multiple | Primitives accessibles (dialogs, selects, etc.) |
| React Hook Form | 7.54.2 | Gestion des formulaires performante |
| Zod | 3.24.2 | Validation des schémas de données |
| Recharts | 2.15.1 | Graphiques et visualisations |
| Framer Motion | 12.38.0 | Animations fluides |
| Supabase JS | 2.103.3 | Client pour Supabase Auth + DB |
| date-fns | 4.1.0 | Manipulation des dates |
| Sonner | 2.0.7 | Notifications toast |
| Lucide React | 0.507.0 | Bibliothèque d'icônes |

### Backend

| Technologie | Version | Pourquoi |
|---|---|---|
| Python | 3.11 | Langage principal du backend |
| FastAPI | 0.115.5 | Framework API REST rapide et moderne |
| Uvicorn | 0.32.1 | Serveur ASGI pour faire tourner FastAPI |
| Supabase Python | 2.10.0 | Accès à la base de données |
| Pydantic | 2.9.2 | Validation et sérialisation des données |
| LangGraph | 0.2.60 | Machine à états pour le chatbot IA |
| LangChain | 0.3.15 | Orchestration des appels LLM |
| OpenAI SDK | ≥1.30.0 | Appels au modèle de langage |
| Resend | 2.0.0 | Envoi d'emails transactionnels |
| pyairtable | 2.3.0 | Intégration CRM Airtable |
| python-dotenv | 1.0.1 | Gestion des variables d'environnement |

### Infrastructure

| Service | Rôle |
|---|---|
| **Supabase** | Base de données PostgreSQL + Auth + Storage |
| **Railway** | Hébergement du backend Python |
| **Vercel** | Hébergement du frontend React |
| **Airtable** | CRM pour les candidatures (chatbot) |
| **Resend** | Service d'emails transactionnels |
| **OpenAI** | Modèle de langage pour le chatbot Aya |

---

## Gestion des rôles et permissions

```
ADMIN
  ├── Voir tout le monde
  ├── Créer des professeurs
  ├── Gérer tous les cours / classes / contenus
  └── Voir toutes les statistiques
      │
      ▼
PROFESSEUR
  ├── Créer des étudiants
  ├── Créer et gérer ses cours
  ├── Créer et gérer ses classes
  ├── Créer des devoirs et des examens
  ├── Corriger les rendus
  └── Planifier des réunions
      │
      ▼
ÉTUDIANT
  ├── Voir ses cours (ceux de sa classe)
  ├── Télécharger les ressources
  ├── Rendre des devoirs
  ├── Passer des examens
  └── Voir ses notes et feedbacks
```

---

## Flux d'authentification

1. L'utilisateur entre son email/mot de passe sur `/auth`
2. Supabase Auth valide les identifiants et renvoie un **JWT token**
3. Le frontend stocke ce token et l'envoie dans chaque requête API (`Authorization: Bearer ...`)
4. Le backend valide le token via `deps.py` avant chaque opération
5. La table `user_roles` détermine ce que l'utilisateur a le droit de faire

---

## Lancer le projet en local

### Prérequis
- Node.js 18+
- Python 3.11+
- Un projet Supabase créé (gratuit sur supabase.com)

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux
pip install -r requirements.txt
cp .env.example .env
# Remplis les variables dans .env
uvicorn main:app --reload --port 9000
```

L'API sera disponible sur `http://localhost:9000`
Documentation interactive : `http://localhost:9000/docs`

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
# Remplis les variables dans .env
npm run dev
```

L'application sera disponible sur `http://localhost:5173`

---

## Variables d'environnement

### Backend (`backend/.env`)

```env
# Base de données Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...        # Clé service (admin)
SUPABASE_ANON_KEY=eyJ...           # Clé anonyme

# URL du frontend (pour CORS)
FRONTEND_URL=https://your-app.vercel.app

# Modèle de langage (OpenAI ou compatible)
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://...        # Optionnel si custom endpoint

# CRM Airtable (candidatures chatbot)
AIRTABLE_TOKEN=pat...
AIRTABLE_BASE_ID=app...
AIRTABLE_TABLE_ID=tbl...

# Emails
RESEND_API_KEY=re_...
FROM_EMAIL=noreply@ipisb.ma
```

### Frontend (`frontend/.env`)

```env
VITE_SUPABASE_URL=https://xxx.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=eyJ...
VITE_API_URL=https://your-backend.up.railway.app
```

---

## Configuration base de données

Dans le SQL Editor de Supabase, exécute les fichiers du dossier `sql/` dans cet ordre :

1. `supabase_migration.sql`
2. `supabase_classes_migration.sql`
3. `supabase_migration_class_courses.sql`
4. `supabase_migration_meetings_class.sql`
5. `supabase_meetings_rls.sql`
6. `supabase_storage_submissions.sql`
7. `supabase_notifications_migration.sql`

Puis, pour créer les premiers comptes administrateurs :

```bash
cd backend
python seed_admins.py
```

---

## Déploiement en production

### Backend → Railway
1. Connecte le repo GitHub à Railway
2. Définis le répertoire racine : `backend`
3. Ajoute toutes les variables d'environnement
4. La commande de démarrage est dans `Procfile` : `uvicorn main:app --host 0.0.0.0 --port $PORT`

### Frontend → Vercel
1. Connecte le repo GitHub à Vercel
2. Définis le répertoire racine : `frontend`
3. Build command : `tsc -b && vite build`
4. Output directory : `dist`
5. Ajoute les variables d'environnement
6. Redéploie après avoir ajouté les variables

---

## Résumé en une phrase

**IPISB Connect est une plateforme web full-stack (React + FastAPI + Supabase) qui gère l'intégralité de la vie pédagogique d'un institut infirmier — des cours aux examens en passant par un chatbot d'admission multilingue propulsé par l'IA.**
