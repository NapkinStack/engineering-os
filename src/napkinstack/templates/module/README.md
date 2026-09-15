# {{MODULE_NAME}}

<Une phrase : à quoi sert ce module.>

- **Owner** : {{OWNER}}
- **Criticité** : {{CRITICALITY}}
- **Manifest** : [MANIFEST.yaml](./MANIFEST.yaml)

## Démarrer

```bash
nstack bootstrap {{MODULE_NAME}}    # depuis un clone vierge, si déclaré
nstack check {{MODULE_NAME}}        # format, lint, types — < 2 min
nstack test {{MODULE_NAME}}         # ne démarre aucun autre module
nstack run {{MODULE_NAME}}          # local, avec doublures pour les dépendances
```

Commandes : section `commands` du MANIFEST, à déclarer pour la stack du module.

## Contrats

- Produits : voir `provides` dans le MANIFEST
- Consommés : voir `consumes` dans le MANIFEST

## Décisions

Voir `docs/adr/`.
