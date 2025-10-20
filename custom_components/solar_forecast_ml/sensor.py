"""Sensor-Plattform für Solar Forecast ML."""
from __future__ import annotations
from datetime import datetime, timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DIAGNOSTIC, CONF_HOURLY, DOMAIN
from .coordinator import SolarForecastCoordinator

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Richtet alle Sensoren basierend auf der Konfiguration ein."""
    coordinator: SolarForecastCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        SolarForecastSensor(coordinator, entry, "heute", "Solar Forecast ML Prognose Heute"),
        SolarForecastSensor(coordinator, entry, "morgen", "Solar Forecast ML Prognose Morgen"),
        SolarAccuracySensor(coordinator, entry),
    ]
    if entry.data.get(CONF_DIAGNOSTIC, True):
        entities.append(DiagnosticStatusSensor(coordinator, entry))
    if entry.data.get(CONF_HOURLY, False):
        entities.append(NextHourSensor(coordinator, entry))
        
    async_add_entities(entities)

class BaseSolarSensor(CoordinatorEntity[SolarForecastCoordinator], SensorEntity):
    """Basisklasse für alle Sensoren der Integration."""
    _attr_has_entity_name = True

    def __init__(self, coordinator: SolarForecastCoordinator, entry: ConfigEntry):
        super().__init__(coordinator)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Solar Forecast ML",
            "manufacturer": "Zara-Toorox",
            "model": "v4.0 Refactored",
        }

class SolarForecastSensor(BaseSolarSensor):
    """Sensor für Heute/Morgen Prognose."""
    def __init__(self, coordinator: SolarForecastCoordinator, entry: ConfigEntry, key: str, name: str):
        super().__init__(coordinator, entry)
        self._key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self.entity_id = f"sensor.solar_forecast_ml_{key}"
        self._attr_name = name
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_icon = "mdi:solar-power"

    @property
    def native_value(self):
        return self.coordinator.data.get(self. _key, 0.0) if self.coordinator.data else 0.0

class SolarAccuracySensor(BaseSolarSensor):
    """Sensor für die Genauigkeit."""
    def __init__(self, coordinator: SolarForecastCoordinator, entry: ConfigEntry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_genauigkeit"
        self._attr_name = "Prognose Genauigkeit"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:target-variant"

    @property
    def native_value(self):
        return self.coordinator.data.get("genauigkeit", 0.0) if self.coordinator.data else 0.0

class DiagnosticStatusSensor(BaseSolarSensor):
    """Sensor für den Status-Text."""
    def __init__(self, coordinator: SolarForecastCoordinator, entry: ConfigEntry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_status"
        self._attr_name = "Status"
        self._attr_icon = "mdi:information-outline"

    @property
    def native_value(self):
        return self.coordinator._get_status_text()

    @property
    def extra_state_attributes(self):
        return {
            "last_update": self.coordinator.last_update.isoformat(),
            "accuracy": f"{self.coordinator.accuracy:.1f}%",
            "weather_type": self.coordinator.weather_type,
            "forecast_method": self.coordinator.forecast_method or "detecting...",
            "base_capacity": f"{self.coordinator.base_capacity:.2f} kWh",
        }

class NextHourSensor(BaseSolarSensor):
    """Sensor für die Prognose der nächsten Stunde."""
    def __init__(self, coordinator: SolarForecastCoordinator, entry: ConfigEntry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_naechste_stunde"
        self._attr_name = "Prognose Nächste Stunde"
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:clock-fast"
        
    @property
    def native_value(self):
        return round(self.coordinator.next_hour_pred, 2)

    @property
    def extra_state_attributes(self):
        return { "next_hour_start": (datetime.now() + timedelta(hours=1)).strftime("%H:00") }
