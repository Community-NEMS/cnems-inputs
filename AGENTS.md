# AGENTS.md

Instructions for AI coding agents (Claude Code, Cursor, Copilot, etc.) working in this
repository. Keep it current: treat stale instructions here as a bug, since agents will
follow whatever this file says even after it stops being true.

## Project overview

This package contains data pipelines that feed inputs into the Community NEMS
project. It's being built up incrementally, one piece of tooling and infrastructure
at a time, and the actual data pipeline code has not landed yet. Runtime dependencies
already present (`pandera`, `frictionless`, `snakemake`, `pydantic`) suggest the
shape of what's coming: Snakemake-orchestrated pipelines that validate tabular data
against Frictionless Data Package schemas and pandera/pydantic models.

## Setup commands

This repo uses [pixi](https://pixi.sh) to manage the development environment and
tasks, defined under `[tool.pixi.*]` in `pyproject.toml`.

- Install [pixi](https://pixi.sh/latest/installation/) if it isn't already available.
- Run `pixi install` once to create the `default` environment.
- Run `pixi run prek install` once to install the git pre-commit hooks (run via
    [prek](https://prek.j178.dev/), a fast drop-in replacement for `pre-commit` that
    still reads `.pre-commit-config.yaml`).

<!--
If this project needs additional one-time setup -- database seeding, credentials,
downloading reference data, environment variables, Docker services, etc. -- document
the exact commands here. An agent can't infer steps that only exist in a teammate's
head or a wiki page.
-->

## Task commands

Run everything through pixi tasks rather than calling the underlying tools directly,
so agents use the same invocations CI does:

- `pixi run test` -- run the unit and integration tests under `tests/` with pytest,
    and report combined test coverage.
- `pixi run lint` -- run `ruff` and `pyrefly` (static analysis and type checking).
    Doesn't modify files.
- `pixi run format` -- automatically reformat code and other files with `ruff`,
    `taplo`, `mdformat`, and `prettier`. Run this before committing.
- `pixi run docs` -- build the documentation with `zensical` into `site/`.
- `pixi run docs-serve` -- serve the documentation locally with live reload.
- `pixi run prek-update` -- bump the hook `rev` pins in `.pre-commit-config.yaml` to
    their latest versions. Run automatically, alongside `pixi update` for
    `pixi.lock`, by the weekly `update-lockfiles` GitHub Action.

An agent should run `pixi run lint` and `pixi run test` before considering a change
complete, and `pixi run format` if it touched code, TOML, YAML, or Markdown files.

There's no `pixi run build` task -- this package is never published to PyPI or
conda-forge, so there's no sdist/wheel to build.

<!--
If we add pixi tasks specific to this project (e.g. running a pipeline stage,
regenerating fixtures, applying migrations), list them here with a one-line
description of what each one does and when to use it.
-->

## Code style

- Formatting and most style rules are enforced by `ruff` (see `[tool.ruff]` in
    `pyproject.toml`) and applied automatically by `pixi run format` / the `ruff` and
    `ruff-format` pre-commit hooks. Don't hand-format code to match a personal
    preference that conflicts with what `ruff format` produces.
- Type checking is done with `pyrefly` (see `[tool.pyrefly]`). New code should be
    typed; if you must suppress a false positive, use a `# pyrefly: ignore[rule-name]`
    comment with a short note explaining *why* it's a false positive, not just that it
    is one.
- Docstrings use the Google convention (`[tool.ruff.lint.pydocstyle]`).
- Runtime and development dependencies are tracked in exactly one place: as conda
    packages under `[tool.pixi.dependencies]`, preferred over PyPI wherever a
    conda-forge build exists. Only fall back to `[tool.pixi.pypi-dependencies]` for
    packages that aren't published to conda-forge or bioconda (e.g. `mdformat-mkdocs`).
    Don't add a dependency under `[project.dependencies]` -- that list is intentionally
    left empty since this package is never installed outside the pixi environment.

<!--
Add anything specific to this codebase that a generic Python style guide wouldn't
tell an agent: preferred patterns, things to avoid (e.g. "don't add new dependencies
without asking"), naming conventions for a particular subsystem, or links to ADRs /
design docs that explain *why* the codebase looks the way it does.
-->

## Testing instructions

- Tests live under `tests/`, split into `tests/unit/` (fast, no external
    dependencies) and `tests/integration/` (may exercise CLI entry points, notebooks,
    or other slower paths).
- Run the full suite with `pixi run test`. To iterate quickly on a single test file
    or `-k` expression while debugging, `pixi run pytest <args>` works too, but always
    confirm with the full `pixi run test` before calling something done -- it also
    reports whether combined coverage still clears the `fail_under = 90` threshold set
    in `[tool.coverage.report]`.
- New behavior needs a test. Bug fixes should add a regression test that fails
    without the fix.
- Pytest also runs as a local pre-commit hook, so failing tests are caught before a
    commit is made, not just in CI. That hook is skipped by pre-commit.ci (it doesn't
    have the pixi environment available), so it's separately enforced by the `pytest`
    GitHub Actions workflow instead.

<!--
Once real pipeline code lands, note here whether its integration tests need
credentials, network access, a running service, or other setup an agent might not
have, and say whether the agent should skip them, mock them, or ask a human to run
them.
-->

## Documentation

- Documentation source lives under `docs/` as Markdown, built with
    [Zensical](https://zensical.org/) (configured in `zensical.toml`) and published to
    GitHub Pages at the default `https://community-nems.github.io/cnems-inputs` URL
    (Community-NEMS doesn't have its own domain yet).
- API reference docs are generated from docstrings via `mkdocstrings` -- add a new
    `::: module.path` line to `docs/reference.md` for any new module that should appear
    in the API reference; it is not automatic.
- Write prose using semantic linefeeds (one sentence, or one independent clause, per
    line) rather than hard-wrapping at a fixed column. This keeps diffs to the
    sentence that actually changed instead of reflowing the whole paragraph.
    `mdformat` won't fight this -- its default `wrap: keep` behavior preserves
    whatever line breaks are already there rather than rejoining and rewrapping
    paragraphs -- but nothing enforces it automatically either, so it's on you (or
    the agent) to actually break lines this way when writing new prose.

<!--
This repo doesn't have a versioned release process yet -- no git tags, no release
workflow -- so `docs/release_notes.md` currently only contains the reusable
`## X.Y.Z (YYYY-MM-DD)` template section, with nothing real recorded below it. Once
we start tagging releases, document the convention here: e.g. never write real
content into that template section itself, add changes to the first real numbered
section below it instead (creating it by copying the template if it doesn't exist),
use `pymdownx.magiclink` shorthand for PR/issue references (`!123`/`#123`), and check
`git tag --sort=-v:refname | head -1` before assuming what the next version number
should be.
-->

## Commit / PR instructions

- Before committing, run `pixi run format`, `pixi run lint`, and `pixi run test`; CI
    (`.github/workflows/pytest.yml`, `.github/workflows/docs.yml`) runs the same
    checks and will fail the PR otherwise.

<!--
Describe the expected commit message format (e.g. Conventional Commits), whether PRs
need a particular template filled out (there's already
`.github/pull_request_template.md` -- link any additional expectations here), what CI
needs to pass before merge, and who needs to review changes to sensitive areas of the
code.
-->

## Security & data handling

<!--
Call out anything an agent should never do without asking: touching production
credentials or infrastructure, modifying published data outputs, changing anything
under a compliance-sensitive directory, adding a new external dependency or service
integration, etc. This is a data pipeline repo, so it's worth being specific about
what data sources are public vs. restricted once that distinction exists.
-->

\[Nothing project-specific has been decided yet -- fill this in as data sources and
handling requirements are established.\]

## Gotchas

<!--
The stuff that isn't obvious from reading the code: known footguns, parts of the
codebase that are mid-refactor, dependencies that are pinned for a non-obvious
reason, CI flakiness, or "we tried X and it didn't work because Y." This is the
section most worth keeping honest and up to date -- it's where agents save the most
time by not re-discovering a problem someone already solved.
-->

- [Add project-specific gotchas as you discover things worth remembering.]
