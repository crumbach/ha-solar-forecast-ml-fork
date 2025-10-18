"""Config flow for Solar Forecast ML."""
import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers import config_validation as cv

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
    CONF_INVERTER_POWER,
    CONF_INVERTER_DAILY,
    CONF_DIAGNOSTIC,
    CONF_HOURLY,
    CONF_NOTIFY_FORECAST,
    CONF_NOTIFY_LEARNING,
    CONF_NOTIFY_INVERTER,
    CONF_NOTIFY_STARTUP,
    DEFAULT_NOTIFY_FORECAST,
    DEFAULT_NOTIFY_LEARNING,
    DEFAULT_NOTIFY_INVERTER,
    DEFAULT_NOTIFY_STARTUP,
    CONF_CURRENT_POWER,
)

_LOGGER = logging.getLogger(__name__)


class SolarForecastMLConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solar Forecast ML."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Setze Notification Defaults, falls nicht gesetzt
            user_input.setdefault(CONF_NOTIFY_FORECAST, DEFAULT_NOTIFY_FORECAST)
            user_input.setdefault(CONF_NOTIFY_LEARNING, DEFAULT_NOTIFY_LEARNING)
            user_input.setdefault(CONF_NOTIFY_INVERTER, DEFAULT_NOTIFY_INVERTER)
            user_input.setdefault(CONF_NOTIFY_STARTUP, DEFAULT_NOTIFY_STARTUP)
            user_input.setdefault(CONF_DIAGNOSTIC, True)
            user_input.setdefault(CONF_HOURLY, False)
            
            return self.async_create_entry(
                title="Solar Forecast ML",
                data=user_input
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
            vol.Optional(CONF_PLANT_KWP): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=1000)),
            vol.Optional(
                CONF_UPDATE_INTERVAL, 
                default=DEFAULT_UPDATE_INTERVAL
            ): vol.All(vol.Coerce(int), vol.Range(min=600, max=86400)),
            
            # Forecast.Solar Sensor
            vol.Optional(CONF_FORECAST_SOLAR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            
            # v2.3.0: Neuer optionaler Sensor für Tagesprofil-Learning
            vol.Optional(CONF_CURRENT_POWER): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="power")
            ),
            
            # Optionale Sensoren
            vol.Optional(CONF_LUX_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="illuminance")
            ),
            vol.Optional(CONF_TEMP_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
            ),
            vol.Optional(CONF_WIND_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="wind_speed")
            ),
            vol.Optional(CONF_UV_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            
            # Inverter Sensoren
            vol.Optional(CONF_INVERTER_POWER): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="power")
            ),
            vol.Optional(CONF_INVERTER_DAILY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="energy")
            ),
            
            # Feature Toggles
            vol.Optional(CONF_DIAGNOSTIC, default=True): cv.boolean,
            vol.Optional(CONF_HOURLY, default=False): cv.boolean,
            
            # Notification Toggles
            vol.Optional(CONF_NOTIFY_FORECAST, default=DEFAULT_NOTIFY_FORECAST): cv.boolean,
            vol.Optional(CONF_NOTIFY_LEARNING, default=DEFAULT_NOTIFY_LEARNING): cv.boolean,
            vol.Optional(CONF_NOTIFY_INVERTER, default=DEFAULT_NOTIFY_INVERTER): cv.boolean,
            vol.Optional(CONF_NOTIFY_STARTUP, default=DEFAULT_NOTIFY_STARTUP): cv.boolean,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "info": "Konfiguriere deine Solar Forecast ML Integration. Alle Einstellungen können später geändert werden."
            }
        )

    async def async_step_reconfigure(self, user_input=None):
        """Handle reconfiguration of the integration."""
        config_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        
        if user_input is not None:
            # Bereinige leere Strings zu None für optionale Felder
            cleaned_input = {}
            for key, value in user_input.items():
                if value == "" or value is None:
                    # Optionale Sensoren nicht in cleaned_input aufnehmen wenn leer
                    if key not in [CONF_WEATHER_ENTITY, CONF_POWER_ENTITY, CONF_UPDATE_INTERVAL, CONF_PLANT_KWP]:
                        continue
                cleaned_input[key] = value
            
            # Merge mit bestehenden Notification-Einstellungen
            new_data = {**config_entry.data, **cleaned_input}
            
            self.hass.config_entries.async_update_entry(
                config_entry,
                data=new_data
            )
            
            # Reload Integration
            await self.hass.config_entries.async_reload(config_entry.entry_id)
            
            return self.async_abort(reason="reconfigure_successful")

        current = config_entry.data
        
        # Schema mit aktuellen Werten
        schema_dict = {
            vol.Required(
                CONF_WEATHER_ENTITY,
                default=current.get(CONF_WEATHER_ENTITY, "weather.home")
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="weather")
            ),
            vol.Required(
                CONF_POWER_ENTITY,
                default=current.get(CONF_POWER_ENTITY)
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional(
                CONF_UPDATE_INTERVAL,
                default=current.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
            ): vol.All(vol.Coerce(int), vol.Range(min=600, max=86400)),
        }
        
        # Plant kWp
        if current.get(CONF_PLANT_KWP):
            schema_dict[vol.Optional(CONF_PLANT_KWP, default=current.get(CONF_PLANT_KWP))] = vol.All(
                vol.Coerce(float), vol.Range(min=0.5, max=1000)
            )
        else:
            schema_dict[vol.Optional(CONF_PLANT_KWP)] = vol.All(
                vol.Coerce(float), vol.Range(min=0.5, max=1000)
            )
        
        reconfigure_schema = vol.Schema(schema_dict)
        
        # Optionale Entity-Felder
        optional_entities = {
            CONF_FORECAST_SOLAR: ("sensor", None),
            CONF_CURRENT_POWER: ("sensor", "power"),
            CONF_LUX_SENSOR: ("sensor", "illuminance"),
            CONF_TEMP_SENSOR: ("sensor", "temperature"),
            CONF_WIND_SENSOR: ("sensor", "wind_speed"),
            CONF_UV_SENSOR: ("sensor", None),
            CONF_INVERTER_POWER: ("sensor", "power"),
            CONF_INVERTER_DAILY: ("sensor", "energy"),
        }
        
        schema_dict = reconfigure_schema.schema
        for key, (domain, device_class) in optional_entities.items():
            current_value = current.get(key)
            config = selector.EntitySelectorConfig(domain=domain)
            if device_class:
                config = selector.EntitySelectorConfig(domain=domain, device_class=device_class)
            
            if current_value:
                schema_dict[vol.Optional(key, default=current_value)] = selector.EntitySelector(config)
            else:
                schema_dict[vol.Optional(key)] = selector.EntitySelector(config)
        
        reconfigure_schema = vol.Schema(schema_dict)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=reconfigure_schema,
            description_placeholders={
                "info": "Ändere die Sensoren und Einstellungen. Die Integration wird automatisch neu geladen."
            }
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return SolarForecastMLOptionsFlow()


class SolarForecastMLOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Solar Forecast ML - Benachrichtigungen und Toggles."""

    # ✅ FIX: ENTFERNT self.config_entry Zuweisung (deprecated)
    # Nutze stattdessen self.handler für Zugriff auf entry_id

    async def async_step_init(self, user_input=None):
        """Manage the options - Benachrichtigungen und Feature Toggles."""
        
        # ✅ FIX: Hole config_entry über handler statt direkter Zuweisung
        config_entry = self.hass.config_entries.async_get_entry(self.handler)
        
        if user_input is not None:
            # Update die Config Entry
            new_data = {**config_entry.data, **user_input}
            
            self.hass.config_entries.async_update_entry(
                config_entry,
                data=new_data
            )
            
            # Reload Integration
            await self.hass.config_entries.async_reload(config_entry.entry_id)
            
            return self.async_create_entry(title="", data={})

        current = config_entry.data

        # Nur Toggles und Benachrichtigungen im Options Flow
        options_schema = vol.Schema({
            # Feature Toggles
            vol.Optional(
                CONF_DIAGNOSTIC,
                default=current.get(CONF_DIAGNOSTIC, True)
            ): cv.boolean,
            
            vol.Optional(
                CONF_HOURLY,
                default=current.get(CONF_HOURLY, False)
            ): cv.boolean,
            
            # Notification Toggles
            vol.Optional(
                CONF_NOTIFY_FORECAST,
                default=current.get(CONF_NOTIFY_FORECAST, DEFAULT_NOTIFY_FORECAST),
                description={"description": "Tägliche Prognose-Benachrichtigung (6:00 Uhr)"}
            ): cv.boolean,
            
            vol.Optional(
                CONF_NOTIFY_LEARNING,
                default=current.get(CONF_NOTIFY_LEARNING, DEFAULT_NOTIFY_LEARNING),
                description={"description": "Lern-Ergebnis-Benachrichtigung (23:00 Uhr)"}
            ): cv.boolean,
            
            vol.Optional(
                CONF_NOTIFY_INVERTER,
                default=current.get(CONF_NOTIFY_INVERTER, DEFAULT_NOTIFY_INVERTER),
                description={"description": "Inverter-Offline-Warnung"}
            ): cv.boolean,
            
            vol.Optional(
                CONF_NOTIFY_STARTUP,
                default=current.get(CONF_NOTIFY_STARTUP, DEFAULT_NOTIFY_STARTUP),
                description={"description": "Start-Benachrichtigung"}
            ): cv.boolean,
        })

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            description_placeholders={
                "info": "Aktiviere/Deaktiviere Benachrichtigungen und Features."
            }
        )