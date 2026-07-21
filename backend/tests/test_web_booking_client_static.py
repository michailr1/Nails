def test_web_booking_inline_client_assets_are_served(client, clean_database):
    page = client.get("/web/")
    script = client.get("/web/web-booking-client-create.js")
    stylesheet = client.get("/web/web-booking-create.css")

    assert page.status_code == 200
    assert script.status_code == 200
    assert stylesheet.status_code == 200
    assert "/web/web-booking-client-create.js" in page.text
    assert page.text.index("/web/web001e-copy.js") < page.text.index(
        "/web/web-booking-client-create.js"
    )
    assert "+ Новая клиентка" in script.text
    assert 'api("/web/api/clients"' in script.text
    assert "Добавить клиентку" in script.text
    assert "bookingClientSelectCreated" in script.text
    assert "client.profile_status" in script.text
    assert "window.confirm" in script.text
    assert ".booking-client-field" in stylesheet.text
    assert ".booking-new-client-panel" in stylesheet.text
    assert ".booking-new-client-status" in stylesheet.text
