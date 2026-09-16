# Backlog d'automatisation

> Toute règle qui vit encore dans le prompt alors qu'elle est mécaniquement vérifiable
> est une **dette**. Ce fichier la rend visible et datée.
>
> Sans ce backlog, le kernel grossit à chaque incident et redevient le document
> illisible qu'il remplace (`skeleton/docs/os/07-governance.md` §9).

| Règle | Où elle vit | Risque si violée | Coût d'automatisation | Déclencheur | Échéance |
|---|---|---|---|---|---|
| *exemple* — un changement de contrat doit être précédé d'un ADR | kernel §6 | Moyen | Faible | 2ᵉ contrat inter-équipes | AAAA-MM-JJ |
| Sections obligatoires d'un ADR : prior art, déviation, critère daté | Index des ADR, revue | Moyen | Faible | Premier projet réel | Revue post-pilote |
| Consommateurs d'une version retirée = 0 | `03-contracts.md` §4, revue | Élevé | Moyen | Premier contrat entre deux équipes | Revue post-pilote |
| Issue de contraction ouverte dès l'expand | `03-contracts.md` §4, à la main | Moyen | Faible | Premier contrat versionné | Revue post-pilote |
| Dépendance externe déclarée au manifest | Playbook sécurité, revue | Moyen | Moyen | Premier module avec dépendances | Revue post-pilote |
| English is the repository's only language (ADR-0003) | `AGENTS.md`, `CONTRIBUTING.md`, review | Low | High — detection rests on accented letters: blind to English borrowings, false-positive on typographic punctuation and proper nouns | First outside contribution written in another language | Post-pilot review |

## Règles déjà automatisées — retirées du prompt

| Règle | Automatisée par | Date |
|---|---|---|
| Une PR = un module | `nstack pr-scope` (`src/napkinstack/fitness/pr_scope.sh`) | |
| Graphe déclaré = graphe réel | `nstack boundaries` | |
| Dates de dépréciation non dépassées | `nstack manifests` | |
| Runbook obligatoire si criticité élevée | `nstack manifests` | |
| Aucun secret dans le dépôt | gitleaks (hook et CI), protection au push | 2026-09-13 |
| Aucun marqueur de conflit de mise à jour | `check-merge-conflict --assume-in-merge` (hook et CI) | 2026-09-15 |
| Réglages de la forge conformes à la checklist | `nstack doctor`, lecture seule | 2026-09-15 |

## Revue

Trimestrielle, avec la revue des décisions. Pour chaque ligne : **automatiser**,
**supprimer la règle**, ou **reconduire avec une nouvelle échéance**.
