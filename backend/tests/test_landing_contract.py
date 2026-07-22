from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LANDING = ROOT / "backend/app/landing_static"


def test_public_landing_is_packaged_separately_from_private_web() -> None:
    dockerfile = (ROOT / "web/Dockerfile").read_text(encoding="utf-8")
    nginx = (ROOT / "web/nginx.conf").read_text(encoding="utf-8")

    assert "backend/app/landing_static /usr/share/nginx/html/landing" in dockerfile
    assert "backend/app/web_static /usr/share/nginx/html/web" in dockerfile
    assert "location = / {" in nginx
    assert "root /usr/share/nginx/html/landing;" in nginx
    assert "location /landing/" in nginx
    assert "location /web/" in nginx
    assert "alias /usr/share/nginx/html/web/;" in nginx
    assert "return 302 /web/;" not in nginx


def test_landing_metadata_and_real_routes_are_present() -> None:
    html = (LANDING / "index.html").read_text(encoding="utf-8")

    assert '<html lang="ru">' in html
    assert "Нэйли — личная помощница мастера маникюра" in html
    assert 'rel="canonical" href="https://de.funti.cc/"' in html
    assert 'property="og:title"' in html
    assert 'href="/web/"' in html
    assert 'href="#features"' in html
    assert 'href="#how"' in html
    assert "Bundled Page" not in html
    assert "Unpacking" not in html
    assert "Fable" not in html
    assert "Claude" not in html


def test_landing_claims_only_confirmed_product_capabilities() -> None:
    html = (LANDING / "index.html").read_text(encoding="utf-8")

    for claim in (
        "Календарь",
        "Мой прайс",
        "Клиентки",
        "Статистика",
        "CSV или Excel",
        "полное редактирование записи",
        "Подключение новых мастеров пока проходит по приглашению",
    ):
        assert claim in html

    for unsupported_claim in (
        "мгновенное подключение",
        "автоматическая оплата",
        "рост дохода",
        "тысячи мастеров",
    ):
        assert unsupported_claim not in html.lower()


def test_landing_mobile_and_reduced_motion_contract() -> None:
    css = (LANDING / "styles.css").read_text(encoding="utf-8")
    script = (LANDING / "app.js").read_text(encoding="utf-8")

    assert "@media(max-width:420px)" in css
    assert "@media(prefers-reduced-motion:reduce)" in css
    assert "min-height:48px" in css
    assert "IntersectionObserver" in script
    assert "prefers-reduced-motion: reduce" in script
