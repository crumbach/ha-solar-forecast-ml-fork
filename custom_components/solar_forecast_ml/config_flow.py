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
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors
        )