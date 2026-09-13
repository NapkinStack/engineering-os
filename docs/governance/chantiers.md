# Chantiers

> Les défauts identifiés du socle, dans l'ordre de traitement.
> **Un chantier = une PR.** Ne jamais les fusionner.
>
> Contexte produit : [`PRODUCT.md`](../../PRODUCT.md). Invariants : §4 de ce fichier.

| # | Chantier | Statut |
|---|---|---|
| C1 | Point d'entrée unique `nstack` | À faire |
| C2 | Check anti-placeholder | À faire |
| C3 | Hook git versionné | À faire |
| C4 | Proxy d'oracle | À faire |
| C5 | Amorçage, `doctor` et marque | À faire |

---

## C1 — Point d'entrée unique `nstack`

**Défaut.** Quatre styles d'invocation coexistent (`make`, `python3 platform/…`,
`bash platform/…`, `./platform/…`). Pire : le `Makefile` racine suppose que chaque
module a un Makefile, ce qui viole l'invariant P1 — un module Node ne devrait pas avoir
à écrire un Makefile pour satisfaire la plateforme.

**Cible.**

```
./nstack help
./nstack doctor                    # diagnostic de l'installation
./nstack fitness                   # manifests + frontières + skills-check
./nstack check [module]            # délègue aux commandes du MANIFEST
./nstack test [module]
./nstack bootstrap [module]
./nstack run <module>
./nstack skills [--check]
./nstack new-module <nom> <owner> <criticité>
./nstack pr-scope [base]
```

**Contraintes.**

- `check`, `test`, `bootstrap`, `run` lisent `commands:` dans le `MANIFEST.yaml` du
  module et exécutent ce qui y est déclaré. Ils ne supposent **jamais** l'existence d'un
  Makefile, d'un `package.json` ou de quoi que ce soit d'autre. C'est le cœur du
  chantier : la plateforme orchestre, elle ne connaît aucune stack.
- Sans argument de module, la commande s'applique à tous et sort en échec au premier qui
  échoue, en nommant lequel.
- Fichier `nstack`, sans extension, shebang `#!/usr/bin/env python3`, exécutable.
  **Pas `os.py`** (masque le module standard de Python), **pas `manage.py`** (collision
  si un module Django arrive), **pas `napkin`** (binaire déjà pris par le paquet npm
  `napkin-ai`, qui utilise aussi un dossier `.napkin/`). Dossier de configuration
  éventuel : `.nstack/`.
- Aucune dépendance nouvelle. Stdlib + PyYAML, déjà présent.
- Les scripts de `platform/fitness/` restent exécutables directement : la CI les appelle
  ainsi et ne doit pas dépendre du CLI.
- Supprimer le `Makefile` racine et celui du squelette de module. Les `commands` du
  gabarit deviennent des `TODO` explicites, plus des appels `make`.
- Mettre à jour toutes les références à `make …` — `README.md`, `CONTRIBUTING.md`,
  `platform/README.md`, workflows, scaffold. Aucune référence morte.
- Écrire `docs/adr/0001-point-d-entree-unique-nstack.md`. Le *prior art* couvre deux
  conventions : le point d'entrée unique (`manage.py` de Django) et le nommage des CLI
  (mot prononçable plutôt qu'initialisme). Les *conséquences* nomment la règle
  nouvellement vérifiable : les commandes sont déclarées dans le manifest, donc la
  plateforme n'impose plus aucune stack.

## C2 — Check anti-placeholder

**Défaut.** `manifests.py` vérifie que `responsibility` est non vide, pas qu'elle a été
écrite. Un module entièrement non rempli passe au vert. Le gabarit garantit la forme,
pas le contenu.

**Cible.** Contrôle `M10` : tout marqueur `TODO`, `FIXME` ou `<…>` restant dans un
`MANIFEST.yaml`, un `AGENTS.md` local ou un `runbook.md` fait échouer la CI **dès que le
module quitte le statut `Proposé`**. Un module `Proposé` a le droit d'être incomplet ;
un module `Actif` n'en a pas.

## C3 — Hook git versionné

**Défaut.** `.git/hooks/` n'est pas versionné : un hook créé à la main n'existe que chez
son auteur.

**Cible.** `core.hooksPath` vers un dossier du dépôt, positionné par
`./nstack bootstrap`. Le hook pre-commit lance `./nstack fitness`.

Il reste contournable par `--no-verify`, et **c'est voulu** (invariant P3). Écris-le en
commentaire dans le hook, sinon quelqu'un le renforcera un jour en croyant bien faire, et
on cessera de considérer la CI comme la vraie barrière.

## C4 — Proxy d'oracle

**Défaut.** L'OS exige que le critère de réussite soit écrit et vu échouer avant la
génération. C'est invérifiable mécaniquement.

**Cible.** Meilleur proxy disponible : sur une PR portant le label `feature` ou `bug`,
vérifier qu'au moins un fichier sous un dossier de test est touché.

**Avertissement, pas blocage** — le proxy attrape le cas franc, pas le cas subtil, et
une gate qui bloque à tort sera contournée. Documenter cette limite dans
`docs/os/07-gouvernance.md`.

## C5 — Amorçage, `doctor` et marque

**Défaut.** Le socle suppose aujourd'hui un `unzip`, et porte encore des marqueurs
génériques.

**Cible.**

- Documenter `gh repo create <nom> --template napkinstack/engineering-os` dans
  le README, à la place de la décompression.
- `./nstack doctor` diagnostique : Python et PyYAML, `gh` disponible, hooks installés,
  marqueurs de personnalisation restants, présence de `PRODUCT.md` dans un projet client
  (erreur d'installation). Il rappelle en sortie que les required checks GitHub sont la
  seule vraie barrière et qu'ils **ne se copient pas** avec le template.
- Remplacer `@equipe-plateforme` par `@napkinstack/platform` dans `.github/CODEOWNERS`
  et dans les manifests de `platform/` et `contracts/`. Adapter le scaffold.
- **Ne rien brander dans `docs/os/`, `playbooks/` ni `AGENTS.md`** (invariant P7). En
  cas d'hésitation sur un fichier : laisser générique.

---

## Definition of Done, par chantier

- [ ] Le comportement est couvert par un test qui échouait avant
- [ ] `./nstack fitness` vert
- [ ] `bash platform/tests/run.sh` vert
- [ ] Documentation impactée mise à jour
- [ ] Aucune référence morte
- [ ] Statut du chantier mis à jour dans le tableau ci-dessus
- [ ] Résumé au format `FAIT / VÉRIFIÉ / SUPPOSÉ / NON VÉRIFIÉ / RISQUES`
