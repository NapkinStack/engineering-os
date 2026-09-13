# <NOM DU PROJET>

<Une phrase : ce que fait ce projet.>

---

> **Ce dépôt est né d'un starter AI Engineering OS.** Cette section est le mode
> d'emploi du socle. Remplace-la par le README de ton projet une fois l'installation
> terminée — les instructions restent dans `docs/os/`.

## Installation — 10 minutes

```bash
# 1. Copier ce dossier comme racine du nouveau projet
cp -r starter/ mon-projet && cd mon-projet && git init

# 2. Préparer l'outillage de gouvernance
make bootstrap

# 3. Remplacer les marqueurs
#    .github/CODEOWNERS      → @equipe-plateforme = ton équipe socle
#    .github/ISSUE_TEMPLATE/config.yml → URL du dépôt
#    ce README               → le tien

# 4. Créer le premier module
make scaffold NAME=billing OWNER=team-revenue CRIT=standard

# 5. Vérifier que les garde-fous répondent
make fitness
```

## À faire une fois sur GitHub — sinon rien n'est garanti

Les workflows **informent** ; ce sont les rulesets qui **bloquent**. Sans cette
étape, tout l'édifice repose sur la bonne volonté, ce que l'OS interdit
(`docs/os/07-gouvernance.md`).

Settings → Rules → Rulesets → sur la branche principale :

- [ ] Pull request obligatoire, ≥ 1 relecture
- [ ] Required checks : `Fitness functions`, `Périmètre et budget de revue`
- [ ] Revue des CODEOWNERS obligatoire
- [ ] Pas de push direct

Créer aussi les labels `cross-module` et `hors-budget` : ils rendent les exceptions
visibles **et comptables** (`docs/os/10-mesure.md` §3).

---

## Ce qu'il y a dans ce dépôt

| Chemin | Rôle | Qui le lit |
|---|---|---|
| `AGENTS.md` | **Kernel** : les règles chargées à chaque tâche | Les agents, à chaque fois |
| `playbooks/` | Règles chargées **par déclencheur** (sécu, données, UX…) | Les agents, quand déclenché |
| `modules/` | Le code — une unité de parallélisme par dossier | Humains et agents, scopé |
| `contracts/` | Le **seul** canal entre modules | Producteurs et consommateurs |
| `platform/` | Verbes standards, fitness functions, scaffold | La CI, l'équipe socle |
| `docs/os/` | **Le manuel** : le pourquoi de chaque règle | Les humains, une fois |
| `docs/adr/`, `docs/pdr/` | Les décisions prises, avec leur critère de succès | Tout le monde, à la demande |
| `docs/governance/` | Backlog d'automatisation, revues périodiques | L'équipe socle, trimestriel |
| `.github/` | Ce qui rend les règles non contournables | GitHub |

> **`docs/os/` n'est jamais chargé dans le contexte d'un agent.** C'est la référence
> humaine. Un agent charge : le kernel, le `AGENTS.md` du module, un playbook si
> déclenché. C'est toute la différence entre un manuel et un système d'exploitation.

---

## Les commandes

```bash
make help        # liste les verbes
make fitness     # manifests + frontières — à lancer avant chaque commit
make skills      # génère les skills Claude Code depuis les playbooks
make check       # validations rapides de tous les modules
make test        # tests de tous les modules
make ci          # ce que fait la CI
make scaffold NAME=x OWNER=team-y CRIT=standard
```

Chaque module expose les **mêmes verbes**, quelle que soit sa technologie. C'est ce qui
permet à quelqu'un de changer de module sans rien réapprendre
(`docs/os/09-plateforme.md` §2).

---

## Skills Claude Code

Les playbooks sont exposés comme skills, dont le chargement à la demande est alors
assuré par le runtime plutôt que par une instruction du kernel.

```bash
make skills          # génère .claude/skills/ depuis playbooks/
make skills-check    # vérifie la synchronisation (tourne en CI)
```

**`playbooks/` reste la source de vérité.** Les skills sont générées, gitignorées, et
jamais éditées à la main — on modifie le playbook, puis on régénère. Un playbook sans
entrée dans `platform/skills.yaml`, ou une skill désynchronisée, fait échouer la CI.

Cette indirection a une raison : un outil est un **adaptateur**, jamais une fondation
(`platform/tooling-profile.md`). Si les règles n'existaient que sous forme de skills,
l'OS cesserait de fonctionner avec tout autre agent — et le tableau des déclencheurs
du kernel §4 reste là précisément pour ce cas.

L'enforcement, lui, **ne descend jamais dans un plugin**. Un hook côté agent est un
feedback rapide, pas une garantie : les checks bloquants restent en CI
(`docs/os/07-gouvernance.md` §4).

---

## Les trois règles à retenir

1. **Une PR = un module.** Un changement qui en touche deux passe par une séquence
   expand/contract sur le contrat (`docs/os/03-contrats.md` §4).
2. **L'oracle avant le code.** Le critère de réussite est exécutable et rouge avant la
   première ligne générée (`docs/os/05-workflow.md` §3).
3. **La convention est le choix par défaut.** Elle ne se justifie pas ; toute déviation
   se justifie par une valeur utilisateur observable (`docs/os/06-decisions.md` §2).

---

## Ce qui n'est pas fourni — et pourquoi

Aucune stack : ni langage, ni framework, ni base de données. L'OS impose une **méthode
de sélection** et une trace de décision, pas une liste de technologies
(`docs/os/06-decisions.md` §7).

Les squelettes de module contiennent donc des `TODO` dans leur `Makefile` : c'est à toi
de câbler `check`, `test` et `run` sur ton outillage. Les **noms** ne changent jamais,
le **contenu** t'appartient.

## Ce qui reste à câbler après l'installation

- [ ] Contenu des verbes dans les `Makefile` de module
- [ ] Détecteur de secrets dans `.github/workflows/governance.yml` (job `secrets`)
- [ ] Format de contrat retenu, et les contract tests associés
- [ ] Calibrage de `SOURCE_SUFFIXES` et `IMPORT_HINTS` dans
      `platform/fitness/boundaries.py` pour ton langage
- [ ] Valeurs du budget de revue (400 lignes / 15 fichiers sont un point de départ)
- [ ] Relire les `description` de `platform/skills.yaml` — ce sont elles qui
      déclenchent les skills, elles doivent parler le vocabulaire de ton domaine
