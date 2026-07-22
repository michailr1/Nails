def test_calendar_fix_assets_are_loaded(client, clean_database):
    response = client.get("/web/")

    assert response.status_code == 200
    assert 'href="/web/web-calendar-fixes.css"' in response.text
    assert 'src="/web/web-calendar-fixes.js"' in response.text


def test_calendar_price_fix_shows_known_subtotal(client, clean_database):
    response = client.get("/web/web-calendar-fixes.js")

    assert response.status_code == 200
    assert 'return `от ${formatted}`' in response.text
    assert 'bookingCatalogPrice(booking) || "Цена после уточнения"' in response.text


def test_calendar_hides_technical_statuses(client, clean_database):
    response = client.get("/web/web-calendar-fixes.js")

    assert response.status_code == 200
    assert 'status === "cancelled"' in response.text
    assert 'status === "no_show"' in response.text
    assert ">Отменена<" in response.text
    assert ">Не пришла<" in response.text
    assert "escapeHtml(booking.status)" not in response.text
    assert ">scheduled<" not in response.text


def test_calendar_period_switch_uses_mobile_grid(client, clean_database):
    response = client.get("/web/web-calendar-fixes.css")

    assert response.status_code == 200
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in response.text
    assert "white-space: normal" in response.text
