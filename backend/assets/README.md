# Assets PDF

## Logo de l'établissement

Déposez le logo IPISB ici, **exactement** sous ce nom :

```
backend/assets/logo.png
```

- Format : **PNG** (fond transparent recommandé).
- Le ratio est conservé automatiquement ; une image ~500×560 px convient parfaitement.
- Si le fichier est absent, les PDF basculent sur un repli textuel (« IPISB ») /
  pastille placeholder — aucune erreur.

Utilisé par `backend/utils/pdf_generators.py` (en-têtes du bon de commande, de la
demande d'achat et de la synthèse comptable) via la constante `_LOGO_PATH`.
