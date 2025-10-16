"""Config flow for Solar Forecast ML."""
import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from .const import (
    DOMAIN, 
    CONF_WEATHER_ENTITY, 
    CONF_POWER_ENTITY, 
    CONF_UPDATE_INTERVAL, 
    DEFAULT_UPDATE_INTERVAL,
    CONF_PLANT_KWP,
    CONF_LUX_SENSOR,
    CONF_TEMP_SENSOR,
    CONF_WIND_SENSOR,
    CONF_UV_SENSOR,
    CONF_FORECAST_SOLAR, 
    CONF_INVERTER_POWER,  # Neu: Current Power
    CONF_INVERTER_DAILY,  # Neu: Daily Yield
    CONF_DIAGNOSTIC,  # Neu: Diagnostic Toggle
    CONF_HOURLY,  # Neu: Hourly Toggle
)

_LOGGER = logging.getLogger(__name__)

class SolarForecastMLConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solar Forecast ML."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Entferne leere optionale Sensoren
            cleaned_data = {k: v for k, v in user_input.items() if v or k in [CONF_WEATHER_ENTITY, CONF_POWER_ENTITY, CONF_UPDATE_INTERVAL]}
                
            return self.async_create_entry(
                title="Solar Forecast ML",
                data=cleaned_data
            )

        data_schema = vol.Schema({
            vol.Required(
                CONF_WEATHER_ENTITY, 
                default="weather.home"
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="weather")
            ),
            vol.Required(
                CONF_POWER_ENTITY, 
                default="sensor.solar_daily_yield"
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional(
                CONF_PLANT_KWP,
                description={"suggested_value": None}
            ): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=1000)),
            vol.Optional(
                CONF_UPDATE_INTERVAL, 
                default=DEFAULT_UPDATE_INTERVAL
            ): vol.All(vol.Coerce(int), vol.Range(min=600, max=86400)),
            
            # NEU: Forecast.Solar Sensor für Blending
            vol.Optional(CONF_FORECAST_SOLAR): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor"
                )
            ),
            
            # Optionale Sensoren
            vol.Optional(CONF_LUX_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                    device_class="illuminance"
                )
            ),
            vol.Optional(CONF_TEMP_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                    device_class="temperature"
                )
            ),
            vol.Optional(CONF_WIND_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                    device_class="wind_speed"
                )
            ),
            vol.Optional(CONF_UV_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            # Neu: Inverter Power-Sensor (einfacher Check: >0 = on)
            vol.Optional(
                CONF_INVERTER_POWER,
                description={
                    "suggested_value": None,
                    "description": "Aktueller Solar-Power-Sensor (z.B. in W) – ich checke, ob >10W für 'Inverter on'. Hilft bei Ausfällen, ohne extra Binary-Sensor."
                }
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                    device_class="power"  # Filtert auf Power-Sensoren
                )
            ),
            # Neu: Optional Daily Yield für robustere Checks (erweitert mit Erklärung & Beispiel)
            vol.Optional(
                CONF_INVERTER_DAILY,
                description={
                    "suggested_value": None,
                    "description": "Täglicher Ertrag deines Inverters (z.B. 'sensor.solar_daily_production' aus deiner Fronius/SMA/Anker-Integration, in kWh) – optional. Hilft, bei Nacht oder Akku-Umschaltungen zu prüfen, ob der Tag aktiv war (>0.1 kWh = 'Inverter on'). Lass leer, wenn du nur den Current-Power nutzt."
                }
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                    device_class="energy"  # Filtert auf Energy-Sensoren
                )
            ),
            # Neu: Diagnostic-Status Toggle
            vol.Optional(
                CONF_DIAGNOSTIC,
                default=True,
                description={"description": "Diagnostic-Status-Sensor aktivieren? – Zeigt laufenden Status (z.B. 'Läuft normal') für mehr Feedback im Dashboard."
                }
            ): bool,
            # Neu: Hourly-Prognose Toggle
            vol.Optional(
                CONF_HOURLY,
                default=False,
                description={"description": "Prognose für nächste Stunde aktivieren? – Neuen Sensor für 'Nächste Stunde' (kWh), basierend auf stündlicher Wettervorhersage. Gut für Automatisierungen wie EV-Laden."
                }
            ): bool,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors
        )