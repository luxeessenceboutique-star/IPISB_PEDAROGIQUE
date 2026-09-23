# IPISB Connect — Instructions Claude Code

## Design System (OBLIGATOIRE)

Pour tout travail UI (composant, page, modification visuelle) :
**Toujours lire et appliquer `DESIGN_SYSTEM.md` à la racine.**

### Règles de design à respecter
- Couleurs : utiliser les variables `--pal-*` (OKLCH) définies dans le design system
- Polices : **Cormorant Garamond** pour les titres, **Manrope** pour l'UI
- Cartes dashboard : classe `.dash-card`
- Boutons custom : `.btn-c-primary`, `.btn-c-ghost`, `.btn-c-soft`, `.btn-c-danger`
- Badges/chips : `.chip-c` avec variantes `-green`, `-amber`, `-red`, `-blue`
- Animations : `.anim-rise`, `.anim-pop`, `.anim-fade`
- Aperçu visuel : `Système Designe ipisbe/Design System.dc.html`

## Stack technique
- Frontend : React 19 + TypeScript + Vite + TanStack Router + Tailwind CSS v4 + shadcn/ui
- Backend : FastAPI (Python 3.14) — dossier `backend/`
- Base de données : Supabase (PostgreSQL + Auth + Storage)

## Lancer en local
- Backend : `cd backend && venv\Scripts\activate && uvicorn main:app --reload --port 9000`
- Frontend : `cd frontend && npm run dev` → http://localhost:5178
- API docs : http://localhost:9000/docs
