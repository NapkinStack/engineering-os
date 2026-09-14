# Chantiers

> Les défauts identifiés du socle, dans l'ordre de traitement.
> **Un chantier = une PR.** Ne jamais les fusionner.
>
> Contexte produit : [`PRODUCT.md`](../../PRODUCT.md). Invariants : `PRODUCT.md` §4.

## Séquence

```mermaid
flowchart LR
    S0["Étape 0<br/>réglages GitHub"]:::fait --> C0["C0<br/>CI verte sur<br/>clone vierge"]:::fait
    C0 --> C01["C0.1<br/>hooks et secrets"]:::fait
    C01 --> C02["C0.2<br/>sécurité des<br/>workflows"]:::fait
    C02 --> C03["C0.3<br/>formats stricts"]:::fait
    C03 --> PDR["PDR-0001<br/>modèle framework<br/>+ prototype"]:::afaire
    PDR --> RP["Replanification<br/>C1 · C2 · C4 · C5"]:::bloque

    classDef fait fill:#065f46,color:#fff
    classDef partiel fill:#92400e,color:#fff
    classDef afaire fill:#374151,color:#fff
    classDef bloque fill:#7c2d12,color:#fff
```

**Légende** — vert : fait · orange : partiel · gris : à faire · rouge : attend une décision.

| # | Chantier | Statut |
|---|---|---|
| 0 | Réglages GitHub (hors dépôt) | Fait |
| C0 | CI verte sur clone vierge | Fait |
| C0.1 | Hooks et secrets | Fait |
| C0.2 | Sécurité des workflows | Fait |
| C0.3 | Formats stricts | Fait |
| PDR-0001 | NapkinStack comme framework | À faire |
| C1 | Point d'entrée unique `nstack` | À replanifier après PDR-0001 |
| C2 | Check anti-placeholder | À replanifier après PDR-0001 |
| C3 | Hook git versionné | Absorbé par C0.1 |
| C4 | Proxy d'oracle | À replanifier après PDR-0001 |
| C5 | Amorçage, `doctor` et marque | À replanifier après PDR-0001 |

---

## Étape 0 — Réglages GitHub

Ils ne se versionnent pas : chaque dépôt doit les refaire. Depuis le passage en
organisation, les politiques Actions, la 2FA et les droits de base se règlent une fois
pour toute l'organisation `NapkinStack`.

| Réglage | État |
|---|---|
| Secret Protection et protection au push | Vérifié par l'API (désactivées par le transfert, réactivées) |
| Graphe de dépendances et alertes Dependabot | Vérifié par l'API |
| Discussions activées (canal des questions du formulaire d'issues) | Vérifié par l'API |
| Organisation : Actions de GitHub seules, SHA obligatoire, jeton en lecture seule, approbation des contributeurs externes | Vérifié par l'API sur le dépôt |
| Organisation : 2FA obligatoire, aucun droit de base, équipe `maintainers` en écriture | Confirmé ; équipe vérifiée par l'API |
| Signalement privé de vulnérabilités | Vérifié par l'API |
| Approbation des workflows pour tout contributeur externe | Confirmé |
| Token Actions en lecture seule ; Actions ne crée ni n'approuve de PR | Confirmé |
| Actions autorisées : celles de GitHub uniquement | Confirmé |
| Wiki désactivé | Vérifié par l'API |
| Ruleset `main` : PR obligatoire, force-push et suppression interdits, squash seul | Vérifié par l'API |
| Required checks `Fitness functions` et `Périmètre et budget de revue` | Vérifié par l'API |
| Required check `Hooks et secrets` | Vérifié par l'API |
| Actions épinglées par SHA obligatoires | Vérifié par l'API |

## C0 — CI verte sur clone vierge

**Défaut.** `main` rouge dès le premier push : S3 exige des skills gitignorées, donc
absentes de la CI. `pr_scope.sh` commité sans bit exécutable (exit 126). Les tests des
garde-fous ne tournent pas en CI.

**Cible.** S3 non applicable sans `.claude/skills/`, et toujours bloquant dès qu'une skill
est générée. Scripts à shebang en `100755`. `platform/tests/run.sh` dans le job
`Fitness functions`.

## C0.1 — Hooks et secrets

**Défaut.** Aucune barrière locale avant publication ; le job `secrets` est factice.

**Cible.** Framework [pre-commit](https://pre-commit.com) : gitleaks, `detect-private-key`,
`check-added-large-files`, `check-merge-conflict`, contrôles de shebang. La même
configuration tourne en CI (P3), plus gitleaks sur les commits poussés.

Le test d'échec génère le faux secret à l'exécution : écrit en dur, il déclencherait la
protection au push. Remplace C3, car pre-commit refuse de s'installer si
`core.hooksPath` est défini.

**Pièges traités.** Le hook gitleaks officiel ne scanne que les changements indexés,
vides en CI : la CI l'ignore et lance un hook local qui scanne tout l'historique. Sortie
masquée (`--redact`), car les logs de CI sont publics. Dependabot met à jour le
hook gitleaks mais pas le scan d'historique : un test bloque la PR tant que les deux
versions divergent (éprouvé sur la PR #5, v8.30.0 → v8.30.1).

## C0.2 — Sécurité des workflows

**Défaut.** Injection possible : `${{ matrix.module }}`, issu des chemins de la PR, est
inséré dans `run:`. Pas de `permissions:`. Actions référencées par tag modifiable. Token
laissé dans `.git/config`. `SECURITY.md` sans canal de signalement. Fichiers locaux
d'agent non ignorés.

**Cible.** zizmor et actionlint ; `permissions: contents: read` ; actions épinglées par SHA
et tenues à jour par Dependabot ; `persist-credentials: false` ; expressions passées par
`env:` ; `SECURITY.md` renvoyant au signalement privé ; `.gitignore` complété.

**Mesuré.** zizmor : 32 constats avant, 0 après. Points retenus : le `git fetch` du job de
périmètre est retiré (redondant avec `fetch-depth: 0`, et il échouerait sur un dépôt
privé sans jeton) ; zizmor tourne hors ligne et actionlint sans shellcheck, pour des
résultats identiques en local et en CI ; Dependabot contourne la politique Actions, donc
l'épinglage SHA obligatoire ne le bloque pas.

## C0.3 — Formats stricts

**Défaut.** Frontmatter YAML des 5 skills générées invalide (` : ` à la française).
Gabarit `MANIFEST.yaml` invalide (`{{MODULE_NAME}}` est lu comme un mapping). PyYAML
accepte les clés dupliquées sans rien dire.

**Cible.** `check-yaml`, yamllint, check-jsonschema (schémas GitHub). Frontmatter sérialisé
par `yaml.safe_dump`, conforme à la spécification Agent Skills.

**Pièges traités.** yamllint ne fait qu'analyser la syntaxe : il laisse passer
`{{MODULE_NAME}}`, que seul le chargement réel de `check-yaml` refuse. Par défaut, la
règle `truthy` n'est qu'un avertissement : `--strict` la rend bloquante. La clé `on:` des
workflows reste permise, les valeurs `yes`/`on` non. Les workflows ne passent pas par
check-jsonschema, actionlint les couvre déjà. Aucun outil maintenu ne valide les skills
(`skills-ref` n'est qu'une démonstration) : d'où le contrôle S4 dans `sync_skills.py`.

**Mesuré.** `check-yaml` : un seul fichier en échec, le gabarit. yamllint : 127 constats de
style avec la configuration par défaut, 0 avec 5 assouplissements (`.yamllint.yaml`), aucun
sur le fond. Les 3 schémas GitHub passaient déjà. Mutations : 12 défauts réintroduits, 12
détectés par `platform/tests/run.sh`.

## PDR-0001 — NapkinStack comme framework

```mermaid
flowchart LR
    subgraph NS["Dépôt NapkinStack"]
        A["A · Développement de l'OS<br/>PRODUCT.md · chantiers · CI de l'OS"]
        B["B · Moteur versionné<br/>CLI · fitness functions<br/>scaffold · presets"]
    end
    B -->|"nstack init"| C["C · Projet généré<br/>gouvernance · ADR/PDR · CI · hooks<br/>modules/ · contracts/"]
    B -.->|"version épinglée"| C
    C -->|"nstack new-module"| M["Module<br/>générateur officiel<br/>+ enveloppe NapkinStack"]
```

**Légende** — trait plein : génération, une seule fois · pointillé : dépendance
versionnée, le projet choisit quand monter de version.

**Décidé (2026-09-13).**

- Modèle Django : le projet généré vit seul, avec son dépôt et sa CI. Seul le moteur
  est une dépendance versionnée. Aucune CI partagée entre dépôts.
- Aucune techno imposée. La stack se choisit **par module**, à `nstack new-module`.
- Un preset de stack est une donnée qui délègue au générateur officiel de l'écosystème.
  Il n'existe qu'après avoir servi à un vrai projet.
- GitHub seul au départ.

**Décidé (2026-09-14).** Organisation GitHub `NapkinStack`, par la voie documentée par
GitHub : compte personnel renommé, organisation créée sous le nom libéré, dépôt transféré.
La conversion automatique, irréversible, aurait supprimé le compte. L'équipe
`maintainers` possède le socle (CODEOWNERS, manifests de `platform/` et `contracts/`).

**À trancher.**

- Identité de l'agent (GitHub App ou compte machine), condition pour exiger une
  approbation humaine : l'auteur d'une PR ne peut pas l'approuver.
- Kernel et playbooks : copiés dans le projet (modifiables, figés) ou générés depuis la
  version installée (à jour, non éditables).
- Réglages GitHub : appliqués par l'API après confirmation, ou checklist vérifiée.
- Nom du paquet : `napkinstack` (`nstack` est déjà pris sur PyPI).
- Cadrage et découpage guidés : à partir de l'idée ou des specs de l'utilisateur, une
  procédure suivie par son agent propose règles, PDR, ADR, modules et contrats ;
  l'humain valide, le CLI génère. À comparer à GitHub Spec Kit et BMAD-METHOD.
- Révision de P1 et du §6 de `PRODUCT.md`.

**Oracle.** Prototype jetable : `init`, création d'un module, puis montée de version
v0.1 → v0.2 sur le projet généré. Le README produit, avec schémas, est réécrit une fois
le PDR accepté.

---

## C1 — Point d'entrée unique `nstack`

> **À replanifier après PDR-0001.** Le modèle framework change sa portée : CLI publié,
> commande `init`, dépendance à pre-commit.

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

> **À replanifier après PDR-0001.**

**Défaut.** `manifests.py` vérifie que `responsibility` est non vide, pas qu'elle a été
écrite. Un module entièrement non rempli passe au vert. Le gabarit garantit la forme,
pas le contenu.

**Cible.** Contrôle `M10` : tout marqueur `TODO`, `FIXME` ou `<…>` restant dans un
`MANIFEST.yaml`, un `AGENTS.md` local ou un `runbook.md` fait échouer la CI **dès que le
module quitte le statut `Proposé`**. Un module `Proposé` a le droit d'être incomplet ;
un module `Actif` n'en a pas.

## C3 — Hook git versionné

> **Absorbé par C0.1.** pre-commit est la convention, et il refuse de s'installer si
> `core.hooksPath` est défini. Texte conservé pour l'historique.

**Défaut.** `.git/hooks/` n'est pas versionné : un hook créé à la main n'existe que chez
son auteur.

**Cible.** `core.hooksPath` vers un dossier du dépôt, positionné par
`./nstack bootstrap`. Le hook pre-commit lance `./nstack fitness`.

Il reste contournable par `--no-verify`, et **c'est voulu** (invariant P3). Écris-le en
commentaire dans le hook, sinon quelqu'un le renforcera un jour en croyant bien faire, et
on cessera de considérer la CI comme la vraie barrière.

## C4 — Proxy d'oracle

> **À replanifier après PDR-0001.**

**Défaut.** L'OS exige que le critère de réussite soit écrit et vu échouer avant la
génération. C'est invérifiable mécaniquement.

**Cible.** Meilleur proxy disponible : sur une PR portant le label `feature` ou `bug`,
vérifier qu'au moins un fichier sous un dossier de test est touché.

**Avertissement, pas blocage** — le proxy attrape le cas franc, pas le cas subtil, et
une gate qui bloque à tort sera contournée. Documenter cette limite dans
`docs/os/07-gouvernance.md`.

## C5 — Amorçage, `doctor` et marque

> **À replanifier après PDR-0001.** `gh repo create --template` sera remplacé par
> `nstack init`. Le marquage de CODEOWNERS et des manifests est fait (organisation,
> 2026-09-14).

**Défaut.** Le socle suppose aujourd'hui un `unzip`, et porte encore des marqueurs
génériques.

**Cible.**

- Documenter `gh repo create <nom> --template napkinstack/engineering-os` dans
  le README, à la place de la décompression.
- `./nstack doctor` diagnostique : Python et PyYAML, `gh` disponible, hooks installés,
  marqueurs de personnalisation restants, présence de `PRODUCT.md` dans un projet client
  (erreur d'installation). Il rappelle en sortie que les required checks GitHub sont la
  seule vraie barrière et qu'ils **ne se copient pas** avec le template.
- ~~Remplacer `@equipe-plateforme` dans `.github/CODEOWNERS` et dans les manifests de
  `platform/` et `contracts/`~~ : fait, `@NapkinStack/maintainers`. Reste à adapter le
  scaffold à un owner de la forme `org/équipe` (D19).
- **Ne rien brander dans `docs/os/`, `playbooks/` ni `AGENTS.md`** (invariant P7). En
  cas d'hésitation sur un fichier : laisser générique.

---

## Registre des défauts

Constatés lors de l'audit du 2026-09-13. Un défaut sans chantier attend d'être ordonnancé.

| # | Constat | Traité par |
|---|---|---|
| D1 | S3 exige des skills gitignorées : `main` rouge sur tout clone vierge | C0 |
| D2 | Scripts à shebang non exécutables (`pr_scope.sh` : exit 126) | C0 |
| D3 | Tests des garde-fous absents de la CI | C0 |
| D4 | Checks sans test d'échec (P5) : M1, M3–M9, B1–B5, S1–S2, P1–P2 | À ordonnancer |
| D5 | M1 documenté mais non implémenté | À ordonnancer |
| D6 | ~34 références mortes `docs/0X-….md`, dont 3 dans le kernel | À ordonnancer |
| D7 | « Module » défini 5 fois, différemment (fitness, `pr_scope.sh`, workflow, scaffold) | À ordonnancer |
| D8 | Manifest malformé : traceback au lieu d'un message (P6) | À ordonnancer |
| D9 | Déclarations sans effet : `review_budget` jamais lu, étapes par criticité en `echo TODO` | À ordonnancer |
| D10 | Frontmatter YAML des skills générées invalide | C0.3 |
| D11 | Gabarit `MANIFEST.yaml` : YAML invalide | C0.3 |
| D12 | Job `secrets` factice ; `.gitignore` renvoie ce détecteur à C5, qui n'en parle pas | C0.1 |
| D13 | Workflows : injection, permissions, épinglage, token persistant | C0.2 |
| D14 | `SECURITY.md` sans canal ; fichiers locaux d'agent non ignorés | C0.2 |
| D15 | Manuel : contrôles promis mais absents (prior art des ADR/PDR, transitions de cycle de vie, issue de contraction, matrice des consommateurs, échéances) | PDR-0001 |
| D16 | `@equipe-plateforme` refusé par GitHub ; équipes impossibles sur un compte utilisateur | Organisation (2026-09-14) |
| D17 | Lien `ORG/REPO` mort dans le formulaire d'issues | Organisation (2026-09-14) |
| D18 | Amorçage : `make` et `pip` absents du poste de référence | PDR-0001 |
| D19 | Scaffold : `sed` casse sur un owner contenant `/` | Replanification |

---

## Definition of Done, par chantier

- [ ] Le comportement est couvert par un test qui échouait avant
- [ ] `./nstack fitness` vert (avant C1 : `manifests.py`, `boundaries.py`, `sync_skills.py --check`)
- [ ] `bash platform/tests/run.sh` vert
- [ ] Documentation impactée mise à jour
- [ ] Aucune référence morte
- [ ] Statut du chantier mis à jour dans le tableau ci-dessus
- [ ] Résumé au format `FAIT / VÉRIFIÉ / SUPPOSÉ / NON VÉRIFIÉ / RISQUES`
