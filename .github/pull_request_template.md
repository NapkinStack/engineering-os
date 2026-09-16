# <titre : ce que ça change, du point de vue du comportement>

Closes #

---

## Module

`modules/<nom>` — **un seul**.

- [ ] Cette PR ne touche qu'un module
- [ ] ⚠️ Cross-module — label `cross-module` requis, justification ci-dessous

<Justification si cross-module. Rappel : un changement de contrat se fait en
séquence expand/contract, pas en une PR (`skeleton/docs/os/03-contracts.md`).>

## Ce que ça change

<Le comportement, pas la liste des fichiers. Le diff dit déjà ce qui a changé ;
cette section dit pourquoi.>

## Oracle

> `skeleton/docs/os/05-workflow.md` §3

- [ ] Le critère de réussite a été écrit **avant** l'implémentation
- [ ] Il a été vu **échouer**, pour la bonne raison
- [ ] Il passe maintenant

Nature de l'oracle : test unitaire · intégration · contract test · fitness function ·
budget · autre : <préciser>

---

## Budget de revue

> `skeleton/docs/os/05-workflow.md` §4

- Lignes modifiées (hors généré) : <n>
- Fichiers touchés : <n>
- [ ] Dans le budget
- [ ] ⚠️ Hors budget — label requis, justification : <génération, migration mécanique,
  renommage massif…>

---

## Contrats

- [ ] Aucun contrat impacté
- [ ] Contrat consommé — version déclarée dans le manifest
- [ ] Contrat modifié, **additif** — contract tests verts
- [ ] Contrat modifié, **breaking** — étape expand/contract n° <1|2|3|4>, ADR lié,
  date de retrait fixée

---

## Definition of Done

> Cocher ce qui est **applicable** selon la criticité du module
> (`skeleton/docs/os/05-workflow.md` §7). Ne jamais cocher une case sans avoir réellement exécuté.

- [ ] Oracle vert
- [ ] Lint, format, types
- [ ] Tests unitaires
- [ ] Build
- [ ] Contract tests *(si contrat)*
- [ ] Fitness functions
- [ ] Tests d'intégration *(selon risque)*
- [ ] Analyse de sécurité
- [ ] Accessibilité *(si UI)*
- [ ] E2E parcours critiques *(criticité élevée+)*
- [ ] Observabilité ajoutée *(criticité élevée+)*
- [ ] Rollback vérifié *(criticité critique)*
- [ ] Documentation impactée mise à jour
- [ ] Diff auto-relu ligne à ligne

---

## Résumé

> Format imposé. Les trois dernières sections sont les plus importantes et les plus
> souvent escamotées. (`skeleton/docs/os/05-workflow.md` §8)

**FAIT**
<une phrase par changement>

**VÉRIFIÉ**
<checks réellement exécutés, avec leur résultat>

**SUPPOSÉ**
<hypothèses prises faute d'information>

**NON VÉRIFIÉ**
<ce qui n'a pas été testé, et pourquoi>

**RISQUES**
<effets de bord possibles, dette introduite, suites nécessaires>

---

## Signaux à remonter

- [ ] J'ai dû regarder l'implémentation d'un autre module → **signal de mauvaise
  frontière** (`skeleton/docs/os/02-modules.md` §9)
- [ ] Une règle du kernel ou d'un playbook m'a gêné sans raison valable
- [ ] Une quality gate a bloqué sans améliorer la qualité
- [ ] Une règle appliquée manuellement mériterait d'être automatisée
  → backlog d'automatisation (`skeleton/docs/os/07-governance.md` §9)
