from __future__ import annotations


def test_statistics_revenue_asset_is_loaded(client, clean_database):
    response = client.get("/web/")

    assert response.status_code == 200
    assert 'src="/web/web-statistics-revenue.js"' in response.text


def test_statistics_revenue_bars_use_money_not_visit_count(client, clean_database):
    response = client.get("/web/web-statistics-revenue.js")

    assert response.status_code == 200
    assert "Number(item.revenue_amount)" in response.text
    assert "formatMoney(item.revenue_amount)" in response.text
    assert "item.visits_count / max" not in response.text
    assert 'label.textContent = "Вклад в выручку"' in response.text


def test_statistics_revenue_copy_explains_attribution_boundary(client, clean_database):
    response = client.get("/web/web-statistics-revenue.js")

    assert response.status_code == 200
    assert "Только записи, где цену можно честно распределить по составу." in response.text
    assert "Пока нет записей с ценой, которую можно распределить по позициям." in response.text
