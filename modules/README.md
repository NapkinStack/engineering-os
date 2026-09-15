# Modules

Une unité de contexte autonome et de parallélisme par dossier.

> **Règle fondamentale.** Un développeur ou un agent doit pouvoir comprendre, modifier,
> tester et valider un module **sans comprendre le reste du système**.
> Si ce n'est pas vrai, ce n'est pas un module : c'est un dossier.

## Créer un module

```bash
uv run nstack new-module billing team-revenue standard
```

Le scaffold produit le manifest, l'`AGENTS.md` local, les verbes standards, la ligne
CODEOWNERS, et active les fitness functions **dès le premier commit** — un module créé
sans garde-fous accumule des violations qu'on découvre trop tard.

Créer un module est une décision : elle passe par un **ADR** (capacité couverte,
frontière, alternatives rejetées).

## Avant de découper

Un module représente une **capacité cohérente**, pas une table ni quelques endpoints.
Voir l'arbre de décision dans `docs/os/02-modules.md` §3.

Ne pas découper si : la capacité n'est pas cohérente, le module ne peut pas être testé
seul, aucun owner n'est identifiable, ou son rythme de changement est identique au
reste sans autre raison explicite.

## Ce qui est uniforme, ce qui ne l'est pas

**Uniforme** : les verbes (`bootstrap`, `check`, `test`, `run`), l'enveloppe de
fichiers, les checks obligatoires, le format des contrats.

**Libre** : langage, framework, base de données, architecture interne, patterns.

> On retrouve les mêmes **verbes**, jamais le même **code**.
