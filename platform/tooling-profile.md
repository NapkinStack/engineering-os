# Profil d'outillage

> Les outils sont des **adaptateurs**, jamais des fondations architecturales.
> L'OS déclare des **capacités** ; ce fichier les mappe sur les outils du moment.
> Changer d'outil ne doit jamais obliger à toucher au kernel ou aux playbooks.
>
> Ce fichier est le seul endroit du dépôt où un nom d'outil apparaît.

| Capacité | À quoi elle sert | Outil retenu | Décision |
|---|---|---|---|
| Recherche et navigation dans le dépôt | Inventaire local sans tout charger | | |
| Recherche documentaire fiable | Vérifier plutôt que supposer | | |
| Accès aux sources officielles | Versions, API, contraintes réelles | | |
| Exécution de commandes et de tests | Rendre l'oracle réellement exécutable | | |
| Interaction Git, issues, PR | Traçabilité, petits lots | | |
| Inspection UI et captures | Validation UX au-delà du « ça compile » | | |
| Analyse de sécurité | Contrôles automatisés intégrés | | |
| Analyse d'architecture | Support des fitness functions | `platform/fitness/` | — |
| Chargement de règles à la demande | Playbooks déclenchés par contexte | Skills Claude Code, générées par `sync_skills.py` | — |
| Agents spécialisés | Revue indépendante, investigation isolée | | |

## Critères de choix

Projet · sécurité · confidentialité · fiabilité · coût · maturité · intégration · et
surtout **capacité à être automatisé**. Un outil utile uniquement en interactif ne peut
jamais devenir une garantie.

> Ne jamais ajouter un outil parce qu'il est populaire. Le Prior Art Gate s'applique
> aussi aux outils (`docs/os/06-decisions.md`).

## Règle de remplacement

Remplacer un outil ne doit toucher que ce fichier et la configuration associée. Si un
changement d'outil oblige à modifier le kernel, un playbook ou un module, c'est que
l'outil était devenu une fondation — corriger l'abstraction, pas le prompt.
