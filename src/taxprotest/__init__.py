"""taxprotest package root.

Lazy export of :func:`create_app` to avoid circular imports during early
module initialization (e.g. when ``extract_data`` imports comparables which
imports this package). Importing ``.app`` eagerly pulled in Flask route
modules that in turn imported ``extract_data`` before its symbols (like
``extract_excel_file``) were defined, resulting in ImportError during test
collection.

Downstream code can still ``from taxprotest import create_app``; the Flask
application factory is imported only when first accessed.
"""

__all__ = ["create_app"]

def create_app(*args, **kwargs):  # type: ignore[no-untyped-def]
	# Local import to avoid circular dependency during test collection
	from .app import create_app as _create_app  # noqa: WPS433
	return _create_app(*args, **kwargs)
