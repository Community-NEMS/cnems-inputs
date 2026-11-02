# Design Decisions and Conventions

## Rule naming

Snakemake rule names pertaining to published resources should be double-underscore (`__`) delimited and contain the following fields:

1. Layer/stage; one of `raw` `core` `out`
    - `raw` for data originally produced outside this repository
    - `core` for cleaned intermediate files, useful for validation or debugging
    - `out` for publishable files that meet the spec in the datapackage
1. Resource name; as listed in datapackage.json
1. [Optional] Descriptive slug; e.g. the type of region aggregation

For example, there are two rules for available capacity,

- `core__available_capacity__county`
    - Stage is `core`
    - Resource name is `available_capacity`
    - Slug is `county`; this file contains data at the county level,
        ready for aggregation to larger regions.
- `out__available_capacity`
    - Stage is `out`
    - Resource name is `available_capacity`
    - Slug is not used

This naming convention lets us use the datapackage file to store properties of each resource,
such as output path and data types,
and look them up wherever they are needed.

## Script naming

Wherever possible, make the script name match the rule name, or use the rule name as a prefix.

This naming convention helps quickly move between the Snakemake file and the `src/` directory,
when you need to know the rule definition for a script, or the script details for a rule.
It also helps make it more obvious when a script file is no longer needed.
