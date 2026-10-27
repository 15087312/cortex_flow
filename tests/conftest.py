"""Pytest isolation: point workflow persistence at a temp SQLite file.

Must be set before ``cortexflow.api.routes`` is imported (it resolves the
DB path at import time), and conftest is imported before test modules.
"""

import os
import tempfile

_tmpdir = tempfile.mkdtemp(prefix="cortexflow-test-")
os.environ.setdefault("CORTEXFLOW_DB_PATH", os.path.join(_tmpdir, "test.db"))
# Keep the pre-existing API tests green: auth is tested separately in
# test_auth.py (which re-enables it per-test via monkeypatch).
os.environ.setdefault("CORTEXFLOW_DISABLE_AUTH", "1")
