def test_calendar_fix_assets_are_loaded(client, clean_database):
    response = client.get("/web/")

    assert response.status_code == 200
    assert 'href="/web/web-calendar-fixes.css"' in response.text
    assert 'src="/web/web-calendar-fixes.js"' in response.text


def test_calendar_price_fix_shows_known_subtotal(client, clean_database):
    response = client.get("/web/web-calendar-fixes.js")

    assert response.status_code == 200
    assert 'return `от ${formatted}`' in response.text
    assert 'return "Цена после уточнения"' in response.text


def test_calendar_period_switch_uses_mobile_grid(client, clean_database):
    response = client.get("/web/web-calendar-fixes.css")

    assert response.status_code == 200
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in response.text
    assert "white-space: normal" in response.text
