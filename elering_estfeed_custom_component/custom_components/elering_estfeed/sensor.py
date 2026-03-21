"""Sensor platform for Elering Estfeed."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            EleringImportEnergySensor(coordinator, entry),
            EleringImportPowerSensor(coordinator, entry),
        ]
    )


class BaseEleringSensor(CoordinatorEntity, SensorEntity):
    """Base sensor."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._entry = entry


class EleringImportEnergySensor(BaseEleringSensor):
    """Grid import energy sensor."""

    _attr_name = "Grid import energy"
    _attr_native_unit_of_measurement = "kWh"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:transmission-tower-import"

    @property
    def unique_id(self):
        return f"{self._entry.entry_id}_grid_import_energy"

    @property
    def native_value(self):
        return self.coordinator.data.total_import_kwh

    @property
    def extra_state_attributes(self):
        return {
            "last_period_end": self.coordinator.data.last_period_end,
        }


class EleringImportPowerSensor(BaseEleringSensor):
    """Grid import power sensor."""

    _attr_name = "Grid import power"
    _attr_native_unit_of_measurement = "W"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:flash"

    @property
    def unique_id(self):
        return f"{self._entry.entry_id}_grid_import_power"

    @property
    def native_value(self):
        return self.coordinator.data.current_import_w
