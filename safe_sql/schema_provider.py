"""Schema retrieval and prompt formatting for DuckDB tables."""

from __future__ import annotations

from typing import Sequence

import duckdb

from safe_sql.models import ColumnSchema, TableSchema


class SchemaProvider:
    """Introspects and formats schema metadata for allow-listed DuckDB tables."""

    def __init__(self, allow_listed_tables: Sequence[str]):
        self.allow_listed_tables = set(allow_listed_tables)
        self._schemas: dict[str, TableSchema] = {}

    def introspect_duckdb(self, conn: duckdb.DuckDBPyConnection) -> dict[str, TableSchema]:
        """Extracts schema info from DuckDB information_schema."""
        schemas: dict[str, TableSchema] = {}
        for table in self.allow_listed_tables:
            try:
                # Query column details for allow-listed table
                cursor = conn.execute(
                    "SELECT column_name, data_type, is_nullable "
                    "FROM information_schema.columns "
                    "WHERE table_name = ? "
                    "ORDER BY ordinal_position",
                    [table],
                )
                rows = cursor.fetchall()
                if rows:
                    columns = [
                        ColumnSchema(name=r[0], data_type=r[1], nullable=(r[2] == "YES"))
                        for r in rows
                    ]
                    schemas[table] = TableSchema(table_name=table, columns=columns)
            except Exception:
                continue

        self._schemas = schemas
        return schemas

    def register_schema(self, schema: TableSchema) -> None:
        if schema.table_name in self.allow_listed_tables:
            self._schemas[schema.table_name] = schema

    def get_schema(self, table_name: str) -> TableSchema | None:
        return self._schemas.get(table_name)

    def format_schema_context(self) -> str:
        """Formats the allow-listed table schemas as safe DDL context for LLM prompts."""
        if not self._schemas:
            return "No allow-listed table schemas available."
        lines = ["Database Schema (Read-Only):"]
        for table in sorted(self._schemas.keys()):
            lines.append(self._schemas[table].ddl_representation())
        return "\n".join(lines)
