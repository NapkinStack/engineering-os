# Architecture Decision Records

Une décision **technique ou architecturale** structurante — coûteuse à inverser, ou
qui contraindra les suivantes.

- Modèle : [`_TEMPLATE.md`](./_TEMPLATE.md)
- Nommage : `NNNN-titre-a-l-infinitif.md`, ex. `0001-adopter-postgres.md`
- Une décision remplacée est **supersédée**, jamais réécrite silencieusement.

## Sections obligatoires

| Section | Check |
|---|---|
| **Prior art** — ≥ 2 références nommées + convention identifiée | Rouge si absente |
| **Déviation** — si l'on s'écarte de la convention | Rouge si absente quand applicable |
| **Critère de succès daté** — si l'on construit sur-mesure | Rouge si absent |
| **Règle à automatiser** — quelle fitness function en découle | Revue |

Voir `docs/os/06-decisions.md`.

## Index

| N° | Titre | Statut | Critère à vérifier le |
|---|---|---|---|
| [0001](./0001-adopter-copier-pour-generer-et-mettre-a-jour-les-projets.md) | Adopter Copier pour générer et mettre à jour les projets | Proposé | Au prototype de PDR-0001 |
| [0002](./0002-distribuer-napkinstack-sur-pypi.md) | Distribuer NapkinStack sur PyPI | Proposé | À la première publication |
