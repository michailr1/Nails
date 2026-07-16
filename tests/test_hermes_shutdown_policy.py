from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path


def _load_policy_module():
    path = (
        Path(__file__).parents[1]
        / "hermes"
        / "plugins"
        / "nails_scheduling"
        / "shutdown_policy.py"
    )
    spec = importlib.util.spec_from_file_location("nails_shutdown_policy", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_suppression_is_profile_local_and_idempotent(monkeypatch):
    calls: list[str] = []

    class GatewayRunner:
        async def _notify_active_sessions_of_shutdown(self) -> None:
            calls.append("upstream")

    gateway_module = types.ModuleType("gateway")
    gateway_run_module = types.ModuleType("gateway.run")
    gateway_run_module.GatewayRunner = GatewayRunner
    gateway_module.run = gateway_run_module
    monkeypatch.setitem(sys.modules, "gateway", gateway_module)
    monkeypatch.setitem(sys.modules, "gateway.run", gateway_run_module)

    policy = _load_policy_module()
    original = GatewayRunner._notify_active_sessions_of_shutdown

    policy.suppress_shutdown_notifications_for_nails()
    patched = GatewayRunner._notify_active_sessions_of_shutdown
    policy.suppress_shutdown_notifications_for_nails()

    assert patched is GatewayRunner._notify_active_sessions_of_shutdown
    assert patched is not original
    asyncio.run(GatewayRunner()._notify_active_sessions_of_shutdown())
    assert calls == []


def test_other_runner_classes_keep_upstream_behavior(monkeypatch):
    calls: list[str] = []

    class GatewayRunner:
        async def _notify_active_sessions_of_shutdown(self) -> None:
            calls.append("nails")

    class OtherProfileRunner:
        async def _notify_active_sessions_of_shutdown(self) -> None:
            calls.append("other")

    gateway_module = types.ModuleType("gateway")
    gateway_run_module = types.ModuleType("gateway.run")
    gateway_run_module.GatewayRunner = GatewayRunner
    gateway_module.run = gateway_run_module
    monkeypatch.setitem(sys.modules, "gateway", gateway_module)
    monkeypatch.setitem(sys.modules, "gateway.run", gateway_run_module)

    policy = _load_policy_module()
    policy.suppress_shutdown_notifications_for_nails()

    asyncio.run(GatewayRunner()._notify_active_sessions_of_shutdown())
    asyncio.run(OtherProfileRunner()._notify_active_sessions_of_shutdown())
    assert calls == ["other"]
