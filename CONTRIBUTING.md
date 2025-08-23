# Contributing

Thanks for your interest in improving this project.

## Environment

Container workflow is preferred:

```powershell
docker compose build
docker compose run --rm ingest   # one‑shot data + geo load
docker compose up -d taxprotest-dev
```

Local (non‑Docker) development works too; see `README.md` for venv notes.

## Tooling

- Lint: Ruff (+ Black for formatting confirmation)
- Types: mypy (strict)
- Tests: pytest (unit + integration)

Install dev deps:

```powershell
pip install -r requirements.txt
pip install .[dev]
pre-commit install
```

## Common Tasks

```powershell
make lint
make type
make test
```

## Pull Requests

1. Branch from `master`.
2. Keep changes focused.
3. Ensure CI (matrix) passes: lint, type, tests, ingestion (Postgres).
4. Update docs / README for behavior or setup changes.

## Large / Generated Data

Do not commit raw downloads, local SQLite databases, or large export artifacts. These are reproducible via the ingestion scripts.

## Commit Style

Use short imperative subject lines:

```text
feat: add spatial fallback for distance queries
fix: correct COPY fallback when stream ends early
docs: clarify profiling flag usage
```

## Code Style

- Keep ingestion hot paths allocation‑light.
- Avoid ORMs inside COPY / bulk load segments.
- Encapsulate feature additions behind environment flags where reasonable.

## Testing Notes

Prefer small focused unit tests; reserve integration tests for end‑to‑end pipeline or web stack.

---
Questions or ideas? Open an issue or start a discussion.
