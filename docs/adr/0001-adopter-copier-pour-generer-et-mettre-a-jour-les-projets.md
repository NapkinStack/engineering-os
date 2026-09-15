# ADR-0001 — Adopter Copier pour générer et mettre à jour les projets

- **Statut** : Proposé
- **Date** : 2026-09-15
- **Décideurs** : mainteneurs NapkinStack (`@NapkinStack/maintainers`)
- **Portée** : projet (moteur et squelette de projet)
- **Réversibilité** : facile pour les projets générés, qui ne contiennent que leurs
  fichiers et un fichier de réponses ; coûteuse pour le moteur, qui devrait remplacer
  l'outil

---

## Contexte

PDR-0001 (Proposé) fixe le comportement : `nstack init` génère un projet qui possède son
squelette ; `nstack update` lui apporte, à sa demande, une nouvelle version fusionnée
avec ses adaptations ; les conflits restent à l'équipe ; une version de NapkinStack
couvre moteur et squelette (R2) ; le poste et la CI exécutent la version épinglée par le
projet (R3). L'outillage est en Python, installé par uv.

Aujourd'hui, le squelette se copie à la main et le seul générateur est
`platform/scaffold/new-module.sh`, qui substitue des marqueurs avec `sed`.

## Problème

Quel outil génère le squelette d'un projet et fusionne les versions suivantes avec les
adaptations locales ?

## Contraintes

- **Fusion à 3 voies** entre la version d'origine, la nouvelle version et le projet
  (PDR-0001, option A).
- **Aucune exécution de code** venant du gabarit lors d'une mise à jour : un projet ne
  doit pas avoir à faire confiance à du code distant pour recevoir des règles.
- **Python, installable par uv** ; licence permissive ; maintenance active.
- **Un seul dépôt** tant qu'un besoin de le scinder n'est pas démontré (PDR-0001).

---

## Prior art

**Convention dominante du domaine :** un générateur de projet à gabarit
(Cookiecutter, Yeoman, modèles de dépôt GitHub). Seule une minorité d'outils sait mettre
à jour un projet déjà généré ; parmi eux, la fusion à 3 voies est la référence.

**Références examinées :**

| Référence | Ce qu'elle fait | Applicable ici ? |
|---|---|---|
| Copier (MIT, v9.18.2 du 2026-09-07, Python ≥ 3.10) | `copy` puis `update` : fusion à 3 voies via `git merge-file`, conflits marqués, refus si l'arbre est sale ou si la version recule, fichiers supprimés non recréés, fonctions exécutant du code refusées sans `--trust` | **Oui**, couvre toutes les contraintes |
| cruft (MIT) | Mise à jour des projets Cookiecutter, diff à valider | Non : aucune activité depuis 2024-12 (filtre maintenance) |
| Cookiecutter (BSD-3) | Génération seule | Non : aucune mise à jour |
| Yeoman (Node) | Chaque réécriture de fichier existant demande validation, sans fusion | Non : pas de fusion, et un runtime Node en plus d'uv |
| projen (Node) | Fichiers synthétisés, non modifiables | Non : c'est l'option C écartée par PDR-0001 |
| Modèles de dépôt GitHub | Copie initiale | Non : aucune mise à jour |

---

## Options considérées

### Option 1 — Copier, piloté par le moteur
- Description : le squelette est **le** gabarit Copier de ce dépôt (`_subdirectory`) ;
  ses versions sont les tags du dépôt ; le moteur appelle l'API publique `run_copy` et
  `run_update`, sans jamais activer `unsafe`.
- Avantages : fusion à 3 voies éprouvée ; refus natifs (arbre sale, retour arrière,
  code distant) ; une version unique pour moteur et squelette ; fichier de réponses
  standard.
- Inconvénients : `update` télécharge le gabarit depuis GitHub ; les fichiers qui
  contiennent des variables prennent le suffixe `.jinja`.
- Coût de mise en place : faible · de maintenance : suivre les versions de Copier ·
  **de sortie** : réécrire `init` et `update` ; les projets générés restent intacts.

### Option 2 — Cookiecutter et cruft
- Description : génération par Cookiecutter, mise à jour par cruft.
- Avantages : Cookiecutter est très adopté.
- Inconvénients : cruft n'est plus maintenu (aucune activité depuis 2024-12).
- Coût de sortie : identique à l'option 1, avec un risque d'abandon déjà matérialisé.

### Option 3 — Construire la fusion dans le moteur
- Description : générer les versions et appeler `git merge-file` nous-mêmes.
- Avantages : aucune dépendance.
- Inconvénients : réimplémente Copier, cas limites compris (fichiers supprimés,
  renommés, versions sautées). Échoue au filtre de proportionnalité
  (`docs/os/06-decisions.md` §3).

### Option 4 — Ne rien faire
- Copie manuelle : contraire à PDR-0001, qui existe pour sortir des copies figées.

---

## Décision

**Option 1.** Parmi les références examinées, Copier est le seul outil maintenu qui
réalise exactement le comportement de PDR-0001, refus de sécurité compris ; c'est l'adoption d'une convention, pas une
construction. Il est piloté par le moteur, pour qu'une version de NapkinStack soit
toujours la même pour le moteur et pour le squelette (R2, R3).

Règles d'usage :

1. **Un seul gabarit dans ce dépôt : le squelette de projet.** Copier recommande un
   gabarit par dépôt, car les tags sont partagés. L'enveloppe de module n'est donc pas un
   second gabarit Copier ; `new-module` reste un scaffold du moteur (D19 à corriger à
   part).
2. **Versions = tags du dépôt**, au format PEP 440 exigé par Copier.
3. **Aucune fonction « unsafe »** (tâches, migrations, extensions Jinja) : le moteur
   n'active jamais `unsafe`, et Copier refuse ces fonctions par défaut.
4. **Conflits en ligne** (défaut de Copier) : le hook `check-merge-conflict` du squelette
   et la CI du projet refusent tout marqueur restant.
5. **Suffixe `.jinja` uniquement** sur les fichiers qui contiennent une variable ; tous
   les autres sont copiés tels quels et restent lisibles et vérifiables.

### Déviation par rapport à la convention

Aucune.

---

## Critère de succès

*(Convention adoptée : critère non obligatoire.)* Validation par le prototype de
PDR-0001 : ses critères d'acceptation 1 et 4 à 7 passent avec Copier, sans code de
fusion propre à NapkinStack.

Si ce n'est pas le cas : superséder par une option documentée dans une nouvelle ADR.

---

## Conséquences

**Positives :**

- Aucun mécanisme de fusion maison à maintenir.
- Un projet ne peut pas exécuter de code venu du gabarit lors d'une mise à jour.
- Le fichier de réponses de Copier enregistre la version d'origine du projet, sans format
  propre à NapkinStack.

**Négatives et dette acceptée :**

- `update` exige un accès au dépôt GitHub public de NapkinStack.
- Un fichier YAML contenant des variables devient un `.jinja` que les hooks YAML ne
  vérifient plus : c'est le projet généré, testé en CI, qui est vérifié à sa place.
- Les versions de Copier suivent Dependabot, comme toute dépendance.

**Impacts sur d'autres modules ou contrats :** `platform/` devient le moteur qui pilote
Copier ; le squelette est extrait dans un sous-dossier ; `new-module.sh` est conservé.

**Règle à automatiser :** aucun check nouveau. Le refus des fonctions « unsafe » est
natif (Copier sort en code 4) et sera exercé par le test de génération d'un projet dans
la CI de NapkinStack, prévu au plan d'implémentation. `docs/os/07-gouvernance.md` §2

---

## Alternatives rejetées

- **cruft** : bon modèle, mais sans activité depuis décembre 2024 ; adopter un outil déjà
  abandonné crée une dette de sortie immédiate.
- **Yeoman** : validation fichier par fichier sans fusion, et un runtime Node en plus.
- **projen** : fichiers non modifiables, contraire au besoin d'adapter les règles.
- **Construire la fusion** : réimplémenter Copier coûte plus cher à maintenir que de
  suivre ses versions.
- **Plusieurs gabarits Copier dans ce dépôt** (squelette et enveloppe de module) :
  contraire à la recommandation de l'outil, les tags étant partagés.
