from __future__ import annotations


def test_long_absent_action_assets_are_loaded(client, clean_database):
    response = client.get("/web/")

    assert response.status_code == 200
    assert 'href="/web/web-statistics-actions.css"' in response.text
    assert 'src="/web/web-statistics-actions.js"' in response.text


def test_long_absent_actions_open_client_card_and_only_offer_manual_call(
    client,
    clean_database,
):
    response = client.get("/web/web-statistics-actions.js")

    assert response.status_code == 200
    assert 'data-open-long-absent-client' in response.text
    assert 'state.view = "clients"' in response.text
    assert "await renderClients()" in response.text
    assert "webClientCardOpenId = clientId" in response.text
    assert 'api("/web/api/clients")' in response.text
    assert "function longAbsentPhoneUri(phone)" in response.text
    assert "/^\\+?\\d{5,15}$/" in response.text
    assert "link.href = phoneUri" in response.text
    assert 'link.textContent = "Позвонить"' in response.text
    assert "if (!client || !phoneUri) return" in response.text
    assert "sendMessage" not in response.text
    assert "POST" not in response.text


def test_long_absent_actions_fit_mobile_width(client, clean_database):
    response = client.get("/web/web-statistics-actions.css")

    assert response.status_code == 200
    assert "grid-template-columns: minmax(0, 1fr) auto" in response.text
    assert "grid-template-columns: 1fr" in response.text
    assert "flex: 1 1 auto" in response.text
