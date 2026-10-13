"""
Regression suite: database connection URLs must never leak credentials into logs.
Verifies:
1. describe_database_url() keeps driver, host, port and database name but drops
   username, password and query parameters (including URL-encoded secrets).
2. redact_credentials() masks URL user-info and password=... pairs in free text.
3. init_db() fallback warning: when PostgreSQL is unreachable, the emitted log
   records contain no username/password while still naming host, port and DB.
   Runs in a subprocess with a throwaway working directory so the SQLite
   fallback file is created there and no real database is touched.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from app.core.redaction import describe_database_url, redact_credentials

BACKEND_DIR = Path(__file__).resolve().parent
SECRET_USER = "leaky_user_7f3a"
SECRET_PASSWORD = "S3cr3t-Pa55w0rd-9q2z"


def test_describe_database_url() -> None:
    cases = {
        f"postgresql+asyncpg://{SECRET_USER}:{SECRET_PASSWORD}@db.internal:5433/intel":
            "postgresql+asyncpg://***@db.internal:5433/intel",
        # URL-encoded password containing '@' and ':'
        f"postgresql://{SECRET_USER}:p%40ss%3A{SECRET_PASSWORD}@localhost/intel":
            "postgresql://***@localhost/intel",
        # credentials passed as query parameters
        f"postgresql://localhost:5432/intel?user={SECRET_USER}&password={SECRET_PASSWORD}":
            "postgresql://localhost:5432/intel",
        "postgresql+asyncpg://localhost:5432/intel": "postgresql+asyncpg://localhost:5432/intel",
        "sqlite+aiosqlite:///intelligence_os_dev.db": "sqlite+aiosqlite:///intelligence_os_dev.db",
        "not a url": "<unparseable database URL>",
    }
    for raw, expected in cases.items():
        got = describe_database_url(raw)
        assert got == expected, f"describe_database_url({raw!r}) -> {got!r}, expected {expected!r}"
        assert SECRET_USER not in got and SECRET_PASSWORD not in got
    print("  [OK] describe_database_url keeps diagnostics and drops credentials")


def test_redact_credentials() -> None:
    samples = [
        f"could not connect to postgresql://{SECRET_USER}:{SECRET_PASSWORD}@10.0.0.5:5432/intel",
        f"redis://:{SECRET_PASSWORD}@cache:6379/0 refused",
        f"dsn: host=db password={SECRET_PASSWORD} dbname=intel",
        f"options password='{SECRET_PASSWORD}' sslmode=require",
        f"PWD: {SECRET_PASSWORD}",
    ]
    for text in samples:
        out = redact_credentials(text)
        assert SECRET_PASSWORD not in out, f"password leaked: {out!r}"
        assert SECRET_USER not in out, f"username leaked: {out!r}"
    assert redact_credentials("connection refused on localhost:5432") == "connection refused on localhost:5432"
    assert "10.0.0.5:5432/intel" in redact_credentials(samples[0]), "host/port/db should be preserved"
    print("  [OK] redact_credentials masks user-info and password pairs, keeps context")


CHILD_SCRIPT = r"""
import asyncio, logging, sys
records = []
class Collect(logging.Handler):
    def emit(self, record):
        records.append(self.format(record))
handler = Collect()
handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
root = logging.getLogger()
root.addHandler(handler)
root.setLevel(logging.DEBUG)

from app.core import database
asyncio.run(database.init_db())
print("ENGINE_DRIVER=" + database.engine.url.drivername)
print("<<<LOGS>>>")
print("\n".join(records))
"""


def test_init_db_fallback_warning_is_redacted() -> None:
    with tempfile.TemporaryDirectory() as workdir:
        env = dict(os.environ)
        # Port 1 on loopback refuses immediately; credentials are fake secrets.
        env["DATABASE_URL"] = (
            f"postgresql+asyncpg://{SECRET_USER}:{SECRET_PASSWORD}@127.0.0.1:1/intel_redaction_probe"
        )
        env["DEBUG"] = "false"
        env["PYTHONPATH"] = str(BACKEND_DIR) + os.pathsep + env.get("PYTHONPATH", "")
        proc = subprocess.run(
            [sys.executable, "-c", CHILD_SCRIPT],
            cwd=workdir,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = proc.stdout + proc.stderr
        assert proc.returncode == 0, f"init_db subprocess failed:\n{output[-2000:]}"
        assert "ENGINE_DRIVER=sqlite+aiosqlite" in proc.stdout, "expected SQLite fallback engine"
        assert Path(workdir, "intelligence_os_dev.db").exists(), "fallback DB should be created in temp dir"

        assert SECRET_PASSWORD not in output, "password leaked into logs/output"
        assert SECRET_USER not in output, "username leaked into logs/output"

        logs = proc.stdout.split("<<<LOGS>>>", 1)[1]
        warning = next((line for line in logs.splitlines() if "PostgreSQL connection to" in line), None)
        assert warning is not None, "fallback warning was not emitted"
        assert "postgresql+asyncpg://***@127.0.0.1:1/intel_redaction_probe" in warning, warning
        assert "Switching to local persistent SQLite database" in warning, warning
    print("  [OK] init_db fallback warning is redacted and keeps host/port/database")


if __name__ == "__main__":
    print("=" * 75)
    print("INTELLIGENCE OS - DATABASE URL LOG REDACTION TESTS")
    print("=" * 75)
    test_describe_database_url()
    test_redact_credentials()
    test_init_db_fallback_warning_is_redacted()
    print("=" * 75)
    print("ALL LOG REDACTION TESTS PASSED!")
    print("=" * 75)
