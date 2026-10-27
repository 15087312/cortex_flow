"""Shared SQLite path resolution for all stores.

``$CORTEXFLOW_DB_PATH`` overrides the default
``<project_root>/data/cortexflow.db`` (tests point it at a temp file).
"""

from __future__ import annotations

import os
from pathlib import Path


def default_db_path() -> Path:
    env = os.environ.get("CORTEXFLOW_DB_PATH")
    if env:
        return Path(env)
    # src/cortexflow/store/... -> parents[3] == project root
    root = Path(__file__).resolve().parents[3]
    return root / "data" / "cortexflow.db"