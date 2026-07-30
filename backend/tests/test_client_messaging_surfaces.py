from __future__ import annotations

from pathlib import Path

WEB_STATIC = Path(__file__).resolve().parents[1] / "app" / "web_static"


def test_contextual_messaging_surfaces_exist_without_campaign_section():
    source = (WEB_STATIC / "web-client-send-surfaces.js").read_text(encoding="utf-8")
    assert "Показать клиенткам" in source
    assert "Напомнить" in source
    assert "Написать" in source
    assert "disabled" in source
    assert "Рассылки" not in source


def test_contextual_surfaces_do_not_call_proactive_send_api():
    source = (WEB_STATIC / "web-client-send-surfaces.js").read_text(encoding="utf-8")
    assert "api(" not in source
    assert "fetch(" not in source


def test_contextual_messaging_module_is_loaded_after_feature_modules():
    index = (WEB_STATIC / "index.html").read_text(encoding="utf-8")
    position = index.index("/web/web-client-send-surfaces.js")
    assert position > index.index("/web/web-service-catalog.js")
    assert position > index.index("/web/web-client-cards.js")
    assert position > index.index("/web/web-statistics-actions.js")
