PY=python

.PHONY: help install dev lint type test fmt ingest geo up down clean

help:
	@echo "Common targets:"; \
	echo "  make install     - install base requirements"; \
	echo "  make dev         - install dev (lint/test) deps"; \
	echo "  make lint        - run ruff + black --check"; \
	echo "  make fmt         - auto-fix style (ruff + black)"; \
	echo "  make type        - run mypy"; \
	echo "  make test        - run pytest"; \
	echo "  make ingest      - run full Postgres ingestion (TAXPROTEST_DATABASE_URL required)"; \
	echo "  make geo         - run geo loader only"; \
	echo "  make up          - docker compose up app + postgres"; \
	echo "  make down        - docker compose down"; \
	echo "  make clean       - remove caches & build artifacts";

install:
	$(PY) -m pip install -r requirements.txt

dev: install
	$(PY) -m pip install .[dev]

lint:
	ruff check .
	black --check .

fmt:
	ruff check --fix . || true
	black .

type:
	mypy src

test:
	pytest -q

ingest:
	$(PY) scripts/ingest_postgres.py

geo:
	$(PY) load_geo_data.py

up:
	docker compose up -d postgres taxprotest

down:
	docker compose down

clean:
	$(PY) - <<'PY'
import pathlib, shutil
for p in pathlib.Path('.').rglob('__pycache__'):
    shutil.rmtree(p, ignore_errors=True)
for ext in ('pyc','pyo'):
    for f in pathlib.Path('.').rglob(f'*.{ext}'):
        try: f.unlink()
        except: pass
for d in ['.pytest_cache','build','dist']:
    shutil.rmtree(d, ignore_errors=True)
for egg in pathlib.Path('.').glob('*.egg-info'):
    shutil.rmtree(egg, ignore_errors=True)
PY
