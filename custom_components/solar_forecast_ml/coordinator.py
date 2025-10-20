"""
DataUpdateCoordinator for the Solar Forecast ML integration.

This file contains the central logic for data fetching, processing,
and machine learning, migrated from the original monolithic sensor.py.
"""

import asyncio
import logging
import statistics
from datetime import date, datetime, timedelta
from typing import Dict

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

# Importiert alle Konstanten aus der zentralen const.py
from .const import *
from .helpers import (
    _read_history_file,
    _write_history_file,
    calculate_initial_base_capacity,
)

_LOGGER = logging.getLogger(__name__)


class SolarForecastCoordinator(DataUpdateCoordinator):
    """Selbstlernender Coordinator für Solar Forecast."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """Initialize the coordinator."""
        self.entry = entry
        config = entry.data
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=config.get(CONF_UPDATE_INTERVAL, 3600)),
        )

        # --- Attribute 1:1 aus der Original-Logik ---
        self.weather_entity = config[CONF_WEATHER_ENTITY]
        self.power_entity = config[CONF_POWER_ENTITY]
        self.fs_sensor = config.get(CONF_FORECAST_SOLAR)
        self.current_power_sensor = config.get(CONF_CURRENT_POWER)
        self.lux_sensor = config.get(CONF_LUX_SENSOR)
        self.temp_sensor = config.get(CONF_TEMP_SENSOR)
        self.wind_sensor = config.get(CONF_WIND_SENSOR)
        self.uv_sensor = config.get(CONF_UV_SENSOR)
        self.inverter_power = config.get(CONF_INVERTER_POWER)
        self.inverter_daily = config.get(CONF_INVERTER_DAILY)
        self.enable_diagnostic = config.get(CONF_DIAGNOSTIC, True)
        self.enable_hourly = config.get(CONF_HOURLY, False)
        self.notify_forecast = config.get(CONF_NOTIFY_FORECAST, False)
        self.notify_learning = config.get(CONF_NOTIFY_LEARNING, False)
        self.notify_inverter = config.get(CONF_NOTIFY_INVERTER, False)
        self.notify_startup = config.get(CONF_NOTIFY_STARTUP, True)

        plant_kwp = config.get(CONF_PLANT_KWP)
        self.base_capacity = (
            calculate_initial_base_capacity(plant_kwp)
            if plant_kwp
            else DEFAULT_BASE_CAPACITY
        )
        _LOGGER.info(f"🏭 Base Capacity initialisiert: {self.base_capacity:.2f} kWh")

        self.weights = DEFAULT_WEIGHTS.copy()
        self.daily_predictions = {}
        self.accuracy = 0.0
        self.last_forecast_date = None
        self.last_inverter_notification = None
        self.last_update = datetime.now()
        self.next_hour_pred = 0.0
        self.hourly_profile = {}
        self.today_hourly_data = {}
        self.last_hourly_collection = None
        self.weather_type = self._detect_weather_type()
        self.forecast_method = None
        self.dwd_forecast_attr = None
        self.data = {"heute": 0.0, "morgen": 0.0, "genauigkeit": 0.0}

        # --- Initialisierung und Zeitplanung ---
        hass.async_create_task(self._initial_setup())
        async_track_time_change(hass, self._morning_forecast, hour=6, minute=0, second=0)
        async_track_time_change(hass, self._midnight_learning, hour=23, minute=0, second=0)
        if self.current_power_sensor:
            async_track_time_change(hass, self._collect_hourly_data, minute=0, second=0)
            _LOGGER.info("📊 Stündliche Datensammlung aktiviert")

    # ==================================================================================
    # === AB HIER BEGINNT DIE KOMPLETTE LOGIK AUS DEINEM ORIGINAL-SKRIPT, 1:1 ÜBERNOMMEN ===
    # ==================================================================================

    async def _initial_setup(self):
        """Führt initiales Laden von Daten durch (wird nur einmal bei Start aufgerufen)."""
        await self._async_load_weights()
        await self._load_history()
        await self._load_hourly_profile()
        self._load_last_data()
        self._calibrate_base_capacity()
        if self.notify_startup:
            await self._notify_start_success()

    async def _async_update_data(self) -> dict:
        """Haupt-Update-Methode, die vom Coordinator periodisch aufgerufen wird."""
        today = date.today()
        if self.last_forecast_date != today:
            await self._create_forecast()
        
        if self.enable_hourly:
            await self._predict_next_hour()

        self.last_update = datetime.now()
        return self.data

    async def async_manual_forecast(self):
        """Löst eine sichere manuelle Prognose aus (für den Button)."""
        _LOGGER.info("🔄 Manuelle Prognose durch Button ausgelöst")
        try:
            await self._load_history()
            await self._create_forecast()
            
            await self.hass.services.async_call("persistent_notification", "create", {
                "title": "✅ Prognose manuell erstellt",
                "message": f"Heute: {self.data.get('heute', 0):.2f} kWh\nMorgen: {self.data.get('morgen', 0):.2f} kWh",
                "notification_id": "solar_forecast_ml_manual"
            })
        except Exception as e:
            _LOGGER.error(f"Fehler beim manuellen Forecast: {e}", exc_info=True)
            await self.hass.services.async_call("persistent_notification", "create", {
                "title": "❌ Fehler bei manueller Prognose", "message": f"Fehler: {str(e)}",
                "notification_id": "solar_forecast_ml_manual_error"
            })

    def _detect_weather_type(self) -> str:
        """Erkennt die Wetter-Integration."""
        entity_id = self.weather_entity.lower()
        if 'dwd' in entity_id or 'deutscher_wetterdienst' in entity_id:
            _LOGGER.info("🌤️ Erkannt: DWD Weather")
            return 'dwd'
        if 'met' in entity_id or 'forecast_home' in entity_id:
            _LOGGER.info("🌤️ Erkannt: Met.no Weather")
            return 'met.no'
        if 'openweather' in entity_id:
            _LOGGER.info("🌤️ Erkannt: OpenWeatherMap")
            return 'openweathermap'
        _LOGGER.info("🌤️ Erkannt: Generische Weather-Integration")
        return 'generic'

    async def _detect_forecast_method(self) -> str | None:
        """Findet die beste Methode, um Wetterdaten abzufragen."""
        _LOGGER.info(f"🔍 Teste Forecast-Methoden für {self.weather_type}...")
        for attempt in range(1, 4):
            if attempt > 1:
                await asyncio.sleep(2 if attempt == 2 else 5)
            try:
                response = await self.hass.services.async_call("weather", "get_forecasts", {"type": "daily", "entity_id": self.weather_entity}, blocking=True, return_response=True)
                forecast = response.get(self.weather_entity, {}).get("forecast") or response.get("forecast")
                if forecast:
                    _LOGGER.info("✅ Weather-Methode: get_forecasts Service")
                    return "service"
            except Exception: pass
            try:
                state = self.hass.states.get(self.weather_entity)
                if state and state.attributes.get('forecast'):
                    _LOGGER.info("✅ Weather-Methode: forecast Attribut (Legacy)")
                    return "attribute"
            except Exception: pass
        _LOGGER.error("❌ Keine funktionierende Forecast-Methode gefunden!")
        return None

    async def _get_weather_forecast(self):
        """Holt die Wettervorhersage basierend auf der erkannten Methode."""
        if self.forecast_method is None:
            self.forecast_method = await self._detect_forecast_method()
        
        if self.forecast_method == "service":
            try:
                response = await self.hass.services.async_call("weather", "get_forecasts", {"type": "daily", "entity_id": self.weather_entity}, blocking=True, return_response=True)
                return response.get(self.weather_entity, {}).get("forecast") or response.get("forecast", [])
            except Exception as e: _LOGGER.error(f"Service-Forecast fehlgeschlagen: {e}")
        elif self.forecast_method == "attribute":
            try:
                state = self.hass.states.get(self.weather_entity)
                return state.attributes.get('forecast', []) if state else []
            except Exception as e: _LOGGER.error(f"Attribut-Forecast fehlgeschlagen: {e}")
        return []

    async def _get_next_hour_forecast(self):
        """Holt die stündliche Vorhersage."""
        try:
            response = await self.hass.services.async_call("weather", "get_forecasts", {"type": "hourly", "entity_id": self.weather_entity}, blocking=True, return_response=True)
            forecast = response.get(self.weather_entity, {}).get("forecast", [])
            return forecast[0] if forecast else None
        except Exception:
            daily_forecast = await self._get_weather_forecast()
            return daily_forecast[0] if daily_forecast else None

    def _is_night_time(self) -> bool:
        """Prüft, ob es aktuell Nacht ist."""
        try:
            now = dt_util.now()
            sunrise = get_astral_event_date(self.hass, SUN_EVENT_SUNRISE, now.date())
            sunset = get_astral_event_date(self.hass, SUN_EVENT_SUNSET, now.date())
            if sunrise and sunset: return now < sunrise or now > sunset
        except Exception: pass
        return datetime.now().hour < 6 or datetime.now().hour >= 21

    async def _collect_hourly_data(self, now):
        """Sammelt stündliche Produktionsdaten."""
        if not self.current_power_sensor: return
        try:
            hour = now.hour
            if self.last_hourly_collection == hour: return
            state = self.hass.states.get(self.current_power_sensor)
            if state and state.state not in ['unknown', 'unavailable']:
                kwh = float(state.state) / 1000.0
                self.today_hourly_data[hour] = kwh
                self.last_hourly_collection = hour
                today = date.today().isoformat()
                if today in self.daily_predictions:
                    if 'hourly_data' not in self.daily_predictions[today]: self.daily_predictions[today]['hourly_data'] = {}
                    self.daily_predictions[today]['hourly_data'].update(self.today_hourly_data)
                    self._save_history()
        except (ValueError, Exception) as e: _LOGGER.error(f"Fehler bei stündlicher Datensammlung: {e}", exc_info=True)
    
    async def _load_hourly_profile(self):
        self.hourly_profile = await self.hass.async_add_executor_job(_read_history_file, HOURLY_PROFILE_FILE)

    def _save_hourly_profile(self):
        self.hass.async_add_executor_job(_write_history_file, HOURLY_PROFILE_FILE, self.hourly_profile)

    def _calculate_hourly_profile(self):
        try:
            if not self.daily_predictions: return
            recent_days = list(self.daily_predictions.items())[-30:]
            hourly_patterns = {}
            for _, day_data in recent_days:
                if isinstance(day_data, dict) and day_data.get('actual', 0) > 0.5:
                    for hour_str, kwh in day_data.get('hourly_data', {}).items():
                        try:
                            hour = int(hour_str)
                            if kwh > 0:
                                percentage = (kwh / day_data['actual']) * 100.0
                                if hour not in hourly_patterns: hourly_patterns[hour] = []
                                hourly_patterns[hour].append(percentage)
                        except (ValueError, TypeError): continue
            new_profile = {}
            for hour, percentages in hourly_patterns.items():
                if len(percentages) >= 3:
                    new_profile[hour] = {
                        'mean': statistics.mean(percentages),
                        'std': statistics.stdev(percentages) if len(percentages) > 1 else 0
                    }
            if new_profile:
                self.hourly_profile = new_profile
                self._save_hourly_profile()
        except Exception as e: _LOGGER.error(f"Fehler bei Tagesprofil-Berechnung: {e}", exc_info=True)

    def _get_status_text(self) -> str:
        """Generiere den vollständigen Status-Text für den Diagnose-Sensor."""
        now = datetime.now()
        hours_since_forecast = (now - self.last_update).total_seconds() / 3600
        next_learning = 23 - now.hour if now.hour < 23 else 23 + 24 - now.hour
        
        inverter_status = "Nicht konfiguriert"
        inverter_offline = False
        if self.inverter_power:
            power_state = self.hass.states.get(self.inverter_power)
            if power_state and power_state.state not in ['unknown', 'unavailable']:
                try:
                    if float(power_state.state) > DEFAULT_INVERTER_THRESHOLD:
                        inverter_status = "Online"
                    else:
                        inverter_status = "Offline (0W)"
                        inverter_offline = True
                except ValueError:
                    inverter_status = "Offline (ungültig)"
                    inverter_offline = True

        status_emoji = "⚠️" if (hours_since_forecast >= 1 or inverter_offline) else "✅"
        
        status_parts = []
        status_parts.append(f"Prognose vor: {hours_since_forecast:.1f}h")
        status_parts.append(f"Learning in: {next_learning}h")
        
        if self.inverter_power or self.inverter_daily:
            status_parts.append(f"Inverter: {inverter_status}")
            
        status_parts.append(f"{self.accuracy:.0f}%")
        
        if self.hourly_profile:
            status_parts.append(f"Profil: {len(self.hourly_profile)}h")
            
        return f"{status_emoji} " + " | ".join(status_parts)

    async def _predict_next_hour(self):
        if not self.enable_hourly or self._is_night_time(): self.next_hour_pred = 0.0; return
        try:
            hour_forecast = await self._get_next_hour_forecast()
            if hour_forecast:
                self.next_hour_pred = self._predict_hour(hour_forecast, await self._get_sensor_data())
        except Exception as e: _LOGGER.error(f"Fehler bei stündlicher Prognose: {e}")

    def _predict_hour(self, forecast: Dict, sensor_data: Dict) -> float:
        if self._is_night_time(): return 0.0
        try:
            condition = forecast.get('condition', 'cloudy')
            if condition in ['clear-night', 'night']: return 0.0
            cloud = forecast.get('cloud_coverage', 50)
            precip = forecast.get('precipitation', 0)
            weather_f = WEATHER_FACTORS.get(condition, 0.4)
            if cloud is not None: weather_f *= (0.5 + 0.5 * (1 - (cloud / 100.0)))
            if precip and precip > 0: weather_f *= 0.5
            hour = datetime.fromisoformat(forecast.get('datetime', datetime.now().isoformat())).hour
            if hour < 6 or hour > 20: return 0.0
            solar_hour_f = max(0, 1 - abs(hour - 12) / 6)
            pred = (self.base_capacity / 10) * weather_f * self.weights['base'] * solar_hour_f
            if 'inverter_factor' in sensor_data: pred *= sensor_data['inverter_factor']
            return max(0, pred)
        except Exception as e:
            _LOGGER.error(f"Fehler bei _predict_hour: {e}")
            return 0.0

    async def _async_load_weights(self):
        saved_weights = await self.hass.async_add_executor_job(_read_history_file, WEIGHTS_FILE)
        if saved_weights:
            self.weights.update(saved_weights)
            self.base_capacity = saved_weights.get('base_capacity', self.base_capacity)

    async def _async_save_weights(self):
        save_data = self.weights.copy(); save_data['base_capacity'] = self.base_capacity
        await self.hass.async_add_executor_job(_write_history_file, WEIGHTS_FILE, save_data)

    def _save_weights(self):
        self.hass.async_create_task(self._async_save_weights())

    async def _load_history(self):
        self.daily_predictions = await self.hass.async_add_executor_job(_read_history_file, HISTORY_FILE)

    def _save_history(self):
        self.hass.async_add_executor_job(_write_history_file, HISTORY_FILE, self.daily_predictions)

    def _load_last_data(self):
        if self.daily_predictions:
            today = date.today().isoformat()
            yesterday = (date.today() - timedelta(days=1)).isoformat()
            last = self.daily_predictions.get(today) or self.daily_predictions.get(yesterday)
            if last and 'predicted' in last:
                self.data = {"heute": last['predicted'], "morgen": last.get('predicted_morgen', 0), "genauigkeit": self.accuracy}

    async def _notify_start_success(self):
        await self.hass.services.async_call("persistent_notification", "create", {"title": "✅ SolarForecastML gestartet", "message": f"Basiskapazität: {self.base_capacity:.2f} kWh", "notification_id": "solar_forecast_ml_start"})

    async def _notify_inverter_offline(self):
        if not self.notify_inverter: return
        if self.last_inverter_notification == date.today().isoformat(): return
        await self.hass.services.async_call("persistent_notification", "create", {"title": "⚠️ Inverter scheint offline", "message": "Prognose auf 0 kWh angepasst.", "notification_id": "solar_forecast_ml_inverter"})
        self.last_inverter_notification = date.today().isoformat()

    def _calibrate_base_capacity(self):
        actuals = [v.get('actual',0) for v in self.daily_predictions.values() if isinstance(v,dict) and v.get('actual',0)>0]
        if actuals:
            avg = sum(actuals)/len(actuals)
            if avg > self.base_capacity * 0.5: self.base_capacity = avg; self._save_weights()

    async def _morning_forecast(self, now):
        await self._create_forecast()

    async def _midnight_learning(self, now):
        _LOGGER.info("🌑 Starte Lernprozess...")
        try:
            today_iso = date.today().isoformat()
            state = self.hass.states.get(self.power_entity)
            if state and state.state not in ['unknown', 'unavailable']:
                actual = float(state.state)
                if actual > 0:
                    if today_iso not in self.daily_predictions: self.daily_predictions[today_iso] = {}
                    self.daily_predictions[today_iso]['actual'] = actual
                    self._save_history()
            
            yesterday_iso = (date.today() - timedelta(days=1)).isoformat()
            if yesterday_iso in self.daily_predictions:
                d = self.daily_predictions[yesterday_iso]
                pred, actual = d.get('predicted', 0), d.get('actual', 0)
                if actual > 0 and pred > 0:
                    error = actual - pred
                    self.weights['base'] += 0.01 * (error / self.base_capacity)
                    self.weights['base'] = max(0.5, min(1.5, self.weights['base']))
                    # Hier könnte noch mehr Lernlogik für andere Sensoren stehen
                    await self._async_save_weights()
                    self._calculate_accuracy()
                    if self.notify_learning: await self._notify_learning_result(yesterday_iso, pred, actual)
        except Exception as e: _LOGGER.error(f"Fehler beim Midnight Learning: {e}", exc_info=True)

    async def _notify_learning_result(self, date_str, pred, actual):
        error_percent = (actual - pred) / actual * 100 if actual > 0 else 0
        await self.hass.services.async_call("persistent_notification", "create", {"title": f"💡 Lern-Ergebnis {date_str}", "message": f"Prognose: {pred:.2f}, Tatsächlich: {actual:.2f}, Abweichung: {error_percent:.1f}%", "notification_id": "solar_forecast_ml_learning"})

    def _calculate_accuracy(self):
        errors = [abs((d['actual'] - d.get('predicted',0)) / d['actual']) * 100 for d in list(self.daily_predictions.values())[-30:] if isinstance(d,dict) and d.get('actual',0)>0]
        if errors: self.accuracy = max(0, 100 - (sum(errors) / len(errors)))

    async def _create_forecast(self):
        """Erstellt eine neue Prognose für heute und morgen."""
        try:
            forecast_data = await self._get_weather_forecast()
            if not forecast_data or len(forecast_data) < 2: return
            
            sensor_data = await self._get_sensor_data()
            heute_kwh = self._predict_day(forecast_data[0], sensor_data, is_today=True)
            morgen_kwh = self._predict_day(forecast_data[1], sensor_data, is_today=False)

            if self._is_night_time() and datetime.now().hour >= 21:
                heute_kwh = 0.0

            today_iso = date.today().isoformat()
            if today_iso not in self.daily_predictions: self.daily_predictions[today_iso] = {}
            self.daily_predictions[today_iso].update({
                'predicted': heute_kwh, 'predicted_morgen': morgen_kwh, 'features': sensor_data
            })
            self._save_history()

            self.data = {"heute": round(heute_kwh, 2), "morgen": round(morgen_kwh, 2), "genauigkeit": round(self.accuracy, 1)}
            self.async_set_updated_data(self.data)
            
            if self.notify_forecast: await self._notify_forecast(heute_kwh, morgen_kwh)
        except Exception as e: _LOGGER.error(f"Fehler bei Prognoseerstellung: {e}", exc_info=True)

    async def _get_sensor_data(self) -> Dict[str, float]:
        """Sammelt Daten von allen optionalen Sensoren."""
        data = {}
        sensors = [(self.lux_sensor,'lux'), (self.temp_sensor,'temp'), (self.wind_sensor,'wind'), (self.uv_sensor,'uv'), (self.fs_sensor,'fs')]
        for sensor, key in sensors:
            if sensor:
                state = self.hass.states.get(sensor)
                if state and state.state not in ['unknown', 'unavailable']:
                    try: data[key] = float(state.state)
                    except ValueError: pass
        
        factor = 1.0
        if self.inverter_power:
            state = self.hass.states.get(self.inverter_power)
            try:
                if state and float(state.state) <= DEFAULT_INVERTER_THRESHOLD: factor = 0.0
            except (ValueError, TypeError): pass
        data['inverter_factor'] = factor
        return data

    def _predict_day(self, forecast: Dict, sensor_data: Dict, is_today: bool) -> float:
        """Führt die eigentliche ML-Prognose für einen Tag durch."""
        if self._is_night_time() and is_today and datetime.now().hour >= 21: return 0.0
        try:
            cond = forecast.get('condition','cloudy')
            cloud = forecast.get('cloud_coverage', 50)
            precip = forecast.get('precipitation', 0)
            weather_f = WEATHER_FACTORS.get(cond, 0.4)
            if cloud is not None: weather_f *= (0.5 + 0.5 * (1 - (cloud / 100.0)))
            if precip and precip > 0: weather_f *= 0.5
            
            pred = self.base_capacity * weather_f * self.weights['base']

            # Einfluss der optionalen Sensoren
            for sensor_type in ['lux', 'temp', 'wind', 'uv']:
                if sensor_type in sensor_data:
                     pred += sensor_data[sensor_type] * self.weights.get(sensor_type, 0)
            
            if 'inverter_factor' in sensor_data: pred *= sensor_data['inverter_factor']
            if is_today and 'fs' in sensor_data:
                fs_blend = self.weights.get('fs', 0.5)
                pred = (pred * (1 - fs_blend)) + (sensor_data['fs'] * fs_blend)
            return max(0, pred)
        except Exception as e:
            _LOGGER.error(f"Fehler bei _predict_day: {e}")
            return 0.0
            
    async def _notify_forecast(self, today_kwh: float, tomorrow_kwh: float):
        await self.hass.services.async_call("persistent_notification", "create", {"title": "☀️ Solar-Prognose", "message": f"Heute: {today_kwh:.1f} kWh, Morgen: {tomorrow_kwh:.1f} kWh", "notification_id": "solar_forecast_ml_daily"})

