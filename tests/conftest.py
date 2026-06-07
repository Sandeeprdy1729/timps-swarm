"""Pytest configuration: ensure the repo root is on ``sys.path`` so
``import src.*`` and ``import mcp_server.*`` work without first running
``pip install -e .``. The package layout uses a flat ``src/`` and a
sibling ``mcp_server/`` module that aren't installed by default.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
