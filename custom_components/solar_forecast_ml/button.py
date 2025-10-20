"""Button-Plattform für Solar Forecast ML."""
import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .coordinator import SolarForecastCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Richtet den Button für die manuelle Prognose ein."""
    # Der Koordinator ist garantiert vorhanden, da __init__.py ihn vorher erstellt.
    coordinator: SolarForecastCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ManualForecastButton(coordinator, entry)])
    _LOGGER.info("Button für manuelle Prognose erfolgreich eingerichtet.")

class ManualForecastButton(ButtonEntity):
    """Ein Button, um die Prognose manuell auszulösen."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SolarForecastCoordinator, entry: ConfigEntry):
        """Initialisiere den Button."""
        self.coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_manual_forecast"
        self._attr_name = "Manuelle Prognose auslösen"
        self._attr_icon = "mdi:refresh-circle"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Solar Forecast ML",
            manufacturer="Zara-Toorox",
        )

    async def async_press(self) -> None:
        """
        Behandelt den Button-Druck.
        Ruft die sichere 'async_manual_forecast'-Methode im Koordinator auf.
        Diese Methode verhindert Datenverlust und Duplikate.
        """
        _LOGGER.info("Button gedrückt, fordere manuelle Prognose an...")
        await self.coordinator.async_manual_forecast()
