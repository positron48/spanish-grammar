#!/usr/bin/env python3
"""Course wrapper for scripts/generate-reading-cover.py."""
from __future__ import annotations

import pathlib
import runpy
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
TARGET = REPO / "scripts" / "generate-reading-cover.py"
sys.argv = [str(TARGET), "--course-root", str(pathlib.Path(".").resolve()), *sys.argv[1:]]
runpy.run_path(str(TARGET), run_name="__main__")
