# {{MODULE_NAME}}

<Une phrase : à quoi sert ce module.>

- **Owner** : {{OWNER}}
- **Criticité** : {{CRITICALITY}}
- **Manifest** : [MANIFEST.yaml](./MANIFEST.yaml)

## Démarrer

```bash
make bootstrap    # depuis un clone vierge
make check        # format, lint, types — < 2 min
make test         # ne démarre aucun autre module
make run          # local, avec doublures pour les dépendances
```

## Contrats

- Produits : voir `provides` dans le MANIFEST
- Consommés : voir `consumes` dans le MANIFEST

## Décisions

Voir `docs/adr/`.
