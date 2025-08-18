"""taxprotest package root.

Public exports kept minimal; web app entry via create_app.
"""

from .app import create_app  # re-export for convenience

__all__ = ["create_app"]
