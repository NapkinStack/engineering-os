# Playbook — Sécurité

> **Déclencheur.** Charge ce playbook si la tâche touche à : authentification,
> autorisation, secrets, données personnelles ou sensibles, entrées externes, upload de
> fichiers, exposition réseau, dépendances.
>
> Format : `situation → action → vérification`. Ce qui n'est pas vérifiable ici doit
> remonter en revue humaine.

---

## Règles absolues

| # | Règle |
|---|---|
| S1 | **Aucun secret dans le repository.** Ni en clair, ni encodé, ni « temporairement », ni dans un test, ni dans un commentaire. |
| S2 | **Toute entrée externe est hostile** jusqu'à validation explicite. |
| S3 | **Moindre privilège par défaut** — y compris pour la CI et les agents. |
| S4 | **Refus par défaut** en autorisation : ce qui n'est pas explicitement permis est interdit. |
| S5 | **Ne jamais concevoir soi-même** un mécanisme cryptographique, de hachage de mot de passe ou d'authentification. Convention établie, toujours (Prior Art Gate). |

Si une de ces règles doit être enfreinte, ce n'est plus une tâche de développement :
c'est une décision, elle passe par un ADR et une validation humaine.

---

## Authentification

| Situation | Action | Vérification |
|---|---|---|
| Nouveau point d'entrée | Vérifier qu'il est couvert par le mécanisme existant, pas un nouveau | Test : appel non authentifié → refus |
| Stockage de mot de passe | Algorithme de hachage lent et standard, jamais maison | Test sur l'algorithme employé |
| Session ou token | Expiration, révocation et rotation prévues | Test : token expiré → refus |
| Message d'erreur d'authentification | Ne jamais révéler si le compte existe | Test sur le contenu du message |

---

## Autorisation

C'est la source de vulnérabilité la plus fréquente, et la plus facile à tester.

| Situation | Action | Vérification |
|---|---|---|
| Nouvel endpoint ou action | Décider explicitement qui a le droit | Test par rôle : autorisé, non autorisé, non authentifié |
| Accès à une ressource par identifiant | Vérifier l'appartenance, pas seulement le rôle | Test : utilisateur A accède à la ressource de B → refus |
| Liste ou recherche | Filtrer côté serveur, jamais côté client | Test : la réponse ne contient aucune donnée d'autrui |
| Élévation de privilège possible | La traiter comme action à haut risque | Test + journalisation + revue humaine |

> **Piège le plus courant.** Masquer un bouton dans l'interface n'est pas une
> autorisation. Toute règle d'accès existe côté serveur, et est testée là.

---

## Secrets

| Situation | Action | Vérification |
|---|---|---|
| Besoin d'un secret | Variable d'environnement ou coffre — jamais le code | Détection automatisée en CI |
| Secret exposé, même brièvement | **Rotation immédiate.** Le retirer du commit ne suffit pas | Incident, pas simple correctif |
| Secret dans un test | Valeur factice explicitement nommée comme telle | Revue du diff |
| Log contenant un secret ou un token | Masquer à la source, pas au moment de l'affichage | Test sur le contenu du log |

---

## Entrées et données

| Situation | Action | Vérification |
|---|---|---|
| Entrée utilisateur | Valider structure, type, bornes, format — puis assainir | Test avec entrée invalide, vide, trop longue, malformée |
| Requête vers une base | Requêtes paramétrées, jamais de concaténation | Test d'injection |
| Affichage de contenu fourni | Échappement au rendu, adapté au contexte | Test XSS |
| Upload de fichier | Type, taille, extension, stockage hors zone exécutable | Test avec fichier hostile |
| Donnée personnelle | Minimiser, chiffrer au repos si sensible, journaliser l'accès | Revue + inventaire des données |
| Log applicatif | Aucune donnée personnelle ni secret | Test sur le contenu du log |

---

## Dépendances et supply chain

| Situation | Action | Vérification |
|---|---|---|
| Nouvelle dépendance | Filtre niche (`docs/os/06-decisions.md` §3) + déclaration au manifest | Revue : dépendance non déclarée (à automatiser) |
| Vulnérabilité signalée | Traiter selon la sévérité et l'exposition réelle, pas seulement le score | Analyse automatisée en CI |
| Dépendance non maintenue | Ouvrir une issue *Dette technique* avec la stratégie de sortie | Revue de dépendances |

---

## Exposition et abus

| Situation | Action |
|---|---|
| Endpoint public coûteux | Rate limiting, dès la première version |
| Opération sensible | Journalisation auditables : qui, quoi, quand, depuis où |
| Erreur renvoyée au client | Message générique ; le détail va dans les logs |
| Ressource interne | Non exposée par défaut ; l'exposition est une décision |

---

## Actions à haut risque

Modification de permissions, accès à des secrets, changement touchant
l'authentification, exposition d'un nouveau service, migration irréversible.

**Procédure obligatoire — jamais d'exécution silencieuse :**

```
1. nommer le risque et son rayon d'impact
2. décrire l'état avant / après
3. proposer la procédure sûre et le rollback
4. demander confirmation explicite
```

---

## Checklist de fin

- [ ] Aucun secret ajouté, sous aucune forme
- [ ] Autorisation testée par rôle **et** par appartenance
- [ ] Entrées validées et assainies, avec tests négatifs
- [ ] Logs exempts de secrets et de données personnelles
- [ ] Messages d'erreur non informatifs pour un attaquant
- [ ] Dépendances nouvelles déclarées et filtrées
- [ ] Actions à haut risque confirmées explicitement
- [ ] Ce qui n'a pas pu être vérifié figure dans `NON VÉRIFIÉ` du résumé
