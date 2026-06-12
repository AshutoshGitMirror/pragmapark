import os, sys, sqlalchemy as sa
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.api.database import get_engine
e = get_engine()
with e.connect() as c:
    try:
        r = c.execute(sa.text('SELECT * FROM alembic_version')).fetchall()
        print("alembic_version rows:", r)
    except Exception as ex:
        print("alembic_version table error:", ex)
    try:
        r2 = c.execute(sa.text("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname='public'")).fetchall()
        tables = sorted([t[0] for t in r2])
        print(f"tables ({len(tables)}):", tables)
    except Exception as ex:
        print("Error listing tables:", ex)
