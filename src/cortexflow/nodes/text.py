"""Text node - string processing helpers (Coze-style text node).

The node reads ``input`` (resolved like every other field), applies one
``text_action`` and returns the result::

    clean:
      type: text
      text_action: replace
      input: "${raw_text}"
      text_args:
        old: "\\n\\n"
        new: "\\n"
      output: cleaned

Supported actions: ``trim``, ``upper``, ``lower``, ``title``,
``capitalize``, ``length``, ``replace``, ``split``, ``join``,
``substring``, ``contains``, ``concat``, ``regex_extract``,
``regex_replace``, ``template``, ``json_parse``, ``to_json``.
"""

from __future__ import annotations

import json
import re
from typing import Any

from cortexflow.nodes.base import BaseNode
from cortexflow.nodes.registry import NodeRegistry
from cortexflow.runtime.context import ExecutionContext

_ACTIONS = {
    "trim",
    "upper",
    "lower",
    "title",
    "capitalize",
    "length",
    "replace",
    "split",
    "join",
    "substring",
    "contains",
    "concat",
    "regex_extract",
    "regex_replace",
    "template",
    "json_parse",
    "to_json",
}

_TEMPLATE_VAR = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")


def _lookup(data: Any, path: str) -> Any:
    """Resolve a dotted path against *data* (``user.name``, ``items.0``)."""
    current = data
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, (list, tuple)):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
        if current is None:
            return None
    return current


@NodeRegistry.register("text")
class TextNode(BaseNode):
    """Apply a string operation to the resolved input."""

    async def execute(self, context: ExecutionContext) -> Any:
        action = str(self.config.get("text_action") or "").lower()
        if not action:
            raise ValueError(f"Text node '{self.node_id}' requires 'text_action'")
        if action not in _ACTIONS:
            raise ValueError(
                f"Text node '{self.node_id}' has unknown text_action '{action}' "
                f"(expected {'|'.join(sorted(_ACTIONS))})"
            )

        value = self.resolve(self.config.get("input"), context)
        args = self.resolve(self.config.get("text_args") or {}, context)
        if not isinstance(args, dict):
            raise TypeError(f"Text node '{self.node_id}' text_args must be a mapping")

        handler = getattr(self, f"_do_{action}")
        return handler(value, args, context)

    # ── simple string ops ───────────────────────────────────────

    def _do_trim(self, value: Any, args: dict[str, Any], _ctx: ExecutionContext) -> str:
        return str(value or "").strip()

    def _do_upper(self, value: Any, args: dict[str, Any], _ctx: ExecutionContext) -> str:
        return str(value or "").upper()

    def _do_lower(self, value: Any, args: dict[str, Any], _ctx: ExecutionContext) -> str:
        return str(value or "").lower()

    def _do_title(self, value: Any, args: dict[str, Any], _ctx: ExecutionContext) -> str:
        return str(value or "").title()

    def _do_capitalize(
        self, value: Any, args: dict[str, Any], _ctx: ExecutionContext
    ) -> str:
        return str(value or "").capitalize()

    def _do_length(
        self, value: Any, args: dict[str, Any], _ctx: ExecutionContext
    ) -> int:
        return len(value) if value is not None else 0

    def _do_replace(
        self, value: Any, args: dict[str, Any], _ctx: ExecutionContext
    ) -> str:
        old = args.get("old")
        if old is None:
            raise ValueError(f"Text node '{self.node_id}' replace needs 'old'")
        new = args.get("new", "")
        count = int(args.get("count", -1))
        return str(value or "").replace(str(old), str(new), count)

    def _do_split(
        self, value: Any, args: dict[str, Any], _ctx: ExecutionContext
    ) -> list[str]:
        separator = args.get("separator")
        if separator is None:
            return str(value or "").split()
        return str(value or "").split(str(separator))

    def _do_join(
        self, value: Any, args: dict[str, Any], _ctx: ExecutionContext
    ) -> str:
        if not isinstance(value, (list, tuple)):
            raise TypeError(
                f"Text node '{self.node_id}' join needs a list input, "
                f"got {type(value).__name__}"
            )
        separator = str(args.get("separator", "\n"))
        return separator.join(str(item) for item in value)

    def _do_substring(
        self, value: Any, args: dict[str, Any], _ctx: ExecutionContext
    ) -> str:
        text = str(value or "")
        start = int(args.get("start", 0))
        end = args.get("end")
        return text[start:] if end is None else text[start : int(end)]

    def _do_contains(
        self, value: Any, args: dict[str, Any], _ctx: ExecutionContext
    ) -> bool:
        needle = args.get("value")
        if needle is None:
            raise ValueError(f"Text node '{self.node_id}' contains needs 'value'")
        return str(needle) in str(value or "")

    def _do_concat(
        self, value: Any, args: dict[str, Any], _ctx: ExecutionContext
    ) -> str:
        items = args.get("items")
        if items is None:
            items = [value] if value is not None else []
        if not isinstance(items, (list, tuple)):
            items = [items]
        separator = str(args.get("separator", ""))
        return separator.join(str(item) for item in items if item is not None)

    # ── regex ───────────────────────────────────────────────────

    def _do_regex_extract(
        self, value: Any, args: dict[str, Any], _ctx: ExecutionContext
    ) -> Any:
        pattern = args.get("pattern")
        if not pattern:
            raise ValueError(
                f"Text node '{self.node_id}' regex_extract needs 'pattern'"
            )
        group: int | str = args.get("group", 0)
        if isinstance(group, str) and group.isdigit():
            group = int(group)
        matches = re.findall(pattern, str(value or ""))
        if not args.get("all"):
            if not matches:
                return None
            first = matches[0]
            if isinstance(first, tuple):
                return first[0] if group == 0 else first[int(group)]
            return first
        if group == 0:
            return list(matches)
        return [m[int(group)] if isinstance(m, tuple) else m for m in matches]

    def _do_regex_replace(
        self, value: Any, args: dict[str, Any], _ctx: ExecutionContext
    ) -> str:
        pattern = args.get("pattern")
        if not pattern:
            raise ValueError(
                f"Text node '{self.node_id}' regex_replace needs 'pattern'"
            )
        replacement = str(args.get("replacement", ""))
        count = int(args.get("count", 0))
        return re.sub(pattern, replacement, str(value or ""), count=count)

    # ── templating / JSON ───────────────────────────────────────

    def _do_template(
        self, value: Any, args: dict[str, Any], _ctx: ExecutionContext
    ) -> str:
        template = args.get("template")
        if not template:
            raise ValueError(f"Text node '{self.node_id}' template needs 'template'")

        def replace(match: re.Match[str]) -> str:
            path = match.group(1)
            found = _lookup(value, path)
            if found is None:
                found = _ctx.get_variable(path)
            return "" if found is None else str(found)

        return _TEMPLATE_VAR.sub(replace, str(template))

    def _do_json_parse(
        self, value: Any, args: dict[str, Any], _ctx: ExecutionContext
    ) -> Any:
        if not isinstance(value, str):
            return value
        return json.loads(value)

    def _do_to_json(
        self, value: Any, args: dict[str, Any], _ctx: ExecutionContext
    ) -> str:
        indent = args.get("indent", 2)
        return json.dumps(value, ensure_ascii=False, indent=indent)
