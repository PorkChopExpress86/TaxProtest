from __future__ import annotations

import os
from . import create_app


def main() -> None:  # pragma: no cover - manual entry
    app = create_app()
    host = os.getenv("TAXPROTEST_HOST", "127.0.0.1")
    port = int(os.getenv("TAXPROTEST_PORT", "5000"))
    debug = os.getenv("TAXPROTEST_DEBUG", "0").lower() in {"1", "true", "yes"}
    # Disable the reloader to avoid VS Code task / module-run detaching behavior on Windows
    print(f"Starting TaxProtest app on http://{host}:{port} (debug={debug})")
    app.run(host=host, port=port, debug=debug, use_reloader=False)


if __name__ == "__main__":  # pragma: no cover
    main()
