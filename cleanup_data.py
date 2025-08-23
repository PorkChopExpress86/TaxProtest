"""Cleanup Utility: Remove downloaded & extracted parcel/tax data artifacts to reclaim disk space.

Usage examples (PowerShell):
  python cleanup_data.py                # interactive summary + prompt
  python cleanup_data.py --yes          # perform default cleanup without prompt
  python cleanup_data.py --dry-run      # show what WOULD be deleted
  python cleanup_data.py --all          # also remove hash JSON files & temp test dirs
  python cleanup_data.py --patterns Parcels_*.zip --dry-run  # simulate removal of matching files in downloads

Default targets (if present):
  downloads/        (ZIP archives)
  extracted/        (extracted production data)
  text_files/       (code description & txt extracts)
  extracted_test/   (test extraction output)
  downloads_test/   (test download zips)
  temp_gis_extract/ (temp GIS extractions)
  extracted_2024/   (year-specific extracted data)
  temp*/            (top-level temp directories starting with 'temp')

Safety:
 - Only deletes paths under the project base directory.
 - Skips SQLite database and source code by default.
 - Hash JSON files retained unless --all specified.

Return code 0 on success; non-zero if any deletion errors occurred.
"""
from __future__ import annotations
import argparse
import os
import sys
import shutil
from pathlib import Path
from typing import Iterable, List, Tuple

BASE_DIR = Path(os.path.abspath(os.path.dirname(__file__)))
DEFAULT_DIRS = [
    "downloads",
    "extracted",
    "text_files",
    "extracted_test",
    "downloads_test",
    "temp_gis_extract",
    "extracted_2024",
]
# Patterns (directories) to expand if they exist
GLOB_DIR_PATTERNS = [
    # NOTE: "temp*" previously matched the project's "templates" directory and
    # accidentally deleted all HTML templates (causing TemplateNotFound errors).
    # We now restrict the pattern to temp-related dirs only. If you create a
    # new temporary directory starting with "temp" that does NOT have an
    # underscore, add it explicitly below.
    "temp_*",          # e.g. temp_gis_extract, temp_cache, etc.
    "tempExtract*",    # example alternate naming pattern (future-proof)
]
HASH_FILES = [
    BASE_DIR / "data" / "download_hashes.json",
    BASE_DIR / "data" / "extraction_hashes.json",
    BASE_DIR / "data" / "import_hashes.json",
]

PROTECTED_NAMES = {"database.sqlite"}


def human_size(num: int) -> str:
    value: float = float(num)
    for unit in ["B","KB","MB","GB","TB"]:
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{value:.1f} TB"


def collect_targets(include_all: bool, extra_patterns: List[str]) -> Tuple[List[Path], List[Path]]:
    dirs: List[Path] = []
    files: List[Path] = []
    # Base directories
    for d in DEFAULT_DIRS:
        p = BASE_DIR / d
        if p.exists():
            dirs.append(p)
    # Glob expansions
    for pattern in GLOB_DIR_PATTERNS + extra_patterns:
        for p in BASE_DIR.glob(pattern):
            # Extra safeguard: never include the real templates folder
            if p.name == "templates":
                continue
            if p.is_dir() and p not in dirs:
                dirs.append(p)
    # Hash files (optional)
    if include_all:
        for h in HASH_FILES:
            if h.exists():
                files.append(h)
    return dirs, files


def safe_inside_base(path: Path) -> bool:
    try:
        path.resolve().relative_to(BASE_DIR.resolve())
        return True
    except ValueError:
        return False


def size_of_path(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    total = 0
    for root, dirs, filenames in os.walk(path):
        for name in filenames:
            try:
                fp = Path(root) / name
                total += fp.stat().st_size
            except OSError:
                pass
    return total


def delete_path(path: Path, dry_run: bool) -> Tuple[bool, str, int]:
    size = size_of_path(path)
    if not safe_inside_base(path):
        return False, f"Refusing to delete outside base: {path}", 0
    if path.is_file():
        if path.name in PROTECTED_NAMES:
            return False, f"Protected file skipped: {path.name}", 0
        if dry_run:
            return True, f"(dry-run) would remove file {path.name}", size
        try:
            path.unlink()
            return True, f"Removed file {path.name}", size
        except Exception as e:
            return False, f"Failed to remove file {path.name}: {e}", 0
    if path.is_dir():
        if dry_run:
            return True, f"(dry-run) would remove directory {path.name}", size
        try:
            shutil.rmtree(path)
            return True, f"Removed directory {path.name}", size
        except Exception as e:
            return False, f"Failed to remove directory {path.name}: {e}", 0
    return False, f"Unknown path type (skipped): {path}", 0


def main():
    parser = argparse.ArgumentParser(description="Cleanup downloaded & extracted tax data files.")
    parser.add_argument('--yes', action='store_true', help='Skip confirmation prompt')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be deleted without removing')
    parser.add_argument('--all', action='store_true', help='Also remove hash JSON files and test dirs/patterns')
    parser.add_argument('--patterns', nargs='*', default=[], help='Additional glob patterns (relative to project root) to delete')
    args = parser.parse_args()

    dirs, files = collect_targets(args.all, args.patterns)

    # If not --all strip test dirs from deletion unless explicitly matched
    if not args.all:
        dirs = [d for d in dirs if d.name not in {'extracted_test','downloads_test'}]

    total_bytes = sum(size_of_path(p) for p in dirs + files)

    print("🧹 Cleanup Plan")
    print("Base directory:", BASE_DIR)
    for d in dirs:
        print(f"  DIR  {d.relative_to(BASE_DIR)}  (size ~ {human_size(size_of_path(d))})")
    for f in files:
        print(f"  FILE {f.relative_to(BASE_DIR)} (size {human_size(f.stat().st_size)})")
    print(f"≈ Total space reclaimable: {human_size(total_bytes)}")

    if not dirs and not files:
        print("Nothing to delete.")
        return 0

    if not args.yes and not args.dry_run:
        reply = input("Proceed with deletion? [y/N]: ").strip().lower()
        if reply not in ('y','yes'):
            print("Aborted.")
            return 1

    any_error = False
    reclaimed = 0
    for p in dirs + files:
        ok, msg, freed = delete_path(p, args.dry_run)
        print(msg)
        if ok:
            reclaimed += freed
        else:
            any_error = True

    if args.dry_run:
        print("\nDry run complete. No changes made.")
    else:
        print(f"\nReclaimed approximately {human_size(reclaimed)} (reported sizes before deletion).")

    if any_error:
        print("Completed with some errors (see above).")
        return 2
    print("Done.")
    return 0

if __name__ == '__main__':
    sys.exit(main())
