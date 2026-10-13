# Changing the schema

`app/db/migrator.py` treats `sql/` as three kinds of files:

| Kind | Files | Applied |
|---|---|---|
| Baseline | `types/`, `models/`, `indexes.sql`, `seed/` | Once, on a fresh database |
| Versioned | `migrations/NNNN_<change>.sql` | Once each, on databases that already have the baseline |
| Repeatable | `triggers/`, `functions/`, `procedures/` | Whenever the file's checksum changes |

**To change a table**, do both:

1. Edit `models/<table>.sql` so it shows the table's *current* shape (fresh databases are built from it).
2. Add `migrations/NNNN_<change>.sql` with the `ALTER` that moves an existing database to that shape.

A fresh database marks every existing migration as applied, because the model files already
include those changes. Never edit a migration that has been applied; add a new one.

**To change a function or procedure**, edit its file. If the signature or return type changes,
start the file with `DROP FUNCTION IF EXISTS ...` / `DROP PROCEDURE IF EXISTS ...` for the old
signature, because `CREATE OR REPLACE` cannot change either.

**To add an index**, add it to `indexes.sql` with `IF NOT EXISTS`. No migration is needed.
