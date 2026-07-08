# Baseline environment

Date: 2026-07-01

## Repository

- Workspace: `C:\Users\usuario\Documents\GitHub\MotorVideojuegosIA`
- Remote: `origin` -> `https://github.com/Yisuescopeta/OpenGame.git`
- Detected remote main branch: `origin/main`
- Base commit: `b18fb1894552ef50ea3966a88276051054286585`
- Work branch: `codex/queen-safe-continuation`
- `origin/main` after `git fetch --all --prune`: `b18fb1894552ef50ea3966a88276051054286585`

## Python

- `python --version`: failed on Windows Store alias.
- `py --version`: `Python 3.11.1`
- Effective command prefix for this environment: `py -m ...`

## Dependency files found

- `pyproject.toml`
- `requirements.txt`

`pyproject.toml` is the primary project metadata source. It declares package name `opengame`, Python `>=3.11`, runtime dependency `raylib-py>=5.0.0.0`, and dev extras for `ruff`, `mypy`, `bandit`, `pip-audit`, `Pillow`, and related tooling. `requirements.txt` only lists `raylib-py>=5.0.0.0`.

## Notes

- No Rust/PyO3 dependency was introduced.
- No new runtime dependency was introduced.

## Runtime input/picking phase update - 2026-07-02

- Work branch: `codex/runtime-input-picking`.
- Base commit: `b18fb1894552ef50ea3966a88276051054286585`.
- Remote main detected again with `git remote show origin`, `git fetch --all --prune`, and `git branch -r --sort=-committerdate`: `origin/main`.
- Dependency files remain `pyproject.toml` and `requirements.txt`; no new dependency system was introduced.
- Effective Python command remains `py -3 -m ...`.
- No Rust/PyO3 change was introduced.
- No new runtime dependency was introduced.
