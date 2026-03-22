"""Unit tests for the Elering sensor entities."""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import types
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = REPO_ROOT / "elering_estfeed_custom_component" / "custom_components" / "elering_estfeed"


def _load_sensor_module():
    package_name = "_test_elering_estfeed_sensor"
    package = types.ModuleType(package_name)
    package.__path__ = [str(PACKAGE_DIR)]
    sys.modules[package_name] = package

    homeassistant = types.ModuleType("homeassistant")
    components = types.ModuleType("homeassistant.components")
    sensor_pkg = types.ModuleType("homeassistant.components.sensor")
    helpers = types.ModuleType("homeassistant.helpers")
    update_coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")

    class SensorEntity:
        pass

    class CoordinatorEntity:
        def __init__(self, coordinator):
            self.coordinator = coordinator

    sensor_pkg.SensorDeviceClass = types.SimpleNamespace(ENERGY="energy")
    sensor_pkg.SensorEntity = SensorEntity
    sensor_pkg.SensorStateClass = types.SimpleNamespace(TOTAL_INCREASING="total_increasing")
    update_coordinator.CoordinatorEntity = CoordinatorEntity

    sys.modules["homeassistant"] = homeassistant
    sys.modules["homeassistant.components"] = components
    sys.modules["homeassistant.components.sensor"] = sensor_pkg
    sys.modules["homeassistant.helpers"] = helpers
    sys.modules["homeassistant.helpers.update_coordinator"] = update_coordinator

    const_spec = spec_from_file_location(f"{package_name}.const", PACKAGE_DIR / "const.py")
    const_module = module_from_spec(const_spec)
    assert const_spec and const_spec.loader
    sys.modules[f"{package_name}.const"] = const_module
    const_spec.loader.exec_module(const_module)

    sensor_spec = spec_from_file_location(f"{package_name}.sensor", PACKAGE_DIR / "sensor.py")
    sensor_module = module_from_spec(sensor_spec)
    assert sensor_spec and sensor_spec.loader
    sys.modules[f"{package_name}.sensor"] = sensor_module
    sensor_spec.loader.exec_module(sensor_module)
    return sensor_module


SENSOR_MODULE = _load_sensor_module()


class CumulativeSensorUniqueIdTests(unittest.TestCase):
    def test_cumulative_sensor_uses_new_unique_id(self):
        coordinator = types.SimpleNamespace(data=types.SimpleNamespace(cumulative_import_kwh=1, last_period_end=None))
        entry = types.SimpleNamespace(entry_id="entry-123")

        sensor = SENSOR_MODULE.EleringCumulativeImportEnergySensor(coordinator, entry)

        self.assertEqual(sensor.unique_id, "entry-123_cumulative_grid_import_energy")


if __name__ == "__main__":
    unittest.main()
