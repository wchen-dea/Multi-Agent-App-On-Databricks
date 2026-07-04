#!/usr/bin/env python3
"""Install bundled wheel and launch the multiagent app."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _find_wheel() -> Path:
    source_root = Path(__file__).resolve().parent
    wheels_dir = source_root / "wheels"
    wheels = sorted(wheels_dir.glob("*.whl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not wheels:
        raise FileNotFoundError(
            "No wheel file found under ./wheels. Deploy with a prepared app source package."
        )
    return wheels[0]


def _install_wheel(wheel_path: Path) -> None:
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-cache-dir",
            "--upgrade",
            "--force-reinstall",
            "--no-warn-conflicts",
            str(wheel_path),
        ]
    )


def main() -> None:
    source_root = Path(__file__).resolve().parent
    wheel_path = _find_wheel()
    print(f"Installing wheel: {wheel_path.name}")
    _install_wheel(wheel_path)

    env = os.environ.copy()
    env.setdefault("REACT_UI_DIST_DIR", str(source_root / "reactui-dist"))
    # Start the packaged app entrypoint after installation.
    cmd = ["uv", "run", "python", "-m", "scripts.start_app"]
    raise SystemExit(subprocess.call(cmd, env=env))


if __name__ == "__main__":
    main()
