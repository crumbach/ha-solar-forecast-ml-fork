"""
Config flow für die Solar Forecast ML Integration.

Diese Datei definiert die Benutzeroberfläche, die beim Hinzufügen und
Konfigurieren der Integration in Home Assistant angezeigt wird.
"""
from __future__ import annotations
from typing import Any
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import OptionsFlowWithReload, SOURCE_RECONFIGURE
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
    # Options-Schlüssel
    CONF_UPDATE_INTERVAL,
    CONF_DIAGNOSTIC,
    CONF_HOURLY,
    CONF_NOTIFY_STARTUP,
    CONF_NOTIFY_FORECAST,
    CONF_NOTIFY_LEARNING,
    CONF_NOTIFY_SUCCESSFUL_LEARNING,
)

@config_entries.HANDLERS.register(DOMAIN)
class SolarForecastMLConfigFlow(config_entries.ConfigFlow):
    """Behandelt den Konfigurations-Flow."""
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Leitet den Benutzer zum Options-Flow."""
        return SolarForecastMLOptionsFlow(config_entry)

    def _get_schema(self, defaults: dict[str, Any] | None) -> vol.Schema:
        """
        Gibt das Schema für die Konfiguration zurück, mit Defaults für Prefill.
        """
        if defaults is None:
            defaults = {}

        def _get_entity_default(key: str) -> Any:
            val = defaults.get(key)
            return val if val and val != "" else vol.UNDEFINED

        def _get_string_default(key: str) -> Any:
            val = defaults.get(key)
            if val is None or val == "":
                return vol.UNDEFINED
            return str(val)

        return vol.Schema({
            vol.Required(
                CONF_WEATHER_ENTITY,
                default=defaults.get(CONF_WEATHER_ENTITY, "")
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain=["weather"])),
            vol.Required(
                CONF_POWER_ENTITY,
                default=defaults.get(CONF_POWER_ENTITY, "")
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain=["sensor"])),
            
            vol.Optional(
                CONF_TOTAL_CONSUMPTION_TODAY,
                default=_get_entity_default(CONF_TOTAL_CONSUMPTION_TODAY)
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain=["sensor"])),
            
            vol.Optional(
                CONF_PLANT_KWP,
                default=_get_string_default(CONF_PLANT_KWP)
            ): str,
            
            vol.Optional(
                CONF_RAIN_SENSOR,
                default=_get_entity_default(CONF_RAIN_SENSOR)
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain=["sensor"])),
            vol.Optional(
                CONF_CURRENT_POWER,
                default=_get_entity_default(CONF_CURRENT_POWER)
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain=["sensor"])),
            vol.Optional(
                CONF_LUX_SENSOR,
                default=_get_entity_default(CONF_LUX_SENSOR)
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain=["sensor"])),
            vol.Optional(
                CONF_TEMP_SENSOR,
                default=_get_entity_default(CONF_TEMP_SENSOR)
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain=["sensor"])),
            vol.Optional(
                CONF_WIND_SENSOR,
                default=_get_entity_default(CONF_WIND_SENSOR)
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain=["sensor"])),
            vol.Optional(
                CONF_UV_SENSOR,
                default=_get_entity_default(CONF_UV_SENSOR)
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain=["sensor"])),
            vol.Optional(
                CONF_FORECAST_SOLAR,
                default=_get_entity_default(CONF_FORECAST_SOLAR)
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain=["sensor"])),
        })

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Behandelt die Ersteinrichtung."""
        errors = {}
        prefill_data = user_input if user_input is not None else {}
        
        if user_input is not None:
            if not user_input.get(CONF_WEATHER_ENTITY):
                errors[CONF_WEATHER_ENTITY] = "required"
            if not user_input.get(CONF_POWER_ENTITY):
                errors[CONF_POWER_ENTITY] = "required"
            if errors:
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._get_schema(prefill_data),
                    errors=errors,
                )

            # UNIQUE-ID-FIX: Basier Unique-ID auf stabiler Weather-Entity (nicht changeable Power)
            unique_id = user_input[CONF_WEATHER_ENTITY].strip()
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            cleaned_data = user_input.copy()
            for key, value in cleaned_data.items():
                if value is None:
                    cleaned_data[key] = ""

            return self.async_create_entry(title="Solar Forecast ML", data=cleaned_data)
        
        return self.async_show_form(
            step_id="user",
            data_schema=self._get_schema({}),
            errors={},
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Behandelt die Rekonfiguration. UNIQUE-ID-FIX: Stabiler Check + Update bei Change."""
        if self.source != SOURCE_RECONFIGURE:
            return self.async_abort(reason="not_reconfigure")

        entry = self._get_reconfigure_entry()
        if entry is None:
            return self.async_abort(reason="entry_not_found")

        errors = {}
        prefill_data = dict(entry.data)  # Kopie für Prefill
        
        if user_input is not None:
            # Merge für Fehler-Prefill
            prefill_data.update(user_input)
            
            # Validierung (erweitert: Prüfe auf leere required nach Trim)
            if not user_input.get(CONF_WEATHER_ENTITY, "").strip():
                errors[CONF_WEATHER_ENTITY] = "required"
            if not user_input.get(CONF_POWER_ENTITY, "").strip():
                errors[CONF_POWER_ENTITY] = "required"
            
            if errors:
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=self._get_schema(prefill_data),
                    errors=errors,
                )

            # UNIQUE-ID-FIX: Basier auf Weather (stabil), trimme, und handle Changes
            new_unique_id = user_input.get(CONF_WEATHER_ENTITY, "").strip()
            old_unique_id = entry.unique_id or ""
            
            if new_unique_id != old_unique_id:
                # Bei Change: Setze neue ID und update Entry explizit (erlaubt in Reconfigure)
                await self.async_set_unique_id(new_unique_id)
                # Kein Mismatch-Check: Stattdessen direkt updaten
                self.hass.config_entries.async_update_entry(entry, unique_id=new_unique_id)
            else:
                # Bei no-change: Standard-Check für Konsistenz
                await self.async_set_unique_id(new_unique_id)
                self._abort_if_unique_id_mismatch()

            # Merge für vollständige Data (preserve alte Keys) + Clean
            cleaned_data = {**entry.data, **user_input}  # Merge: Alte + Neue
            for key, value in cleaned_data.items():
                if value is None or value == "":
                    cleaned_data[key] = ""  # Safe default für Entities/Strings
            
            # Korrekter Helper: data_updates (merge), + no-reload bei no change
            return self.async_update_reload_and_abort(
                entry,
                data_updates=cleaned_data,
                reload_even_if_entry_is_unchanged=False,  # Effizient bei no change
            )

        # Initial: Prefill mit Entry-Data
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._get_schema(prefill_data),
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