# platform — instructions locales

## Responsabilité

Fournit les verbes standards, les fitness functions et le scaffold de module.

## Ce que ce module ne fait pas

Il ne contient **aucune logique métier** et ne dépend d'aucun module. Toute règle
métier ici serait partagée par tous les modules, donc les rendrait inséparables.

## Invariants

- Une fitness function doit être **rapide** (< 30 s), **déterministe** (aucun faux
  positif aléatoire) et **explicative** : message d'échec nommant la règle violée,
  le fichier, et l'action corrective.
- Les verbes standards ne changent **jamais de nom**. Leur contenu est libre.
- Un changement ici affecte tous les modules : le budget de revue s'applique
  strictement, et un ADR est attendu pour toute nouvelle règle bloquante.

## Pièges connus

- `boundaries.py` détecte textuellement. Modifier `IMPORT_HINTS` sans tester sur le
  dépôt réel produit soit du bruit, soit des angles morts.
- Le scaffold écrit dans `.github/CODEOWNERS` : vérifier l'absence de doublon.

## Zones à ne pas modifier sans validation

`fitness/` — ce sont les garde-fous eux-mêmes. Les affaiblir silencieusement
reviendrait à contourner une quality gate.
