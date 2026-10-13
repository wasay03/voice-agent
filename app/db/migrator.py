"""Apply everything under `sql/` to the database. Run before the app starts:

    python -m app.db.migrator

Three kinds of files (see sql/migrations/README.md):

* Baseline, applied once to a fresh database, in order: types/ -> models/ -> indexes.sql -> seed/.
  The model files describe the *current* table shapes, so every versioned migration that already
  exists is marked as applied at baseline time.
* Versioned, `migrations/NNNN_*.sql`: applied once each on existing databases; editing an
  applied file fails the run.
* Repeatable, triggers/ functions/ procedures/: `CREATE OR REPLACE` files re-applied whenever
  their checksum changes. indexes.sql is idempotent and re-run every time.

Everything happens in one transaction under an advisory lock, so a failed run changes nothing
and two instances can never migrate at once. This is infrastructure, not a repository, so it
runs DDL directly.
"""

import asyncio
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import asyncpg

from app.core.config import get_settings, normalize_dsn
from app.core.logging import configure_logging, get_logger

log = get_logger("migrator")

SQL_DIR = Path(__file__).resolve().parents[2] / "sql"
BOOKKEEPING_FILE = "models/000_schema_migrations.sql"
BASELINE_GLOBS = ("types/*.sql", "models/*.sql", "indexes.sql", "seed/*.sql")
VERSIONED_GLOB = "migrations/*.sql"
REPEATABLE_GLOBS = ("triggers/*.sql", "functions/*.sql", "procedures/*.sql")
ADVISORY_LOCK_KEY = 0x5A11_7A6E  # arbitrary, constant for this application


class MigrationError(RuntimeError):
    pass


@dataclass
class MigrationReport:
    baseline_applied: bool = False
    versioned: list[str] = field(default_factory=list)
    repeatable: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SqlFile:
    name: str
    sql: str

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.sql.encode()).hexdigest()


def _collect(sql_dir: Path, *globs: str) -> list[SqlFile]:
    files: list[SqlFile] = []
    for pattern in globs:
        for path in sorted(sql_dir.glob(pattern)):
            files.append(SqlFile(path.relative_to(sql_dir).as_posix(), path.read_text(encoding="utf-8")))
    return files


async def _record(conn: asyncpg.Connection, name: str, kind: str, checksum: str) -> None:
    await conn.execute(
        """
        INSERT INTO schema_migrations (name, kind, checksum) VALUES ($1, $2, $3)
        ON CONFLICT (name) DO UPDATE SET checksum = EXCLUDED.checksum, applied_at = now()
        """,
        name,
        kind,
        checksum,
    )


async def _apply(conn: asyncpg.Connection, file: SqlFile) -> None:
    try:
        await conn.execute(file.sql)
    except asyncpg.PostgresError as exc:
        raise MigrationError(f"{file.name}: {exc}") from exc


async def migrate(dsn: str, sql_dir: Path = SQL_DIR) -> MigrationReport:
    report = MigrationReport()
    conn = await asyncpg.connect(normalize_dsn(dsn))
    try:
        async with conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock($1)", ADVISORY_LOCK_KEY)
            await conn.execute((sql_dir / BOOKKEEPING_FILE).read_text(encoding="utf-8"))
            rows = await conn.fetch("SELECT name, checksum FROM schema_migrations")
            applied = {r["name"]: r["checksum"] for r in rows}
            versioned = _collect(sql_dir, VERSIONED_GLOB)

            if "baseline" not in applied:
                baseline = [f for f in _collect(sql_dir, *BASELINE_GLOBS) if f.name != BOOKKEEPING_FILE]
                for file in baseline:
                    await _apply(conn, file)
                digest = hashlib.sha256("".join(f.checksum for f in baseline).encode()).hexdigest()
                await _record(conn, "baseline", "baseline", digest)
                for file in versioned:  # the model files already include these changes
                    await _record(conn, file.name, "versioned", file.checksum)
                report.baseline_applied = True
            else:
                for file in versioned:
                    if file.name in applied:
                        if applied[file.name] != file.checksum:
                            raise MigrationError(
                                f"{file.name} was edited after being applied; add a new migration"
                            )
                        continue
                    await _apply(conn, file)
                    await _record(conn, file.name, "versioned", file.checksum)
                    report.versioned.append(file.name)

            # Routines may reference each other; validate bodies at call time, not creation time.
            await conn.execute("SET LOCAL check_function_bodies = off")
            for file in _collect(sql_dir, *REPEATABLE_GLOBS):
                if applied.get(file.name) != file.checksum:
                    await _apply(conn, file)
                    await _record(conn, file.name, "repeatable", file.checksum)
                    report.repeatable.append(file.name)

            indexes = sql_dir / "indexes.sql"
            if indexes.exists():
                await _apply(conn, SqlFile("indexes.sql", indexes.read_text(encoding="utf-8")))
    finally:
        await conn.close()
    return report


async def _main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, json_logs=settings.json_logs)
    report = await migrate(settings.database_url)
    log.info(
        "migrations.done",
        baseline_applied=report.baseline_applied,
        versioned=report.versioned,
        repeatable=report.repeatable,
    )


if __name__ == "__main__":
    asyncio.run(_main())
