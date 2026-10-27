"""Safe snapshots of node inputs/outputs for traces (Coze-style IO inspection).

Snapshots must never break tracing: arbitrary user values (huge strings,
binary blobs, exotic objects) are truncated and converted to JSON-safe
structures.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

MAX_STRING_LEN = 2000
MAX_ITEMS = 100
MAX_DEPTH = 5


def snapshot_value(value: Any, depth: int = 0) -> Any:
    """Convert *value* to a JSON-safe, size-bounded snapshot."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        if len(value) > MAX_STRING_LEN:
            return value[:MAX_STRING_LEN] + f"…(truncated {len(value) - MAX_STRING_LEN} chars)"
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray)):
        preview = bytes(value[:64])
        suffix = f"…(truncated {len(value) - 64} bytes)" if len(value) > 64 else ""
        return f"<bytes len={len(value)} {preview!r}>{suffix}"
    if depth >= MAX_DEPTH:
        return f"<{type(value).__name__} …(max depth)>"
    if isinstance(value, dict):
        items = list(value.items())[:MAX_ITEMS]
        out = {str(k): snapshot_value(v, depth + 1) for k, v in items}
        if len(value) > MAX_ITEMS:
            out["…"] = f"(truncated {len(value) - MAX_ITEMS} keys)"
        return out
    if isinstance(value, (list, tuple)):
        out_list = [snapshot_value(v, depth + 1) for v in value[:MAX_ITEMS]]
        if len(value) > MAX_ITEMS:
            out_list.append(f"…(truncated {len(value) - MAX_ITEMS} items)")
        return out_list
    if isinstance(value, (set, frozenset)):
        return snapshot_value(sorted(value, key=repr)[:MAX_ITEMS], depth)
    try:
        import json

        json.dumps(value)
        return value
    except (TypeError, ValueError):
        pass
    return f"<{type(value).__name__} {repr(value)[:200]}>"
