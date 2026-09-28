"""Initialize MySQL schema for ISSF RAG backend.
This file is auto-executed on MySQL container first boot via docker-entrypoint-initdb.d.
It uses schema-only creation; seed data is inserted by migrate.py + seed_db.py or Flyway/scripts.
"""
from pathlib import Path

migrations_dir = Path(__file__).resolve().parent.parent.parent / "migrations"
init_sql = Path(__file__).resolve().parent / "init.sql"
print("Placeholder init script for MySQL. Use migrations/ or seed_db.py instead.", flush=True)
