from __future__ import annotations


def test_calendar_price_fallback_uses_current_price_catalog(client, clean_database):
    response = client.get("/web/web-calendar-fixes.js")

    assert response.status_code == 200
    assert 'apiWithoutCalendarPriceFallback("/web/api/services")' in response.text
    assert "calendarServicePriceIndex" in response.text
    assert "bookingCatalogPrice" in response.text
    assert "return bookingCatalogPrice(booking)" in response.text


def test_long_absent_calendar_insight_has_human_copy(client, clean_database):
    index = client.get("/web/")
    response = client.get("/web/web-insight-copy-fix.js")

    assert index.status_code == 200
    assert 'src="/web/web-insight-copy-fix.js"' in index.text
    assert response.status_code == 200
    assert 'return "Давно не была 1 клиентка"' in response.text
    assert 'label.textContent = "Нэйли подсказывает"' in response.text
    assert "— посмотреть" not in response.text


def test_long_absent_calendar_insight_stacks_cleanly_on_mobile(client, clean_database):
    response = client.get("/web/web-statistics-insight.css")

    assert response.status_code == 200
    assert "grid-template-columns: minmax(0, 1fr) auto" in response.text
    assert ".naily-insight strong" in response.text
    assert "line-height: 1.25" in response.text
