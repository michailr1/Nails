from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "backend/app/web_static"


def _read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def test_catalog_readability_layer_loads_after_catalog_base() -> None:
    index = _read("index.html")
    base = index.index('/web/web-service-catalog.js')
    overlay = index.index('/web/web-catalog-readability.js')
    assert base < overlay
    assert '/web/web-catalog-readability.css' in index


def test_price_sections_are_native_collapsible_groups() -> None:
    source = _read("web-catalog-readability.js")
    assert 'class="panel catalog-section catalog-section-collapsible"' in source
    assert '<summary class="catalog-section-summary">' in source
    assert 'catalogPositionLabel(items.length)' in source
    assert 'hasEditingCard ? "open" : ""' in source
    assert 'items.some(({ index }) => index === expandedServiceIndex)' in source
    renderer = (
        'index === expandedServiceIndex ? serviceEditorCard(service, index) '
        ': serviceSummaryCard(service, index)'
    )
    assert renderer in source


def test_catalog_renderer_uses_browser_lexical_catalog_state_not_this_binding() -> None:
    base = _read("web-service-catalog.js")
    overlay = _read("web-catalog-readability.js")
    assert "let serviceCatalogDraft = [];" in base
    assert "function catalogGroups()" in base
    assert "serviceCatalogDraft.forEach((service, index) =>" in base
    assert "this.serviceCatalogDraft" not in base
    assert "this.catalogGroups" not in base
    assert "return catalogGroups().map(([category, items]) =>" in overlay


def test_catalog_price_format_matches_client_readability_rules() -> None:
    source = _read("web-catalog-readability.js")
    assert 'if (value === null || value === undefined || value === "") return null;' in source
    assert 'if (!Number.isFinite(number)) return null;' in source

    assert 'if (service.price_type === "range")' in source
    assert '`${low}–${high}${currency}`' in source

    assert 'if (service.price_type === "per_unit")' in source
    assert 'String(service.price_unit || "ед.").trim()' in source
    assert '`${amount}${currency} / ${escapeHtml(unit)}`' in source

    assert 'if (service.price_type === "on_request") return "цена уточняется";' in source
    assert 'return amount ? `${amount}${currency}` : "цена уточняется";' in source

    # Missing prices must never silently become zero.
    assert 'Number(value || 0)' not in source
    assert '0 ₽' not in source


def test_catalog_time_format_covers_base_addon_and_buffer() -> None:
    source = _read("web-catalog-readability.js")
    assert 'const prefix = approximate ? "~" : addon ? "+" : "";' in source
    assert '`${prefix}${hours} ч ${remainder} мин`' in source
    assert '`${prefix}${hours} ч`' in source
    assert '`${prefix}${remainder} мин`' in source
    assert 'catalogDuration(service.extra_minutes, { addon: true })' in source
    assert 'catalogDuration(service.duration_minutes, { approximate: true })' in source
    assert '`${duration} · +${bufferAfter} мин после`' in source


def test_catalog_russian_position_count_rules_are_complete() -> None:
    source = _read("web-catalog-readability.js")
    singular = 'if (mod10 === 1 && mod100 !== 11) return `${count} позиция`;'
    few = (
        'if ([2, 3, 4].includes(mod10) && ![12, 13, 14].includes(mod100)) '
        'return `${count} позиции`;'
    )
    assert singular in source
    assert few in source
    assert 'return `${count} позиций`;' in source


def test_catalog_empty_state_and_collapsed_default_remain_explicit() -> None:
    source = _read("web-catalog-readability.js")
    empty_state = (
        'if (!serviceCatalogDraft.length) return '
        '\'<div class="panel empty">В прайсе пока нет позиций.</div>\';'
    )
    assert empty_state in source
    # There is no unconditional open attribute; it is tied to active editor membership.
    assert '${hasEditingCard ? "open" : ""}' in source


def test_collapsible_sections_have_mobile_layout_and_long_name_wrap() -> None:
    css = _read("web-catalog-readability.css")
    assert '.catalog-section-collapsible[open]' in css
    assert '@media (max-width: 760px)' in css
    assert '.catalog-card-summary' in css
    assert 'flex-direction: column' in css
    assert '.catalog-summary-main strong' in css
    assert 'white-space: normal' in css
    assert '.catalog-summary-actions' in css
    assert 'justify-content: flex-end' in css


def test_catalog_readability_css_uses_existing_design_tokens() -> None:
    css = _read("web-catalog-readability.css")
    assert 'color: var(--text)' in css
    assert 'color: var(--muted)' in css
    assert 'border-right: 2px solid var(--muted)' in css
    assert 'border-bottom: 1px solid var(--border)' in css
    assert 'border-top: 1px solid var(--border)' in css
    # Presentation layer must not introduce literal hex/rgb colors.
    assert "#" not in css
    assert "rgb(" not in css
    assert "rgba(" not in css


def test_catalog_overlay_does_not_define_api_save_or_domain_paths() -> None:
    source = _read("web-catalog-readability.js")
    forbidden = (
        "fetch(",
        "api(",
        "saveServiceCatalog =",
        "normalizeCatalogService =",
        "serviceEditorCard =",
        "serviceSummaryCard =",
        "catalogGroups =",
    )
    for token in forbidden:
        assert token not in source
