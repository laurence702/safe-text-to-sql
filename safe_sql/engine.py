"""End-to-end Safe Text-to-SQL Engine."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import duckdb

from safe_sql.executor import SafeSQLExecutor
from safe_sql.llm import FakeTextToSQLClient, TextToSQLClient
from safe_sql.models import ExecutionResult, ValidationResult
from safe_sql.schema_provider import SchemaProvider
from safe_sql.validator import SQLValidator


class SafeTextToSQLEngine:
    """Coordinates schema retrieval, LLM query generation, safety validation, and execution."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        allow_listed_tables: Sequence[str] | None = None,
        max_row_limit: int = 100,
        llm_client: TextToSQLClient | None = None,
    ):
        self.allow_listed_tables = list(allow_listed_tables or [
            "raw_trips", "stg_trips", "fct_trips", "trips_rejected",
            "agg_hourly_demand", "agg_tip_by_payment", "agg_pickup_grid",
            "customers", "orders",
        ])
        self.max_row_limit = max_row_limit
        self.schema_provider = SchemaProvider(self.allow_listed_tables)
        self.validator = SQLValidator(self.allow_listed_tables, max_row_limit=self.max_row_limit)
        self.executor = SafeSQLExecutor(db_path=db_path, validator=self.validator)
        self.llm_client = llm_client or FakeTextToSQLClient()

        # Introspect schema from connected database
        self.schema_provider.introspect_duckdb(self.executor.conn)

    def ask(self, natural_language_query: str) -> ExecutionResult:
        """Translates user question to SQL, validates safety, and executes safely."""
        schema_context = self.schema_provider.format_schema_context()
        generated_sql = self.llm_client.generate_sql(natural_language_query, schema_context)
        return self.executor.execute_safe_query(generated_sql)

    def close(self) -> None:
        self.executor.close()
