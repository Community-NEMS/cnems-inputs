# cnems-inputs

[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/Community-NEMS/cnems-inputs/main.svg)](https://results.pre-commit.ci/latest/github/Community-NEMS/cnems-inputs/main)
[![Pixi Badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/prefix-dev/pixi/main/assets/badge/v0.json)](https://pixi.sh)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Data pipelines that feed inputs into the Community NEMS project.

## Development tooling

This repo is being set up incrementally, one piece of tooling at a time, so each part
can be reviewed on its own. Here's what's here so far and how it works.

### Python Package Skeleton

- The `src/cnems_inputs` directory contains the code that will be imported as the
  `cnems_inputs` package. Using a separate `src` directory helps avoid accidentally
  importing the package when you're working in the top level directory of the
  repository.
- This package is never published to PyPI or conda-forge -- it's only ever installed
  locally, in editable mode, inside the pixi environment defined in `pyproject.toml`.
- We use [hatch-vcs](https://github.com/ofek/hatch-vcs) (configured under
  `[tool.hatch.version]`) to obtain the package's version directly from `git` tags,
  rather than storing it in the repository and manually updating it.

### Environment & Task Management with Pixi

- We use [pixi](https://pixi.sh) to manage the development environment and the tasks
  used to lint and format the project.
- Run `pixi install` once to create the environment described in `pyproject.toml`
  (under `[tool.pixi.*]`), then use `pixi run <task>` to run any of the tasks defined
  under `[tool.pixi.tasks]`.
- The most important tasks so far are:
  - `pixi run lint` -- run `ruff` and `pyrefly` to catch errors and style issues.
  - `pixi run format` -- automatically reformat the code and other files using
    `ruff`, `taplo`, `mdformat`, and `prettier`.
- There's a single `default` pixi environment that contains everything needed for
  local development.
- Runtime dependencies (`pandas`, `pyarrow`, `duckdb`, etc.) and development tools
  (`ruff`, `pyrefly`, `prek`, and the rest of the linters below) are all installed as
  conda packages under `[tool.pixi.dependencies]`, rather than via PyPI. That keeps
  every dependency tracked in exactly one place, and lets us prefer conda-forge
  builds, which tend to be better-optimized for the scientific Python stack we're
  using here.

### Git Pre-commit Hooks

- A variety of sanity checks are defined as git pre-commit hooks -- they run any time
  you try to make a commit, to catch common issues before they are saved. Many of
  these hooks are taken from the excellent [pre-commit project](https://pre-commit.com/).
- The hooks are configured in `.pre-commit-config.yaml`, and run using
  [prek](https://prek.j178.dev/), a much faster, dependency-free tool that reads that
  same standard config format.
- For them to run automatically when you try to make a commit, you **must** install
  the hooks in your cloned repository first by running `pixi run prek install`. This
  only has to be done once.
- We also use the [pre-commit.ci](https://pre-commit.ci) service to run the same
  checks on any code that is pushed to GitHub, and to apply standard code formatting
  to the PR in case it hasn't been run locally prior to being committed.
- Run `pixi run prek-update` to bump the hook `rev` pins in `.pre-commit-config.yaml`
  to their latest versions. The `update-lockfiles` GitHub Action
  (`.github/workflows/update-lockfiles.yml`) runs this (along with `pixi update` for
  `pixi.lock`) weekly and opens a PR with the changes.

### Code Formatting & Linting

To avoid the tedium of meticulously formatting all the code ourselves, and to ensure a
standard style of formatting and syntactical idioms across the codebase, we use the
`ruff` code linter and formatter, which runs both as a pre-commit hook and via
`pixi run format` / `pixi run lint`. These can be integrated directly into your text
editor or IDE with the appropriate plugins. The `ruff` linter / formatter has a huge
array of configuration options and different kinds of checks it can run, which are
defined under the `tool.ruff` section of `pyproject.toml`.

### Type Checking

We use [pyrefly](https://pyrefly.org/), a fast Rust-based type checker. It's
configured under the `tool.pyrefly` section of `pyproject.toml` and run via
`pixi run lint`.

### Code & Documentation Linters

To catch errors before commits are made, and to ensure uniform formatting across the
codebase, we also use linters outside of `ruff`. They don't change the code or
documentation files, but they will raise an error or warning when something doesn't
look right so you can fix it.

- `pre-commit` has a collection of built-in checks that
  [use pygrep to search Python files](https://github.com/pre-commit/pygrep-hooks) for
  common problems, as well as
  [language agnostic problems](https://github.com/pre-commit/pre-commit-hooks) like
  accidentally checking large binary files into the repository or having unresolved
  merge conflicts.
- [actionlint](https://github.com/rhysd/actionlint) checks the GitHub Actions workflow
  files for errors. It runs as a pre-commit hook.
- [shellcheck](https://github.com/shellcheck-py/shellcheck-py) checks shell scripts,
  including the embedded `run:` steps in our GitHub Actions workflows, for common
  bugs and portability issues. It runs as a pre-commit hook.
- [markdownlint](https://github.com/DavidAnson/markdownlint) and
  [mdformat](https://mdformat.readthedocs.io/) check and reformat Markdown files,
  including the issue and PR templates under `.github/`. The `mdformat-frontmatter`
  plugin keeps `mdformat` from mangling the YAML front matter those templates use.
