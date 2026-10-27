"""Minimal HS256 JWT — stdlib only (hmac/hashlib/base64/json).

Structure-compatible with RFC 7519 HS256 tokens so any standard JWT
library can verify them; no third-party dependency required.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64d(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def create_token(secret: str, subject: str, ttl: int = 7 * 24 * 3600) -> str:
    """Create a signed HS256 token with subject and expiry."""
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {"sub": subject, "iat": now, "exp": now + ttl}
    signing_input = ".".join([
        _b64(json.dumps(header, separators=(",", ":")).encode("utf-8")),
        _b64(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
    ])
    signature = hmac.new(secret.encode("utf-8"), signing_input.encode("ascii"),
                         hashlib.sha256).digest()
    return f"{signing_input}.{_b64(signature)}"


def verify_token(secret: str, token: str) -> str | None:
    """Verify a token; returns the subject (username) or None."""
    try:
        signing_input, signature = token.rsplit(".", 1)
        expected = hmac.new(secret.encode("utf-8"), signing_input.encode("ascii"),
                            hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64d(signature)):
            return None
        payload = json.loads(_b64d(signing_input.split(".")[1]))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload.get("sub")
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None