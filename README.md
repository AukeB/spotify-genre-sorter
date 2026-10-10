# Template repository

This is a template repository that can be used for starting other repositories.

## Validation stack

This template comes with a fully configured validation stack covering static analysis, testing, runtime data validation, and git hook automation.

| Tool | Description |
|---|---|
| **Ruff** | Handles formatting, linting, import sorting, and annotation coverage enforcement in a single tool, replacing Black, Flake8, and isort. |
| **Docstring-tailor** | Handles formatting (line wrapping) for docstrings. |
| **ty** | Static type checker that verifies types flow correctly through the codebase, replacing Mypy. |
| **pytest** | Runs the test suite with branch-level coverage measurement via pytest-cov. |
| **Pydantic** | Enforces the shape and type of data at runtime boundaries. |

## Makefile

The Makefile orchestrates the validation stack with the following commands, all
run via `uv` for consistent environment management:

| Command | Description |
|---|---|
| `make ruff` | Runs Ruff linting with auto-fix, then formats the codebase. |
| `make format-docstrings` | Applies `docstring-tailor` to all python modules |
| `make ty` | Runs ty for static type checking. |
| `make pytest` | Runs the full test suite with verbose output and branch coverage. |
| `make clean` | Removes caches and temporary files (`__pycache__`, `.ruff_cache`, `.ty_cache`, `.pytest_cache`, `.coverage`, `artifacts`). |
| `make git` | Stages all changes, commits with the default message `"Updated"`, and pushes to remote. |
| `make all` | Runs the full workflow: `ruff` → `docstring-tailor` → `ty` → `pytest` → `clean` → `git`. |

## Branches

This repository is structured as one template per branch, so you can start a new project from whichever base fits it best.

| Branch | Use case |
|---|---|
| `main` | Base template for 'normal' Python projects. |
| `pygame_projects` | For general Python projects that will work with pygame. |
| `pygame_grid_projects` | For Python projects that visualize grids (2D lists) with pygame. |

To use a branch as the starting point for a new repository, switch to it on GitHub, then click **"Use this template" → "Create a new repository"** — this generates a new repo from that branch's snapshot.

## Possible additions

| Tool | Description |
|---|---|
| **prek** | Rust-based replacement for `pre-commit` that runs hooks in parallel before every commit, significantly faster than `pre-commit`. Would apply `ruff` and `ty` (and eventually `docstring-tailor`, once it supports pre-commit hooks) automatically before each commit. Not currently adopted — feels like more process than needed for personal hobby projects. |