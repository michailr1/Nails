from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LANDING = ROOT / "backend" / "app" / "landing_static"
WEB = ROOT / "backend" / "app" / "web_static"


def test_public_landing_uses_shared_web_tokens() -> None:
    html = (LANDING / "index.html").read_text(encoding="utf-8")
    css = (LANDING / "landing.css").read_text(encoding="utf-8")

    assert '<link rel="stylesheet" href="/web/styles.css" />' in html
    assert '<link rel="stylesheet" href="/landing/landing.css" />' in html
    assert ":root" not in css
    assert "--primary" in css
    assert "--gold" in css
    assert "--surface" in css
    assert "--serif" in css


def test_public_landing_has_honest_product_structure() -> None:
    html = (LANDING / "index.html").read_text(encoding="utf-8")

    for copy in (
        "Вы делаете ногти",
        "Нэйли ведёт записи",
        "Календарь",
        "Клиентки",
        "Мой прайс",
        "Статистика",
        "Telegram",
        'href="/web/"',
    ):
        assert copy in html

    forbidden = (
        "crm",
        "тысяч мастеров",
        "бесплатный тариф",
        "отзыв",
        "оплатить",
        "настройте рабочее время",
        "обычный график",
    )
    assert all(copy not in html.lower() for copy in forbidden)


def test_public_landing_steps_follow_open_availability_contract() -> None:
    html = (LANDING / "index.html").read_text(encoding="utf-8")

    for step in (
        "Соберите свой прайс",
        "Записывайте клиенток",
        "Держите клиенток под рукой",
        "Смотрите результат",
    ):
        assert step in html

    assert "Просто назовите время — Нэйли проверит день и сохранит." in html
    assert "Контакты, заметки и кто давно не был." in html


def test_public_root_and_private_cabinet_are_packaged_separately() -> None:
    nginx = (ROOT / "web" / "nginx.conf").read_text(encoding="utf-8")
    dockerfile = (ROOT / "web" / "Dockerfile").read_text(encoding="utf-8")

    assert "root /usr/share/nginx/html/landing;" in nginx
    assert "location /landing/" in nginx
    assert "location /web/" in nginx
    assert "return 302 /web/" not in nginx
    assert "backend/app/landing_static /usr/share/nginx/html/landing" in dockerfile
    assert "backend/app/web_static /usr/share/nginx/html/web" in dockerfile


def test_landing_is_mobile_first_and_motion_safe() -> None:
    css = (LANDING / "landing.css").read_text(encoding="utf-8")
    shared = (WEB / "styles.css").read_text(encoding="utf-8")

    assert "@media (max-width: 620px)" in css
    assert "min-height: 44px" in css
    assert "env(safe-area-inset-top)" in css
    assert "env(safe-area-inset-bottom)" in css
    assert "@media (prefers-reduced-motion: no-preference)" in css
    assert "@media (prefers-reduced-motion: reduce)" in shared
