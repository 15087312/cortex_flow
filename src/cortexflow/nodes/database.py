"""Database node - CRUD against a SQLite database (Coze-style database node).

Two ways to use it:

1. Table helpers (identifiers are validated, values are always bound)::

       save:
         type: database
         db_action: insert
         table: orders
         values:
           order_id: "${order_id}"
           amount: "${total}"
         output: insert_result

2. Raw parameterised SQL::

       lookup:
         type: database
         db_action: query
         sql: "SELECT id, name FROM users WHERE name = ?"
         db_params: ["${user_name}"]
         limit: 1
         output: users

``query`` returns a list of row dicts; writes return
``{"rowcount": n, "lastrowid": id}``.

By default the node uses the same SQLite file as the rest of the app
(``$CORTEXFLOW_DB_PATH`` or ``<project>/data/cortexflow.db``); set
``database: /path/to.db`` to point elsewhere.
"""

from __future__ import annotations

import asyncio
import re
import sqlite3
from pathlib import Path
from typing import Any

from cortexflow.nodes.base import BaseNode
from cortexflow.nodes.registry import NodeRegistry
from cortexflow.runtime.context import ExecutionContext
from cortexflow.store.common import default_db_path

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_WRITE_ACTIONS = {"insert", "update", "delete"}
_ACTIONS = {"query", "insert", "update", "delete", "execute"}


def _check_identifier(name: str, kind: str) -> str:
    if not _IDENTIFIER.match(name):
        raise ValueError(f"Invalid SQL {kind}: {name!r}")
    return name


def _run_sql(
    db_path: str | Path, sql: str, params: list[Any], is_query: bool
) -> Any:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            cursor = conn.execute(sql, params)
            if is_query:
                return [dict(row) for row in cursor.fetchall()]
            return {"rowcount": cursor.rowcount, "lastrowid": cursor.lastrowid}
    finally:
        conn.close()


@NodeRegistry.register("database")
class DatabaseNode(BaseNode):
    """Query or mutate a SQLite database."""

    async def execute(self, context: ExecutionContext) -> Any:
        action = str(self.config.get("db_action") or "query").lower()
        if action not in _ACTIONS:
            raise ValueError(
                f"Database node '{self.node_id}' has unknown db_action "
                f"'{action}' (expected {'|'.join(sorted(_ACTIONS))})"
            )

        sql, params = self._build_statement(action, context)
        db_path = self.config.get("database") or default_db_path()
        return await asyncio.to_thread(_run_sql, db_path, sql, params, action == "query")

    # ── statement building ──────────────────────────────────────

    def _build_statement(
        self, action: str, context: ExecutionContext
    ) -> tuple[str, list[Any]]:
        raw_sql = self.config.get("sql")
        params = self.resolve(self.config.get("db_params") or [], context)

        if raw_sql:
            if not isinstance(params, list):
                raise TypeError(
                    f"Database node '{self.node_id}' db_params must be a list"
                )
            return str(raw_sql), params

        table = self.config.get("table")
        if not table:
            raise ValueError(
                f"Database node '{self.node_id}' needs 'sql' or 'table'"
            )
        table = _check_identifier(str(table), "table")

        where_sql, where_params = self._build_where(context)

        if action == "query":
            sql = f"SELECT * FROM {table}{where_sql}"
            limit = self.config.get("limit")
            if limit:
                sql += f" LIMIT {int(limit)}"
            return sql, where_params

        if action == "insert":
            values = self.resolve(self.config.get("values") or {}, context)
            if not isinstance(values, dict) or not values:
                raise ValueError(
                    f"Database node '{self.node_id}' insert needs 'values'"
                )
            columns = [_check_identifier(str(k), "column") for k in values]
            placeholders = ", ".join("?" for _ in columns)
            sql = (
                f"INSERT INTO {table} ({', '.join(columns)}) "
                f"VALUES ({placeholders})"
            )
            return sql, list(values.values())

        if action == "update":
            values = self.resolve(self.config.get("values") or {}, context)
            if not isinstance(values, dict) or not values:
                raise ValueError(
                    f"Database node '{self.node_id}' update needs 'values'"
                )
            self._require_where(where_sql, action)
            assignments = ", ".join(
                f"{_check_identifier(str(k), 'column')} = ?" for k in values
            )
            sql = f"UPDATE {table} SET {assignments}{where_sql}"
            return sql, [*values.values(), *where_params]

        # delete
        self._require_where(where_sql, action)
        return f"DELETE FROM {table}{where_sql}", where_params

    def _build_where(self, context: ExecutionContext) -> tuple[str, list[Any]]:
        where = self.resolve(self.config.get("where") or {}, context)
        if not where:
            return "", []
        if not isinstance(where, dict):
            raise TypeError(
                f"Database node '{self.node_id}' where must be a mapping"
            )
        clauses = [f"{_check_identifier(str(k), 'column')} = ?" for k in where]
        return f" WHERE {' AND '.join(clauses)}", list(where.values())

    def _require_where(self, where_sql: str, action: str) -> None:
        if not where_sql and not self.config.get("allow_all"):
            raise ValueError(
                f"Database node '{self.node_id}' {action} without 'where' would "
                f"affect every row; set allow_all: true to confirm"
            )
