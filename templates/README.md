# Modèles de documents IPISB

## Pourquoi des `{{ placeholders }}`

Un modèle Word peut être uploadé de deux façons dans la plateforme :

| Forme du modèle | Détection des champs | Risque |
|---|---|---|
| Blancs en pointillés (`…………`) ou déjà rempli avec un vrai élève | 1 passe LLM à l'upload (`utils/templates._detect_fields_from_text`) | Le modèle lit **tout** le document et ne distingue pas un blanc à remplir d'un texte fixe |
| `{{ variable }}` | Déterministe, zéro LLM (`utils/templates._detect_fields_jinja`) | Aucun — un placeholder = un champ, tout le reste est intouchable |

Le certificat de scolarité a d'abord été fait en pointillés : la détection avait
tagué comme « données élève » l'en-tête de l'institut, le nom de la directrice,
le numéro d'autorisation et l'adresse du pied de page, et les effaçait à chaque
génération. **Pour tout nouveau modèle, écrire des `{{ variables }}`.**

## Variables reconnues

Écrites telles quelles dans le `.docx` — la casse et les espaces intérieurs sont
libres (`{{ nom_prenom }}`, `{{NOM_PRENOM}}`).

| Variable | Contenu | Source |
|---|---|---|
| `{{ nom_prenom }}` | Nom complet | fiche administrative (`prenom` + `nom`), sinon `profiles.full_name` |
| `{{ nom_etudiant }}` / `{{ prenom_etudiant }}` | Nom / prénom séparés | fiche administrative |
| `{{ date_naissance }}` | JJ/MM/AAAA | fiche administrative |
| `{{ lieu_naissance }}` | Ville de naissance | fiche administrative |
| `{{ cin_etudiant }}` | N° CIN | fiche administrative |
| `{{ numero_inscription }}` | « Sous N° » / matricule | fiche administrative (`matricule`) |
| `{{ date_inscription }}` | Date d'entrée | `class_students.added_at` de la classe actuelle |
| `{{ classe }}` | Nom du groupe | `classes.name` |
| `{{ filiere }}` | Filière / spécialité | `specialties.name` via `classes.specialty_id` |
| `{{ niveau }}` | « 1ère année », « 2ème année »… | `classes.year_number` |
| `{{ annee_scolaire }}` | Ex. 2025-2026 | calculée (rentrée en septembre) |
| `{{ email_etudiant }}` | Email | `profiles.email` |
| `{{ date_edition }}` | Date du jour | génération |
| `{{ ville_edition }}` | El Jadida | constante backend |
| `{{ nom_etablissement }}` / `{{ adresse_etablissement }}` / `{{ telephone_etablissement }}` | Coordonnées IPISB | constantes backend |
| `{{ code_verification }}` | Code de la page /verify | génération |

Une variable inconnue est remplacée par `____________` plutôt que laissée en
`{{ … }}` dans le document délivré.

> **Filière et niveau viennent de la classe**, pas de la fiche élève : une classe
> = une filière + une année (`sql/supabase_academic_extensions_migration.sql`).
> Si une classe n'a ni spécialité ni `year_number`, ces deux lignes sortent
> vides — les renseigner dans l'écran Classes.

## Fichiers

- `Certificat_de_Scolarite_IPISB.docx` — le modèle en service (uploadé dans le
  bucket `document-templates`).
- `Certificat_de_Scolarite_IPISB_v3.docx` — la version d'origine en pointillés,
  gardée comme source de mise en page.
- `build_certificat_scolarite.py` — regénère le premier à partir du second
  (`python build_certificat_scolarite.py`), en ne touchant que les pointillés.
