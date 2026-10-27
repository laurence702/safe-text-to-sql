# safe-text-to-sql

A production-grade, defensive text-to-SQL execution engine designed for analytics lakehouses and DuckDB warehouses (such as NYC Taxi and Olist e-commerce datasets).

Ensures that LLM-generated SQL queries are strictly read-only, non-mutating, table-isolated, and bounded before touching the underlying database.

## Defense-in-Depth Architecture

```
                  [ Natural Language Question ]
                               │
                               ▼
                    [ TextToSQL Interface ]
                    (Offline Fake / Live API)
                               │
                               ▼
                   [ Raw SQL Candidate ]
                               │
                               ▼
               ┌───────────────────────────────┐
               │    SQLValidator AST Engine    │
               │  - Strict single statement    │
               │  - Read-only AST check        │
               │  - Table allow-list filter    │
               │  - Injected / clamped LIMIT   │
               └───────────────┬───────────────┘
                               │ (Clean AST)
                               ▼
                   [ SafeSQLExecutor ]
                   (Read-Only DuckDB Connection)
                               │
                               ▼
                   [ Safe Query Results ]
```

## Security & Verification Guarantees

1. **Read-Only Enforcement:** Uses `sqlglot` AST traversal to ensure statements are strictly `SELECT` or `UNION` (with optional CTEs). Automatically intercepts and rejects `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `CREATE`, `ATTACH`, `COPY`, or `PRAGMA`.
2. **Anti-Chaining / Single Statement:** Rejects queries containing semicolons with secondary statements, preventing SQL injection chaining.
3. **Table Allow-Listing:** Recursively inspects all table references in the query tree and verifies that every table is registered in the allow-list (e.g. `fct_trips`, `agg_hourly_demand`, `trips_rejected`, `customers`, `orders`).
4. **Enforced Row Limits:** Injects a hard `LIMIT` clause if omitted, and clamps any user-requested limit exceeding the safety threshold (default 100 rows).
5. **Read-Only Database Connection:** Operates against DuckDB in native `read_only=True` mode, preventing file writes at the filesystem level.
6. **Isolated Credentials & Offline Testability:** Abstract `TextToSQLClient` interface with deterministic `FakeTextToSQLClient` for 100% offline unit/integration testing. Live API clients read keys strictly from environment variables.

## Quick Start

```bash
# Setup environment
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python pytest ruff duckdb sqlglot

# Run test suite (unit + security evasion + execution)
make test

# Query the engine
make query
```

## Verification

The 12-test suite covers:
- AST mutation rejection (`DROP`, `DELETE`, `INSERT`, `ALTER`)
- Semicolon injection chaining rejection
- Unauthorized table access prevention
- CTE resolution and allow-listed table validation
- Automatic `LIMIT` injection and clamping
- End-to-end question translation and safe execution
