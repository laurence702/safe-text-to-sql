.PHONY: test query all

test:
	.venv/bin/pytest -v

query:
	.venv/bin/python -m safe_sql.cli "busiest pickup hours" --db ../nyc-taxi-duckdb-lakehouse/data/lakehouse.duckdb

all: test query
