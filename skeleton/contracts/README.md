# Contrats

Le **seul** canal de communication entre modules, et le seul point de coordination
entre équipes.

Ce dossier est un **module à part entière** : il a un owner, un manifest, ses propres
tests et une criticité élevée. Une frontière orpheline se dégrade.

## Structure

```
contracts/
├── MANIFEST.yaml
├── <nom-du-contrat>/
│   ├── v1/          ← schéma exécutable, doc, exemples, cas d'erreur
│   └── v2/
└── tests/           ← contract tests, exécutés des DEUX côtés
```

## Faire évoluer un contrat

**Additif** (champ optionnel, nouvel endpoint) → PR simple, contract tests verts.

**Breaking** → séquence expand/contract en 4 PR, jamais une seule
(`docs/os/03-contracts.md` §4) :

1. contrat v2 déclaré, additif — v1 intacte, tests des deux versions verts
2. le producteur sert v1 **et** v2
3. chaque consommateur migre à son rythme, met à jour son manifest
4. retrait de v1 quand `consommateurs v1 = 0`

Toute version dépréciée porte une **date de retrait**. Un check échoue quand la date
est dépassée.

## Piège

Une structure inchangée mais une **sémantique modifiée** est un breaking change :
un champ qui gagne une valeur inattendue, une unité qui change, un champ nullable qui
devient toujours rempli. Aucun outil de diff ne le détecte — seuls les contract tests
le font.
