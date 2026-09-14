# platform

La plateforme interne du projet. Elle existe pour **réduire la charge cognitive**, pas
pour contrôler : chaque fois qu'une équipe doit reconstruire un mécanisme déjà
construit ailleurs, c'est un échec de la plateforme.

## Contenu

| Chemin | Rôle |
|---|---|
| `fitness/` | Les checks d'architecture, non contournables |
| `scaffold/` | Création d'un module avec ses garde-fous actifs |
| `templates/module/` | Le squelette copié par le scaffold |
| `sync_skills.py` | Génère les skills Claude Code depuis les playbooks |
| `skills.yaml` | Frontmatter des skills — nom et description de déclenchement |
| `tooling-profile.md` | Mapping capacités → outils du moment |

## Fitness functions

| Fichier | Contrôles |
|---|---|
| `fitness/manifests.py` | M1–M9 : champs, cycles de vie, dates de dépréciation, runbook, enveloppe |
| `fitness/boundaries.py` | B1–B5 : graphe déclaré vs réel, imports internes, cycles, accès données |
| `fitness/pr_scope.sh` | P1–P2 : une PR = un module, budget de revue |

```bash
make fitness      # manifests + frontières
./platform/fitness/pr_scope.sh origin/main
```

## Skills

```bash
make skills          # génère .claude/skills/
make skills-check    # S1, S2, S4 bloquants en CI ; S3 dès que des skills sont générées
```

| Check | Vérifie |
|---|---|
| S1 | Chaque playbook a une entrée dans `skills.yaml` |
| S2 | Chaque entrée pointe vers un playbook existant, avec description non vide |
| S3 | Les skills générées correspondent aux playbooks actuels. Non applicable sans `.claude/skills/` : un clone vierge, et donc la CI, n'en a pas |
| S4 | Nom et description conformes à la [spécification Agent Skills](https://agentskills.io/specification) : nom de 1 à 64 caractères `a-z0-9` et tirets simples, description d'au plus 1024 caractères. Bloque aussi la génération |

La `description` est ce qui déclenche la skill : elle dit **quoi** et **quand**, à la
troisième personne, sans instruction comportementale — celles-ci vivent dans le corps
du playbook. Une description vague produit une skill qui ne se déclenche jamais, ou
qui se déclenche tout le temps.

## Calibrage

`boundaries.py` détecte les dépendances **textuellement**, ce qui est volontairement
simple et donc imparfait. Deux réglages en tête de fichier :

- `SOURCE_SUFFIXES` — les extensions scannées
- `IMPORT_HINTS` — ce qui ressemble à une ligne d'import dans ton langage

Un faux positif se corrige en déclarant la dépendance. Un faux négatif se corrige en
enrichissant les motifs — et mérite une issue, car c'est une violation qui passait.

## Ajouter une fitness function

Par ordre de rentabilité, les suivantes à écrire sont listées dans
`docs/os/07-gouvernance.md` §3. Une bonne fitness function est rapide, déterministe,
et **explicative en cas d'échec** : une fonction qui dit seulement « violation
d'architecture » sera contournée.
