# Sécurité

## Signaler une vulnérabilité

**Ne jamais ouvrir d'issue publique pour une vulnérabilité.**

Utiliser le signalement privé de la forge : sur GitHub, onglet **Security**, puis
**Report a vulnerability**. Le rapport n'est visible que des mainteneurs.

Délai de première réponse visé : **7 jours**.

## Règles absolues du projet

| # | Règle |
|---|---|
| S1 | Aucun secret dans le dépôt — ni en clair, ni encodé, ni dans un test |
| S2 | Toute entrée externe est hostile jusqu'à validation explicite |
| S3 | Moindre privilège par défaut, y compris pour la CI et les agents |
| S4 | Refus par défaut en autorisation |
| S5 | Jamais de mécanisme cryptographique ou d'authentification maison |

Détail opérationnel : `playbooks/securite.md`.

## Secret exposé

Un secret exposé, même brièvement, même dans un commit réécrit depuis :
**rotation immédiate**. Le retirer de l'historique ne suffit pas. C'est un incident,
pas un correctif.

## Actions à haut risque

Modification de permissions, accès à des secrets, exposition d'un nouveau service,
migration irréversible : jamais d'exécution silencieuse. Risque nommé, impact décrit,
procédure sûre et rollback proposés, confirmation explicite demandée
(`AGENTS.md` §5).
