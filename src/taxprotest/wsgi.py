"""WSGI entrypoint for production servers (Gunicorn, uWSGI, etc.).

Exposes ``app`` so a server can import ``taxprotest.wsgi:app``.
"""
from __future__ import annotations

from .app import create_app

app = create_app()


@app.route("/health")  # pragma: no cover - trivial
def _health():
    return {"status": "ok"}
