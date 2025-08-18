"""Compatibility stub.

The Flask application has moved to the package module `taxprotest.app`.
Use one of:
    python -m taxprotest.app
    taxprotest-app  (installed console script)

This stub remains to avoid breaking existing workflows that import `app`.
"""
from taxprotest.app import create_app  # type: ignore

app = create_app()

if __name__ == "__main__":  # pragma: no cover
        app.run(host="0.0.0.0", port=5000, debug=True)
