#!/usr/bin/env python
"""Convenience runner ensuring src/ is on sys.path then launching the app."""
import sys, os

BASE = os.path.dirname(__file__)
SRC = os.path.join(BASE, 'src')
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from taxprotest.app import create_app  # noqa: E402


def _in_venv() -> bool:
    return (hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix))


if __name__ == "__main__":
    if not _in_venv():
        print("[WARN] It looks like the virtual environment is not active (sys.prefix == sys.base_prefix). Activate with: .\\.venv\\Scripts\\Activate.ps1")
    app = create_app()
    host = os.getenv("TAXPROTEST_HOST", "127.0.0.1")
    port = int(os.getenv("TAXPROTEST_PORT", "5000"))
    debug = os.getenv("TAXPROTEST_DEBUG", "1").lower() in {"1", "true", "yes", "y"}
    print(f"Running (debug={debug}) on http://{host}:{port}")
    # use_reloader follows debug so live template/code edits reload
    app.run(host=host, port=port, debug=debug, use_reloader=debug)
