# platform

La plateforme interne du projet. Elle existe pour **réduire la charge cognitive**, pas
pour contrôler : chaque fois qu'une équipe doit reconstruire un mécanisme déjà
construit ailleurs, c'est un échec de la plateforme.

## Contenu

Le code du moteur vit dans `src/napkinstack/` et s'exécute par la commande `nstack`
(`uv run nstack --help`). Ce dossier garde l'enveloppe du module : manifest, consignes,
runbook, tests et configuration.

| Chemin | Rôle |
|---|---|
| `src/napkinstack/fitness/` | Les checks d'architecture, non contournables |
| `src/napkinstack/scaffold/` | Création d'un module avec ses garde-fous actifs, et son squelette |
| `src/napkinstack/skills.py` | Génère les skills Claude Code depuis les playbooks |
| `src/napkinstack/project.py` | Création et mise à jour d'un projet, par Copier |
| `src/napkinstack/doctor.py` | Diagnostic du poste et des réglages GitHub, en lecture seule |
| `tests/run.sh` | L'oracle : chaque garde-fou prouve qu'il sait échouer |

## Fitness functions

| Commande | Contrôles |
|---|---|
| `nstack manifests` | M1–M9 : champs, cycles de vie, dates de dépréciation, runbook, enveloppe |
| `nstack boundaries` | B1–B5 : graphe déclaré vs réel, imports internes, cycles, accès données |
| `nstack pr-scope` | P1–P2 : une PR = un module, budget de revue |

```bash
uv run nstack fitness                      # manifests + frontières + skills
uv run nstack pr-scope --base origin/main
uv run nstack init <dossier>               # crée un projet (PDR-0001)
uv run nstack update                       # met à jour un projet, sur une branche à relire
uv run nstack doctor --root <projet>       # poste et réglages GitHub, en lecture seule
```

## Skills

```bash
uv run nstack skills           # génère .claude/skills/
uv run nstack skills --check   # S1, S2, S4 bloquants en CI ; S3 dès que des skills sont générées
```

| Check | Vérifie |
|---|---|
| S1 | Chaque playbook a une entrée dans `.nstack/skills.yaml` |
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
`skeleton/docs/os/07-gouvernance.md` §3. Une bonne fitness function est rapide, déterministe,
et **explicative en cas d'échec** : une fonction qui dit seulement « violation
d'architecture » sera contournée.
