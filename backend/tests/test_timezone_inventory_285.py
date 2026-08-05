from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"
OPS_ROOT = REPO_ROOT / "ops"
WEB_ROOTS = (
    REPO_ROOT / "backend" / "app" / "web_static",
    REPO_ROOT / "backend" / "app" / "landing_static",
)


def _matches(roots: tuple[Path, ...], suffix: str, pattern: re.Pattern[str]) -> list[str]:
    findings: list[str] = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob(f"*{suffix}")):
            text = path.read_text(encoding="utf-8")
            for line_number, line in enumerate(text.splitlines(), start=1):
                if pattern.search(line):
                    findings.append(
                        f"{path.relative_to(REPO_ROOT)}:{line_number}: {line.strip()}"
                    )
    return findings


def test_global_timezone_helper_is_only_legacy_outbox_fallback():
    findings = _matches(
        (BACKEND_APP,),
        ".py",
        re.compile(r"\bapp_timezone\b"),
    )
    unexpected = [
        finding
        for finding in findings
        if not (
            finding.startswith("backend/app/services/scheduling_common.py:")
            and "def app_timezone() -> ZoneInfo:" in finding
        )
        and not (
            finding.startswith("backend/app/client_bot_outbox.py:")
            and (
                "app_timezone," in finding
                or "timezone or app_timezone()" in finding
            )
        )
    ]

    assert unexpected == []
    assert any("timezone or app_timezone()" in finding for finding in findings)


def test_direct_clocks_are_utc_or_explicit_owner_local():
    findings = _matches(
        (BACKEND_APP, OPS_ROOT),
        ".py",
        re.compile(r"\bdatetime\.now\s*\(|\bdate\.today\s*\("),
    )
    unexpected = [
        finding
        for finding in findings
        if "datetime.now(UTC)" not in finding
        and not (
            finding.startswith("backend/app/services/scheduling_dates.py:")
            and "datetime.now(timezone)" in finding
        )
        and not (
            finding.startswith("backend/app/client_bot_booking_flow.py:")
            and "datetime.now(ZoneInfo(timezone_name)).date()" in finding
        )
        and not (
            finding.startswith("backend/app/client_bot.py:")
            and "start = today or date.today()" in finding
        )
    ]

    assert unexpected == []


def test_browser_has_no_hardcoded_owner_timezone():
    findings: list[str] = []
    for root in WEB_ROOTS:
        findings.extend(
            _matches(
                (root,),
                ".js",
                re.compile(
                    r"Europe/Moscow|Asia/Yekaterinburg|timeZone\s*:\s*['\"]"
                ),
            )
        )

    assert len(findings) == 1
    assert findings[0].startswith("backend/app/web_static/app.js:")
    assert 'timeZone: "UTC"' in findings[0]

    app_source = (BACKEND_APP / "web_static" / "app.js").read_text(encoding="utf-8")
    assert "Europe/Moscow" not in app_source
    assert "APP_TIMEZONE" not in app_source
    assert "/web/api/auth/session?include_timezone=true" in app_source
    assert "state.timezone = session.timezone" in app_source
