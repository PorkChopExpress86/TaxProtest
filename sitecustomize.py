"""Test-time path bootstrap so the src layout works without editable install.
Automatically imported by Python if present on sys.path root.
"""
import os, sys
ROOT = os.path.abspath(os.path.dirname(__file__))
SRC = os.path.join(ROOT, 'src')
if os.path.isdir(SRC) and SRC not in sys.path:
    sys.path.insert(0, SRC)
