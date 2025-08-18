
# Copilot Instructions: Python (Clean Code, Python 3.13)

These are concise, high-signal instructions you can paste into **Copilot Custom Instructions**, a repo’s **README**, or **CONTRIBUTING.md** to steer Copilot toward production-quality Python **3.13** code.

---

## Project Defaults
- Target **Python 3.13** (use `python_requires=">=3.13"` in packaging).
- **Type hints everywhere.** Prefer precise types (`TypedDict`, `Protocol`, `Literal`, `Annotated`, `NewType`). No implicit `Any` in public APIs.
- Tooling: **Black** (line length 88), **Ruff** (lint + autofix), **Mypy** (`--strict` where practical), **Pytest**. Use **Pydantic v2** when schema validation is needed.
- Logging: use the `logging` module; avoid `print` in libraries/CLIs except for explicit stdout UX.
- Errors: raise specific exceptions; never swallow exceptions silently.

## Architecture & Structure
- Write **small, single-responsibility, side-effect-light functions** (≤ ~40 lines is a good heuristic).
- Organize by domain and boundary:
  - `domain/` (pure logic, dataclasses/models)
  - `adapters/` (IO: db, http, files, external services)
  - `services/` (application use-cases orchestrating domain + adapters)
  - `cli/` (commands via `typer` or `argparse`)
- Hide implementation details behind clear, typed interfaces (classes or `Protocol`).
- Use `@dataclass(slots=True, frozen=True)` or Pydantic models at boundaries (IO/DB/API).

## Function/Module Template
Use this as a starting point for new modules and functions.

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Sequence, Protocol

class DataSource(Protocol):
    def fetch_rows(self) -> Iterable[dict]: ...

@dataclass(slots=True, frozen=True)
class Record:
    id: int
    name: str
    value: float

def parse_row(row: dict) -> Record:
    """
    Convert a raw mapping into a validated Record.

    Args:
        row: Mapping with keys 'id', 'name', 'value'.

    Returns:
        A validated Record.

    Raises:
        KeyError: Missing required keys.
        ValueError: Invalid types or ranges.
    """
    id_ = int(row["id"])
    name = str(row["name"]).strip()
    value = float(row["value"])
    if value < 0:
        raise ValueError("value must be non-negative")
    return Record(id=id_, name=name, value=value)

def compute_metric(records: Sequence[Record]) -> float:
    """
    Compute a stable metric from records.

    Pre-conditions:
        - records may be empty; return 0.0 in that case.

    Post-conditions:
        - Result is finite and >= 0.
    """
    if not records:
        return 0.0
    total = sum(r.value for r in records)
    avg = total / len(records)
    assert avg >= 0.0
    return avg
```

## Docstrings & Comments
- Use **Google** or **NumPy** style docstrings consistently.
- Document **purpose, args, returns, raises, invariants**, and edge cases.
- Comments explain **why**, not **what**. Avoid redundant narration of code.

## Error Handling
- Catch only what you can handle; re-raise with context:
  ```python
  try:
      do_work()
  except SomeLibError as e:
      raise RuntimeError("Failed to process batch") from e
  ```
- Validate inputs early; fail fast with clear messages.

## Logging
- Module-level logger: `logger = logging.getLogger(__name__)`.
- Levels: `debug` (flow & sizes), `info` (milestones), `warning` (recoverable), `error` (failed operation with context).
- Never log secrets, tokens, or PII.

## IO Boundaries
- Keep **pure logic** separate from **IO** (files/DB/HTTP). Pure functions are easier to test.
- Prefer `pathlib` for files, context managers for resources.
- For HTTP, prefer `httpx` with **timeouts**, **retries**, and **circuit-breaker/backoff** at the adapter layer.

## Data & pandas (if used)
- Validate columns/dtypes at boundaries; keep core logic typed.
- Prefer vectorized ops; avoid `.apply` in hot paths.
- Consider `pyarrow` dtypes for large tables or `polars` for performance-critical workloads.

## CLI & Configuration
- Use `typer` (or `argparse`) for CLIs. Provide `--help` with examples.
- Configuration via env vars (e.g., `pydantic-settings`) or a `settings.toml`. No hard-coded paths.
- Make side effects explicit; prefer dependency injection (pass adapters/clients into services).

## Dependencies & Packaging
- Be dependency-light; prefer stdlib.
- Layout:
  ```
  pyproject.toml
  README.md
  CONTRIBUTING.md
  src/
    package_name/
      __init__.py
      domain/
      services/
      adapters/
      cli/
  tests/
  ```
- Keep `__init__.py` exports minimal and stable.
- Set `python_requires = ">=3.13"` and enable type info with `py.typed` if you export typed APIs.

## Testing (Pytest)
- For each public function:
  - **Happy path** test
  - **Edge case** test (empty input, extremes, None)
  - **Failure** test (invalid inputs)
- Use fixtures for IO boundaries; use **fakes** or lightweight test doubles over heavy mocks.
- Property-based tests with `hypothesis` for critical pure functions.
- Keep tests fast and deterministic; no network or real disk by default.

**Example tests**:
```python
import pytest
from package_name.domain import parse_row, compute_metric, Record

def test_parse_row_ok():
    r = parse_row({"id": "1", "name": " A ", "value": "3.5"})
    assert r == Record(id=1, name="A", value=3.5)

@pytest.mark.parametrize("row", [
    {"id": "1", "name": "x"},                   # missing value
    {"id": "not-int", "name": "x", "value": 1}, # bad id
    {"id": "1", "name": "x", "value": -1},      # invalid value
])
def test_parse_row_bad(row):
    with pytest.raises((KeyError, ValueError)):
        parse_row(row)

def test_compute_metric_empty():
    assert compute_metric([]) == 0.0
```

## Performance & Scalability
- Favor **O(n)** one-pass transforms; avoid nested loops over big inputs.
- Stream where possible (generators/iterators) to reduce memory.
- Profile before optimizing (`cProfile`, `py-spy`, `line_profiler`).

## Security & Robustness
- Never `eval`/`exec` untrusted input.
- Validate/normalize file paths; allowlist extensions and directories.
- Timeouts and retries on all external calls; exponential backoff with jitter.
- Consider `secrets` module for tokens and `hashlib`/`hmac` for signing.

## Code Review Checklist (for Copilot output)
1. **Types**: all public functions fully typed; avoid `Any` leaks.
2. **Names**: descriptive, consistent, unambiguous.
3. **Simplicity**: small functions; DRY; avoid cleverness.
4. **Tests**: happy/edge/failure; fast; deterministic.
5. **Docs**: docstrings; README updates if needed.
6. **Lint/Format/Types**: `ruff --fix .`, `black .`, `mypy --strict`.
7. **Logging & Errors**: helpful, contextual, no secrets.

## Ready-to-Use `pyproject.toml` (Drop-In)
```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "package-name"
version = "0.1.0"
description = "Your package description"
readme = "README.md"
requires-python = ">=3.13"
license = { text = "MIT" }
authors = [{ name = "Your Name" }]
dependencies = []

[tool.black]
line-length = 88
target-version = ["py313"]

[tool.ruff]
line-length = 88
target-version = "py313"
fix = true
select = ["E","F","I","UP","B","C4","SIM","PL"]
ignore = ["D"]  # enable pydocstyle later if desired

[tool.mypy]
python_version = "3.13"
disallow_untyped_defs = true
disallow_any_generics = true
no_implicit_optional = true
warn_return_any = true
warn_unused_ignores = true
warn_redundant_casts = true
strict_optional = true
show_error_codes = true
pretty = true

[tool.pytest.ini_options]
addopts = "-q"
testpaths = ["tests"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools]
package-dir = {"" = "src"}
```

## Minimal Repo Scaffolding
```
pyproject.toml
README.md
CONTRIBUTING.md
src/
  package_name/
    __init__.py
    domain/
    services/
    adapters/
    cli/
tests/
```

---

### How Copilot Should Use This
- Prefer stdlib and simple designs.
- Default to typed, small functions and clear boundaries.
- Always add or update tests alongside new code.
- Run `ruff --fix`, `black`, and `mypy` locally and in CI.

---

*Paste this file as `CONTRIBUTING.md` or `copilot-python-clean-code.md` in your repo.*
