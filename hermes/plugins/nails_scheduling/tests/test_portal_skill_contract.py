from pathlib import Path


def _portal_skill_text() -> str:
    skill_path = (
        Path(__file__).resolve().parents[3]
        / "skills"
        / "nails-portal"
        / "SKILL.md"
    )
    return skill_path.read_text(encoding="utf-8")


def test_portal_skill_has_exact_command_and_master_cabinet_url() -> None:
    text = _portal_skill_text()

    assert "exact Telegram command `/portal`" in text
    assert "Личный кабинет мастера: https://de.funti.cc" in text
    assert "Do not call tools" in text
    assert "public client portal" in text


def test_portal_skill_has_final_newline() -> None:
    assert _portal_skill_text().endswith("\n")
