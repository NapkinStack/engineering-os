# Product Decision Records

Une décision **produit** importante : objectif utilisateur, comportement attendu,
arbitrage, règle métier structurante, décision UX ou business.

Le PDR décrit **ce que le produit doit faire et pourquoi**, jamais son implémentation.

- Modèle : [`_TEMPLATE.md`](./_TEMPLATE.md)
- Nommage : `NNNN-titre-oriente-utilisateur.md`

## Sections obligatoires

| Section | Pourquoi |
|---|---|
| **Prior art** — ≥ 2 références | Sur une interface, la valeur d'une convention vient de ce que l'utilisateur la connaît déjà |
| **Critère de succès daté** | Rend la décision falsifiable, donc utile |
| **Condition de retrait** | Sans elle, une fonctionnalité est définitive par défaut, même inutilisée |

> Le format **FDR** n'existe pas dans cet OS. Pour les fonctionnalités réellement
> complexes, la section *Conception fonctionnelle détaillée* du PDR suffit
> (`docs/os/06-decisions.md` §4).

## Index

| N° | Titre | Statut | Critère à vérifier le |
|---|---|---|---|
| [0001](./0001-creer-un-projet-et-recevoir-les-evolutions.md) | Créer un projet et recevoir les évolutions de NapkinStack | Proposé | 2026-12-31 |
