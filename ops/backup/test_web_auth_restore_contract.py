from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "backend/alembic/versions/0009_add_web_auth.py"
BACKUP_SCRIPT = ROOT / "ops/backup/backup.sh"

REQUIRED_TABLES = (
    "web_login_challenges",
    "web_sessions",
    "web_auth_rate_buckets",
)


def main() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    backup_script = BACKUP_SCRIPT.read_text(encoding="utf-8")

    for table in REQUIRED_TABLES:
        assert table in migration
        assert migration.count(table) >= 3

    assert backup_script.count("pg_tables") == 2
    assert backup_script.count("ORDER BY tablename") == 2
    assert "RESTORE_COUNTS" in backup_script
    assert "SOURCE_COUNTS" in backup_script
    assert "RESTORE_ALEMBIC" in backup_script
    assert "SOURCE_ALEMBIC" in backup_script

    print("WEB_AUTH_BACKUP_RESTORE_CONTRACT_OK")


if __name__ == "__main__":
    main()
