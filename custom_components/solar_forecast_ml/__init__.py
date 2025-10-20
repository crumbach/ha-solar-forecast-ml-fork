"""Solar Forecast ML Integration."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import SolarForecastCoordinator
from .helpers import _migrate_data_files

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Solar Forecast ML from a config entry."""
    _LOGGER.info("Setting up Solar Forecast ML integration")
    
    hass.data.setdefault(DOMAIN, {})
    
    # Migriere Dateien vor dem Start des Koordinators
    await hass.async_add_executor_job(_migrate_data_files)

    # Erstelle und speichere den zentralen Koordinator mit dem kompletten entry-Objekt
    coordinator = SolarForecastCoordinator(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Lade initiale Daten
    await coordinator.async_config_entry_first_refresh()

    # Lade die Sensor- und Button-Plattformen
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "button"])
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Solar Forecast ML integration")
    
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor", "button"])
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        _LOGGER.info("Solar Forecast ML erfolgreich entladen")
    
    return unload_ok
