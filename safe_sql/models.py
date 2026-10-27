"""Data models for safe text-to-SQL system."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ColumnSchema:
    name: str
    data_type: str
    nullable: bool = True
    description: str = ""


@dataclass(frozen=True)
class TableSchema:
    table_name: str
    columns: list[ColumnSchema] = field(default_factory=list)
    description: str = ""

    def ddl_representation(self) -> str:
        cols = ", ".join(f"{c.name} {c.data_type}" for c in self.columns)
        return f"CREATE TABLE {self.table_name} ({cols});"


@dataclass
class ValidationResult:
    is_valid: bool
    sanitized_sql: str
    tables_referenced: list[str] = field(default_factory=list)
    error_message: str | None = None


@dataclass
class ExecutionResult:
    query: str
    sql: str
    columns: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)
    row_count: int = 0
    duration_ms: float = 0.0
    error: str | None = None
