# contracts — instructions locales

## Responsabilité

Définit et versionne les contrats d'interface entre modules.

## Invariants

- Un contrat ne contient **jamais** de structure interne d'un producteur.
- Toute version dépréciée porte une `removal_date`. Sans date, la PR est refusée.
- Un changement breaking se fait en **4 PR** (expand/contract), jamais en une.
- Les contract tests tournent des **deux côtés** : producteur et consommateur.

## Piège principal

Structure inchangée mais **sémantique modifiée** = breaking change. Une nouvelle valeur
d'énumération, un changement d'unité, un nullable qui devient obligatoire. Aucun diff ne
le détecte ; seuls les contract tests le font.

## Avant de modifier

Vérifier la matrice des consommateurs, générée depuis les manifests. On ne retire une
version que quand `consommateurs = 0`.
