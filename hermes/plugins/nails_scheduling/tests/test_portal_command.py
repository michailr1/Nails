from types import SimpleNamespace

from nails_scheduling import open_master_portal, register


def test_portal_command_opens_exact_master_cabinet_url():
    expected = "Личный кабинет мастера: https://de.funti.cc/web/"

    assert open_master_portal("") == expected
    assert open_master_portal("ignored") == expected


def test_plugin_registers_portal_command_for_telegram_menu():
    tools = []
    commands = []
    ctx = SimpleNamespace(
        register_tool=lambda **kwargs: tools.append(kwargs),
        register_command=lambda name, **kwargs: commands.append({"name": name, **kwargs}),
    )

    register(ctx)

    assert len(tools) == 2
    assert commands == [
        {
            "name": "portal",
            "handler": open_master_portal,
            "description": "Личный кабинет мастера",
        }
    ]
