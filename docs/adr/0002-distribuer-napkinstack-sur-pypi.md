# ADR-0002 — Distribuer NapkinStack sur PyPI

- **Statut** : Accepté (2026-09-15, après la publication de la v0.1.0)
- **Date** : 2026-09-15
- **Décideurs** : mainteneurs NapkinStack (`@NapkinStack/maintainers`)
- **Portée** : projet (moteur)
- **Réversibilité** : coûteuse — un nom publié et une commande apprise se changent mal

---

## Contexte

PDR-0001 (Proposé) fixe uv comme seul prérequis et exige que le poste et la CI d'un projet
exécutent la version de NapkinStack qu'il épingle (R3). ADR-0001 (Proposé) fait des tags
du dépôt, au format PEP 440, les versions du squelette ; le moteur et le squelette partagent
donc la même version (R2).

L'organisation GitHub n'autorise que les actions publiées par GitHub, épinglées par SHA.
Le dépôt ne contient aucun secret et ne doit pas en contenir.

## Problème

Sous quel nom, par quel registre et par quel circuit de publication NapkinStack est-il
distribué ?

## Contraintes

- Installable par `uv tool install`, sans autre prérequis.
- Version du paquet identique au tag du dépôt.
- Aucun secret de publication stocké.
- Nom de paquet et nom de commande sans collision.

---

## Prior art

**Convention dominante du domaine :** pour un outil Python en ligne de commande, PyPI,
installation isolée (`uv tool install`, `pipx`), publication depuis la CI par Trusted
Publishing (jeton OpenID Connect éphémère, aucun secret stocké).

**Références examinées :**

| Référence | Ce qu'elle fait | Applicable ici ? |
|---|---|---|
| GitHub Spec Kit | CLI Python installée par `uv tool install`, mise à jour par la même voie | Oui : installation |
| uv (guide officiel de publication) | `uv_build`, version dans `pyproject.toml` (`uv version --bump`), workflow sur tag, deux jobs séparés, environnement `pypi`, Trusted Publishing | Oui : build et circuit |
| PyPI / PyPA (`pypa/gh-action-pypi-publish` v1.14.2) | Publication par Trusted Publishing, attestations de provenance (PEP 740) générées par défaut | Oui : étape de publication |
| Paquet npm, binaire Go ou Rust | Autres registres et formats | Non : l'outillage est Python (PDR-0001) |

---

## Options considérées

### Option 1 — PyPI, `napkinstack`, commande `nstack`, circuit uv + PyPA
- Description : distribution `napkinstack` ; commande `nstack` ; build `uv_build` ;
  publication sur tag par Trusted Publishing avec `pypa/gh-action-pypi-publish`.
- Avantages : conventions de chaque brique ; attestations sans outil supplémentaire ;
  aucun secret.
- Inconvénients : deux actions tierces à autoriser nommément dans l'organisation.
- Coût de sortie : renommer = nouveau paquet et nouvelle commande pour tous les projets.

### Option 2 — Même distribution, publication par `uv publish` et `astral-sh/attest-action`
- Avantages : un seul outil pour build et publication.
- Inconvénients : l'action d'attestation est jeune (v0.0.6, 10 étoiles) ; échoue au
  filtre niche (`docs/os/06-decisions.md` §3).

### Option 3 — Même distribution, uv installé par `pip` sans action tierce
- Avantages : la politique d'actions de l'organisation reste inchangée.
- Inconvénients : s'écarte de la voie officielle d'uv (`astral-sh/setup-uv`), qui sera de
  toute façon nécessaire pour exécuter la version épinglée en CI (R3).

### Option 4 — Ne rien faire
- Pas de distribution : `init` et `update` sont impossibles, PDR-0001 ne peut pas exister.

---

## Décision

**Option 1.**

| Élément | Choix | Fait vérifié |
|---|---|---|
| Registre | PyPI | — |
| Nom de distribution | `napkinstack` | Libre sur PyPI (2026-09-15) |
| Commande | `nstack` | Le paquet PyPI `nstack` (0.2.1, 2018) n'installe aucune commande ; le paquet npm `nstack` (0.0.1) non plus |
| Installation | `uv tool install napkinstack` | Convention de Spec Kit |
| Build | `uv_build`, version écrite dans `pyproject.toml`, montée par `uv version --bump` | `uv_build` refuse les métadonnées dynamiques (uv 0.12.14, `crates/uv-build-backend/src/metadata.rs`) |
| Version publiée | Tag `vX.Y.Z` égal à la version du projet ; publication refusée sinon | Tags PEP 440 exigés par Copier (ADR-0001) |
| Circuit | Workflow sur tag de version : job de build sans droit, job de publication seul à recevoir `id-token: write`, environnement `pypi` | Guide officiel d'uv |
| Publication | `pypa/gh-action-pypi-publish`, Trusted Publishing, attestations par défaut | README de l'action |
| uv en CI | `astral-sh/setup-uv` | Voie officielle d'uv |

Les deux actions tierces sont ajoutées **nommément** à la liste autorisée de
l'organisation, épinglées par SHA comme les autres. Ce sont les seules exceptions à la
règle « actions de GitHub uniquement ».

Aucune publication de réservation : la première version publiée est une vraie version,
à la fin du plan d'implémentation. PyPI décourage la réservation de noms (PEP 541).

### Déviation par rapport à la convention

Aucune.

---

## Critère de succès

*(Convention adoptée : critère non obligatoire.)* La première version publiée s'installe
par `uv tool install napkinstack` sur un poste neuf, affiche son attestation de provenance
sur PyPI, et sa publication n'a utilisé aucun secret stocké.

**Constaté le 2026-09-15**, sur la v0.1.0 :

- `uv tool install napkinstack==0.1.0 --with-executables-from pre-commit`, dossiers d'outils
  et cache isolés : `nstack 0.1.0` et `pre-commit` installés ; `nstack init` crée un projet
  depuis le tag publié, qui passe ses fitness functions, ses hooks et `nstack new-module` ;
- API d'intégrité de PyPI : une attestation pour le wheel et une pour l'archive source,
  éditeur de confiance GitHub, dépôt `NapkinStack/engineering-os`, workflow `release.yml`,
  environnement `pypi` ;
- aucun secret : `release.yml` n'en référence aucun, l'action PyPA ne reçoit pas de mot de
  passe et échange le jeton OpenID Connect du job.

---

## Conséquences

**Positives :**

- Aucun jeton PyPI à stocker ni à renouveler.
- Chaque version publiée est reliée à son workflow et à son commit par une attestation.
- Un seul numéro de version pour le moteur, le squelette et le paquet.

**Négatives et dette acceptée :**

- La politique d'actions de l'organisation s'élargit à deux actions nommées.
- Un compte PyPI à l'identité NapkinStack, 2FA obligatoire, porte l'éditeur de confiance ;
  sa gestion reste une action humaine.
- Le nom `nstack` reste un nom de commande non réservé : un autre outil pourrait
  l'installer un jour.

**Impacts sur d'autres modules ou contrats :** `platform/` devient un paquet Python
installable ; D18 (`make` et `pip` absents) est résolu par uv.

**Règle à automatiser :** la publication échoue si le tag diffère de la version du
projet. Le workflow de publication est couvert par les hooks existants : zizmor
(permissions, épinglage, audit `use-trusted-publishing`) et actionlint.
`docs/os/07-gouvernance.md` §2

---

## Alternatives rejetées

- **`uv publish` avec `astral-sh/attest-action`** : action d'attestation trop jeune.
- **uv installé par `pip`** : écart à la voie officielle pour éviter une autorisation que
  R3 rendra de toute façon nécessaire.
- **Commande `napkin`** : binaire déjà installé par le paquet npm `napkin-ai`, qui utilise
  aussi un dossier `.napkin/`.
- **Commande `os.py` ou `manage.py`** : masque le module standard `os`, ou entre en
  collision avec un module Django.
- **Commande `napkinstack`** : sans collision, mais longue à taper à chaque usage ; elle
  reste le nom de distribution.
