from __future__ import annotations

from flask import Flask
from pathlib import Path

from taxprotest.config.settings import get_settings
from taxprotest.comparables.engine import set_db_path
from .routes import bp as main_bp, register_template_filters
from taxprotest.logging_config import configure_logging


def create_app() -> Flask:
    settings = get_settings()
    configure_logging()

    # Determine project root (repo root) and explicitly set template/static folders.
    # Default Flask behavior would look for 'templates' relative to this package
    # (src/taxprotest/app/templates) but the project keeps them at repo root.
    try:
        project_root = Path(__file__).resolve().parents[3]  # .../TaxProtest
    except IndexError:  # Fallback – unexpected layout
        project_root = Path(__file__).resolve().parent
    templates_dir = project_root / "templates"
    static_dir = project_root / "static"

    app = Flask(
        __name__,
        template_folder=str(templates_dir) if templates_dir.exists() else None,
        static_folder=str(static_dir) if static_dir.exists() else None,
    )
    app.config["SECRET_KEY"] = settings.SECRET_KEY
    # Configure comparables engine database path
    set_db_path(str(settings.DATABASE_PATH))

    app.register_blueprint(main_bp)
    register_template_filters(app)
    return app
