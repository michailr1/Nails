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
    calls = [
        finding
        for finding in _matches(
            (BACKEND_APP,),
            ".py",
            re.compile(r"\bapp_timezone\s*\("),
        )
        if "def app_timezone()" not in finding
    ]
    imports = _matches(
        (BACKEND_APP,),
        ".py",
        re.compile(
            r"\bfrom\s+app\.services\.scheduling_common\s+import\s+app_timezone\b"
            r"|\bapp_timezone\s*,|,\s*app_timezone\b"
        ),
    )

    assert calls == [
        next(
            finding
            for finding in calls
            if finding.startswith("backend/app/client_bot_outbox.py:")
            and "timezone or app_timezone()" in finding
        )
    ]
    assert imports == [
        next(
            finding
            for finding in imports
            if finding.startswith("backend/app/client_bot_outbox.py:")
            and "import app_timezone" in finding
        )
    ]

    common_source = (
        BACKEND_APP / "services" / "scheduling_common.py"
    ).read_text(encoding="utf-8")
    assert "def app_timezone() -> ZoneInfo:" in common_source


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
        and "datetime.now(timezone.utc)" not in finding
        and not (
            finding.startswith("backend/app/services/scheduling_dates.py:")
            and "datetime.now(timezone)" in finding
        )
        and not (
            finding.startswith("backend/app/client_bot_booking_flow.py:")
            and (
                "datetime.now(ZoneInfo(timezone_name)).date()" in finding
                or "datetime.now(_draft_timezone(draft)).date()" in finding
            )
        )
        and not (
            finding.startswith("backend/app/client_bot.py:")
            and "start = today or date.today()" in finding
        )
    ]

    assert unexpected == []

    draft_source = (BACKEND_APP / "client_bot_booking_flow.py").read_text(
        encoding="utf-8"
    )
    assert "def _draft_timezone(draft: dict[str, Any]) -> ZoneInfo:" in draft_source
    assert "return ZoneInfo(timezone_name)" in draft_source
    assert "datetime.now(_draft_timezone(draft)).date()" in draft_source


def test_browser_has_no_hardcoded_owner_timezone():
    hardcoded: list[str] = []
    legacy_identifier: list[str] = []
    for root in WEB_ROOTS:
        hardcoded.extend(
            _matches(
                (root,),
                ".js",
                re.compile(
                    r"Europe/Moscow|Asia/Yekaterinburg|timeZone\s*:\s*['\"]"
                ),
            )
        )
        legacy_identifier.extend(
            _matches((root,), ".js", re.compile(r"\bAPP_TIMEZONE\b"))
        )

    assert len(hardcoded) == 1
    assert hardcoded[0].startswith("backend/app/web_static/app.js:")
    assert 'timeZone: "UTC"' in hardcoded[0]
    assert legacy_identifier == []

    app_source = (BACKEND_APP / "web_static" / "app.js").read_text(encoding="utf-8")
    assert "Europe/Moscow" not in app_source
    assert "/web/api/auth/session?include_timezone=true" in app_source
    assert "state.timezone = session.timezone" in app_source
