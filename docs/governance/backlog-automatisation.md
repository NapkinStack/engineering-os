# Backlog d'automatisation

> Toute règle qui vit encore dans le prompt alors qu'elle est mécaniquement vérifiable
> est une **dette**. Ce fichier la rend visible et datée.
>
> Sans ce backlog, le kernel grossit à chaque incident et redevient le document
> illisible qu'il remplace (`skeleton/docs/os/07-gouvernance.md` §9).

| Règle | Où elle vit | Risque si violée | Coût d'automatisation | Déclencheur | Échéance |
|---|---|---|---|---|---|
| *exemple* — un changement de contrat doit être précédé d'un ADR | kernel §6 | Moyen | Faible | 2ᵉ contrat inter-équipes | AAAA-MM-JJ |
| | | | | | |

## Règles déjà automatisées — retirées du prompt

| Règle | Automatisée par | Date |
|---|---|---|
| Une PR = un module | `nstack pr-scope` (`src/napkinstack/fitness/pr_scope.sh`) | |
| Graphe déclaré = graphe réel | `nstack boundaries` | |
| Dates de dépréciation non dépassées | `nstack manifests` | |
| Runbook obligatoire si criticité élevée | `nstack manifests` | |
| Aucun secret dans le dépôt | gitleaks (hook et CI), protection au push | 2026-09-13 |

## Revue

Trimestrielle, avec la revue des décisions. Pour chaque ligne : **automatiser**,
**supprimer la règle**, ou **reconduire avec une nouvelle échéance**.
