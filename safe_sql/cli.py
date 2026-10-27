"""Command-line interface for safe text-to-SQL execution."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from safe_sql.engine import SafeTextToSQLEngine


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="safe-sql", description="Safe Text-to-SQL over DuckDB Warehouse")
    parser.add_argument("question", type=str, help="Natural language query")
    parser.add_argument("--db", type=Path, default=None, help="Path to DuckDB database file")
    parser.add_argument("--limit", type=int, default=50, help="Row limit")

    args = parser.parse_args(argv)
    engine = SafeTextToSQLEngine(db_path=args.db, max_row_limit=args.limit)

    res = engine.ask(args.question)
    print(f"Question: {args.question}")
    if res.error:
        print(f"\n[BLOCKED / ERROR]: {res.error}")
        return 1

    print(f"\nValidated SQL:\n{res.sql}")
    print(f"\nReturned {res.row_count} rows in {res.duration_ms:.2f}ms:")
    if res.columns:
        print(" | ".join(res.columns))
        print("-" * 50)
        for r in res.rows:
            print(" | ".join(str(val) for val in r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
