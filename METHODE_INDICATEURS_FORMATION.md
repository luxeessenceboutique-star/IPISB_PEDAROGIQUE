# Méthode — Indicateurs de pilotage de la formation

Objectif : mesurer automatiquement **3 indicateurs** par formation et par formateur.

| Indicateur | Question à laquelle il répond |
|---|---|
| **CA par session** | Combien rapporte chaque promo (classe) ? |
| **Encours de facturation** | Combien nous doit-on encore (dû mais pas encaissé) ? |
| **Coût de revient par formateur** | Combien nous coûte chaque formateur ? |

---

## 1. Décisions validées

- **Une « session » = une classe / promotion** (table `classes` déjà existante).
- **Le CA vient des frais de scolarité par élève** inscrit dans la classe.
- **Le coût d'un formateur = tarif horaire × heures données**, les heures étant lues depuis l'emploi du temps (`schedules`).

---

## 2. Ce qu'on ajoute au modèle de données

Rien de lourd : **3 petits ajouts** qui connectent l'argent aux formations et aux formateurs.

### a) Prix de la scolarité (pour le CA)
- `classes.tuition_per_student` — frais de scolarité **par élève** de la promo (montant par défaut).
- `class_students.tuition_amount` — montant **spécifique** à un élève (optionnel : bourse, remise). Si vide → on prend le prix par défaut de la classe.

### b) Rattachement des encaissements à une promo + un élève
- On étend la table **`revenues`** (Recettes) avec :
  - `class_id` → à quelle promo l'encaissement se rapporte,
  - `student_id` → quel élève a payé.
- Concrètement : quand un élève paie, l'admin crée une **recette** de type *Scolarité* et la relie à sa promo + son nom. (On réutilise le module Recettes déjà en place.)

### c) Tarif horaire du formateur (pour le coût de revient)
- Nouvelle table **`trainer_rates`** : `user_id` (le formateur) + `hourly_rate` (tarif/heure).
- Les **heures** ne sont pas saisies : elles sont **calculées** à partir des créneaux `schedules` (`end_time − start_time`) rattachés au formateur (`professor_id`) et à la classe (`class_id`).

---

## 3. Comment on calcule (les formules)

### Pour chaque **session (classe)** X
```
Nb élèves            = nombre d'élèves inscrits (class_students)
CA facturable        = Σ frais de scolarité des élèves inscrits
Encaissé             = Σ recettes "reçues" rattachées à la classe X
Encours facturation  = CA facturable − Encaissé
Coût formateurs      = Σ ( tarif horaire du formateur × heures du créneau )
                       pour tous les créneaux de la classe X
Marge                = Encaissé − Coût formateurs        (bonus)
```

### Pour chaque **formateur** F (sur une période choisie)
```
Heures données   = Σ durées des créneaux de F sur la période
Coût de revient  = tarif horaire de F × Heures données
```
*(répartition possible par classe : « le formateur F a coûté X DH sur la promo Y »)*

### Encours de facturation **global**
```
Encours global = Σ (CA facturable − Encaissé) sur toutes les classes
```

> Note technique : pour les créneaux **hebdomadaires** (`recurrence = 'weekly'`),
> les heures sont multipliées par le nombre de semaines de la période analysée.
> Les créneaux ponctuels (`once`) sont comptés une fois s'ils tombent dans la période.

---

## 4. Exemple chiffré (pour visualiser)

**Promo « Comptabilité 2026 » — 20 élèves, scolarité 10 000 DH/élève**

| Élément | Calcul | Résultat |
|---|---|---|
| CA facturable | 20 × 10 000 | **200 000 DH** |
| Encaissé à ce jour | recettes reçues | 150 000 DH |
| **Encours de facturation** | 200 000 − 150 000 | **50 000 DH** |
| Coût formateur Ahmed | 120 DH/h × 80 h | 9 600 DH |
| Coût formateur Sara | 150 DH/h × 40 h | 6 000 DH |
| **Coût formateurs (session)** | 9 600 + 6 000 | **15 600 DH** |
| Marge | 150 000 − 15 600 | 134 400 DH |

**Vue par formateur (trimestre, toutes promos)**

| Formateur | Heures | Tarif | **Coût de revient** |
|---|---|---|---|
| Ahmed | 200 h | 120 DH/h | **24 000 DH** |
| Sara | 130 h | 150 DH/h | **19 500 DH** |

---

## 5. Où ça s'affiche (UI)

Un nouvel onglet **« Analytique »** (ou une section dans la Vue d'ensemble) avec :
- un **tableau par session** : CA facturable · encaissé · encours · coût formateurs · marge ;
- un **tableau par formateur** : heures · tarif · coût de revient ;
- un **sélecteur de période** (ce trimestre / cette année) pour le calcul des heures.

---

## 6. Plan d'implémentation

1. **SQL** : ajouter `classes.tuition_per_student`, `class_students.tuition_amount`,
   `revenues.class_id` + `revenues.student_id`, et créer `trainer_rates`.
2. **Backend** : endpoint `GET /api/accounting/analytics/formation`
   (agrège par classe + par formateur sur une période) ; petit CRUD pour saisir
   la scolarité d'une classe et le tarif d'un formateur.
3. **Frontend** : onglet « Analytique » (tableaux + sélecteur de période) ;
   ajout du rattachement classe/élève dans le formulaire Recettes.
4. **Vérif** : jeu de test avec 1 promo, 2 élèves, 1 formateur.
