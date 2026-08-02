from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "backend" / "app" / "web_static"
INDEX = WEB / "index.html"
PERSONAL_LINK = WEB / "web-personal-link.js"
SHELL_CSS = WEB / "web-shell-ui.css"


def test_personal_link_controller_loads_after_reachability():
    index = INDEX.read_text(encoding="utf-8")

    assert "/web/web-personal-link.js" in index
    assert index.index("/web/web-client-reachability.js") < index.index(
        "/web/web-personal-link.js"
    )


def test_personal_link_is_a_collapsible_disclosure():
    source = PERSONAL_LINK.read_text(encoding="utf-8")

    assert 'button.textContent = "Получить ссылку"' in source
    assert 'trigger.textContent = "Скрыть"' in source
    assert 'trigger.setAttribute("aria-expanded", "true")' in source
    assert 'trigger.setAttribute("aria-expanded", "false")' in source
    assert "closePersonalLink(actions)" in source
    assert "client-personal-invite-block" in source
    assert "data-close-personal-link" in source
    assert "data-copy-personal-link" in source
    assert "prompt(" not in source


def test_personal_link_copy_explains_the_real_user_outcome():
    source = PERSONAL_LINK.read_text(encoding="utf-8")

    assert "Подключить клиентку к Telegram" in source
    assert "подключится к вашему Telegram-боту" in source
    assert "сможет пользоваться записью" in source
    assert "Откроется только для этой карточки" not in source


def test_personal_link_reuses_cached_url_and_does_not_stack_blocks():
    source = PERSONAL_LINK.read_text(encoding="utf-8")

    assert "button.dataset.personalInviteUrl" in source
    assert "actions.querySelector(PERSONAL_LINK_BLOCK_SELECTOR)?.remove()" in source
    assert "actions.append(block)" in source
    assert "event.stopImmediatePropagation()" in source


def test_personal_link_has_inner_spacing_and_readable_copy():
    css = SHELL_CSS.read_text(encoding="utf-8")

    actions = css.split(".client-reachability-actions {", 1)[1].split("}", 1)[0]
    help_text = css.split(".client-personal-link-help {", 1)[1].split("}", 1)[0]
    block = css.split(".client-invite-block {", 1)[1].split("}", 1)[0]

    assert "padding: 18px 20px 20px" in actions
    assert "max-width: 38rem" in help_text
    assert "line-height: 1.55" in help_text
    assert "padding: 18px" in block


def test_long_absent_actions_share_one_box_model():
    css = SHELL_CSS.read_text(encoding="utf-8")

    assert ".long-absent-actions > .secondary-button" in css
    assert '.long-absent-actions > [data-client-remind] > .secondary-button' in css
    assert "display: inline-flex" in css
    assert "min-height: 48px" in css
    assert "align-items: center" in css
    assert "justify-content: center" in css
    assert "line-height: 1.15" in css
    assert '.long-absent-actions > [data-open-long-absent-client]' in css
    assert "grid-column: 1 / -1" in css
