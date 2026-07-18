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
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WEB_PROXY_PATH = REPOSITORY_ROOT / "backend" / "app" / "web_proxy.py"
WEB_PROXY_SPEC = importlib.util.spec_from_file_location(
    "nails_web_proxy",
    WEB_PROXY_PATH,
)
assert WEB_PROXY_SPEC and WEB_PROXY_SPEC.loader
web_proxy = importlib.util.module_from_spec(WEB_PROXY_SPEC)
WEB_PROXY_SPEC.loader.exec_module(web_proxy)


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

    def test_untrusted_peer_cannot_spoof_forwarded_ip(self) -> None:
        resolved = web_proxy.resolve_client_ip(
            peer_ip="192.0.2.10",
            x_real_ip="192.0.2.20",
            x_forwarded_for="192.0.2.20",
            trusted_proxy_cidrs=("172.18.0.0/16",),
        )
        self.assertEqual(resolved, "192.0.2.10")

    def test_trusted_peer_accepts_one_consistent_client_ip(self) -> None:
        resolved = web_proxy.resolve_client_ip(
            peer_ip="172.18.0.5",
            x_real_ip="192.0.2.20",
            x_forwarded_for="192.0.2.20",
            trusted_proxy_cidrs=("172.18.0.0/16",),
        )
        self.assertEqual(resolved, "192.0.2.20")

    def test_trusted_peer_rejects_forwarded_chain(self) -> None:
        resolved = web_proxy.resolve_client_ip(
            peer_ip="172.18.0.5",
            x_real_ip="192.0.2.20",
            x_forwarded_for="192.0.2.30, 192.0.2.20",
            trusted_proxy_cidrs=("172.18.0.0/16",),
        )
        self.assertEqual(resolved, "172.18.0.5")

    def test_trusted_peer_rejects_inconsistent_headers(self) -> None:
        resolved = web_proxy.resolve_client_ip(
            peer_ip="172.18.0.5",
            x_real_ip="192.0.2.20",
            x_forwarded_for="192.0.2.30",
            trusted_proxy_cidrs=("172.18.0.0/16",),
        )
        self.assertEqual(resolved, "172.18.0.5")

    def test_web_edge_contract(self) -> None:
        compose = (REPOSITORY_ROOT / "compose.yaml").read_text(encoding="utf-8")
        nginx = (REPOSITORY_ROOT / "web" / "nginx.conf").read_text(
            encoding="utf-8"
        )
        dockerfile = (REPOSITORY_ROOT / "web" / "Dockerfile").read_text(
            encoding="utf-8"
        )
        caddy_disabled = (
            REPOSITORY_ROOT / "ops" / "edge" / "nails-web.Caddyfile"
        ).read_text(encoding="utf-8")
        caddy_enabled = (
            REPOSITORY_ROOT / "ops" / "edge" / "nails-web.enabled.Caddyfile"
        ).read_text(encoding="utf-8")

        for fragment in (
            '${NAILS_API_BIND:-127.0.0.1}:${NAILS_API_PORT:-8210}:8000',
            '${NAILS_WEB_BIND:-127.0.0.1}:${NAILS_WEB_PORT:-8220}:8080',
            "WEB_AUTH_ENABLED: ${WEB_AUTH_ENABLED:-false}",
            "WEB_AUTH_HMAC_KEY: ${WEB_AUTH_HMAC_KEY:-}",
            "WEB_TRUSTED_PROXY_CIDRS: ${WEB_TRUSTED_PROXY_CIDRS:-}",
            "nails-web:",
        ):
            self.assertIn(fragment, compose)

        self.assertIn("location ^~ /web/api/auth/", nginx)
        self.assertIn("location ^~ /web/api/", nginx)
        self.assertIn("resolver 127.0.0.11 valid=10s ipv6=off;", nginx)
        self.assertIn("set $api_upstream http://nails-api:8000;", nginx)
        self.assertEqual(nginx.count("proxy_pass $api_upstream;"), 2)
        self.assertNotIn("proxy_pass http://nails-api:8000;", nginx)
        self.assertNotIn("/api/v1/", nginx)
        self.assertIn("client_max_body_size 16k;", nginx)
        self.assertIn("limit_req zone=web_auth", nginx)
        self.assertIn("set_real_ip_from 172.18.0.1;", nginx)
        self.assertIn("real_ip_recursive off;", nginx)
        self.assertIn("proxy_set_header X-Forwarded-For $remote_addr;", nginx)
        self.assertNotIn("$proxy_add_x_forwarded_for", nginx)
        self.assertIn("frame-ancestors 'none'", nginx)

        self.assertIn('respond "web interface unavailable" 503', caddy_disabled)
        self.assertNotIn("reverse_proxy", caddy_disabled)
        self.assertIn("reverse_proxy 127.0.0.1:8220", caddy_enabled)
        self.assertIn("header_up X-Real-IP {remote_host}", caddy_enabled)
        self.assertIn("header_up X-Forwarded-For {remote_host}", caddy_enabled)

        self.assertTrue(
            dockerfile.startswith("FROM nginxinc/nginx-unprivileged:")
        )
        self.assertIn("EXPOSE 8080", dockerfile)
        self.assertIn("HEALTHCHECK", dockerfile)
        self.assertIn("/web-health", dockerfile)


if __name__ == "__main__":
    unittest.main()
