"""Test suite for safe text-to-SQL validation and execution."""

from __future__ import annotations

import unittest

import duckdb

from safe_sql.engine import SafeTextToSQLEngine
from safe_sql.executor import SafeSQLExecutor
from safe_sql.llm import FakeTextToSQLClient
from safe_sql.models import ColumnSchema, TableSchema
from safe_sql.schema_provider import SchemaProvider
from safe_sql.validator import SQLValidator


class TestSQLValidator(unittest.TestCase):
    def setUp(self):
        self.validator = SQLValidator(
            allow_listed_tables=["fct_trips", "agg_hourly_demand", "customers"],
            max_row_limit=50,
        )

    def test_valid_select_passes_with_limit_injected(self):
        res = self.validator.validate("SELECT pickup_hour, trips FROM agg_hourly_demand")
        self.assertTrue(res.is_valid)
        self.assertIn("limit 50", res.sanitized_sql.lower())
        self.assertIn("agg_hourly_demand", res.tables_referenced)

    def test_valid_cte_select_passes(self):
        query = (
            "WITH ranked AS (SELECT * FROM fct_trips) "
            "SELECT * FROM ranked WHERE fare_amount > 20 LIMIT 10"
        )
        res = self.validator.validate(query)
        self.assertTrue(res.is_valid)
        self.assertIn("fct_trips", res.tables_referenced)

    def test_reject_drop_table(self):
        res = self.validator.validate("DROP TABLE fct_trips")
        self.assertFalse(res.is_valid)
        self.assertIn("Only SELECT", res.error_message)

    def test_reject_delete_statement(self):
        res = self.validator.validate("DELETE FROM fct_trips WHERE trip_id = 1")
        self.assertFalse(res.is_valid)
        self.assertIn("Only SELECT", res.error_message)

    def test_reject_insert_statement(self):
        res = self.validator.validate("INSERT INTO fct_trips VALUES (1, 2, 3)")
        self.assertFalse(res.is_valid)

    def test_reject_statement_chaining(self):
        res = self.validator.validate("SELECT * FROM fct_trips; DROP TABLE fct_trips;")
        self.assertFalse(res.is_valid)
        self.assertIn("multiple statements", res.error_message)

    def test_reject_unauthorized_table(self):
        res = self.validator.validate("SELECT * FROM secret_credentials")
        self.assertFalse(res.is_valid)
        self.assertIn("forbidden", res.error_message)

    def test_clamps_excessive_limit(self):
        res = self.validator.validate("SELECT * FROM fct_trips LIMIT 10000")
        self.assertTrue(res.is_valid)
        self.assertIn("limit 50", res.sanitized_sql.lower())


class TestSchemaProvider(unittest.TestCase):
    def test_schema_formatting(self):
        provider = SchemaProvider(["fct_trips"])
        table = TableSchema(
            table_name="fct_trips",
            columns=[
                ColumnSchema("trip_id", "BIGINT"),
                ColumnSchema("fare_amount", "DOUBLE"),
            ],
        )
        provider.register_schema(table)
        formatted = provider.format_schema_context()
        self.assertIn("CREATE TABLE fct_trips", formatted)
        self.assertIn("trip_id BIGINT", formatted)


class TestSafeTextToSQLEngine(unittest.TestCase):
    def setUp(self):
        # Create an in-memory DuckDB test instance with sample tables
        self.conn = duckdb.connect(":memory:")
        self.conn.execute("CREATE TABLE agg_hourly_demand (pickup_hour INT, trips INT);")
        self.conn.execute("INSERT INTO agg_hourly_demand VALUES (18, 5000), (12, 3200), (8, 4100);")

        self.conn.execute("CREATE TABLE fct_trips (trip_id INT, payment_method VARCHAR, total_amount DOUBLE);")
        self.conn.execute("INSERT INTO fct_trips VALUES (1, 'credit_card', 25.5), (2, 'cash', 12.0);")

        self.validator = SQLValidator(["agg_hourly_demand", "fct_trips"], max_row_limit=10)
        self.executor = SafeSQLExecutor(":memory:", validator=self.validator)
        # Use our pre-populated connection
        self.executor.conn = self.conn

    def test_safe_execution_returns_rows(self):
        res = self.executor.execute_safe_query("SELECT pickup_hour, trips FROM agg_hourly_demand ORDER BY trips DESC")
        self.assertIsNone(res.error)
        self.assertEqual(res.row_count, 3)
        self.assertEqual(res.rows[0][0], 18)
        self.assertEqual(res.rows[0][1], 5000)

    def test_injection_blocked_at_executor_level(self):
        res = self.executor.execute_safe_query("DROP TABLE fct_trips")
        self.assertIsNotNone(res.error)
        self.assertIn("Safety Validation Rejected", res.error)
        # Verify table still exists
        check = self.conn.execute("SELECT count(*) FROM fct_trips").fetchone()
        self.assertEqual(check[0], 2)

    def test_fake_llm_end_to_end_question(self):
        client = FakeTextToSQLClient()
        sql = client.generate_sql("busiest pickup hours", "")
        res = self.executor.execute_safe_query(sql)
        self.assertIsNone(res.error)
        self.assertGreater(res.row_count, 0)


if __name__ == "__main__":
    unittest.main()
