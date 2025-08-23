TaxProtest — Quick Start
=========================

Minimal instructions to get the project running locally using Docker Compose.

1) Place exported text files in `text_files/` (e.g. `real_acct.txt`, `owners.txt`, `building_res.txt`).
2) Start Postgres and run the importer:

```bash
docker compose up -d postgres
docker compose run --rm ingest
```

3) Start the web app after DB is populated:

```bash
docker compose up -d django
docker compose logs -f django
```

Notes:
- The GitHub Actions CI workflow was removed from `.github/workflows/`.
- Large data directories (downloads, extracted, Exports, data) are ignored by `.gitignore`.
- For full developer instructions, see `README.md`.

If you want this short README merged into the main `README.md` instead, I can do that.
