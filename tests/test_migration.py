"""Unit tests for config entry migration."""

from __future__ import annotations

import asyncio
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import types
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = REPO_ROOT / "custom_components" / "elering"


def _load_init_module():
    package_name = "_test_elering_init"
    package = types.ModuleType(package_name)
    package.__path__ = [str(PACKAGE_DIR)]
    sys.modules[package_name] = package

    homeassistant_config_entries = types.ModuleType("homeassistant.config_entries")
    homeassistant_config_entries.ConfigEntry = object
    homeassistant_const = types.ModuleType("homeassistant.const")
    homeassistant_const.Platform = types.SimpleNamespace(SENSOR="sensor")
    homeassistant_core = types.ModuleType("homeassistant.core")
    homeassistant_core.HomeAssistant = object
    homeassistant_helpers = types.ModuleType("homeassistant.helpers")
    aiohttp_client = types.ModuleType("homeassistant.helpers.aiohttp_client")
    aiohttp_client.async_get_clientsession = lambda hass: hass

    sys.modules["homeassistant.config_entries"] = homeassistant_config_entries
    sys.modules["homeassistant.const"] = homeassistant_const
    sys.modules["homeassistant.core"] = homeassistant_core
    sys.modules["homeassistant.helpers"] = homeassistant_helpers
    sys.modules["homeassistant.helpers.aiohttp_client"] = aiohttp_client

    api_stub = types.ModuleType(f"{package_name}.api")
    api_stub.EleringApiClient = object
    sys.modules[f"{package_name}.api"] = api_stub

    coordinator_stub = types.ModuleType(f"{package_name}.coordinator")
    coordinator_stub.EleringCoordinator = object
    sys.modules[f"{package_name}.coordinator"] = coordinator_stub

    const_spec = spec_from_file_location(f"{package_name}.const", PACKAGE_DIR / "const.py")
    const_module = module_from_spec(const_spec)
    assert const_spec and const_spec.loader
    sys.modules[f"{package_name}.const"] = const_module
    const_spec.loader.exec_module(const_module)

    init_spec = spec_from_file_location(f"{package_name}.__init__", PACKAGE_DIR / "__init__.py")
    init_module = module_from_spec(init_spec)
    assert init_spec and init_spec.loader
    sys.modules[f"{package_name}.__init__"] = init_module
    init_spec.loader.exec_module(init_module)

    return init_module, const_module


INIT_MODULE, CONST_MODULE = _load_init_module()


class MigrationTests(unittest.TestCase):
    def test_migrates_legacy_cookie_to_api_token(self):
        entry = types.SimpleNamespace(
            version=2,
            data={"cookie_header": "legacy-token", "meter_eic": "123"},
            options={"cookie_header": "legacy-opt-token"},
        )
        captured = {}

        class _ConfigEntries:
            @staticmethod
            def async_update_entry(entry, data, options, version):
                captured["data"] = data
                captured["options"] = options
                captured["version"] = version

        hass = types.SimpleNamespace(config_entries=_ConfigEntries())

        result = asyncio.run(INIT_MODULE.async_migrate_entry(hass, entry))

        self.assertTrue(result)
        self.assertEqual(captured["version"], 3)
        self.assertEqual(captured["data"][CONST_MODULE.CONF_API_TOKEN], "legacy-token")
        self.assertEqual(captured["options"][CONST_MODULE.CONF_API_TOKEN], "legacy-opt-token")


if __name__ == "__main__":
    unittest.main()
