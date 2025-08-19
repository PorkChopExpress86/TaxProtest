## Production Dockerfile for TaxProtest
# Multi-stage build keeps runtime image slim.
# Build with (from repo root):
#   docker build -t taxprotest:latest .
# Run (mount a host folder for persistent sqlite DB & exports):
#   docker run -d -p 8000:8000 \
#      -e TAXPROTEST_SECRET_KEY=change-me \
#      -v $(pwd)/data:/app/data \
#      -v $(pwd)/Exports:/app/Exports \
#      --name taxprotest taxprotest:latest

ARG PYTHON_VERSION=3.13-slim
FROM python:${PYTHON_VERSION} AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8

WORKDIR /app

# System packages + optional spatial libs (proj, geos, gdal minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libgeos-c1v5 \
        libproj-dev \
        gdal-bin \
    && rm -rf /var/lib/apt/lists/*

# Copy project metadata only first (maximize layer cache for deps)
COPY pyproject.toml README.md ./
COPY requirements.txt ./

# Install third-party dependencies (core + optional geo if present)
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    if [ -f requirements-geo.txt ]; then pip install -r requirements-geo.txt; fi

# Copy application source and assets
COPY src ./src
COPY templates ./templates
COPY static ./static
COPY setup_complete.py step1_download.py step2_extract.py step3_import.py ./

# Install the project package (no dependency re-resolution)
RUN pip install --no-deps .

# Create unprivileged user
RUN useradd -u 1001 -m appuser
USER appuser

EXPOSE 8000

ENV TAXPROTEST_HOST=0.0.0.0 \
    TAXPROTEST_PORT=8000 \
    TAXPROTEST_DEBUG=0

CMD ["gunicorn", "-w", "3", "-k", "gthread", "-b", "0.0.0.0:8000", "taxprotest.wsgi:app"]
