#!/usr/bin/env python3
"""Build a wheel and prepare a minimal Databricks app source directory."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DIST_DIR = REPO_ROOT / "dist"
APP_SOURCE_DIR = REPO_ROOT / ".databricks_app_source"
WHEELS_DIR = APP_SOURCE_DIR / "wheels"


def _run(command: list[str]) -> None:
    subprocess.check_call(command, cwd=REPO_ROOT)


def _latest_wheel() -> Path:
    wheels = sorted(DIST_DIR.glob("*.whl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not wheels:
        raise FileNotFoundError("No wheel artifacts found in dist/.")
    return wheels[0]


def main() -> int:
    APP_SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    WHEELS_DIR.mkdir(parents=True, exist_ok=True)

    # Build a fresh wheel artifact for this revision.
    _run(["uv", "build", "--wheel"])

    # Keep only one wheel in the deploy payload to minimize source size.
    for old_wheel in WHEELS_DIR.glob("*.whl"):
        old_wheel.unlink()

    latest = _latest_wheel()
    destination = WHEELS_DIR / latest.name
    shutil.copy2(latest, destination)

    print(f"Prepared Databricks app source at: {APP_SOURCE_DIR}")
    print(f"Wheel included: {destination.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
