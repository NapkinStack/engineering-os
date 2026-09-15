# Contribuer à NapkinStack

Ce dépôt développe le framework ; il en est aussi le premier utilisateur. Lire d'abord
[`PRODUCT.md`](PRODUCT.md), en particulier §5.

## Le parcours d'un chantier

```mermaid
flowchart LR
    C["Chantier<br/>chantiers.md"]:::suivi --> P["Plan détaillé<br/>plans/"]:::suivi
    P --> T["Test qui échoue<br/>platform/tests/run.sh"]:::code
    T --> I["Implémentation<br/>test vert"]:::code
    I --> V["Vérifications<br/>hooks · fitness · clone vierge"]:::code
    V --> R["PR<br/>résumé en 5 blocs"]:::revue
    R --> CI["CI et relecture"]:::revue
    CI --> M["Merge<br/>squash"]:::fin

    classDef suivi fill:#374151,color:#fff
    classDef code fill:#1f2937,color:#fff
    classDef revue fill:#1e3a8a,color:#fff
    classDef fin fill:#065f46,color:#fff
```

**Légende** — gris clair : suivi (`docs/governance/`) · gris foncé : travail sur la branche ·
bleu : revue · vert : intégré à `main`.

## Les règles du lot

- **Un chantier = une PR**, jamais deux ensemble. Dans les modèles d'issue et de PR, « le
  module » se lit « le chantier ».
- **Le test d'abord** : chaque contrôle a un test qui prouve qu'il échoue (P5), vu rouge
  avant l'implémentation ; chaque échec nomme la règle, l'endroit et l'action (P6).
- **Budget de revue** : 400 lignes et 15 fichiers ; au-delà, label `hors-budget` justifié
  dans la PR (migration mécanique, plan détaillé, génération).
- **Résumé de PR** : `FAIT / VÉRIFIÉ / SUPPOSÉ / NON VÉRIFIÉ / RISQUES`.
- **Documentation dans le même lot** : un changement de commande, de statut ou de décision
  met à jour toutes les pages concernées, schémas légendés compris.
- **Definition of Done** : [`docs/governance/chantiers.md`](docs/governance/chantiers.md).

## Publier une version

```mermaid
flowchart LR
    V["PR de version<br/>uv version --bump"]:::humain --> T["Tag vX.Y.Z<br/>sur main"]:::humain
    T --> C["Construction<br/>tag = version, sinon arrêt"]:::ci
    C --> A{"Approbation<br/>environnement pypi"}:::humain
    A --> P["PyPI<br/>Trusted Publishing, attestation"]:::pypi

    classDef humain fill:#065f46,color:#fff
    classDef ci fill:#1f2937,color:#fff
    classDef pypi fill:#1e3a8a,color:#fff
```

**Légende** — vert : action d'un mainteneur · gris : `.github/workflows/release.yml` ·
bleu : PyPI. Décision : [ADR-0002](docs/adr/0002-distribuer-napkinstack-sur-pypi.md).

1. Monter la version dans une PR : `uv version --bump patch` (ou `minor`), puis la fusionner.
2. Poser le tag sur le commit fusionné : `git tag -a vX.Y.Z -m "NapkinStack vX.Y.Z" <commit>`,
   puis `git push origin vX.Y.Z`.
3. Approuver le déploiement dans GitHub Actions (« Review deployments »).

Aucun secret n'est stocké : GitHub prouve son identité à PyPI à chaque publication. Une
version publiée ne se remplace pas ; une erreur se corrige par la version suivante, et une
version défectueuse se retire (*yank*) sur PyPI.

Barrières contre les fuites et exceptions (`cross-module`, `hors-budget`) : les mêmes que
dans les projets, décrites dans [`skeleton/CONTRIBUTING.md`](skeleton/CONTRIBUTING.md).
