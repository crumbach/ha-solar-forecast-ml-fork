"""
DataUpdateCoordinator for the Solar Forecast ML integration.

This file contains the central logic for data fetching, processing,
and machine learning, including all feature updates.
"""
import asyncio
import logging
import statistics
from datetime import date, datetime, timedelta
from typing import Dict, List, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET
from homeassistant.core import HomeAssistant, ServiceCall, State
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import *
from .helpers import (
    _read_history_file,
    _write_history_file,
    calculate_initial_base_capacity,
)

_LOGGER = logging.getLogger(__name__)

# NEU (FIX 1): Konstanten für Retry-Logik
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 2  # Sekunden


class SolarForecastCoordinator(DataUpdateCoordinator):
    """Selbstlernender Coordinator für Solar Forecast."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """Initialize the coordinator."""
        self.entry = entry
        config = {**entry.data, **entry.options}

        super().__init__(
            hass, _LOGGER, name=DOMAIN,
            update_interval=timedelta(seconds=config.get(CONF_UPDATE_INTERVAL, 3600)),
        )

        # --- Attribute aus Konfiguration laden ---
        self.weather_entity = config.get(CONF_WEATHER_ENTITY)
        self.power_entity = config.get(CONF_POWER_ENTITY)
        self.total_consumption_entity = config.get(CONF_TOTAL_CONSUMPTION_TODAY)
        self.fs_sensor = config.get(CONF_FORECAST_SOLAR)
        self.current_power_sensor = config.get(CONF_CURRENT_POWER)
        self.lux_sensor = config.get(CONF_LUX_SENSOR)
        self.temp_sensor = config.get(CONF_TEMP_SENSOR)
        self.wind_sensor = config.get(CONF_WIND_SENSOR)
        self.uv_sensor = config.get(CONF_UV_SENSOR)
        self.rain_sensor = config.get(CONF_RAIN_SENSOR)
        self.enable_diagnostic = config.get(CONF_DIAGNOSTIC, True)
        self.enable_hourly = config.get(CONF_HOURLY, False)
        self.notify_forecast = config.get(CONF_NOTIFY_FORECAST, False)
        self.notify_learning = config.get(CONF_NOTIFY_LEARNING, False)
        self.notify_startup = config.get(CONF_NOTIFY_STARTUP, True)
        self.notify_successful_learning = config.get(CONF_NOTIFY_SUCCESSFUL_LEARNING, True)

        plant_kwp_val = config.get(CONF_PLANT_KWP)
        plant_kwp_float = 0.0
        if plant_kwp_val:
            try:
                plant_kwp_str = str(plant_kwp_val)
                plant_kwp_float = float(plant_kwp_str.replace(",", "."))
            except (ValueError, TypeError):
                _LOGGER.warning(f"Ungültiger Wert für plant_kwp: '{plant_kwp_val}'. Verwende Standard.")
                plant_kwp_float = 0.0
        self.base_capacity = (calculate_initial_base_capacity(plant_kwp_float) if plant_kwp_float > 0 else DEFAULT_BASE_CAPACITY)

        # --- Interne Zustände des Modells ---
        self.data_lock = asyncio.Lock()
        self.weights = DEFAULT_WEIGHTS.copy()
        self.daily_predictions = {}
        self.accuracy = 0.0
        self.last_forecast_date = None
        self.last_update = datetime.now()
        self.next_hour_pred = 0.0
        self.hourly_profile = None
        self.today_hourly_data = {}
        self.last_hourly_collection = None
        self.weather_type = self._detect_weather_type()
        self.forecast_method = None
        self.data = {"heute": 0.0, "morgen": 0.0, "genauigkeit": 0.0}
        self.last_successful_learning = None
        self.last_day_error_kwh = None
        self.average_yield_30_days = 0.0
        self.production_time_today = "Noch keine Produktion"
        self.autarky_today = None
        self.peak_production_time_today = "Wird berechnet..."

        # --- Initialisierung und Zeitplanung ---
        hass.async_create_task(self._initial_setup())
        async_track_time_change(hass, self._morning_forecast, hour=6, minute=0, second=0)
        async_track_time_change(hass, self._midnight_learning, hour=23, minute=0, second=0)
        if self.current_power_sensor:
            async_track_time_change(hass, self._collect_hourly_data, minute=0, second=0)

    async def _initial_setup(self):
        """Führt initiales Laden von Daten durch."""
        async with self.data_lock:
            await self._async_load_weights()
            await self._async_load_history()
            await self._async_load_hourly_profile()

        self._calculate_average_yield()
        self._calculate_peak_production_hour()
        if self.notify_startup: await self._notify_start_success()

    async def _async_update_data(self) -> dict:
        """Haupt-Update-Methode des Koordinators."""
        today = date.today()
        if self.last_forecast_date != today:
            self.production_time_today = "Noch keine Produktion"
            self.autarky_today = None
            await self._create_forecast()

        if self.enable_hourly: await self._predict_next_hour()
        self.last_update = datetime.now()

        self.data["average_yield_30_days"] = self.average_yield_30_days
        return self.data

    async def async_manual_forecast(self):
        _LOGGER.info("🔄 Manuelle Prognose durch Button ausgelöst")
        await self._create_forecast()
        if self.enable_hourly: await self._predict_next_hour()
        self.async_set_updated_data(self.data)

    async def async_manual_learning(self):
        _LOGGER.info("🧠 Manuelles Lernen durch Button ausgelöst.")
        await self._midnight_learning(dt_util.now())

    def _get_status_text(self) -> str:
        now = datetime.now()
        hours_since_forecast = (now - self.last_update).total_seconds() / 3600
        next_learning = 23 - now.hour if now.hour < 23 else 23 + 24 - now.hour
        status_emoji = "⚠️" if (hours_since_forecast >= 1) else "✅"
        parts = [f"Prognose vor: {hours_since_forecast:.1f}h", f"Learning in: {next_learning}h", f"Genauigkeit: {self.accuracy:.0f}%"]
        return f"{status_emoji} " + " | ".join(parts)

    async def _midnight_learning(self, now):
        _LOGGER.info("🌑 Starte Lernprozess...")
        async with self.data_lock:
            try:
                today_iso = date.today().isoformat()
                state: State | None = self.hass.states.get(self.power_entity)
                actual_value = 0.0 # NEU (FIX 2): Standardwert
                if state and state.state not in ['unknown', 'unavailable']:
                    try:
                        # NEU (FIX 2): Sicherer Float-Cast
                        actual_value = float(state.state)
                        if actual_value > 0:
                            if today_iso not in self.daily_predictions: self.daily_predictions[today_iso] = {}
                            self.daily_predictions[today_iso]['actual'] = actual_value
                            # await self._async_save_history() # Wird am Ende gespeichert
                            self._calculate_autarky(actual_value)
                    except ValueError:
                         _LOGGER.warning(f"Ungültiger Wert '{state.state}' vom Sensor {self.power_entity}, kann 'actual' nicht speichern.")
                         actual_value = 0.0 # Sicherer Wert
                    except Exception as e:
                         _LOGGER.error(f"Unerwarteter Fehler beim Lesen von {self.power_entity}: {e}", exc_info=True)
                         actual_value = 0.0

                yesterday_iso = (date.today() - timedelta(days=1)).isoformat()
                if yesterday_iso in self.daily_predictions:
                    d = self.daily_predictions[yesterday_iso]
                    pred, actual = d.get('predicted', 0), d.get('actual', 0)
                    if actual > 0 and pred > 0:
                        error = actual - pred
                        self.last_day_error_kwh = error
                        self.weights['base'] += 0.01 * (error / self.base_capacity)
                        self.weights['base'] = max(0.5, min(1.5, self.weights['base']))
                        # await self._async_save_weights() # Wird am Ende gespeichert
                        self._calculate_accuracy()
                        self._calculate_average_yield()
                        if self.notify_learning: await self._notify_learning_result(yesterday_iso, pred, actual)
                        if self.notify_successful_learning: await self._notify_successful_learning(yesterday_iso, error)
                        self.last_successful_learning = dt_util.now()
                        _LOGGER.info("✅ Lernprozess erfolgreich abgeschlossen.")

                        _LOGGER.info("🧠 Starte Lernen des Stundenprofils...")
                        await self._calculate_hourly_profile()
                        self._calculate_peak_production_hour()

                    else:
                        _LOGGER.warning(f"⏩ Überspringe Lernen für {yesterday_iso}: Actual={actual:.2f}, Predicted={pred:.2f}.")

                # NEU (FIX 4): Speichern am Ende des Blocks
                await self._async_save_weights()
                await self._async_save_history()

            except Exception as e: _LOGGER.error(f"❌ Fehler beim Midnight Learning: {e}", exc_info=True)

    def _calculate_autarky(self, solar_yield: float):
        if not self.total_consumption_entity: self.autarky_today = None; return
        consumption_state: State | None = self.hass.states.get(self.total_consumption_entity)
        if consumption_state and consumption_state.state not in ['unknown', 'unavailable']:
            try:
                # NEU (FIX 2): Sicherer Float-Cast
                total_consumption = float(consumption_state.state)
                if total_consumption > 0:
                    direct_consumption = min(solar_yield, total_consumption)
                    self.autarky_today = (direct_consumption / total_consumption) * 100
                else:
                    self.autarky_today = 100.0
            except ValueError:
                 _LOGGER.warning(f"Ungültiger Wert '{consumption_state.state}' vom Sensor {self.total_consumption_entity}, kann Autarkie nicht berechnen.")
                 self.autarky_today = None
            except Exception as e:
                 _LOGGER.error(f"Unerwarteter Fehler beim Lesen von {self.total_consumption_entity}: {e}", exc_info=True)
                 self.autarky_today = None

    def _calculate_peak_production_hour(self):
        if not self.hourly_profile or not isinstance(self.hourly_profile, dict):
            self.peak_production_time_today = "Keine Profildaten";
            return
        try:
            peak_hour_str = max(self.hourly_profile, key=self.hourly_profile.get)
            peak_hour = int(peak_hour_str)
            self.peak_production_time_today = f"{peak_hour:02d}:00 - {peak_hour + 1:02d}:00"
        except (ValueError, TypeError) as e:
            _LOGGER.error(f"Fehler bei Berechnung der Peak-Stunde: {e}")
            self.peak_production_time_today = "Fehler bei Berechnung"

    async def _create_forecast(self):
        async with self.data_lock:
            # NEU (FIX 4): Async laden
            await self._async_load_history()
            try:
                # NEU (FIX 1): Wetterdaten mit Retry holen
                forecasts = await self._get_weather_forecast_with_retry()
                if not forecasts or len(forecasts) < 2:
                     _LOGGER.warning("Konnte keine gültige Wettervorhersage abrufen, Prognose wird übersprungen.")
                     return

                sensor_data = await self._get_sensor_data()
                heute_kwh = self._predict_day(forecasts[0], sensor_data, True)
                morgen_kwh = self._predict_day(forecasts[1], sensor_data, False)
                if self._is_night_time() and datetime.now().hour >= 21: heute_kwh = 0.0

                today = date.today().isoformat()
                if today not in self.daily_predictions: self.daily_predictions[today] = {}
                self.daily_predictions[today].update({'predicted': heute_kwh, 'predicted_morgen': morgen_kwh, 'features': sensor_data})
                
                # NEU (FIX 4): Async speichern
                await self._async_save_history()

                self.data = {"heute": round(heute_kwh, 2), "morgen": round(morgen_kwh, 2), "genauigkeit": round(self.accuracy, 1)}
                self.last_forecast_date = date.today()

                self.async_set_updated_data(self.data)
                if self.notify_forecast: await self._notify_forecast(heute_kwh, morgen_kwh)
            except Exception as e: _LOGGER.error(f"Fehler bei Prognoseerstellung: {e}", exc_info=True)

    def _predict_day(self, forecast: Dict, data: Dict, is_today: bool) -> float:
        if self._is_night_time() and is_today and datetime.now().hour >= 21: return 0.0
        try:
            cond, cloud, precip = forecast.get('condition','cloudy'), forecast.get('cloud_coverage', 50), forecast.get('precipitation', 0)
            wf = WEATHER_FACTORS.get(cond, 0.4)
            if cloud is not None: wf *= (0.5 + 0.5 * (1 - (cloud / 100.0)))
            if precip and precip > 0: wf *= 0.5
            pred = self.base_capacity * wf * self.weights['base']
            for st in ['lux', 'temp', 'wind', 'uv', 'rain']:
                if st in data: pred += data[st] * self.weights.get(st, 0)
            if 'rain' in data and data['rain'] > 0.1: pred *= 0.5
            if is_today and 'fs' in data:
                fs_blend = self.weights.get('fs', 0.5)
                pred = (pred * (1 - fs_blend)) + (data['fs'] * fs_blend)
            return max(0, pred)
        except Exception as e: _LOGGER.error(f"Fehler bei _predict_day: {e}"); return 0.0

    async def _get_sensor_data(self) -> Dict[str, float]:
        data = {}
        sensors = [(self.lux_sensor,'lux'),(self.temp_sensor,'temp'),(self.wind_sensor,'wind'),(self.uv_sensor,'uv'),(self.fs_sensor,'fs'),(self.rain_sensor,'rain')]
        for sensor, key in sensors:
            if sensor:
                state: State | None = self.hass.states.get(sensor)
                if state and state.state not in ['unknown', 'unavailable']:
                    try:
                        # NEU (FIX 2): Sicherer Float-Cast
                        data[key] = float(state.state)
                    except ValueError:
                         _LOGGER.debug(f"Ungültiger Wert '{state.state}' vom optionalen Sensor {sensor}, wird ignoriert.")
                    except Exception as e:
                         _LOGGER.error(f"Unerwarteter Fehler beim Lesen von {sensor}: {e}", exc_info=True)
        return data

    def _detect_weather_type(self) -> str:
        if not self.weather_entity: return 'generic' # Sicherstellen, dass None abgefangen wird
        entity_id = self.weather_entity.lower()
        if 'dwd' in entity_id or 'deutscher_wetterdienst' in entity_id: return 'dwd'
        if 'met' in entity_id or 'forecast_home' in entity_id: return 'met.no'
        if 'openweather' in entity_id: return 'openweathermap'
        return 'generic'

    async def _detect_forecast_method(self) -> str | None:
        delay = INITIAL_RETRY_DELAY
        for attempt in range(MAX_RETRIES):
            try:
                response = await self.hass.services.async_call(
                    "weather", "get_forecasts",
                    {"type": "daily", "entity_id": self.weather_entity},
                    blocking=True, return_response=True, timeout=10 # NEU (FIX 1): Timeout hinzugefügt
                )
                if response and (response.get(self.weather_entity, {}).get("forecast") or response.get("forecast")):
                    return "service"
            except asyncio.TimeoutError:
                _LOGGER.debug(f"Timeout beim Erkennen der Service-Methode (Versuch {attempt + 1}/{MAX_RETRIES})")
            except Exception as e:
                _LOGGER.debug(f"Fehler beim Erkennen der Service-Methode: {e}")

            try:
                state: State | None = self.hass.states.get(self.weather_entity)
                if state and state.attributes.get('forecast'):
                    return "attribute"
            except Exception as e:
                _LOGGER.debug(f"Fehler beim Erkennen der Attribut-Methode: {e}")

            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(delay)
                delay *= 2 # Exponential backoff

        _LOGGER.error("❌ Keine funktionierende Forecast-Methode gefunden nach mehreren Versuchen!")
        return None

    # NEU (FIX 1): Funktion mit Retry-Logik
    async def _get_weather_forecast_with_retry(self) -> List[Dict[str, Any]]:
        if self.forecast_method is None: self.forecast_method = await self._detect_forecast_method()
        if not self.forecast_method: return [] # Keine Methode gefunden

        delay = INITIAL_RETRY_DELAY
        for attempt in range(MAX_RETRIES):
            forecast = await self._get_weather_forecast()
            if forecast: # Erfolg, wenn Liste nicht leer ist
                return forecast

            _LOGGER.warning(f"Fehler beim Abrufen der Wettervorhersage (Methode: {self.forecast_method}, Versuch {attempt + 1}/{MAX_RETRIES}). Warte {delay}s.")
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(delay)
                delay *= 2
            else:
                 _LOGGER.error(f"Konnte Wettervorhersage nach {MAX_RETRIES} Versuchen nicht abrufen.")
                 return [] # Endgültiger Fehler
        return [] # Sollte nie erreicht werden

    async def _get_weather_forecast(self) -> List[Dict[str, Any]]:
        """Versucht, die tägliche Prognose einmal abzurufen."""
        if self.forecast_method == "service":
            try:
                response = await self.hass.services.async_call(
                    "weather", "get_forecasts",
                    {"type": "daily", "entity_id": self.weather_entity},
                    blocking=True, return_response=True, timeout=10 # NEU (FIX 1): Timeout
                )
                # Sicherer Zugriff
                return response.get(self.weather_entity, {}).get("forecast") or response.get("forecast", [])
            except asyncio.TimeoutError:
                 _LOGGER.debug("Timeout beim Abrufen der Service-Prognose.")
                 return []
            except Exception as e:
                _LOGGER.error(f"Service-Forecast fehlgeschlagen: {e}")
                return []
        elif self.forecast_method == "attribute":
            try:
                state: State | None = self.hass.states.get(self.weather_entity)
                return state.attributes.get('forecast', []) if state else []
            except Exception as e:
                _LOGGER.error(f"Attribut-Forecast fehlgeschlagen: {e}")
                return []
        return []

    # NEU (FIX 1): Funktion mit Retry-Logik
    async def _get_hourly_weather_forecasts_with_retry(self) -> List[Dict[str, Any]]:
        delay = INITIAL_RETRY_DELAY
        for attempt in range(MAX_RETRIES):
            forecasts = await self._get_hourly_weather_forecasts()
            if forecasts: # Erfolg, wenn Liste nicht leer
                return forecasts

            _LOGGER.warning(f"Fehler beim Abrufen der stündlichen Prognose (Versuch {attempt + 1}/{MAX_RETRIES}). Warte {delay}s.")
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(delay)
                delay *= 2
            else:
                 _LOGGER.error(f"Konnte stündliche Prognose nach {MAX_RETRIES} Versuchen nicht abrufen.")
                 return []
        return []

    async def _get_hourly_weather_forecasts(self) -> List[Dict[str, Any]]:
        """Versucht, die stündliche Prognose einmal abzurufen."""
        try:
            response = await self.hass.services.async_call(
                "weather", "get_forecasts",
                {"type": "hourly", "entity_id": self.weather_entity},
                blocking=True, return_response=True, timeout=10 # NEU (FIX 1): Timeout
            )
            forecasts = response.get(self.weather_entity, {}).get("forecast", [])
            if forecasts:
                return forecasts
            _LOGGER.warning("Stündliche Prognose von Wetter-Entität erhalten, aber 'forecast'-Liste ist leer.")
            return []
        except asyncio.TimeoutError:
             _LOGGER.debug("Timeout beim Abrufen der stündlichen Prognose.")
             return []
        except Exception as e:
            _LOGGER.error(f"Fehler beim Abrufen der stündlichen Prognose: {e}")
            return []

    def _is_night_time(self) -> bool:
        try:
            now = dt_util.now() # NEU (FIX 5): Verwende aktuelle Zeit
            sunrise = get_astral_event_date(self.hass, SUN_EVENT_SUNRISE, now.date())
            sunset = get_astral_event_date(self.hass, SUN_EVENT_SUNSET, now.date())
            if sunrise and sunset:
                # Sicherstellen, dass die Zeiten Timezone-aware sind
                sunrise = dt_util.as_local(sunrise)
                sunset = dt_util.as_local(sunset)
                return now < (sunrise - timedelta(minutes=30)) or now > (sunset + timedelta(minutes=30))
        except Exception as e:
            _LOGGER.debug(f"Fehler bei Sonnenauf-/untergangsberechnung: {e}, nutze Fallback.")

        # Fallback
        return datetime.now().hour < 6 or datetime.now().hour >= 21

    async def _collect_hourly_data(self, now):
        if not self.current_power_sensor: return
        if self.last_hourly_collection == now.hour: return

        async with self.data_lock:
            try:
                hour = now.hour
                if self.last_hourly_collection == hour: return

                state: State | None = self.hass.states.get(self.current_power_sensor)
                kwh_this_hour = 0.0 # NEU (FIX 2): Standardwert
                if state and state.state not in ['unknown', 'unavailable']:
                    try:
                        # NEU (FIX 2): Sicherer Float-Cast
                        power_watts = float(state.state)
                        kwh_this_hour = power_watts / 1000.0
                    except ValueError:
                         _LOGGER.debug(f"Ungültiger Wert '{state.state}' vom Sensor {self.current_power_sensor}, setze Stunde auf 0 kWh.")
                         kwh_this_hour = 0.0
                    except Exception as e:
                         _LOGGER.error(f"Unerwarteter Fehler beim Lesen von {self.current_power_sensor}: {e}", exc_info=True)
                         kwh_this_hour = 0.0

                self.today_hourly_data[hour] = kwh_this_hour
                self.last_hourly_collection = hour
                self._update_production_time()
                today = date.today().isoformat()
                if today in self.daily_predictions:
                    if 'hourly_data' not in self.daily_predictions[today]: self.daily_predictions[today]['hourly_data'] = {}
                    self.daily_predictions[today]['hourly_data'].update(self.today_hourly_data)
                    
                    # NEU (FIX 4): Async speichern (optional hier, da _midnight_learning eh speichert)
                    # await self._async_save_history() # Könnte Performance kosten, wenn jede Stunde gespeichert wird
            except Exception as e: _LOGGER.error(f"Fehler bei stündlicher Datensammlung: {e}", exc_info=True)

    def _calculate_average_yield(self):
        # Nutzt nur gelesene Daten, kein Lock nötig
        actuals = [v.get('actual', 0) for v in list(self.daily_predictions.values())[-30:] if isinstance(v, dict) and v.get('actual', 0) > 0]
        if actuals: self.average_yield_30_days = round(sum(actuals) / len(actuals), 2)

    def _update_production_time(self):
        prod_hours = [h for h, kwh in self.today_hourly_data.items() if kwh > 0]
        if prod_hours: self.production_time_today = f"{min(prod_hours):02d}:00 - {max(prod_hours) + 1:02d}:00"
        else: self.production_time_today = "Noch keine Produktion"

    # --- NEU (FIX 4): Async I/O Funktionen ---
    async def _async_load_hourly_profile(self):
        self.hourly_profile = await self.hass.async_add_executor_job(_read_history_file, HOURLY_PROFILE_FILE)
        if not self.hourly_profile or not isinstance(self.hourly_profile, dict):
            self.hourly_profile = {str(h): (1/24) for h in range(24)} # Gleichmäßiges Profil als Fallback
            _LOGGER.info("Kein Stundenprofil gefunden oder ungültig, starte mit gleichmäßigem Profil.")

    async def _async_save_hourly_profile(self):
        await self.hass.async_add_executor_job(_write_history_file, HOURLY_PROFILE_FILE, self.hourly_profile)
        _LOGGER.info(f"Stundenprofil gespeichert.") # Profil nicht loggen (zu lang)

    async def _async_load_weights(self):
        d = await self.hass.async_add_executor_job(_read_history_file, WEIGHTS_FILE)
        if d and isinstance(d, dict):
             # Sicherstellen, dass nur erwartete Keys geladen werden
             valid_keys = list(DEFAULT_WEIGHTS.keys()) + ['base_capacity']
             loaded_weights = {k: v for k, v in d.items() if k in valid_keys and isinstance(v, (int, float))}
             self.weights.update(loaded_weights)
             self.base_capacity = loaded_weights.get('base_capacity', self.base_capacity)
             _LOGGER.info("Gewichte erfolgreich geladen.")
        else:
             _LOGGER.info("Keine gültigen Gewichte gefunden, verwende Standardwerte.")


    async def _async_save_weights(self):
        await self.hass.async_add_executor_job(_write_history_file, WEIGHTS_FILE, {**self.weights, 'base_capacity': self.base_capacity})
        _LOGGER.debug("Gewichte gespeichert.")

    async def _async_load_history(self):
        self.daily_predictions = await self.hass.async_add_executor_job(_read_history_file, HISTORY_FILE)
        if not self.daily_predictions or not isinstance(self.daily_predictions, dict):
            self.daily_predictions = {}
        _LOGGER.debug(f"History geladen: {len(self.daily_predictions)} Tage.")

    async def _async_save_history(self):
        # NEU (BONUS FIX 5): History Pruning
        today = date.today()
        cutoff_date = today - timedelta(days=365)
        keys_to_delete = [
            day_str for day_str in self.daily_predictions
            if date.fromisoformat(day_str) < cutoff_date
        ]
        if keys_to_delete:
            for key in keys_to_delete:
                del self.daily_predictions[key]
            _LOGGER.info(f"{len(keys_to_delete)} alte History-Einträge entfernt (älter als 365 Tage).")

        await self.hass.async_add_executor_job(_write_history_file, HISTORY_FILE, self.daily_predictions)
        _LOGGER.debug(f"History gespeichert: {len(self.daily_predictions)} Tage.")
    # --- Ende Async I/O ---

    def _load_last_data(self):
        # Wird nur initial aufgerufen, Lock nicht nötig
        if self.daily_predictions:
            today, yesterday = date.today().isoformat(), (date.today() - timedelta(days=1)).isoformat()
            last = self.daily_predictions.get(today) or self.daily_predictions.get(yesterday)
            if last and isinstance(last, dict) and 'predicted' in last:
                self.data = {"heute": last.get('predicted',0), "morgen": last.get('predicted_morgen', 0), "genauigkeit": self.accuracy}

    async def _notify_start_success(self):
        await self.hass.services.async_call("persistent_notification", "create", {"title": "✅ SolarForecastML gestartet", "message": f"Basiskapazität: {self.base_capacity:.2f} kWh", "notification_id": "solar_forecast_ml_start"})

    def _calibrate_base_capacity(self):
        # Diese Funktion wird nicht mehr aktiv genutzt, das Lernen übernimmt _midnight_learning
        pass
        # actuals = [v.get('actual',0) for v in self.daily_predictions.values() if isinstance(v,dict) and v.get('actual',0)>0]
        # if actuals:
        #     avg = sum(actuals)/len(actuals)
        #     if avg > self.base_capacity * 0.5:
        #         self.base_capacity = avg
        #         # NEU (FIX 4): Async speichern (muss als Task erstellt werden)
        #         self.hass.async_create_task(self._async_save_weights_locked())

    # NEU (FIX 4): Helfer für _calibrate_base_capacity (falls wieder verwendet)
    async def _async_save_weights_locked(self):
         async with self.data_lock:
             await self._async_save_weights()

    async def _morning_forecast(self, now):
        await self._create_forecast()

    async def _notify_learning_result(self, date_str, pred, actual):
        error = (actual - pred) / actual * 100 if actual > 0 else 0
        await self.hass.services.async_call("persistent_notification", "create", {"title": f"💡 Lern-Ergebnis {date_str}", "message": f"Prognose: {pred:.2f}, Tatsächlich: {actual:.2f}, Abweichung: {error:.1f}%", "notification_id": "solar_forecast_ml_learning"})

    async def _notify_successful_learning(self, date_str: str, error: float):
        await self.hass.services.async_call("persistent_notification", "create", {
            "title": f"🧠 Modell hat für {date_str} gelernt",
            "message": f"Die Prognoseabweichung betrug {error:+.2f} kWh. Die Gewichte wurden angepasst.",
            "notification_id": "solar_forecast_ml_learning_success"
        })

    def _calculate_accuracy(self):
        # Nutzt nur gelesene Daten, kein Lock nötig
        errors = [abs((d['actual']-d.get('predicted',0))/d['actual'])*100 for d in list(self.daily_predictions.values())[-30:] if isinstance(d,dict) and d.get('actual',0)>0 and d.get('predicted') is not None]
        if errors: self.accuracy = max(0, 100 - (sum(errors) / len(errors)))

    async def _notify_forecast(self, today_kwh: float, tomorrow_kwh: float):
        await self.hass.services.async_call("persistent_notification", "create", {"title": "☀️ Solar-Prognose", "message": f"Heute: {today_kwh:.1f} kWh, Morgen: {tomorrow_kwh:.1f} kWh", "notification_id": "solar_forecast_ml_daily"})

    async def _calculate_hourly_profile(self):
        _LOGGER.debug("Berechne Stundenprofil neu...")
        hourly_ratios: Dict[int, List[float]] = {h: [] for h in range(24)}
        days_processed = 0

        for day_str, day_data in reversed(list(self.daily_predictions.items())):
            if not isinstance(day_data, dict): continue

            actual_total = day_data.get('actual')
            hourly_data = day_data.get('hourly_data')

            if not actual_total or actual_total <= 0 or not hourly_data or not isinstance(hourly_data, dict):
                continue

            for hour_str, kwh in hourly_data.items():
                try:
                    hour = int(hour_str)
                    if 0 <= hour < 24 and kwh is not None and kwh >= 0: # Sicherer Check
                        ratio = kwh / actual_total if actual_total > 0 else 0 # Verhindere ZeroDivision
                        hourly_ratios[hour].append(ratio)
                except (ValueError, TypeError):
                    continue

            days_processed += 1
            if days_processed >= 60:
                break

        if days_processed == 0:
            _LOGGER.warning("Konnte Stundenprofil nicht lernen: Keine validen Verlaufsdaten gefunden.")
            return # Behalte altes Profil

        new_profile = {}
        total_ratio = 0.0
        for hour, ratios in hourly_ratios.items():
            if ratios:
                median_ratio = statistics.median(ratios)
                new_profile[str(hour)] = median_ratio
                total_ratio += median_ratio
            else:
                new_profile[str(hour)] = 0.0

        # NEU (FIX 3): Verhindere Zero-Division und NaN
        if total_ratio <= 0:
             _LOGGER.warning("Gesamtsumme der Profil-Ratios ist 0. Erstelle gleichmäßiges Standardprofil.")
             self.hourly_profile = {str(h): (1/24) for h in range(24)}
        else:
            for hour_str in new_profile:
                new_profile[hour_str] = new_profile[hour_str] / total_ratio
            self.hourly_profile = new_profile

        # NEU (FIX 4): Async speichern
        await self._async_save_hourly_profile()
        _LOGGER.info(f"✅ Stundenprofil erfolgreich aus {days_processed} Tagen gelernt und gespeichert.")


    async def _predict_next_hour(self):
        if self._is_night_time():
            self.next_hour_pred = 0.0
            return

        total_day_forecast = self.data.get("heute", 0.0)
        if total_day_forecast <= 0:
            _LOGGER.debug("Überspringe Stundenvorhersage: Tagesprognose ist 0.")
            self.next_hour_pred = 0.0
            return

        if not self.hourly_profile:
            _LOGGER.debug("Überspringe Stundenvorhersage: Stundenprofil noch nicht geladen/gelernt.")
            self.next_hour_pred = 0.0
            return

        now = dt_util.now()
        next_hour_dt = now + timedelta(hours=1)
        next_hour_int = next_hour_dt.hour

        # NEU (FIX 1): Stündliche Wetterdaten mit Retry holen
        hourly_forecasts = await self._get_hourly_weather_forecasts_with_retry()
        if not hourly_forecasts:
            _LOGGER.warning("Konnte Stundenvorhersage nicht erstellen: Keine stündlichen Wetterdaten verfügbar.")
            self.next_hour_pred = 0.0
            return

        next_hour_weather = None
        for forecast in hourly_forecasts:
            try:
                forecast_time = dt_util.parse_datetime(forecast.get("datetime"))
                if forecast_time and forecast_time.hour == next_hour_int and forecast_time.date() == next_hour_dt.date():
                    next_hour_weather = forecast
                    break
            except Exception:
                continue

        if not next_hour_weather:
            _LOGGER.warning(f"Konnte keine Wetterprognose für {next_hour_int}:00 Uhr finden.")
            self.next_hour_pred = 0.0
            return

        try:
            profile_ratio = self.hourly_profile.get(str(next_hour_int), 0.0)
            condition = next_hour_weather.get("condition", "cloudy")
            cloud_coverage = next_hour_weather.get("cloud_coverage")
            weather_factor = WEATHER_FACTORS.get(condition, 0.4)
            if cloud_coverage is not None:
                weather_factor *= (1 - (cloud_coverage / 100.0))

            base_hour_pred = total_day_forecast * profile_ratio
            final_pred = base_hour_pred * weather_factor
            self.next_hour_pred = round(max(0, final_pred), 2)
            _LOGGER.debug(f"Stundenprognose für {next_hour_int}h: {self.next_hour_pred} kWh (Base: {base_hour_pred:.2f}, WF: {weather_factor:.2f})")

        except Exception as e:
            _LOGGER.error(f"Fehler bei Berechnung der Stundenvorhersage: {e}", exc_info=True)
            self.next_hour_pred = 0.0