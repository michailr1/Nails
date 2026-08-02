from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "backend" / "app" / "web_static" / "web-client-reachability.js"


def _controls_function() -> str:
    source = SOURCE.read_text(encoding="utf-8")
    return source.split("function renderReachabilityControls(reachability) {", 1)[1].split(
        "\n}\n\nasync function renderFilteredClientsFromBackend",
        1,
    )[0]


def test_reachability_controls_replace_previous_instances_before_prepend():
    function = _controls_function()

    remove_position = function.index(
        'actions.querySelectorAll(".client-reachability-controls")'
    )
    prepend_position = function.index("actions.prepend(wrapper)")

    assert remove_position < prepend_position
    assert "control.remove()" in function
    assert function.count("actions.prepend(wrapper)") == 1


def test_reachability_controls_bind_only_the_new_wrapper_once():
    function = _controls_function()

    assert 'wrapper.querySelector("#connected-clients-only")' in function
    assert 'wrapper.querySelector("#show-client-invitation")' in function
    assert 'document.querySelector("#connected-clients-only")' not in function
    assert 'document.querySelector("#show-client-invitation")' not in function
    assert function.count('addEventListener("change"') == 1
    assert function.count('addEventListener("click"') == 1


def test_reachability_controls_keep_one_filter_and_one_general_link_definition():
    function = _controls_function()

    assert function.count('id="connected-clients-only"') == 1
    assert function.count('id="show-client-invitation"') == 1
    assert function.count("Кому можно написать") == 1
    assert function.count("Общая ссылка для записи") == 1
