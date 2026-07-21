def test_web_client_card_editor_assets_are_served(client, clean_database):
    page = client.get("/web/")
    script = client.get("/web/web-client-cards.js")
    stylesheet = client.get("/web/web-client-cards.css")

    assert page.status_code == 200
    assert script.status_code == 200
    assert stylesheet.status_code == 200
    assert "/web/web-client-cards.css" in page.text
    assert "/web/web-client-cards.js" in page.text
    assert page.text.index("/web/web-booking-client-create.js") < page.text.index(
        "/web/web-client-cards.js"
    )
    assert "Карточка клиентки" in script.text
    assert "Сохранить изменения" in script.text
    assert "WEB_CLIENT_FIELD_LABELS" in script.text
    assert "window.confirm" in script.text
    assert 'method: "PUT"' in script.text
    assert "webClientResultMatches" in script.text
    assert "client_name_conflict" in script.text
    assert "редактирование в кабинете появится" not in script.text
    assert ".client-card-editor" in stylesheet.text
    assert ".client-card-section-grid" in stylesheet.text
    assert ".client-card-actions" in stylesheet.text
