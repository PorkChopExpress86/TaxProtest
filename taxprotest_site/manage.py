#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    # Use fully-qualified nested package path (outer project dir + inner project package)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "taxprotest_site.taxprotest_site.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError:
        raise
    execute_from_command_line(sys.argv)
