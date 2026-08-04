from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"
WEB_ROOTS = (
    REPO_ROOT / "backend" / "app" / "web_static",
    REPO_ROOT / "backend" / "app" / "landing_static",
)


def _matches(root: Path, suffix: str, pattern: re.Pattern[str]) -> list[str]:
    findings: list[str] = []
    if not root.exists():
        return findings
    for path in sorted(root.rglob(f"*{suffix}")):
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                findings.append(
                    f"{path.relative_to(REPO_ROOT)}:{line_number}: {line.strip()}"
                )
    return findings


def test_inventory_global_timezone_dependencies():
    app_timezone_calls = _matches(
        BACKEND_APP,
        ".py",
        re.compile(r"\bapp_timezone\s*\("),
    )
    app_timezone_imports = _matches(
        BACKEND_APP,
        ".py",
        re.compile(r"\bimport\s+app_timezone\b|\bapp_timezone\s*,|,\s*app_timezone\b"),
    )
    direct_clock_calls = _matches(
        BACKEND_APP,
        ".py",
        re.compile(r"\bdatetime\.now\s*\(|\bdate\.today\s*\("),
    )
    javascript_timezone_literals: list[str] = []
    for root in WEB_ROOTS:
        javascript_timezone_literals.extend(
            _matches(
                root,
                ".js",
                re.compile(
                    r"Europe/Moscow|Asia/Yekaterinburg|timeZone\s*:\s*['\"]"
                ),
            )
        )

    report = [
        "app_timezone calls:",
        *app_timezone_calls,
        "app_timezone imports:",
        *app_timezone_imports,
        "datetime.now/date.today calls requiring review:",
        *direct_clock_calls,
        "JavaScript timezone literals/options:",
        *javascript_timezone_literals,
    ]

    raise AssertionError("\n".join(report))
