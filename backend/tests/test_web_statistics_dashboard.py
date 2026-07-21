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
    assert 'summary.revenue_amount' in response.text
    assert 'summary.estimated_revenue_amount' in response.text
    assert 'summary.unknown_price_count' in response.text
    assert 'Клиентки по выручке' in response.text
    assert 'Процедуры' in response.text
    assert 'Дополнения' in response.text
