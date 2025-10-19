"""Solar Forecast ML Button Platform - v3.0.2."""
import logging
import asyncio
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Solar Forecast button."""
    # ✅ v3.0.0 FIX: Warte auf Coordinator wenn noch nicht da
    coordinator_key = f"{entry.entry_id}_coordinator"
    
    # Warte bis zu 5 Sekunden auf den Coordinator
    for i in range(50):
        coordinator = hass.data.get(DOMAIN, {}).get(coordinator_key)
        if coordinator:
            break
        await asyncio.sleep(0.1)
        _LOGGER.debug(f"Warte auf Coordinator... ({i}/50)")
    
    if coordinator:
        _LOGGER.info("✅ Button Setup: Coordinator gefunden")
        async_add_entities([
            ManualForecastButton(coordinator, "manual_forecast", "Solar Forecast ML Manuelle Prognose")
        ])
    else:
        _LOGGER.error("❌ Button Setup: Coordinator nicht gefunden!")
        _LOGGER.error(f"   Verfügbare Keys in hass.data[DOMAIN]: {list(hass.data.get(DOMAIN, {}).keys())}")


class ManualForecastButton(CoordinatorEntity, ButtonEntity):
    """Button zum manuellen Triggern der Prognose."""
    
    def __init__(self, coordinator, key, name):
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{key}"
        self._attr_name = name
        self._key = key
        self._attr_icon = "mdi:refresh"
        self._attr_device_class = "restart"
        self._attr_entity_category = None

    async def async_press(self):
        """Handle button press - trigger forecast."""
        _LOGGER.info("🔄 Manuelle Prognose durch Button ausgelöst")
        try:
            # CRITICAL FIX v3.0.2: Lade History VORHER um alle Tage zu bewahren!
            _LOGGER.info("📚 Lade History vor manueller Prognose...")
            await self.coordinator._load_history()
            
            # Jetzt Prognose erstellen (mit vollständiger History im RAM)
            await self.coordinator._create_forecast()
            
            # Benachrichtigung über erfolgreiche Prognose
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "✅ Prognose manuell erstellt",
                    "message": (
                        f"Heute: {self.coordinator.data.get('heute', 0):.2f} kWh\n"
                        f"Morgen: {self.coordinator.data.get('morgen', 0):.2f} kWh"
                    ),
                    "notification_id": "solar_forecast_ml_manual"
                }
            )
        except Exception as e:
            _LOGGER.error(f"Fehler beim manuellen Forecast: {e}", exc_info=True)
            
            # Fehler-Benachrichtigung
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "❌ Fehler bei manueller Prognose",
                    "message": f"Fehler: {str(e)}",
                    "notification_id": "solar_forecast_ml_manual_error"
                }
            )