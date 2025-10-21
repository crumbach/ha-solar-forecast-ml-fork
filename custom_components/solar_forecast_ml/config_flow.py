"""
Config flow für die Solar Forecast ML Integration.

Diese Datei definiert die Benutzeroberfläche, die beim Hinzufügen und
Konfigurieren der Integration in Home Assistant angezeigt wird.
"""
from __future__ import annotations
from typing import Any
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import OptionsFlowWithReload  # FIX: Expliziter Import für OptionsFlowWithReload
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    # Basis-Konstanten
    DOMAIN,
    # Config-Schlüssel
    CONF_CURRENT_POWER,
    CONF_FORECAST_SOLAR,
    CONF_LUX_SENSOR,
    CONF_PLANT_KWP,
    CONF_POWER_ENTITY,
    CONF_RAIN_SENSOR,
    CONF_TEMP_SENSOR,
    CONF_TOTAL_CONSUMPTION_TODAY,
    CONF_UV_SENSOR,
    CONF_WEATHER_ENTITY,
    CONF_WIND_SENSOR,
    # Options-Schlüssel (neu hinzugefügt für OPTIONS_SCHEMA)
    CONF_UPDATE_INTERVAL,
    CONF_DIAGNOSTIC,
    CONF_HOURLY,
    CONF_NOTIFY_STARTUP,
    CONF_NOTIFY_FORECAST,
    CONF_NOTIFY_LEARNING,
    CONF_NOTIFY_SUCCESSFUL_LEARNING,
)


@config_entries.HANDLERS.register(DOMAIN)
class SolarForecastMLConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Behandelt den Konfigurations-Flow."""
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Leitet den Benutzer zum Options-Flow."""
        return SolarForecastMLOptionsFlow(config_entry)

    def _get_schema(self, user_input: dict[str, Any] | None) -> vol.Schema:
        """Gibt das Schema für die Konfiguration zurück, mit Defaults für Prefill."""
        if user_input is not None:
            defaults = user_input
        else:
            defaults = {}

        return vol.Schema({
            vol.Required(
                CONF_WEATHER_ENTITY,
                default=defaults.get(CONF_WEATHER_ENTITY)
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain=["weather"])),
            vol.Required(
                CONF_POWER_ENTITY,
                default=defaults.get(CONF_POWER_ENTITY)
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain=["sensor"])),
            vol.Optional(
                CONF_TOTAL_CONSUMPTION_TODAY,
                default=defaults.get(CONF_TOTAL_CONSUMPTION_TODAY)
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain=["sensor"])),
            vol.Optional(
                CONF_PLANT_KWP,
                default=defaults.get(CONF_PLANT_KWP, "")
            ): str,
            vol.Optional(
                CONF_RAIN_SENSOR,
                default=defaults.get(CONF_RAIN_SENSOR)
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain=["sensor"])),
            vol.Optional(
                CONF_CURRENT_POWER,
                default=defaults.get(CONF_CURRENT_POWER)
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain=["sensor"])),
            vol.Optional(
                CONF_LUX_SENSOR,
                default=defaults.get(CONF_LUX_SENSOR)
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain=["sensor"])),
            vol.Optional(
                CONF_TEMP_SENSOR,
                default=defaults.get(CONF_TEMP_SENSOR)
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain=["sensor"])),
            vol.Optional(
                CONF_WIND_SENSOR,
                default=defaults.get(CONF_WIND_SENSOR)
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain=["sensor"])),
            vol.Optional(
                CONF_UV_SENSOR,
                default=defaults.get(CONF_UV_SENSOR)
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain=["sensor"])),
            vol.Optional(
                CONF_FORECAST_SOLAR,
                default=defaults.get(CONF_FORECAST_SOLAR)
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain=["sensor"])),
        })

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Behandelt die Ersteinrichtung."""
        errors = {}
        if user_input is not None:
            # Validierung: Erforderliche Felder prüfen
            if not user_input.get(CONF_WEATHER_ENTITY):
                errors[CONF_WEATHER_ENTITY] = "required"
            if not user_input.get(CONF_POWER_ENTITY):
                errors[CONF_POWER_ENTITY] = "required"
            if errors:
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._get_schema(user_input),
                    errors=errors,
                )

            # Prüfe auf Duplikate basierend auf power_entity
            await self.async_set_unique_id(user_input[CONF_POWER_ENTITY])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(title="Solar Forecast ML", data=user_input)
        
        return self.async_show_form(
            step_id="user",
            data_schema=self._get_schema({}),
            errors={},
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Behandelt die Rekonfiguration."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        errors = {}
        
        if user_input is not None:
            # Validierung: Erforderliche Felder prüfen
            if not user_input.get(CONF_WEATHER_ENTITY):
                errors[CONF_WEATHER_ENTITY] = "required"
            if not user_input.get(CONF_POWER_ENTITY):
                errors[CONF_POWER_ENTITY] = "required"
            if errors:
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=self._get_schema(user_input),
                    errors=errors,
                )

            # Update der Entry-Daten (nur nicht-leere Werte übernehmen und mergen)
            new_data = {**entry.data}
            for key, value in user_input.items():
                if value and value.strip():  # Nur setzen, wenn nicht leer
                    new_data[key] = value

            return self.async_update_entry(
                entry,
                data=new_data,
            )

        # Prefill mit aktuellen Daten
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._get_schema(entry.data),
            errors=errors,
        )


class SolarForecastMLOptionsFlow(OptionsFlowWithReload):
    """Behandelt den Options-Flow mit automatischer Reload nach Änderungen."""
    def __init__(self, config_entry: config_entries.ConfigEntry):
        self.config_entry = config_entry

    OPTIONS_SCHEMA = vol.Schema({
        vol.Optional(
            CONF_UPDATE_INTERVAL,
            default=3600
        ): vol.All(vol.Coerce(int), vol.Range(min=300, max=86400)),
        vol.Optional(
            CONF_DIAGNOSTIC,
            default=True
        ): bool,
        vol.Optional(
            CONF_HOURLY,
            default=False
        ): bool,
        vol.Optional(
            CONF_NOTIFY_STARTUP,
            default=True
        ): bool,
        vol.Optional(
            CONF_NOTIFY_FORECAST,
            default=False
        ): bool,
        vol.Optional(
            CONF_NOTIFY_LEARNING,
            default=False
        ): bool,
        vol.Optional(
            CONF_NOTIFY_SUCCESSFUL_LEARNING,
            default=True
        ): bool,
    })

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Verwaltet die Optionen."""
        errors = {}
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                self.OPTIONS_SCHEMA, self.config_entry.options
            ),
            errors=errors,
        )