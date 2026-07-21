def test_web_booking_composer_assets_are_served(client, clean_database):
    page = client.get("/web/")
    script = client.get("/web/web-booking-create.js")
    overlap_script = client.get("/web/web-booking-overlap-details.js")
    stylesheet = client.get("/web/web-booking-create.css")

    assert page.status_code == 200
    assert script.status_code == 200
    assert overlap_script.status_code == 200
    assert stylesheet.status_code == 200
    assert "/web/web-booking-create.css" in page.text
    assert "/web/web-booking-create.js" in page.text
    assert "/web/web-booking-overlap-details.js" in page.text
    assert page.text.index("/web/web-service-catalog.js") < page.text.index(
        "/web/web-booking-create.js"
    )
    assert page.text.index("/web/web-booking-create.js") < page.text.index(
        "/web/web-booking-overlap-details.js"
    )
    assert page.text.index("/web/web-booking-overlap-details.js") < page.text.index(
        "/web/web001e-copy.js"
    )
    assert "Добавить запись" in script.text
    assert 'api("/web/api/bookings"' in script.text
    assert "addon_names" in script.text
    assert "price_override_amount" in script.text
    assert "duration_override_minutes" in script.text
    assert "idempotency_key" in script.text
    assert "Создать запись?" in script.text
    assert "bookingResultMatches" in script.text
    assert "Цена уточняется" in script.text
    assert "Только просмотр" not in script.text
    assert "bookingMutationApi" in overlap_script.text
    assert "error.details" in overlap_script.text
    assert "Клиентка:" in overlap_script.text
    assert "Процедура:" in overlap_script.text
    assert "Запись:" in overlap_script.text
    assert "С учётом времени до/после занято:" in overlap_script.text
    assert ".booking-composer" in stylesheet.text
    assert ".booking-addon-group" in stylesheet.text
    assert ".booking-create-summary" in stylesheet.text
