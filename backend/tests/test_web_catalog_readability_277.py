from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "backend/app/web_static"


def test_catalog_readability_layer_loads_after_catalog_base() -> None:
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    base = index.index('/web/web-service-catalog.js')
    overlay = index.index('/web/web-catalog-readability.js')
    assert base < overlay
    assert '/web/web-catalog-readability.css' in index


def test_price_sections_are_native_collapsible_groups() -> None:
    source = (STATIC / "web-catalog-readability.js").read_text(encoding="utf-8")
    assert 'class="panel catalog-section catalog-section-collapsible"' in source
    assert '<summary class="catalog-section-summary">' in source
    assert 'catalogPositionLabel(items.length)' in source
    assert 'hasEditingCard ? "open" : ""' in source
    assert 'index === expandedServiceIndex ? serviceEditorCard' in source


def test_catalog_price_format_matches_client_readability_rules() -> None:
    source = (STATIC / "web-catalog-readability.js").read_text(encoding="utf-8")
    assert '`${low}–${high}${currency}`' in source
    assert '`${amount}${currency} / ${escapeHtml(unit)}`' in source
    assert 'return "цена уточняется"' in source
    assert 'approximate: true' in source
    assert 'addon: true' in source
    assert '· +${bufferAfter} мин после' in source


def test_collapsible_sections_have_mobile_layout() -> None:
    css = (STATIC / "web-catalog-readability.css").read_text(encoding="utf-8")
    assert '.catalog-section-collapsible[open]' in css
    assert '@media (max-width: 760px)' in css
    assert '.catalog-card-summary' in css
    assert 'flex-direction: column' in css
