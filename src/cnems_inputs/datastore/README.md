# DataStore

Input resource management for reproducible collaborative data pipelines.

Based off a subcomponent of [PUDL](https://github.com/catalyst-cooperative/pudl).

## Notes from initial cloning, July 2026

### TODOs

Components

- A way to specify and override defaults for the local resource cache,
    previously provided by PudlPaths

Decisions

- Will there be a cloud cache?
- What are the epacems-specific unit tests for? Is there a dataset-agnostic way to express the same constraints?

Errands

- Verify Zenodo DOIs for C-NEMS will still match `/(10\.5072|10\.5281)/zenodo.([\d]+)/`

### Things we had to customize

- local import package paths for script, caching, logging, etc
- User Agent
- ZenodoDoiSettings attributes
- ZenodoDoiSettings configdict prefix
- get_zenodo_dois_path
