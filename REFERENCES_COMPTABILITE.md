# Références de la comptabilité — IPISB Connect

Chaque enregistrement du module Comptabilité porte une **référence unique**,
**auto-générée** et **immuable** : elle est produite automatiquement à la création
de la ligne (côté base de données) et n'est jamais modifiée par la suite. Elle
sert d'identifiant lisible pour retrouver, citer et suivre chaque opération
(dépense, facture, reçu, versement de scolarité, etc.).

## Tableau des références par partie

| Partie | Table | Champ réf | Préfixe | Format | Champ commentaire | Exemple |
|---|---|---|---|---|---|---|
| Recettes | `revenues` | `revenue_number` | REC | `REC-000001` (compteur global existant) | `comment` | `REC-000042` |
| Dépenses | `expenses` | `reference` | DEP | `DEP-2026-0001` | `comment` | `DEP-2026-0007` |
| Factures | `invoices` | `reference` | FAC | `FAC-2026-0001` | `comment` | `FAC-2026-0007` |
| Achats | `purchases` | `purchase_number` | PUR | `PUR-000001` (compteur global existant) | `comment` | `PUR-000015` |
| Demandes d'achat | `purchase_requests` | `request_number` | DA | `DA-000001` (compteur global existant) | `comment` | `DA-000003` |
| Reçus / Paiements | `purchase_payments` | `recu_number` | RCU | `RCU-2026-0001` | `comment` | `RCU-2026-0002` |
| Scolarité (versements) | `tuition_payments` | `reference` | VER | `VER-2026-0001` | `comment` | `VER-2026-0009` |
| Fournisseurs | `suppliers` | `reference` | FRN | `FRN-2026-0001` | `comment` | `FRN-2026-0004` |
| Budgets | `budgets` | `reference` | BUD | `BUD-2026-0001` | `comment` | `BUD-2026-0002` |
| Inventaire | `inventory_items` | `code_unique` | (existant) | code auto existant | `comment` | (selon convention actuelle) |

> Remarque sur les **Factures** : le champ `invoice_number`, saisi manuellement,
> reste distinct de la référence automatique `reference` (FAC). Les deux
> coexistent : `invoice_number` est le numéro officiel du document, `reference`
> est l'identifiant interne auto-généré.
>
> Remarque sur les **Reçus / Paiements** : le n° de reçu auto est porté par une
> colonne **dédiée** `recu_number` (RCU). Le champ `reference` de la table
> `purchase_payments` existait déjà et reste la **référence bancaire/chèque saisie**
> par l'utilisateur (ex. n° de chèque) — les deux coexistent sans collision.

## Fonctionnement

- **Compteur par (préfixe, année)** : les nouvelles références s'appuient sur la
  table `reference_counters`, qui tient un compteur distinct pour chaque couple
  `(préfixe, année)`. Le compteur est **réinitialisé chaque année** : la première
  dépense de 2026 est `DEP-2026-0001`, la première de 2027 sera `DEP-2027-0001`.
- **Unicité garantie** : un **index unique** est posé sur le champ `reference` de
  chaque table concernée, ce qui interdit tout doublon au niveau de la base.
- **Génération automatique à l'INSERT** : la référence est définie comme
  `DEFAULT` SQL (fonction `next_reference`). Si l'application ne fournit pas de
  valeur, PostgreSQL appelle automatiquement la fonction et attribue le prochain
  numéro. Les modèles de création n'envoient donc jamais la référence.
- **Immuabilité** : la référence étant posée à la création et jamais réécrite par
  l'application, elle reste stable pendant toute la vie de l'enregistrement.
- **Références historiques** : les parties déjà pourvues d'une référence
  (Recettes `REC`, Achats `PUR`, Demandes d'achat `DA`) conservent leur **format
  global à 6 chiffres non réinitialisé** (`PRÉFIXE-000001`). Ce format historique
  est conservé tel quel ; seules les parties qui n'avaient pas de référence
  reçoivent le nouveau format annuel `PRÉFIXE-2026-0001`.

## Commentaire

Chaque partie de saisie possède un champ **`comment`** : un texte libre et
**optionnel**, indépendant des champs `description` / `notes` déjà existants. Il
permet d'ajouter une remarque contextuelle à l'enregistrement (précision, motif,
rappel interne) sans détourner les champs métier. Ce champ est disponible sur :
`expenses`, `revenues`, `invoices`, `purchases`, `purchase_requests`,
`purchase_payments`, `tuition_payments`, `suppliers`, `budgets` et
`inventory_items`.
