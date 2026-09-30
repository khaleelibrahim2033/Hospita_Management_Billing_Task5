"""One-time SQLite-compatible migration for audit fields and appointment table. Back up DB first."""
from sqlalchemy import inspect, text
from app.database import Base, engine
from app import models  # register all model metadata

inspector = inspect(engine)
for table in ("users", "doctors", "patients"):
    if table not in inspector.get_table_names():
        continue
    existing = {c["name"] for c in inspector.get_columns(table)}
    with engine.begin() as conn:
        for name, sql_type in (("created_at", "DATETIME"), ("updated_at", "DATETIME"), ("created_by", "VARCHAR(100)"), ("updated_by", "VARCHAR(100)")):
            if name not in existing:
                default = " DEFAULT CURRENT_TIMESTAMP" if name in ("created_at", "updated_at") else ""
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}{default}"))
Base.metadata.create_all(bind=engine)
print("Migration completed. Verify the schema and test with a backup database.")
