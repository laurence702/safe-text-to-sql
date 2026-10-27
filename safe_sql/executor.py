"""DuckDB query executor running strictly in read-only mode."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import duckdb

from safe_sql.models import ExecutionResult, ValidationResult
from safe_sql.validator import SQLValidator


class SafeSQLExecutor:
    """Executes validated, read-only SQL queries against DuckDB databases."""

    def __init__(self, db_path: str | Path | None = None, validator: SQLValidator | None = None):
        self.db_path = str(db_path) if db_path else ":memory:"
        self.validator = validator or SQLValidator(allow_listed_tables=[])
        self._init_connection()

    def _init_connection(self) -> None:
        if self.db_path == ":memory:":
            self.conn = duckdb.connect(self.db_path)
        else:
            self.conn = duckdb.connect(self.db_path, read_only=True)

    def execute_safe_query(self, sql_query: str) -> ExecutionResult:
        """Validates and executes a query, returning structured results."""
        start_time = time.perf_counter()

        val: ValidationResult = self.validator.validate(sql_query)
        if not val.is_valid:
            duration = (time.perf_counter() - start_time) * 1000.0
            return ExecutionResult(
                query=sql_query,
                sql="",
                error=f"Safety Validation Rejected: {val.error_message}",
                duration_ms=duration,
            )

        try:
            cursor = self.conn.execute(val.sanitized_sql)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            duration = (time.perf_counter() - start_time) * 1000.0

            return ExecutionResult(
                query=sql_query,
                sql=val.sanitized_sql,
                columns=columns,
                rows=rows,
                row_count=len(rows),
                duration_ms=duration,
            )
        except Exception as exc:
            duration = (time.perf_counter() - start_time) * 1000.0
            return ExecutionResult(
                query=sql_query,
                sql=val.sanitized_sql,
                error=f"DuckDB Execution Error: {exc}",
                duration_ms=duration,
            )

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
