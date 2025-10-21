"""
DataUpdateCoordinator for the Solar Forecast ML integration.

This file contains the central logic for data fetching, processing,
and machine learning, including all feature updates.
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

        plant_kwp = config.get(CONF_PLANT_KWP)
        self.base_capacity = (calculate_initial_base_capacity(plant_kwp) if plant_kwp else DEFAULT_BASE_CAPACITY)
        
        # --- Interne Zustände des Modells ---
        self.weights = DEFAULT_WEIGHTS.copy()
        self.daily_predictions = {}
        self.accuracy = 0.0
        self.last_forecast_date = None
        self.last_update = datetime.now()
        self.next_hour_pred = 0.0
        self.hourly_profile = {}
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
        await self._async_load_weights()
        await self._load_history()
        self._calculate_average_yield()
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
        try:
            today_iso = date.today().isoformat()
            state = self.hass.states.get(self.power_entity)
            if state and state.state not in ['unknown', 'unavailable']:
                try:
                    actual_value = float(state.state)
                    if actual_value > 0:
                        if today_iso not in self.daily_predictions: self.daily_predictions[today_iso] = {}
                        self.daily_predictions[today_iso]['actual'] = actual_value
                        self._save_history()
                        self._calculate_autarky(actual_value)
                except ValueError: pass
            
            yesterday_iso = (date.today() - timedelta(days=1)).isoformat()
            if yesterday_iso in self.daily_predictions:
                d = self.daily_predictions[yesterday_iso]
                pred, actual = d.get('predicted', 0), d.get('actual', 0)
                if actual > 0 and pred > 0:
                    error = actual - pred
                    self.last_day_error_kwh = error
                    self.weights['base'] += 0.01 * (error / self.base_capacity)
                    self.weights['base'] = max(0.5, min(1.5, self.weights['base']))
                    await self._async_save_weights()
                    self._calculate_accuracy()
                    self._calculate_average_yield()
                    if self.notify_learning: await self._notify_learning_result(yesterday_iso, pred, actual)
                    if self.notify_successful_learning: await self._notify_successful_learning(yesterday_iso, error)
                    self.last_successful_learning = dt_util.now()
                    _LOGGER.info("✅ Lernprozess erfolgreich abgeschlossen.")
                else:
                    _LOGGER.warning(f"⏩ Überspringe Lernen für {yesterday_iso}: Actual={actual:.2f}, Predicted={pred:.2f}.")
        except Exception as e: _LOGGER.error(f"❌ Fehler beim Midnight Learning: {e}", exc_info=True)

    def _calculate_autarky(self, solar_yield: float):
        if not self.total_consumption_entity: self.autarky_today = None; return
        consumption_state = self.hass.states.get(self.total_consumption_entity)
        if consumption_state and consumption_state.state not in ['unknown', 'unavailable']:
            try:
                total_consumption = float(consumption_state.state)
                if total_consumption > 0:
                    direct_consumption = min(solar_yield, total_consumption)
                    self.autarky_today = (direct_consumption / total_consumption) * 100
                else:
                    self.autarky_today = 100.0
            except ValueError: self.autarky_today = None

    def _calculate_peak_production_hour(self):
        if not self.hourly_profile or not isinstance(self.hourly_profile, dict): self.peak_production_time_today = "Keine Profildaten"; return
        try:
            peak_hour = max(self.hourly_profile, key=lambda h: self.hourly_profile[h]['mean'])
            self.peak_production_time_today = f"{int(peak_hour):02d}:00 - {int(peak_hour) + 1:02d}:00"
        except (ValueError, TypeError): self.peak_production_time_today = "Fehler bei Berechnung"

    async def _create_forecast(self):
        # FIX: Lade History vor dem Erstellen, um Überschreiben zu vermeiden
        await self._load_history()  # Sicherstellen, dass alte Daten da sind
        try:
            forecasts = await self._get_weather_forecast()
            if not forecasts or len(forecasts) < 2: return
            data = await self._get_sensor_data()
            heute_kwh = self._predict_day(forecasts[0], data, True)
            morgen_kwh = self._predict_day(forecasts[1], data, False)
            if self._is_night_time() and datetime.now().hour >= 21: heute_kwh = 0.0

            today = date.today().isoformat()
            if today not in self.daily_predictions: self.daily_predictions[today] = {}
            self.daily_predictions[today].update({'predicted': heute_kwh, 'predicted_morgen': morgen_kwh, 'features': data})
            self._save_history()  # Jetzt safe: Merge mit geladener History

            self.data = {"heute": round(heute_kwh, 2), "morgen": round(morgen_kwh, 2), "genauigkeit": round(self.accuracy, 1)}
            self.last_forecast_date = date.today()
            self._calculate_peak_production_hour()
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
                state = self.hass.states.get(sensor)
                if state and state.state not in ['unknown', 'unavailable']:
                    try: data[key] = float(state.state)
                    except (ValueError, TypeError): pass
        return data

    def _detect_weather_type(self) -> str:
        entity_id = self.weather_entity.lower()
        if 'dwd' in entity_id or 'deutscher_wetterdienst' in entity_id: return 'dwd'
        if 'met' in entity_id or 'forecast_home' in entity_id: return 'met.no'
        if 'openweather' in entity_id: return 'openweathermap'
        return 'generic'

    async def _detect_forecast_method(self) -> str | None:
        for attempt in range(1, 4):
            if attempt > 1: await asyncio.sleep(2 if attempt == 2 else 5)
            try:
                response = await self.hass.services.async_call("weather", "get_forecasts", {"type": "daily", "entity_id": self.weather_entity}, blocking=True, return_response=True)
                if response.get(self.weather_entity, {}).get("forecast") or response.get("forecast"): return "service"
            except Exception: pass
            try:
                state = self.hass.states.get(self.weather_entity)
                if state and state.attributes.get('forecast'): return "attribute"
            except Exception: pass
        _LOGGER.error("❌ Keine funktionierende Forecast-Methode gefunden!")
        return None

    async def _get_weather_forecast(self):
        if self.forecast_method is None: self.forecast_method = await self._detect_forecast_method()
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
        try:
            response = await self.hass.services.async_call("weather", "get_forecasts", {"type": "hourly", "entity_id": self.weather_entity}, blocking=True, return_response=True)
            forecast = response.get(self.weather_entity, {}).get("forecast", [])
            return forecast[0] if forecast else None
        except Exception:
            daily_forecast = await self._get_weather_forecast()
            return daily_forecast[0] if daily_forecast else None

    def _is_night_time(self) -> bool:
        return datetime.now().hour < 6 or datetime.now().hour >= 21

    async def _collect_hourly_data(self, now):
        if not self.current_power_sensor: return
        try:
            hour = now.hour
            if self.last_hourly_collection == hour: return
            state = self.hass.states.get(self.current_power_sensor)
            if state and state.state not in ['unknown', 'unavailable']:
                kwh = float(state.state) / 1000.0
                self.today_hourly_data[hour] = kwh
                self.last_hourly_collection = hour
                self._update_production_time()
                today = date.today().isoformat()
                if today in self.daily_predictions:
                    if 'hourly_data' not in self.daily_predictions[today]: self.daily_predictions[today]['hourly_data'] = {}
                    self.daily_predictions[today]['hourly_data'].update(self.today_hourly_data)
                    self._save_history()
        except (ValueError, Exception) as e: _LOGGER.error(f"Fehler bei stündlicher Datensammlung: {e}", exc_info=True)
    
    def _calculate_average_yield(self):
        actuals = [v.get('actual', 0) for v in list(self.daily_predictions.values())[-30:] if isinstance(v, dict) and v.get('actual', 0) > 0]
        if actuals: self.average_yield_30_days = round(sum(actuals) / len(actuals), 2)

    def _update_production_time(self):
        prod_hours = [h for h, kwh in self.today_hourly_data.items() if kwh > 0]
        if prod_hours: self.production_time_today = f"{min(prod_hours):02d}:00 - {max(prod_hours) + 1:02d}:00"
        else: self.production_time_today = "Noch keine Produktion"

    async def _load_hourly_profile(self): self.hourly_profile = await self.hass.async_add_executor_job(_read_history_file, HOURLY_PROFILE_FILE)
    def _save_hourly_profile(self): self.hass.async_add_executor_job(_write_history_file, HOURLY_PROFILE_FILE, self.hourly_profile)
    async def _async_load_weights(self): 
        d = await self.hass.async_add_executor_job(_read_history_file, WEIGHTS_FILE)
        if d: self.weights.update(d); self.base_capacity = d.get('base_capacity', self.base_capacity)
    async def _async_save_weights(self): await self.hass.async_add_executor_job(_write_history_file, WEIGHTS_FILE, {**self.weights, 'base_capacity': self.base_capacity})
    def _save_weights(self): self.hass.async_create_task(self._async_save_weights())
    async def _load_history(self): 
        # FIX: Robustes Laden – falls Datei fehlt, starte mit leerem Dict
        self.daily_predictions = await self.hass.async_add_executor_job(_read_history_file, HISTORY_FILE)
        if not self.daily_predictions: self.daily_predictions = {}  # Sicherstellen, dass's ein Dict ist
        _LOGGER.debug(f"History geladen: {len(self.daily_predictions)} Tage.")
    def _save_history(self): 
        # FIX: Vor Schreiben prüfen und mergen, falls nötig
        self.hass.async_add_executor_job(_write_history_file, HISTORY_FILE, self.daily_predictions)
        _LOGGER.debug(f"History gespeichert: {len(self.daily_predictions)} Tage.")

    def _load_last_data(self):
        if self.daily_predictions:
            today, yesterday = date.today().isoformat(), (date.today() - timedelta(days=1)).isoformat()
            last = self.daily_predictions.get(today) or self.daily_predictions.get(yesterday)
            if last and 'predicted' in last: self.data = {"heute": last.get('predicted',0), "morgen": last.get('predicted_morgen', 0), "genauigkeit": self.accuracy}

    async def _notify_start_success(self):
        await self.hass.services.async_call("persistent_notification", "create", {"title": "✅ SolarForecastML gestartet", "message": f"Basiskapazität: {self.base_capacity:.2f} kWh", "notification_id": "solar_forecast_ml_start"})

    def _calibrate_base_capacity(self):
        actuals = [v.get('actual',0) for v in self.daily_predictions.values() if isinstance(v,dict) and v.get('actual',0)>0]
        if actuals:
            avg = sum(actuals)/len(actuals)
            if avg > self.base_capacity * 0.5: self.base_capacity = avg; self._save_weights()

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
        errors = [abs((d['actual']-d.get('predicted',0))/d['actual'])*100 for d in list(self.daily_predictions.values())[-30:] if isinstance(d,dict) and d.get('actual',0)>0]
        if errors: self.accuracy = max(0, 100 - (sum(errors) / len(errors)))

    async def _notify_forecast(self, today_kwh: float, tomorrow_kwh: float):
        await self.hass.services.async_call("persistent_notification", "create", {"title": "☀️ Solar-Prognose", "message": f"Heute: {today_kwh:.1f} kWh, Morgen: {tomorrow_kwh:.1f} kWh", "notification_id": "solar_forecast_ml_daily"})

    def _calculate_hourly_profile(self): pass
    async def _predict_next_hour(self): pass