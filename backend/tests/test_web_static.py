from conftest import WEB_ORIGIN_HEADERS


def test_web_master_interface_is_served(client, clean_database):
    response = client.get("/web/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cache-control"] == "no-store"
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "Нэйли — кабинет мастера" in response.text
    assert "/web/web-auth-bootstrap.js" in response.text
    assert "/web/app.js" in response.text
    assert "/web/web-service-catalog.js" in response.text
    assert "/web/web001e-copy.js" in response.text
    assert 'type="module"' not in response.text
    assert response.text.index("/web/web-auth-bootstrap.js") < response.text.index(
        "/web/app.js"
    )
    assert response.text.index("/web/app.js") < response.text.index(
        "/web/web-service-catalog.js"
    )
    assert response.text.index("/web/web-service-catalog.js") < response.text.index(
        "/web/web001e-copy.js"
    )
    assert "prototype" not in response.text.lower()


def test_web_assets_are_served(client, clean_database):
    bootstrap = client.get("/web/web-auth-bootstrap.js")
    script = client.get("/web/app.js")
    catalog_editor = client.get("/web/web-service-catalog.js")
    login_enhancements = client.get("/web/web001e-copy.js")
    stylesheet = client.get("/web/styles.css")

    assert bootstrap.status_code == 200
    assert script.status_code == 200
    assert catalog_editor.status_code == 200
    assert login_enhancements.status_code == 200
    assert stylesheet.status_code == 200
    assert 'LOGIN_CHALLENGE_BOOTSTRAP_KEY = "nails.web-login.pending-challenge"' in (
        bootstrap.text
    )
    assert "gateSessionBootstrap" in bootstrap.text
    assert 'pathname === "/web/api/auth/session"' in bootstrap.text
    assert "gatedSessionRequest" in bootstrap.text
    assert "releaseSessionCheck()" in bootstrap.text
    assert "nativeFetch(input, options).then(resolve, reject)" in bootstrap.text
    assert "return false;" in bootstrap.text
    assert "return true;" in bootstrap.text
    assert "fetch(path" in script.text
    assert 'calendarMode: "day"' in script.text
    assert '["week", "Неделя"]' in script.text
    assert '["month", "Месяц"]' in script.text
    assert "/web/api/exports/calendar/all" in script.text
    assert "Выгрузить всех клиенток" in script.text
    assert "Не заполнено" in script.text
    assert 'state.view !== "services"' in catalog_editor.text
    assert 'api("/web/api/services")' in catalog_editor.text
    assert 'api("/web/api/services/catalog"' in catalog_editor.text
    assert "Сохранить весь каталог?" in catalog_editor.text
    assert "result.verified !== true" in catalog_editor.text
    assert "current → future" not in catalog_editor.text
    assert "Поля цены появятся только когда они нужны." in catalog_editor.text
    assert "Поля с пометкой «необязательно» можно оставить пустыми." in (
        catalog_editor.text
    )
    assert '"sort_order", "Порядок"' not in catalog_editor.text
    assert 'service.price_type === "per_unit"' in catalog_editor.text
    assert 'service.price_type === "range"' in catalog_editor.text
    assert "За что цена" in catalog_editor.text
    assert "Помогает группировать услуги" in catalog_editor.text
    assert 'TELEGRAM_BOT_USERNAME = "smartnails_bot"' in login_enhancements.text
    assert 'LOGIN_CHALLENGE_STORAGE_KEY = "nails.web-login.pending-challenge"' in (
        login_enhancements.text
    )
    assert "Отправить код Нэйли" in login_enhancements.text
    assert "Нэйли, подтверждаю вход:" in login_enhancements.text
    assert "это сразу подтвердит вход" in login_enhancements.text
    assert "Telegram откроется отдельно" in login_enhancements.text
    assert "кабинет откроется автоматически" in login_enhancements.text
    assert "https://t.me/${TELEGRAM_BOT_USERNAME}?text=" in login_enhancements.text
    assert 'link.target = "_blank"' in login_enhancements.text
    assert 'link.rel = "noopener noreferrer"' in login_enhancements.text
    assert "localStorage.setItem(LOGIN_CHALLENGE_STORAGE_KEY" in login_enhancements.text
    assert "localStorage.removeItem(LOGIN_CHALLENGE_STORAGE_KEY)" in login_enhancements.text
    assert "async function restoreStoredChallenge()" in login_enhancements.text
    assert '["pending", "approved"].includes(current.status)' in login_enhancements.text
    assert 'renderConfirmation("Проверяем подтверждение' in login_enhancements.text
    assert "releaseInitialSessionCheck()" in login_enhancements.text
    assert "wrapAuthenticatedRender()" in login_enhancements.text
    assert "challengePollInFlight" in login_enhancements.text
    assert "pollChallenge = pollPersistedChallenge" in login_enhancements.text
    assert "const resumedInitialRender = releaseInitialSessionCheck();" in (
        login_enhancements.text
    )
    assert "if (!resumedInitialRender) renderApp();" in login_enhancements.text
    assert 'location.replace("/web/")' not in login_enhancements.text
    assert "forgetStoredChallenge();" in login_enhancements.text
    assert "window.setTimeout(restoreStoredChallenge" not in login_enhancements.text
    assert 'window.addEventListener("focus", restoreStoredChallenge)' in (
        login_enhancements.text
    )
    assert 'window.addEventListener("pageshow", restoreStoredChallenge)' in (
        login_enhancements.text
    )
    assert 'window.addEventListener("storage", restoreStoredChallenge)' in (
        login_enhancements.text
    )
    assert 'document.addEventListener("visibilitychange", restoreStoredChallenge)' in (
        login_enhancements.text
    )
    assert '/^\\d{6}$/' in login_enhancements.text
    assert ".telegram-code-button" in stylesheet.text
    assert "text-decoration: none" in stylesheet.text
    assert "min-height: 52px" in stylesheet.text
    assert ".mobile-logout" in stylesheet.text
    assert ".catalog-grid" in stylesheet.text
    assert "repeat(3, 1fr)" in stylesheet.text
    assert "display: inline-flex" in stylesheet.text
    assert "--primary" in stylesheet.text


def test_web_api_routes_take_precedence_over_static_mount(client, clean_database):
    response = client.get(
        "/web/api/auth/session",
        headers=WEB_ORIGIN_HEADERS,
    )

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["content-security-policy"].startswith("default-src")
    assert response.json() == {"detail": {"code": "unauthorized"}}
