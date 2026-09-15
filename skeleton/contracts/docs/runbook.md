# Runbook — contracts

## Un consommateur casse après un changement de contrat

1. Vérifier l'étape expand/contract en cours (1 à 4).
2. Si le retrait de v1 a eu lieu trop tôt : le restaurer immédiatement — c'est un
   rollback, pas une correction.
3. Post-mortem : pourquoi le check « consommateurs v1 = 0 » n'a-t-il pas bloqué ?

## Contraction en retard

Version dépréciée dont la date de retrait est dépassée. La CI est rouge, et c'est
voulu : c'est un état intermédiaire permanent en train de s'installer.

Deux issues possibles : terminer la migration du dernier consommateur, ou repousser la
date **explicitement**, avec justification.
