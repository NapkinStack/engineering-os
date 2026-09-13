# Runbook — platform

## Un check bloque toute l'équipe

1. Vérifier que l'échec est réel et non un faux positif de détection.
2. Si faux positif : corriger le motif dans `boundaries.py`, ajouter un cas au test.
3. **Ne jamais désactiver le check** pour débloquer. Utiliser le label d'exception
   prévu, qui laisse une trace comptée.

## Rollback

Les fitness functions sont sans état : `git revert` suffit. Vérifier ensuite
`make fitness` sur la branche principale.

## Faux positif récurrent

C'est un défaut de la plateforme, pas des équipes. Ouvrir une issue *Architecture* :
une gate systématiquement contournée est une gate mal conçue.
