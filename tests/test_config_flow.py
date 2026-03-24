"""Unit tests for config flow credential validation helpers."""

from __future__ import annotations

import asyncio
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = REPO_ROOT / "custom_components" / "elering"


def _install_stub_modules(package_name: str) -> None:
    package = types.ModuleType(package_name)
    package.__path__ = [str(PACKAGE_DIR)]
    sys.modules[package_name] = package

    aiohttp_stub = types.ModuleType("aiohttp")

    class _ClientError(Exception):
        """Stub aiohttp client error."""

    aiohttp_stub.ClientError = _ClientError
    sys.modules["aiohttp"] = aiohttp_stub

    voluptuous_stub = types.ModuleType("voluptuous")
    voluptuous_stub.Schema = lambda schema: schema
    voluptuous_stub.Required = lambda value, default=None: value
    sys.modules["voluptuous"] = voluptuous_stub

    homeassistant_stub = types.ModuleType("homeassistant")
    config_entries_stub = types.ModuleType("homeassistant.config_entries")
    data_entry_flow_stub = types.ModuleType("homeassistant.data_entry_flow")
    helpers_stub = types.ModuleType("homeassistant.helpers")
    aiohttp_client_stub = types.ModuleType("homeassistant.helpers.aiohttp_client")

    class _ConfigFlow:
        def __init_subclass__(cls, **kwargs):
            return super().__init_subclass__()

    class _OptionsFlow:
        def __init__(self, *args, **kwargs):
            pass

    config_entries_stub.ConfigFlow = _ConfigFlow
    config_entries_stub.OptionsFlow = _OptionsFlow
    data_entry_flow_stub.FlowResult = dict
    aiohttp_client_stub.async_get_clientsession = lambda hass: hass

    sys.modules["homeassistant"] = homeassistant_stub
    sys.modules["homeassistant.config_entries"] = config_entries_stub
    sys.modules["homeassistant.data_entry_flow"] = data_entry_flow_stub
    sys.modules["homeassistant.helpers"] = helpers_stub
    sys.modules["homeassistant.helpers.aiohttp_client"] = aiohttp_client_stub


def _load_modules():
    package_name = "_test_elering_config_flow"
    _install_stub_modules(package_name)

    const_spec = spec_from_file_location(f"{package_name}.const", PACKAGE_DIR / "const.py")
    const_module = module_from_spec(const_spec)
    assert const_spec and const_spec.loader
    sys.modules[f"{package_name}.const"] = const_module
    const_spec.loader.exec_module(const_module)

    api_spec = spec_from_file_location(f"{package_name}.api", PACKAGE_DIR / "api.py")
    api_module = module_from_spec(api_spec)
    assert api_spec and api_spec.loader
    sys.modules[f"{package_name}.api"] = api_module
    api_spec.loader.exec_module(api_module)

    config_flow_spec = spec_from_file_location(
        f"{package_name}.config_flow",
        PACKAGE_DIR / "config_flow.py",
    )
    config_flow_module = module_from_spec(config_flow_spec)
    assert config_flow_spec and config_flow_spec.loader
    sys.modules[f"{package_name}.config_flow"] = config_flow_module
    config_flow_spec.loader.exec_module(config_flow_module)
    return api_module, config_flow_module


API_MODULE, CONFIG_FLOW_MODULE = _load_modules()


class ValidateInputTests(unittest.TestCase):
    """Verify credential validation helper behavior."""

    def test_returns_entry_title_after_successful_validation(self):
        mock_fetch = AsyncMock(return_value=None)

        with patch.object(API_MODULE.EleringApiClient, "async_fetch_meter_data", mock_fetch):
            title = asyncio.run(
                CONFIG_FLOW_MODULE.async_validate_input(
                    hass=object(),
                    user_input={"client_id": "id", "client_secret": "secret", "meter_eic": "123"},
                )
            )

        self.assertEqual(title, "Elering 123")

    def test_propagates_authentication_error(self):
        mock_fetch = AsyncMock(side_effect=API_MODULE.EleringAuthenticationError("bad credentials"))

        with patch.object(API_MODULE.EleringApiClient, "async_fetch_meter_data", mock_fetch):
            with self.assertRaises(API_MODULE.EleringAuthenticationError):
                asyncio.run(
                    CONFIG_FLOW_MODULE.async_validate_input(
                        hass=object(),
                        user_input={"client_id": "id", "client_secret": "secret", "meter_eic": "123"},
                    )
                )

if __name__ == "__main__":
    unittest.main()
