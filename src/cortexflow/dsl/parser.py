"""YAML/JSON parser for workflow definitions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from cortexflow.dsl.schema import WorkflowDefinition


class Parser:
    """Parse workflow definitions from YAML/JSON."""

    def parse_file(self, path: str | Path) -> WorkflowDefinition:
        """Parse workflow from file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Workflow file not found: {path}")

        content = path.read_text(encoding="utf-8")
        format = "json" if path.suffix == ".json" else "yaml"
        return self.parse_string(content, format)

    def parse_string(self, content: str, format: str = "yaml") -> WorkflowDefinition:
        """Parse workflow from string."""
        if format == "json":
            data = json.loads(content)
        else:
            data = yaml.safe_load(content)

        return self.parse_dict(data)

    def parse_dict(self, data: dict[str, Any]) -> WorkflowDefinition:
        """Parse workflow from dictionary."""
        for tier_name, tier_def in data.get("tiers", {}).items():
            tier_def.setdefault("name", tier_name)
        return WorkflowDefinition(**data)
