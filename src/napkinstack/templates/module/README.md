# {{MODULE_NAME}}

<One sentence: what this module is for.>

- **Owner**: {{OWNER}}
- **Criticality**: {{CRITICALITY}}
- **Manifest**: [MANIFEST.yaml](./MANIFEST.yaml)

## Getting started

```bash
nstack bootstrap {{MODULE_NAME}}    # from a fresh clone, when declared
nstack check {{MODULE_NAME}}        # format, lint, types - under 2 min
nstack test {{MODULE_NAME}}         # never starts another module
nstack run {{MODULE_NAME}}          # locally, with doubles for the dependencies
```

Commands: the `commands` section of the MANIFEST, to declare for this module's stack.

## Contracts

- Provided: see `provides` in the MANIFEST
- Consumed: see `consumes` in the MANIFEST

## Decisions

See `docs/adr/`.
