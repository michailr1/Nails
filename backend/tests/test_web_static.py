from conftest import WEB_ORIGIN_HEADERS


def test_web_master_interface_is_served(client, clean_database):
    response = client.get("/web/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Нэйли — кабинет мастера" in response.text
    assert "/web/app.js" in response.text
    assert "prototype" not in response.text.lower()


def test_web_assets_are_served(client, clean_database):
    script = client.get("/web/app.js")
    stylesheet = client.get("/web/styles.css")

    assert script.status_code == 200
    assert stylesheet.status_code == 200
    assert "fetch(path" in script.text
    assert "--primary" in stylesheet.text


def test_web_api_routes_take_precedence_over_static_mount(client, clean_database):
    response = client.get(
        "/web/api/auth/session",
        headers=WEB_ORIGIN_HEADERS,
    )

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"detail": {"code": "unauthorized"}}
