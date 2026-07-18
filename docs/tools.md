# Development Tooling

This repo is being set up incrementally, one piece of tooling at a time, so each part
can be reviewed on its own. Here's what's here so far and how it works.

## Python Package Skeleton

- The `src/cnems_inputs` directory contains the code that will be imported as the
    `cnems_inputs` package. Using a separate `src` directory helps avoid accidentally
    importing the package when you're working in the top level directory of the
    repository.
- This package is never published to PyPI or conda-forge -- it's only ever installed
    locally, in editable mode, inside the pixi environment defined in `pyproject.toml`.
- We use [hatch-vcs](https://github.com/ofek/hatch-vcs) (configured under
    `[tool.hatch.version]`) to obtain the package's version directly from `git` tags,
    rather than storing it in the repository and manually updating it.
- `src/cnems_inputs/dummy.py` and `cli.py` are placeholder examples: a trivial
    function, and a minimal argparse-based CLI wrapping it, registered as the `dummy`
    console script under `[project.scripts]`. They exist to give the test suite (and
    future real entry points) something to model.

## Environment & Task Management with Pixi

- We use [pixi](https://pixi.sh) to manage the development environment and the tasks
    used to test, lint, format, and document the project.
- Run `pixi install` once to create the environment described in `pyproject.toml`
    (under `[tool.pixi.*]`), then use `pixi run <task>` to run any of the tasks defined
    under `[tool.pixi.tasks]`.
- The most important tasks so far are:
    - `pixi run test` -- run the unit and integration tests with `pytest` and report
        combined test coverage.
    - `pixi run lint` -- run `ruff` and `pyrefly` to catch errors and style issues.
    - `pixi run format` -- automatically reformat the code and other files using
        `ruff`, `taplo`, `mdformat`, and `prettier`.
    - `pixi run docs` -- build the documentation with `zensical`.
- There's a single `default` pixi environment that contains everything needed for
    local development.
- Runtime dependencies (`pandas`, `pyarrow`, `duckdb`, etc.) and development tools
    (`ruff`, `pyrefly`, `prek`, `pytest`, `zensical`, and the rest of the tools
    described below) are installed as conda packages under `[tool.pixi.dependencies]`
    wherever they're available on conda-forge, rather than via PyPI. That keeps every
    dependency tracked in exactly one place, and lets us prefer conda-forge builds,
    which tend to be better-optimized for the scientific Python stack we're using
    here. The handful of tools not published to conda-forge (currently just
    `mdformat-mkdocs`) are installed from PyPI instead, via
    `[tool.pixi.pypi-dependencies]`.

## Pytest Testing Framework

- A skeleton [pytest](https://docs.pytest.org/) testing setup is included in the
    `tests/` directory.
- Tests are split into `unit` and `integration` categories.
- Session-wide test fixtures, additional command line options, and other pytest
    configuration can be added to `tests/conftest.py`.
- Exactly what pytest commands are run during continuous integration is controlled by
    the pixi tasks defined in `pyproject.toml`, and run there via
    `.github/workflows/pytest.yml`.
- Pytest can also be run manually without going through the pixi task, but still in
    the pixi environment by prefixing the command with `pixi run`. For example
    `pixi run pytest --no-cov tests/unit`. Running pytest on its own is a good way to
    debug a specific new or failing test quickly, but we should always use
    `pixi run test` for actual testing.
- Pytest also runs as a local pre-commit hook (see below), so failing tests are caught
    before a commit is made, not just in CI.

## Git Pre-commit Hooks

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
    to the PR in case it hasn't been run locally prior to being committed. The local
    `pytest` hook is skipped by pre-commit.ci (it doesn't have the pixi environment
    available), so it's separately enforced by the `pytest` GitHub Actions workflow
    instead.
- Run `pixi run prek-update` to bump the hook `rev` pins in `.pre-commit-config.yaml`
    to their latest versions. The `update-lockfiles` GitHub Action
    (`.github/workflows/update-lockfiles.yml`) runs this (along with `pixi update` for
    `pixi.lock`) weekly and opens a PR with the changes.

## Code Formatting & Linting

To avoid the tedium of meticulously formatting all the code ourselves, and to ensure a
standard style of formatting and syntactical idioms across the codebase, we use the
`ruff` code linter and formatter, which runs both as a pre-commit hook and via
`pixi run format` / `pixi run lint`. These can be integrated directly into your text
editor or IDE with the appropriate plugins. The `ruff` linter / formatter has a huge
array of configuration options and different kinds of checks it can run, which are
defined under the `tool.ruff` section of `pyproject.toml`.

## Type Checking

We use [pyrefly](https://pyrefly.org/), a fast Rust-based type checker. It's
configured under the `tool.pyrefly` section of `pyproject.toml` and run via
`pixi run lint`. It also runs as a pre-commit hook, and unlike `pytest`, that hook
*is* run by pre-commit.ci, so type errors are caught there too.

## Code & Documentation Linters

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
    including the documentation under `docs/` and the issue and PR templates under
    `.github/`. The `mdformat-mkdocs` plugin keeps `mdformat` from mangling
    Zensical/MkDocs-flavored syntax, like `docs/index.md`'s snippet-include line, and
    `mdformat-frontmatter` keeps it from mangling the YAML front matter the issue/PR
    templates use.

## Test Coverage

- We use the pytest `coverage` plugin to measure and record what percentage of our
    codebase is being tested, and to identify which modules, functions, and individual
    lines of code are not being exercised by the tests.
- When you run `pixi run test`, a summary of the test coverage will be printed at the
    end of the tests (assuming they succeed). The full details of the test coverage are
    written to `coverage.xml`.
- There are some configuration options for this process set in the
    `tool.coverage.report` section of `pyproject.toml`, including a `fail_under = 90`
    threshold: `pixi run test` fails if combined coverage drops below 90%.
- When the tests are run via the `pytest` workflow in GitHub Actions, the test coverage
    data from the `coverage.xml` output is uploaded to a service called
    [CodeCov](https://about.codecov.io/) that saves historical data about our test
    coverage, and provides a nice visual representation of the data -- identifying
    which subpackages, modules, and individual lines are being tested.
- The connection to CodeCov is configured in the `.codecov.yml` YAML file. Uploads
    authenticate with the `Community-NEMS` org's shared "Global Upload Token," stored
    as an organization-level `CODECOV_TOKEN` secret in GitHub, so individual repos
    don't need their own CodeCov token minted and stored separately.
- CodeCov also adds a couple of test coverage checks to any pull request, to alert us
    if a PR reduces overall test coverage (which we would like to avoid).

## Documentation Builds

- We build our documentation using [Zensical](https://zensical.org/), a modern
    Markdown-based static site generator from the Material for MkDocs team.
- Standalone docs files are stored under the `docs/` directory as Markdown, and the
    Zensical configuration lives in `zensical.toml` at the top of the repository.
- The top level documentation page (`docs/index.md`) simply embeds this `README.md`
    verbatim using Zensical's `pymdownx.snippets` syntax (`--8<-- "README.md"`);
    `docs/license.md` embeds `LICENSE` the same way. `docs/release_notes.md` is a
    standalone Markdown file.
- `docs/reference.md` holds the API reference, rendered from docstrings by
    [mkdocstrings](https://mkdocstrings.github.io/) (configured under
    `[project.plugins.mkdocstrings...]` in `zensical.toml`, currently a preliminary
    Zensical integration). Add a `::: module.path` line there for any new module that
    should show up in the API reference -- it isn't generated automatically.
- Build the docs with `pixi run docs`, which wipes the previously generated `site/`
    directory and rebuilds everything from scratch, or preview them locally with
    `pixi run docs-serve`.
- There's no custom branding (logo, favicon, social links) configured yet -- the site
    uses Zensical's defaults until Community-NEMS has its own to add.

## Documentation Publishing

- We publish our documentation to [GitHub Pages](https://pages.github.com/), at the
    default `https://community-nems.github.io/cnems-inputs` URL. Community-NEMS
    doesn't have an organizational domain to publish under yet, so there's no custom
    domain configured here.
- When you push to `main` the `docs` GitHub Actions workflow builds the site with
    Zensical and deploys it automatically.
- For this to work, the repo's Settings -> Pages -> "Build and deployment" source must
    be set to "GitHub Actions."

## Dependabot

We use GitHub's
[Dependabot](https://docs.github.com/en/code-security/dependabot/dependabot-version-updates)
to automatically update the versions of the
[GitHub Actions](https://docs.github.com/en/actions) that we employ, configured in
`.github/dependabot.yml`. Our Python dependencies are refreshed separately, by the
weekly `update-lockfiles` GitHub Action described below, instead of by Dependabot.

## GitHub Actions

Under `.github/workflows` are YAML files that configure the
[GitHub Actions](https://docs.github.com/en/actions) associated with the repository.
We use GitHub Actions to:

- Run continuous integration with `pixi run test` and upload test coverage to
    CodeCov (`pytest.yml`).
- Build the documentation with Zensical and deploy it to GitHub Pages (`docs.yml`).
- Refresh `pixi.lock` and the `rev` pins in `.pre-commit-config.yaml` weekly, opening
    a PR with the changes so CI can confirm the updated dependencies still work
    (`update-lockfiles.yml`).
