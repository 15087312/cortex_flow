"""User accounts + token-signing secret (SQLite, stdlib only).

Passwords are hashed with PBKDF2-HMAC-SHA256 (per-user salt, 200k iters).
The HMAC signing secret is generated once and persisted, so JWTs stay
valid across restarts.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

from cortexflow.store.common import default_db_path

_PBKDF2_ITER = 200_000

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  username TEXT PRIMARY KEY,
  password_hash TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS app_secrets (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), _PBKDF2_ITER
    )
    return f"pbkdf2${_PBKDF2_ITER}${salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iters, salt, expected = stored.split("$")
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt), int(iters)
        )
        return hmac.compare_digest(dk.hex(), expected)
    except (ValueError, TypeError):
        return False


class AuthStore:
    """Persist user accounts and the app's token-signing secret."""

    def __init__(self, path: Path | str | None = None):
        self._path = Path(path) if path else default_db_path()
        self._lock = threading.Lock()
        if str(self._path) != ":memory:":
            self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock, self._conn:
            self._conn.executescript(_SCHEMA)

    def count_users(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()
        return int(row["n"])

    def create_user(self, username: str, password: str) -> bool:
        """Create a user. Returns False if the username already exists."""
        username = (username or "").strip().lower()
        if not username or not password:
            return False
        with self._lock, self._conn:
            exists = self._conn.execute(
                "SELECT 1 FROM users WHERE username = ?", (username,)
            ).fetchone()
            if exists:
                return False
            self._conn.execute(
                "INSERT INTO users (username, password_hash, created_at) "
                "VALUES (?, ?, ?)",
                (username, hash_password(password),
                 datetime.now(UTC).isoformat()),
            )
            return True

    def verify_user(self, username: str, password: str) -> bool:
        username = (username or "").strip().lower()
        with self._lock:
            row = self._conn.execute(
                "SELECT password_hash FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        if not row:
            return False
        return verify_password(password, row["password_hash"])

    def get_secret(self) -> str:
        """The HMAC secret, generated on first access and persisted."""
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT value FROM app_secrets WHERE key = 'jwt_secret'"
            ).fetchone()
            if row:
                return row["value"]
            secret = secrets.token_hex(32)
            self._conn.execute(
                "INSERT INTO app_secrets (key, value) VALUES ('jwt_secret', ?)",
                (secret,),
            )
            return secret

    def clear(self) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM users")
            self._conn.execute("DELETE FROM app_secrets")