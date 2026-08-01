from pathlib import Path

STATIC = Path(__file__).parents[1] / "app" / "web_static"


def test_web_statistics_assets_are_loaded(client, clean_database):
    response = client.get("/web/")

    assert response.status_code == 200
    assert 'href="/web/web-statistics.css"' in response.text
    assert 'src="/web/web-statistics.js"' in response.text


def test_web_statistics_dashboard_uses_read_only_statistics_api(client, clean_database):
    response = client.get("/web/web-statistics.js")

    assert response.status_code == 200
    assert 'button.textContent = "Статистика"' in response.text
    assert 'state.view === "statistics"' in response.text
    assert "/web/api/statistics?date_from=" in response.text
    assert "summary.revenue_amount" in response.text
    assert "summary.assumed_visits_count" in response.text
    assert "summary.unknown_price_count" in response.text
    assert '<h2>По выручке</h2>' in response.text
    assert '<h2>Процедуры</h2>' in response.text
    assert '<h2>Дополнения</h2>' in response.text


def test_web_statistics_hides_internal_confirmation_language_from_metric_cards(
    client,
    clean_database,
):
    response = client.get("/web/web-statistics.js")

    assert response.status_code == 200
    assert "Из неё предварительно" not in response.text
    assert "Без ручного уточнения" not in response.text
    assert 'statisticCard("Выручка", formatMoney(summary.revenue_amount))' in response.text
    assert 'statisticCard("Визиты", String(summary.visits_count))' in response.text
    assert "учтены автоматически" in response.text


def test_web_statistics_mobile_layout_prevents_overflow_and_bottom_nav_overlap(
    client,
    clean_database,
):
    response = client.get("/web/web-statistics.css")
    base_css = (STATIC / "styles.css").read_text(encoding="utf-8")

    assert response.status_code == 200
    assert "grid-template-columns: repeat(4, minmax(0, 1fr));" in response.text
    assert ".main { padding: 24px 16px 96px; }" in base_css
    assert ".main" not in response.text
    assert "overflow-wrap: anywhere;" in response.text
    assert "overflow-x: auto;" in response.text
    assert "min-width: 36rem;" in response.text
