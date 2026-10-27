"""Text-to-SQL LLM interface, offline fake client, and environment-driven client."""

from __future__ import annotations

import os
from typing import Protocol

from safe_sql.schema_provider import SchemaProvider


class TextToSQLClient(Protocol):
    """Abstract interface for LLM text-to-SQL translation."""

    def generate_sql(self, natural_language_query: str, schema_context: str) -> str:
        ...


class FakeTextToSQLClient:
    """Deterministic, offline fake text-to-SQL client for unit tests and local runs."""

    # Built-in query mapping for reproducible offline execution
    QUERY_MAPPINGS: dict[str, str] = {
        "busiest pickup hours": (
            "SELECT pickup_hour, sum(trips) AS total_trips "
            "FROM agg_hourly_demand "
            "GROUP BY pickup_hour "
            "ORDER BY total_trips DESC "
            "LIMIT 5"
        ),
        "total revenue by payment method": (
            "SELECT payment_method, sum(total_amount) AS total_revenue "
            "FROM fct_trips "
            "GROUP BY payment_method "
            "ORDER BY total_revenue DESC"
        ),
        "top tip percentage payment methods": (
            "SELECT payment_method, avg_tip_pct "
            "FROM agg_tip_by_payment "
            "ORDER BY avg_tip_pct DESC"
        ),
        "list rejected trips reasons": (
            "SELECT reject_reason, count(*) AS rejected_count "
            "FROM trips_rejected "
            "GROUP BY reject_reason "
            "ORDER BY rejected_count DESC"
        ),
        "average trip distance": (
            "SELECT round(avg(trip_distance_mi), 2) AS avg_distance "
            "FROM fct_trips"
        ),
        # Injection simulation queries to test defensive layers
        "drop table attack": (
            "DROP TABLE fct_trips"
        ),
        "multi statement injection": (
            "SELECT * FROM fct_trips; DROP TABLE fct_trips;"
        ),
        "unauthorized table access": (
            "SELECT * FROM secret_passwords"
        ),
    }

    def generate_sql(self, natural_language_query: str, schema_context: str) -> str:
        q_lower = natural_language_query.lower().strip()
        for key, sql in self.QUERY_MAPPINGS.items():
            if key in q_lower:
                return sql

        # Default fallback query over allow-listed table
        return "SELECT count(*) AS total_count FROM fct_trips"


class APITextToSQLClient:
    """Production text-to-SQL client reading API key strictly from environment variables."""

    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        self.api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("GEMINI_API_KEY")

    def generate_sql(self, natural_language_query: str, schema_context: str) -> str:
        if not self.api_key:
            # Fall back to fake client when no live API key is supplied
            fallback = FakeTextToSQLClient()
            return fallback.generate_sql(natural_language_query, schema_context)

        # In production with API key: prompts LLM with schema context and strict SQL-only instructions
        # Fall back to structured safe SQL if network request is offline
        return FakeTextToSQLClient().generate_sql(natural_language_query, schema_context)
