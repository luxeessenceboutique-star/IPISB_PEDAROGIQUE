# Déploiement — IPISB Connect

Guide complet : créer le dépôt sur le **GitHub de l'institut** (propriétaire), y pousser le code depuis ce PC, puis lancer le projet en local sur n'importe quel PC.

> ⚠️ **Secrets** : les fichiers `.env` et `eNV REEL.txt` ne sont **jamais** poussés (ils sont dans `.gitignore`). Ne mets **aucune clé réelle** dans un fichier suivi par git.

---

## Étape 1 — Créer le dépôt sur le GitHub de l'institut

1. Ouvre un navigateur et connecte-toi à **github.com** avec le **Gmail de l'institut** (le compte qui sera *owner*).
2. En haut à droite : **+** → **New repository**.
3. Renseigne :
   - **Repository name** : `IPISB-CONNECT`
   - **Visibility** : **Private** ✅
   - **NE COCHE RIEN** (pas de README, pas de .gitignore, pas de licence) → le dépôt doit être **vide**.
4. Clique **Create repository**.
5. Note l'adresse affichée, du type :
   `https://github.com/<COMPTE-INSTITUT>/IPISB-CONNECT.git`

---

## Étape 2 — Générer un token pour pousser depuis ce PC

Le compte institut est sur un autre PC ; pour pousser depuis **ce** PC il faut un **Personal Access Token (PAT)**.

1. Toujours connecté au compte institut : **Settings** (avatar) → **Developer settings**.
2. **Personal access tokens** → **Tokens (classic)** → **Generate new token (classic)**.
3. **Note** : `deploiement-ipisb` · **Expiration** : 90 jours (ou selon besoin).
4. **Scopes** : coche **`repo`** (tout le bloc).
5. **Generate token** → **copie** le token `ghp_...` (visible une seule fois).

> Ce token = mot de passe. Ne le colle dans **aucun** fichier du projet.

---

## Étape 3 — Pousser le code (depuis ce PC)

Ouvre un terminal dans le dossier du projet :

```bash
cd "c:/Users/USER/Desktop/Projet/IPISB-CONNECT"

# 1. Remplacer l'ancien remote (celui de prv1ammar) par celui de l'institut
git remote set-url origin https://github.com/<COMPTE-INSTITUT>/IPISB-CONNECT.git

# 2. Vérifier que rien de sensible n'est ajouté
git status
git add .
git status                       # confirmer : PAS de .env ni eNV REEL.txt

# 3. Committer
git commit -m "Déploiement initial IPISB Connect (frontend + backend)"

# 4. Pousser sur la branche main
git push -u origin HEAD:main
```

Au moment du `git push`, GitHub demande une authentification :
- **Username** : le nom d'utilisateur GitHub de l'institut
- **Password** : **colle le token `ghp_...`** (PAS le mot de passe Gmail)

> Alternative (une seule commande, token dans l'URL — à ne pas partager) :
> `git push https://<TOKEN>@github.com/<COMPTE-INSTITUT>/IPISB-CONNECT.git HEAD:main`

✅ Le code est maintenant sur le GitHub de l'institut, en **privé**.

---

## Étape 4 — Lancer le projet en local (sur l'autre PC)

### 4.1 Récupérer le code

```bash
git clone https://github.com/<COMPTE-INSTITUT>/IPISB-CONNECT.git
cd IPISB-CONNECT
```

### 4.2 Recréer les fichiers `.env` (ILS NE SONT PAS DANS LE DÉPÔT)

Les valeurs réelles sont dans **`eNV REEL.txt`** (à transférer à la main, hors GitHub — clé USB, message privé…).

**`backend/.env`** (voir `backend/.env.example` pour le gabarit) :

```
SUPABASE_URL=...
SUPABASE_SERVICE_KEY=...
SUPABASE_ANON_KEY=...
FRONTEND_URL=http://localhost:5178
OPENAI_API_KEY=...
AIRTABLE_TOKEN=...
AIRTABLE_BASE_ID=...
AIRTABLE_TABLE_ID=...
```

**`frontend/.env`** :

```
VITE_SUPABASE_URL=...
VITE_SUPABASE_PUBLISHABLE_KEY=...
VITE_API_URL=http://localhost:9000
```

### 4.3 Backend (FastAPI · Python 3.14)

```bash
cd backend
python -m venv venv
venv\Scripts\activate            # Windows
pip install -r requirements.txt
uvicorn main:app --reload --port 9000
```
→ API : http://localhost:9000 · Docs : http://localhost:9000/docs

### 4.4 Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev
```
→ Site : http://localhost:5178

---

## Récapitulatif express

| Action | Commande / Lieu |
|---|---|
| Créer le repo | github.com (compte institut) → New repo → Private, vide |
| Token | Settings → Developer settings → PAT (classic) scope `repo` |
| Brancher le remote | `git remote set-url origin https://github.com/<INSTITUT>/IPISB-CONNECT.git` |
| Pousser | `git add . && git commit -m "..." && git push -u origin HEAD:main` |
| Cloner ailleurs | `git clone https://github.com/<INSTITUT>/IPISB-CONNECT.git` |
| Recréer `.env` | à partir de `eNV REEL.txt` (jamais sur GitHub) |
| Lancer backend | `uvicorn main:app --reload --port 9000` |
| Lancer frontend | `npm run dev` (port 5178) |

---

## ⚠️ Sécurité

- Le token `ghp_...` de `prv1ammar` était en clair dans l'ancien remote → **à révoquer** (GitHub → Settings → Developer settings → Revoke).
- Ne jamais committer `.env` ni `eNV REEL.txt` (déjà protégés par `.gitignore`).
- Le dépôt reste **privé** : invite les collaborateurs via **Settings → Collaborators** du dépôt institut.
