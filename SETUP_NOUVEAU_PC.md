# Installation sur un nouveau poste

> **À Claude Code :** ce dossier a été **copié** depuis un autre PC (pas cloné).
> Les dépendances sont déjà là, sauf une qui n'est pas transportable.
> Exécute la checklist ci-dessous, puis lance les deux serveurs.

Phrase à coller dans Claude Code sur le nouveau poste :

```
Lis SETUP_NOUVEAU_PC.md à la racine et fais ce qu'il dit.
```

---

## 1. Prérequis à vérifier (et à installer si absents)

| Outil | Version utilisée sur le poste d'origine |
|---|---|
| Python | **3.11.0** — surtout pas 3.14 |
| Node.js | **v24.11.0** (npm 11.6.1) |

`requirements.txt` épingle `fastapi==0.115.5` et `pydantic==2.9.2`, qui ne compilent
pas forcément sur Python 3.14. Si le poste a une autre version de Python, installer
le 3.11 **en plus** plutôt que de remplacer.

```powershell
python --version
node --version
```

## 2. Recréer le venv Python — OBLIGATOIRE

Le `backend/venv` copié est **inutilisable** : un venv contient des chemins absolus
en dur (`pyvenv.cfg` pointe vers `C:\Users\USER\AppData\Local\Programs\Python\Python311`
et les `.exe` de `Scripts/` embarquent le chemin du python d'origine). Si le nom
d'utilisateur ou le chemin d'installation diffère, `activate` passe sans erreur
mais `uvicorn` échoue ensuite — symptôme trompeur.

**Le supprimer et le refaire :**

```powershell
cd backend
Remove-Item -Recurse -Force venv
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## 3. `frontend/node_modules` — normalement rien à faire

Les binaires natifs embarqués sont tous `win32-x64` (`@esbuild/win32-x64`,
`@rollup/rollup-win32-x64-msvc`, `lightningcss-win32-x64-msvc`). Sur un Windows
64 bits, le dossier copié fonctionne tel quel.

Ne relancer `npm install` que si :
- le dossier `frontend/node_modules` est absent ou incomplet après la copie ;
- ou `npm run dev` renvoie une erreur du type *"You installed esbuild for another
  platform"* / *"Cannot find module @rollup/rollup-win32-..."*.

## 4. Vérifier que les fichiers cachés ont bien suivi

Ils commencent par un point : l'Explorateur Windows les copie avec le dossier
parent, mais pas si on a sélectionné les fichiers un par un à l'intérieur.

```powershell
Test-Path .git ; Test-Path backend\.env ; Test-Path frontend\.env
```

Les trois doivent répondre `True`.

- **`backend/.env`** — `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_ANON_KEY`,
  `FRONTEND_URL`, Airtable, OpenAI.
- **`frontend/.env`** — `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY`,
  `VITE_API_URL`.

Si l'un des deux `.env` manque, il faut le récupérer depuis le poste d'origine
(clé USB ou gestionnaire de mots de passe) : ces fichiers contiennent la clé
`service_role` Supabase et ne sont **pas** dans le dépôt Git, volontairement.
Ne jamais les faire transiter par mail ou messagerie.

⚠️ Ne pas reconstruire `backend/.env` à partir de `backend/.env.example` sans
corriger le port : l'exemple indique `FRONTEND_URL=http://localhost:5173` alors
que Vite écoute sur **5178**. Avec la mauvaise valeur, le CORS bloque toutes les
requêtes et l'application semble morte sans message d'erreur clair.

## 5. Lancer

```powershell
# Terminal 1 — API
cd backend
venv\Scripts\activate
uvicorn main:app --reload --port 9000

# Terminal 2 — UI
cd frontend
npm run dev
```

- Front : http://localhost:5178
- API : http://localhost:9000 — docs sur http://localhost:9000/docs

## 6. Base de données : rien à faire

Supabase est **hébergé**, le nouveau poste attaque la même base que l'ancien.
Toutes les migrations du dossier `sql/` (jusqu'à `supabase_l41_tuition_delete_validation.sql`)
y sont **déjà appliquées**. Ne rejouer aucun script : plusieurs sont destructifs
(purges de lignes orphelines) et les données de production sont déjà en place.

## 7. Git

Le dépôt distant suit avec le dossier `.git` :

- `origin` → `https://github.com/luxeessenceboutique-star/IPISB.git`
- branche de travail → `dev/aymen`

GitHub demandera les identifiants au premier `git push` depuis ce poste.
Configurer l'identité locale si les commits doivent être signés du même nom :

```powershell
git config user.name "Aymen Rami"
git config user.email "aymen.rami@fizazi.ma"
```

## Détails connus, sans gravité

- **`instutie-connect`** est référencé comme sous-module Git mais sans fichier
  `.gitmodules`, et le dossier est vide. Vestige inoffensif — ne pas chercher à
  le réparer ni à l'initialiser.
- **`backend/secrets/jaas_private_key.pem`** (visio Jitsi/8x8) est absent et
  exclu du dépôt. À re-télécharger depuis la console https://jaas.8x8.vc
  uniquement si la visioconférence doit fonctionner.
- **`frontend/.env.example`** n'existe pas : les trois variables du front ne sont
  documentées que dans ce fichier-ci.
