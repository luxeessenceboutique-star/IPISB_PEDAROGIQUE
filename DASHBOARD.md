 # Tableau de bord — IPISB Connect

Documentation des fonctionnalités du tableau de bord (dashboard) de la plateforme IPISB Connect.

Le menu latéral **s'adapte automatiquement au rôle** de l'utilisateur connecté (Administrateur, Professeur, Étudiant). Chaque section appelle un routeur FastAPI dédié (`backend/routers/…`), protégé par un token JWT + vérification du rôle ([backend/deps.py](backend/deps.py)).

---

## 🔐 Rôles et permissions

| Rôle | Peut faire |
|---|---|
| **Administrateur** | Accès total : gérer les utilisateurs, créer des **professeurs**, attribuer/retirer des rôles, gérer cours/examens/devoirs/classes. |
| **Professeur** | Créer des **étudiants**, gérer ses cours, examens, devoirs, réunions, agenda. |
| **Étudiant** | Consulter ses cours, rendre ses devoirs, passer les examens, voir son agenda et ses notifications. |

> Un même compte peut **cumuler plusieurs rôles** (ex. un utilisateur Étudiant **+** Professeur).
> La logique d'attribution est dans `can_create_role()` : un admin crée des profs, un prof crée des étudiants.

---

## 🧭 Sections du tableau de bord

### 📊 Aperçu
Page d'accueil du dashboard. Statistiques globales (nombre d'étudiants, cours, examens à venir…), raccourcis et activité récente. Vue synthétique de la plateforme.
- Route : `dashboard.index` · Routeur : `routers/dashboard.py`

### 📖 Cours
Gestion des cours et de leurs supports.
- **Admin / Prof** : créer, éditer, supprimer des cours ; ajouter vidéos et supports (PDF).
- **Étudiant** : consulter les cours auxquels il est inscrit.
- Tables : `courses`, `course_materials`, `course_enrollments` · Routeur : `routers/courses.py`

### 📝 Devoirs
Dépôt et correction des travaux.
- **Prof / Admin** : créer un devoir avec date limite, consulter et corriger les rendus.
- **Étudiant** : déposer son fichier avant l'échéance.
- Tables : `assignments`, `submissions` · Routeur : `routers/assignments.py`

### 🎓 Examens
Examens QCM avec correction automatique.
- **Prof / Admin** : créer un examen (questions + bonnes réponses), définir un chronomètre.
- **Étudiant** : passer l'examen → **correction et résultat instantanés**.
- Tables : `exams`, `exam_questions`, `exam_responses` · Routeur : `routers/exams.py`

### 🗓️ Agenda
Calendrier synchronisé : cours, examens, réunions et événements.
- **Admin / Prof** : créer des événements. **Tous** : consulter.
- Table : `calendar_events` · Routeur : `routers/agenda.py`

### 🎥 Réunions
Visioconférences planifiées, rattachées à des classes/cours (cours en ligne).
- **Admin / Prof** : créer/planifier une réunion et son lien.
- Table : `meetings` · Routeur : `routers/meetings.py`

### 🔔 Notifications
Centre de notifications (nouveau devoir, résultat d'examen, réunion à venir…).
Le backend envoie aussi des **emails** automatiques.
- Table : `notifications` · Routeur : `routers/notifications.py` · Envoi : `utils/email.py`, `utils/notify.py`

### 🏫 Classes
Regroupement des étudiants en promotions/groupes, avec rattachement de cours.
- **Admin** : créer des classes, y affecter étudiants et cours.
- Tables : `classes`, `class_courses`, `class_students` · Routeur : `routers/classes.py`

### 👥 Utilisateurs *(Administrateur uniquement)*
Gestion complète des comptes et des rôles. **Voir le détail ci-dessous.**
- Tables : `profiles`, `user_roles` · Routeur : `routers/users.py`

### 👤 Profil
Informations du compte connecté (nom, e-mail, rôle) et bouton **Déconnexion**.
- Route : `dashboard.profile`

---

## 👥 Page « Utilisateurs » — affichage détaillé

Réservée aux **administrateurs**. Elle gère l'ensemble des comptes de la plateforme.

### Cartes de statistiques (en haut)
| Carte | Contenu |
|---|---|
| **Étudiants** | Nombre de comptes ayant le rôle `student` |
| **Professeurs** | Nombre de comptes ayant le rôle `professor` |
| **Administrateurs** | Nombre de comptes ayant le rôle `admin` |
| **Comptes** | Nombre total de profils (`profiles`) |

> Un utilisateur multi-rôles est compté dans **chaque** catégorie correspondante.

### Barre d'actions
- **Rechercher un utilisateur** : filtre par nom ou e-mail.
- **« Créer un compte Professeur »** : un admin crée un prof (un prof, lui, crée des étudiants).

### Tableau des utilisateurs
| Colonne | Description |
|---|---|
| **Utilisateur** | Avatar (initiales) + nom complet (`profiles.full_name`) |
| **E-mail** | Adresse du compte (`profiles.email`) |
| **Rôles** | Puces colorées : **Étudiant** (vert clair), **Professeur** (vert clair), **Administrateur** (vert foncé). Chaque puce a un **×** pour **retirer** le rôle |
| **Inscrit** | Date de création du compte (`created_at`) |
| **Actions** | Bouton **« + Ajouter un rôle »** (menu déroulant) pour **attribuer** un nouveau rôle |

### Gestion des rôles
- **Ajouter un rôle** : bouton « + Ajouter un rôle » → choisir Étudiant / Professeur / Administrateur.
- **Retirer un rôle** : cliquer le **×** sur la puce du rôle.
- **Cumul** : un compte peut avoir plusieurs rôles simultanément (ex. *omar* = Étudiant + Professeur).
- Les rôles sont stockés dans la table `user_roles` (une ligne = un couple `user_id` + `role`).

---

## 🔎 Explorer les données (base Supabase)

Depuis le dossier `backend/`, avec la clé service_role :

```bash
venv/Scripts/python.exe explore_db.py                # liste des tables + nb de lignes
venv/Scripts/python.exe explore_db.py profiles       # comptes (noms + e-mails)
venv/Scripts/python.exe explore_db.py user_roles     # rôles attribués
venv/Scripts/python.exe explore_db.py courses 20     # 20 premières lignes de "courses"
```

## 🔑 Comptes de test (seed)

| E-mail | Mot de passe | Rôle |
|---|---|---|
| `admin1@ipisb.ma` | `Admin@IPISB2026!` | Administrateur |
| `admin2@ipisb.ma` | `Admin@IPISB2026!` | Administrateur |

## ▶️ Lancer en local

```bash
# Backend  (http://localhost:9000  ·  docs : /docs)
cd backend && venv/Scripts/python.exe -m uvicorn main:app --reload --port 9000

# Frontend (http://localhost:5178)
cd frontend && npm run dev
```
