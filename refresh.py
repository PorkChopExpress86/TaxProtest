"""Orchestrator: Smart refresh pipeline.

Quick-win orchestration logic:
 1. Run step1 (download) -> parse summary (changed flag)
 2. If downloads changed: run step2 (extract)
 3. If extraction produced new archives: run step3 (import)

Exit codes:
  0 = nothing changed (all skipped)
 10 = downloads changed only
 20 = extraction run (archives extracted) but import skipped (no key file change / hashes up to date)
 30 = import completed / database updated

The script relies on JSON summary emitted by modified step1 and derives extraction/import status from stdout heuristics.
For robustness, we also create a JSON summary at data/last_refresh_report.json.
"""
from __future__ import annotations
import subprocess, sys, json, re, pathlib, time
from datetime import datetime

BASE_DIR = pathlib.Path(__file__).parent
DATA_DIR = BASE_DIR / 'data'
REPORT_PATH = DATA_DIR / 'last_refresh_report.json'
STEP1_REPORT = DATA_DIR / 'last_download_report.json'
STEP2_REPORT = DATA_DIR / 'last_extraction_report.json'
STEP3_REPORT = DATA_DIR / 'last_import_report.json'


def run_step(cmd: list[str]) -> tuple[int,str]:
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return proc.returncode, proc.stdout


def run_refresh():
    DATA_DIR.mkdir(exist_ok=True)
    overall = {
        'timestamp_utc': datetime.utcnow().isoformat() + 'Z',
        'download_changed': False,
        'extraction_changed': False,
        'import_changed': False,
        'exit_code': 0,
    }

    # Step 1
    print('== Step 1: Download ==')
    rc1, out1 = run_step([sys.executable, 'step1_download.py'])
    print(out1)
    if STEP1_REPORT.exists():
        try:
            d = json.loads(STEP1_REPORT.read_text())
            overall['download_changed'] = bool(d.get('changed'))
        except Exception:
            pass

    # Step 2 (only if downloads changed)
    if overall['download_changed']:
        print('\n== Step 2: Extract ==')
        rc2, out2 = run_step([sys.executable, 'step2_extract.py'])
        print(out2)
        if STEP2_REPORT.exists():
            try:
                e = json.loads(STEP2_REPORT.read_text())
                overall['extraction_changed'] = bool(e.get('changed'))
            except Exception:
                pass
    else:
        print('Skip extraction (no new downloads)')

    # Heuristic: if extraction skipped but parcels.csv missing previously, we might still need import
    # We'll check key DB file presence & continue only if changed

    # Step 3 (only if extraction changed)
    if overall['extraction_changed']:
        print('\n== Step 3: Import ==')
        rc3, out3 = run_step([sys.executable, 'step3_import.py'])
        print(out3)
        if STEP3_REPORT.exists():
            try:
                i = json.loads(STEP3_REPORT.read_text())
                overall['import_changed'] = bool(i.get('import_changed'))
            except Exception:
                pass
    else:
        print('Skip import (no extraction changes)')

    # Decide exit code
    if overall['import_changed']:
        overall['exit_code'] = 30
    elif overall['extraction_changed']:
        overall['exit_code'] = 20
    elif overall['download_changed']:
        overall['exit_code'] = 10
    else:
        overall['exit_code'] = 0

    try:
        REPORT_PATH.write_text(json.dumps(overall, indent=2))
    except Exception:
        pass

    print('\n== Refresh Summary ==')
    print(json.dumps(overall, indent=2))
    return overall['exit_code']


if __name__ == '__main__':
    sys.exit(run_refresh())
