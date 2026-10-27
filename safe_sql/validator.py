"""SQL safety validator using AST parsing with sqlglot."""

from __future__ import annotations

import re
from typing import Sequence

import sqlglot
from sqlglot import exp

from safe_sql.models import ValidationResult

FORBIDDEN_KEYWORDS = {
    "insert", "update", "delete", "drop", "alter", "create", "truncate",
    "attach", "detach", "copy", "export", "import", "pragma", "call",
    "execute", "vacuum", "checkpoint", "grant", "revoke", "commit", "rollback",
    "replace", "merge", "show", "describe", "summarize", "install", "load",
}


class SQLSecurityError(ValueError):
    """Raised when a query violates safety constraints."""


class SQLValidator:
    """Validates that queries are strictly read-only, single-statement, and table-restricted."""

    def __init__(self, allow_listed_tables: Sequence[str], max_row_limit: int = 100):
        self.allow_listed_tables = {t.lower() for t in allow_listed_tables}
        self.max_row_limit = max_row_limit

    def validate(self, sql_query: str) -> ValidationResult:
        raw_sql = sql_query.strip()
        if not raw_sql:
            return ValidationResult(is_valid=False, sanitized_sql="", error_message="Empty query provided.")

        # 1. Reject statement chaining via semicolons
        semicolon_split = [s.strip() for s in raw_sql.split(";") if s.strip()]
        if len(semicolon_split) > 1:
            return ValidationResult(
                is_valid=False,
                sanitized_sql="",
                error_message="Query contains multiple statements. Only single read-only statements are permitted.",
            )

        clean_sql = semicolon_split[0]

        # 2. Parse AST using sqlglot DuckDB dialect
        try:
            statements = sqlglot.parse(clean_sql, read="duckdb")
        except Exception as exc:
            return ValidationResult(
                is_valid=False, sanitized_sql="", error_message=f"Syntax parsing error: {exc}"
            )

        if len(statements) != 1 or statements[0] is None:
            return ValidationResult(
                is_valid=False, sanitized_sql="", error_message="Failed to parse valid single statement."
            )

        statement = statements[0]

        # 3. Read-only validation: Must be Select or Union
        if not isinstance(statement, (exp.Select, exp.Union)):
            return ValidationResult(
                is_valid=False,
                sanitized_sql="",
                error_message=f"Non-read-only statement type: {statement.key.upper()}. Only SELECT queries are permitted.",
            )

        # Deep check: Ensure no nested write operations inside CTEs or functions
        for node in statement.walk():
            if isinstance(node, (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter, exp.Command)):
                return ValidationResult(
                    is_valid=False,
                    sanitized_sql="",
                    error_message=f"Disallowed mutating operation '{node.key.upper()}' detected in query tree.",
                )

        # 4. Table allow-list check
        # Extract CTE aliases to avoid false-flagging CTE names as external tables
        cte_aliases = {cte.alias.lower() for cte in statement.find_all(exp.CTE) if cte.alias}

        referenced_tables: list[str] = []
        for table_expr in statement.find_all(exp.Table):
            t_name = table_expr.name.lower()
            if t_name in cte_aliases:
                continue
            referenced_tables.append(t_name)
            if t_name not in self.allow_listed_tables:
                return ValidationResult(
                    is_valid=False,
                    sanitized_sql="",
                    tables_referenced=referenced_tables,
                    error_message=f"Access to table '{t_name}' is forbidden. Allow-listed tables: {sorted(self.allow_listed_tables)}",
                )

        # 5. Row limit enforcement (enforce or clamp LIMIT <= max_row_limit)
        limit_expr = statement.args.get("limit")
        if limit_expr is None:
            statement = statement.limit(self.max_row_limit)
        else:
            try:
                curr_limit = int(limit_expr.expression.this)
                if curr_limit > self.max_row_limit or curr_limit < 0:
                    statement.args["limit"] = exp.Limit(expression=exp.Literal.number(self.max_row_limit))
            except Exception:
                statement.args["limit"] = exp.Limit(expression=exp.Literal.number(self.max_row_limit))

        sanitized_sql = statement.sql(dialect="duckdb")

        return ValidationResult(
            is_valid=True,
            sanitized_sql=sanitized_sql,
            tables_referenced=list(set(referenced_tables)),
            error_message=None,
        )
