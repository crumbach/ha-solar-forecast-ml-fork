"""
Solar Forecast ML Integration.

Diese Datei ist der Haupteinstiegspunkt für die Integration in Home Assistant.
Sie initialisiert den Koordinator, lädt die Plattformen (sensor, button) und
richtet die Kommunikationsdienste ein.
"""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import SolarForecastCoordinator
from .helpers import _migrate_data_files

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Richtet die Solar Forecast ML Integration aus einem Konfigurationseintrag ein.
    Wird von Home Assistant nach erfolgreicher Konfiguration durch den User aufgerufen.
    """
    _LOGGER.info("--- STARTING Solar Forecast ML Setup ---")
    hass.data.setdefault(DOMAIN, {})

    # Schritt 1: Migriere alte Datendateien, falls vorhanden
    _LOGGER.info("Step 1: Checking for data file migration...")
    await hass.async_add_executor_job(_migrate_data_files)
    _LOGGER.info(" -> Step 1 Complete: Migration check finished.")

    # Schritt 2: Erstelle und speichere den zentralen Koordinator
    _LOGGER.info("Step 2: Creating coordinator instance...")
    coordinator = SolarForecastCoordinator(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = coordinator
    _LOGGER.info(" -> Step 2 Complete: Coordinator instance created and stored.")

    # Schritt 3: Führe den ersten Refresh durch, um initiale Daten zu laden
    _LOGGER.info("Step 3: Triggering initial coordinator refresh...")
    await coordinator.async_config_entry_first_refresh()
    _LOGGER.info(" -> Step 3 Complete: Initial refresh done.")

    # Schritt 4: Lade die Plattformen (sensor, button), die sich den Koordinator holen
    _LOGGER.info("Step 4: Forwarding setup to sensor and button platforms...")
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "button"])
    _LOGGER.info(" -> Step 4 Complete: Platform setup forwarded.")

    # Schritt 5: Registriere den manuellen Lern-Service für Debugging und Tests
    _LOGGER.info("Step 5: Registering 'trigger_learning' service...")

    async def handle_trigger_learning(call):
        """Behandelt den Service-Aufruf, um das Lernen manuell auszulösen."""
        _LOGGER.info("🔧 Service 'trigger_learning' aufgerufen. Starte Lernprozess manuell.")
        await coordinator._midnight_learning(dt_util.now())

    hass.services.async_register(DOMAIN, "trigger_learning", handle_trigger_learning)
    _LOGGER.info(" -> Step 5 Complete: 'trigger_learning' service registered.")

    _LOGGER.info("--- ✅ Solar Forecast ML Setup Finished Successfully ---")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Entlädt einen Konfigurationseintrag.
    Wird aufgerufen, wenn die Integration deaktiviert oder entfernt wird.
    """
    _LOGGER.info("Unloading Solar Forecast ML integration...")
    
    # Entlade die Sensor- und Button-Plattformen
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor", "button"])
    
    if unload_ok:
        # Entferne den registrierten Service
        hass.services.async_remove(DOMAIN, "trigger_learning")
        
        # Entferne den Koordinator aus dem globalen hass.data-Speicher
        hass.data[DOMAIN].pop(entry.entry_id, None)
        _LOGGER.info("✅ Solar Forecast ML unloaded successfully.")
    
    return unload_ok

