#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("retention.py")
SPEC = importlib.util.spec_from_file_location("nails_backup_retention", MODULE_PATH)
assert SPEC and SPEC.loader
retention = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(retention)

WEB_AUTH_CONTRACT_PATH = Path(__file__).with_name(
    "test_web_auth_restore_contract.py"
)
WEB_AUTH_CONTRACT_SPEC = importlib.util.spec_from_file_location(
    "nails_web_auth_restore_contract",
    WEB_AUTH_CONTRACT_PATH,
)
assert WEB_AUTH_CONTRACT_SPEC and WEB_AUTH_CONTRACT_SPEC.loader
web_auth_restore_contract = importlib.util.module_from_spec(WEB_AUTH_CONTRACT_SPEC)
WEB_AUTH_CONTRACT_SPEC.loader.exec_module(web_auth_restore_contract)

NOW = datetime(2026, 7, 16, 12, tzinfo=timezone.utc)


class RetentionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "backups"
        self.runtime = Path(self.temp.name) / "runtime"
        for name in ("daily", "weekly", "monthly", "logs"):
            (self.root / name).mkdir(parents=True, exist_ok=True)
        self.runtime.mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def touch(self, path: Path, age: timedelta) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")
        timestamp = (NOW - age).timestamp()
        os.utime(path, (timestamp, timestamp))
        return path

    def run_policy(self) -> None:
        retention.apply_retention(self.root, self.runtime, apply=True, now=NOW)

    def test_daily_weekly_monthly_limits_and_same_day_deduplication(self) -> None:
        for day in range(7):
            stamp = (NOW - timedelta(days=day)).strftime("%Y%m%d")
            self.touch(
                self.root / "daily" / f"nails-{stamp}T010000Z.sql.gz",
                timedelta(days=day, hours=2),
            )
            self.touch(
                self.root / "daily" / f"nails-{stamp}T020000Z.sql.gz",
                timedelta(days=day, hours=1),
            )
        for index in range(5):
            self.touch(
                self.root / "weekly" / f"nails-2026-W{index:02d}.sql.gz",
                timedelta(weeks=index),
            )
        for index in range(14):
            self.touch(
                self.root / "monthly" / f"nails-2025{index + 1:02d}.sql.gz",
                timedelta(days=index * 30),
            )

        self.run_policy()

        self.assertEqual(len(list((self.root / "daily").glob("*"))), 5)
        self.assertEqual(len(list((self.root / "weekly").glob("*"))), 3)
        self.assertEqual(len(list((self.root / "monthly").glob("*"))), 12)

    def test_predeploy_keeps_all_24h_then_one_per_day_for_five_days(self) -> None:
        recent_a = self.touch(
            self.root / "nails-before-deploy-a.sql.gz",
            timedelta(hours=2),
        )
        recent_b = self.touch(
            self.root / "nails-before-deploy-b.sql.gz",
            timedelta(hours=20),
        )
        old_same_day_a = self.touch(
            self.root / "nails-before-deploy-c.sql.gz",
            timedelta(days=2, hours=3),
        )
        old_same_day_b = self.touch(
            self.root / "nails-before-deploy-d.sql.gz",
            timedelta(days=2, hours=1),
        )
        expired = self.touch(
            self.root / "nails-before-deploy-e.sql.gz",
            timedelta(days=6),
        )

        self.run_policy()

        self.assertTrue(recent_a.exists())
        self.assertTrue(recent_b.exists())
        self.assertFalse(old_same_day_a.exists())
        self.assertTrue(old_same_day_b.exists())
        self.assertFalse(expired.exists())

    def test_runtime_keeps_two_successes_failed_three_days_and_local_patches(
        self,
    ) -> None:
        for index in range(4):
            self.touch(
                self.runtime / f"deploy-success-{index}",
                timedelta(hours=index + 1),
            )
        failed_recent = self.touch(
            self.runtime / "deploy-failed-recent",
            timedelta(days=2),
        )
        failed_old = self.touch(
            self.runtime / "deploy-failed-old",
            timedelta(days=4),
        )
        patches = self.touch(
            self.runtime / "hermes-local-patches",
            timedelta(days=100),
        )

        self.run_policy()

        self.assertEqual(len(list(self.runtime.glob("deploy-success-*"))), 2)
        self.assertTrue(failed_recent.exists())
        self.assertFalse(failed_old.exists())
        self.assertTrue(patches.exists())

    def test_dry_run_does_not_remove(self) -> None:
        expired = self.touch(self.root / "logs" / "old.log", timedelta(days=20))
        retention.apply_retention(self.root, self.runtime, apply=False, now=NOW)
        self.assertTrue(expired.exists())

    def test_web_auth_tables_are_covered_by_restore_contract(self) -> None:
        web_auth_restore_contract.main()


if __name__ == "__main__":
    unittest.main()
