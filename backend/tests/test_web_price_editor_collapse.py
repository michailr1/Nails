def test_web_price_editor_has_explicit_collapse_action(client, clean_database):
    response = client.get("/web/web-service-catalog.js")

    assert response.status_code == 200
    assert 'data-collapse-service="${index}"' in response.text
    assert ">Свернуть</button>" in response.text
    assert 'document.querySelectorAll("[data-collapse-service]")' in response.text
    assert "button.dataset.collapseService" in response.text
    assert 'block: "nearest"' in response.text
