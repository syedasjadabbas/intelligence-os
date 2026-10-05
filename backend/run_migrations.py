"""
Alembic migration runner script for Intelligence OS.
Checks PostgreSQL connectivity before applying migrations.
"""

import os
import sys
from alembic.config import Config
from alembic import command
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings


async def check_database():
    """Verify that PostgreSQL is reachable before triggering migrations."""
    print(f"Checking database connectivity at {settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}...")
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1;"))
        print("[OK] Connected to PostgreSQL database successfully.")
        return True
    except Exception as exc:
        print(f"[WARNING] Database connection failed: {exc}")
        print("\nEnsure Docker containers are running by executing:")
        print("  docker compose up -d")
        return False
    finally:
        await engine.dispose()


def run_alembic_upgrade():
    """Execute alembic upgrade head using alembic.ini configuration."""
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    ini_path = os.path.join(backend_dir, "alembic.ini")
    alembic_cfg = Config(ini_path)
    alembic_cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

    print("Running database migrations: alembic upgrade head...")
    command.upgrade(alembic_cfg, "head")
    print("[SUCCESS] Database schema migrated to latest head.")


if __name__ == "__main__":
    is_connected = asyncio.run(check_database())
    if is_connected:
        run_alembic_upgrade()
    else:
        print("\nMigration skipped because database is not running.")
        sys.exit(0)
