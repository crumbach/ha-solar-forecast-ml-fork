"""Solar Forecast ML Integration - v3.0.0 FINAL."""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Solar Forecast ML from a config entry."""
    _LOGGER.info("Setting up Solar Forecast ML integration v3.0.0")
    
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data
    
    # ✅ v2.3.0: Button als separate Platform
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "button"])
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Solar Forecast ML integration")
    
    # ✅ v2.3.0: Sensor Removal Fix - Sauberes Aufräumen der Entity Registry
    entity_reg = er.async_get(hass)
    
    # Finde alle Entities dieser Integration
    entities_to_remove = er.async_entries_for_config_entry(entity_reg, entry.entry_id)
    
    # Entferne jede Entity aus der Registry
    for entity in entities_to_remove:
        try:
            entity_reg.async_remove(entity.entity_id)
            _LOGGER.debug(f"✅ Entity entfernt: {entity.entity_id}")
        except Exception as e:
            _LOGGER.warning(f"Fehler beim Entfernen von {entity.entity_id}: {e}")
    
    # ✅ v2.3.0: Unload beide Platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor", "button"])
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        # Cleanup Coordinator aus data
        coordinator_key = f"{entry.entry_id}_coordinator"
        if coordinator_key in hass.data[DOMAIN]:
            hass.data[DOMAIN].pop(coordinator_key)
        _LOGGER.info("✅ Solar Forecast ML erfolgreich entladen")
    else:
        _LOGGER.warning("⚠️ Probleme beim Entladen der Platforms")
    
    return unload_ok