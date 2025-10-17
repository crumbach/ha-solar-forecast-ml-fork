"""Solar Forecast ML Sensor Platform - Selbstlernend mit optionalen Sensoren."""
import logging
from datetime import timedelta, datetime, date
import json
import os
from typing import Dict

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.components.button import ButtonEntity  # ✅ FIX: Korrekter Import
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    CoordinatorEntity,
)
from homeassistant.helpers.event import async_track_time_change

from .const import (
    DOMAIN,
    CONF_WEATHER_ENTITY,
    CONF_POWER_ENTITY,
    CONF_UPDATE_INTERVAL,
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
    WEIGHTS_FILE,
    HISTORY_FILE,
    DEFAULT_BASE_CAPACITY,
    DEFAULT_KWP_TO_KWH_FACTOR,
    DEFAULT_INVERTER_THRESHOLD,
)

_LOGGER = logging.getLogger(__name__)

WEATHER_FACTORS = {
    'sunny': 1.0,
    'partlycloudy': 0.6,
    'cloudy': 0.3,
    'rainy': 0.1,
    'snowy': 0.05,
    'clear-night': 0.0,
    'fog': 0.2,
}

DEFAULT_WEIGHTS = {
    'base': 1.0,
    'lux': 0.1,
    'temp': 0.05,
    'wind': -0.02,
    'uv': 0.08,
    'fs': 0.5,
}

# --- HILFSFUNKTIONEN ---

def _read_history_file(filepath):
    """Blockierende Hilfsfunktion zum Lesen der Datei."""
    if not os.path.exists(filepath):
        return {}
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception as e:
        _LOGGER.error(f"Fehler beim Lesen der History-Datei: {e}")
        return {}

def _write_history_file(filepath, data):
    """Blockierende Hilfsfunktion zum Speichern der Datei."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        _LOGGER.error(f"Fehler beim Speichern der History-Datei: {e}")

# -------------------------------------------------------------

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Solar Forecast sensors."""
    config = entry.data
    _LOGGER.info(f"Setting up Solar Forecast ML BETA 1.1 with config: {config}")
    coordinator = SolarForecastCoordinator(hass, config)
    await coordinator.async_config_entry_first_refresh()
    entities = [
        SolarForecastSensor(coordinator, "heute", "Solar Forecast ML Prognose Heute"),
        SolarForecastSensor(coordinator, "morgen", "Solar Forecast ML Prognose Morgen"),
        SolarAccuracySensor(coordinator, "genauigkeit", "Solar Forecast ML Prognose Genauigkeit"),
    ]
    # Neu: Diagnostic-Sensor, wenn enabled
    if config.get(CONF_DIAGNOSTIC, True):
        entities.append(DiagnosticStatusSensor(coordinator, "status", "Solar Forecast ML Status"))
    # Neu: Hourly-Sensor, wenn enabled
    if config.get(CONF_HOURLY, False):
        entities.append(NextHourSensor(coordinator, "naechste_stunde", "Solar Forecast ML Prognose Nächste Stunde"))
    # Neu: Manual Button
    entities.append(ManualForecastButton(coordinator, "manual_forecast", "Solar Forecast ML Manuelle Prognose"))
    async_add_entities(entities)

class SolarForecastCoordinator(DataUpdateCoordinator):
    """Selbstlernender Coordinator für Solar Forecast."""
    def __init__(self, hass: HomeAssistant, config: Dict):
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Solar Forecast ML",
            update_interval=timedelta(seconds=config.get(CONF_UPDATE_INTERVAL, 3600)),
        )

        self.weather_entity = config[CONF_WEATHER_ENTITY]
        self.power_entity = config[CONF_POWER_ENTITY]

        self.fs_sensor = config.get(CONF_FORECAST_SOLAR)

        self.lux_sensor = config.get(CONF_LUX_SENSOR)
        self.temp_sensor = config.get(CONF_TEMP_SENSOR)
        self.wind_sensor = config.get(CONF_WIND_SENSOR)
        self.uv_sensor = config.get(CONF_UV_SENSOR)

        # Neu: Inverter-Sensoren
        self.inverter_power = config.get(CONF_INVERTER_POWER)
        self.inverter_daily = config.get(CONF_INVERTER_DAILY)

        # Neu: Toggles
        self.enable_diagnostic = config.get(CONF_DIAGNOSTIC, True)
        self.enable_hourly = config.get(CONF_HOURLY, False)  # ✅ FIX: Vervollständigt

        plant_kwp = config.get(CONF_PLANT_KWP)
        self.base_capacity = plant_kwp * DEFAULT_KWP_TO_KWH_FACTOR if plant_kwp else DEFAULT_BASE_CAPACITY
        _LOGGER.info(f"🏭 Base Capacity: {self.base_capacity:.2f} kWh (kWp: {plant_kwp or 'default'})")

        self.weights = DEFAULT_WEIGHTS.copy()
        self.daily_predictions = {}
        self.accuracy = 0.0
        self.last_forecast_date = None
        self.last_inverter_notification = None
        self.last_update = datetime.now()
        self.next_hour_pred = 0.0

        self._load_weights()
        hass.async_create_task(self._load_history())
        self._load_last_data()
        
        hass.async_create_task(self._initial_setup()) 

        # Zeitplanung
        async_track_time_change(hass, self._morning_forecast, hour=6, minute=0, second=0)
        async_track_time_change(hass, self._midnight_learning, hour=23, minute=0, second=0)

    def _get_status_text(self):
        """Generiere Status-Text für Diagnostic-Sensor."""
        now = datetime.now()
        hours_since_forecast = (now - self.last_update).total_seconds() / 3600
        next_learning = 23 - now.hour if now.hour < 23 else 23 + 24 - now.hour
        inverter_status = "Online" if self.inverter_power else "Nicht konfiguriert"
        if self.inverter_power:
            power_state = self.hass.states.get(self.inverter_power)
            if power_state and power_state.state not in ['unknown', 'unavailable']:
                try:
                    if float(power_state.state) > DEFAULT_INVERTER_THRESHOLD:
                        inverter_status = "Online"
                    else:
                        inverter_status = "Offline (0W)"
                except ValueError:
                    inverter_status = "Offline (ungültig)"
        status_emoji = "✅" if hours_since_forecast < 1 else "⚠️"
        return f"{status_emoji} Läuft normal | Letzte Prognose: {hours_since_forecast:.1f}h her | Nächstes Learning: {next_learning}h | Inverter: {inverter_status} | Genauigkeit: {self.accuracy:.0f}%"

    async def _get_next_hour_forecast(self):
        """Hole stündliche Wettervorhersage für nächste Stunde."""
        try:
            response = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {"type": "hourly", "entity_id": self.weather_entity},
                blocking=True,
                return_response=True,
            )
            forecast = response.get(self.weather_entity, {}).get("forecast", [])
            return forecast[0] if forecast else None
        except Exception as e:
            _LOGGER.error(f"Fehler beim Abrufen der stündlichen Wettervorhersage: {e}")
            return None

    async def _predict_next_hour(self):
        """Berechne Prognose für nächste Stunde."""
        if not self.enable_hourly:
            return 0.0
        try:
            hour_forecast = await self._get_next_hour_forecast()
            if not hour_forecast:
                return 0.0
            sensor_data = await self._get_sensor_data()
            pred = self._predict_hour(hour_forecast, sensor_data)
            self.next_hour_pred = pred
            _LOGGER.debug(f"⏰ Nächste Stunde Prognose: {pred:.2f} kWh")
            return pred
        except Exception as e:
            _LOGGER.error(f"Fehler bei stündlicher Prognose: {e}")
            return 0.0

    def _predict_hour(self, forecast: Dict, sensor_data: Dict) -> float:
        """Erstelle stündliche Prognose."""
        LUX_MAX_NORM = 100000.0 
        try:
            condition = forecast.get('condition', 'cloudy')
            if condition in ['clear-night', 'night']:
                return 0.0
            cloud_coverage = forecast.get('cloud_coverage', 50)
            precipitation = forecast.get('precipitation', 0)
            
            weather_factor = WEATHER_FACTORS.get(condition, 0.4)
            if cloud_coverage is not None:
                cloud_factor = 1.0 - (cloud_coverage / 100.0)
                weather_factor *= (0.5 + 0.5 * cloud_factor)
            if precipitation and precipitation > 0:
                weather_factor *= 0.5
            
            hour = datetime.fromisoformat(forecast.get('datetime', datetime.now().isoformat())).hour
            if hour < 6 or hour > 20:
                return 0.0
            solar_hour_factor = max(0, 1 - abs(hour - 12) / 6)
            prediction_ml = (self.base_capacity / 10) * weather_factor * self.weights['base'] * solar_hour_factor
            
            for sensor_type in ['lux', 'temp', 'wind', 'uv']:
                if sensor_type in sensor_data:
                    sensor_value = sensor_data[sensor_type]
                    if sensor_type == 'lux':
                        norm_value = sensor_value / LUX_MAX_NORM
                        prediction_ml += norm_value * self.weights['lux'] * (self.base_capacity / 10) * 0.1 
                    else:
                        prediction_ml += sensor_value * self.weights[sensor_type] / 10

            if 'inverter_factor' in sensor_data:
                prediction_ml *= sensor_data['inverter_factor']

            return max(0, prediction_ml)
        except Exception as e:
            _LOGGER.error(f"Fehler bei stündlicher Prognose: {e}")
            return 0.0

    def _load_weights(self):
        """Lade gelernte Gewichte aus Datei."""
        try:
            if os.path.exists(WEIGHTS_FILE):
                with open(WEIGHTS_FILE, 'r') as f:
                    saved_weights = json.load(f)
                    self.weights.update(saved_weights)
                    self.base_capacity = saved_weights.get('base_capacity', self.base_capacity)
                    _LOGGER.info(f"💾 Gewichte geladen: {self.weights}")
        except Exception as e:
            _LOGGER.warning(f"Konnte Gewichte nicht laden: {e}")

    def _save_weights(self):
        """Speichere gelernte Gewichte."""
        try:
            save_data = self.weights.copy()
            save_data['base_capacity'] = self.base_capacity
            os.makedirs(os.path.dirname(WEIGHTS_FILE), exist_ok=True)
            with open(WEIGHTS_FILE, 'w') as f:
                json.dump(save_data, f, indent=2)
            _LOGGER.info(f"💾 Gewichte gespeichert")
        except Exception as e:
            _LOGGER.error(f"Fehler beim Speichern der Gewichte: {e}")

    async def _load_history(self):
        """Lade Vorhersage-Historie asynchron."""
        try:
            saved_data = await self.hass.async_add_executor_job(_read_history_file, HISTORY_FILE)
            if saved_data:
                self.daily_predictions = saved_data
                _LOGGER.info(f"📚 Lokale History geladen: {len(self.daily_predictions)} Einträge")
        except Exception as e:
            _LOGGER.warning(f"Konnte History nicht laden: {e}")
            self.daily_predictions = {}

    def _save_history(self):
        """Speichere Vorhersage-Historie asynchron."""
        try:
            self.hass.async_add_executor_job(_write_history_file, HISTORY_FILE, self.daily_predictions)
            _LOGGER.info("📁 Historie gespeichert")
        except Exception as e:
            _LOGGER.error(f"Fehler beim Speichern der Historie: {e}")

    def _load_last_data(self):
        """Lade letzten bekannten Prognose-Wert für Restart-Resilienz."""
        try:
            if self.daily_predictions:
                today_iso = date.today().isoformat()
                yesterday_iso = (date.today() - timedelta(days=1)).isoformat()
                
                last_entry = self.daily_predictions.get(today_iso) or self.daily_predictions.get(yesterday_iso)
                if last_entry and 'predicted' in last_entry:
                    morgen_fallback = last_entry.get('predicted_morgen', self.base_capacity * 0.8)
                    self.data = {
                        "heute": round(last_entry['predicted'], 2),
                        "morgen": round(morgen_fallback, 2),
                        "genauigkeit": round(self.accuracy, 1),
                    }
                    _LOGGER.info(f"💾 Letzter Wert geladen: Heute {self.data['heute']:.2f} kWh")
                else:
                    _LOGGER.debug("Keine History für Last-State – starte mit Defaults")
        except Exception as e:
            _LOGGER.warning(f"Last-State-Laden fehlgeschlagen: {e}")

    async def _initial_setup(self):
        """Initialer Setup."""
        self._calibrate_base_capacity()
        await self._notify_start_success()

    async def _notify_start_success(self):
        """Benachrichtigung über erfolgreichen Start."""
        try:
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "✅ SolarForecastML erfolgreich gestartet",
                    "message": (
                        f"• Basiskapazität: {self.base_capacity:.2f} kWh\n"
                        f"• Das Modell lernt jetzt täglich (23:00 Uhr) und erstellt Prognosen."
                    ),
                    "notification_id": "solar_forecast_ml_start_success"
                }
            )
            _LOGGER.info("📱 Erfolgreicher Start benachrichtigt")
        except Exception as e:
            _LOGGER.warning(f"Start-Benachrichtigung fehlgeschlagen: {e}")

    async def _notify_inverter_offline(self):
        """Benachrichtigung bei Inverter-Ausfall."""
        if self.last_inverter_notification == date.today().isoformat():
            return
        try:
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "⚠️ SolarForecastML: Inverter scheint offline",
                    "message": "Aktueller Power ist 0W – Prognose auf 0 kWh angepasst.",
                    "notification_id": "solar_forecast_ml_inverter_offline"
                }
            )
            self.last_inverter_notification = date.today().isoformat()
            _LOGGER.warning("📱 Inverter-Offline-Benachrichtigung gesendet")
        except Exception as e:
            _LOGGER.warning(f"Inverter-Notification fehlgeschlagen: {e}")

    def _calibrate_base_capacity(self):
        """Kalibriere Basiskapazität aus Historie."""
        try:
            actuals = [v.get('actual', 0) for k, v in self.daily_predictions.items()
                       if isinstance(v, dict) and v.get('actual', 0) > 0]
            if actuals:
                avg = sum(actuals) / len(actuals)
                if avg > self.base_capacity * 0.5:
                    self.base_capacity = avg
                    self.weights['base_capacity'] = avg
                    self.hass.async_create_task(self._save_weights())
                    _LOGGER.info(f"⚖️ Kalibrierte Base Capacity: {self.base_capacity:.2f} kWh")
        except Exception as e:
            _LOGGER.warning(f"Kalibrierung fehlgeschlagen: {e}")

    async def _morning_forecast(self, now):
        """Erstelle Prognose um 6:00 Uhr."""
        _LOGGER.info("🔆 Berechne Tagesprognose um 6:00 Uhr...")
        await self._create_forecast()

    async def _midnight_learning(self, now):
        """Lerne um 23:00 Uhr."""
        _LOGGER.info("🌒 Starte Lernprozess um 23:00 Uhr...")
        try:
            today = date.today().isoformat()
            actual_power = self.hass.states.get(self.power_entity)
            
            if actual_power and actual_power.state not in ['unknown', 'unavailable']:
                try:
                    actual_value = float(actual_power.state)
                    if actual_value > 0:
                        self.daily_predictions[today] = self.daily_predictions.get(today, {})
                        self.daily_predictions[today]['actual'] = actual_value
                        self._save_history()
                        _LOGGER.info(f"📚 Tagesertrag {today}: {actual_value:.2f} kWh gespeichert")
                except ValueError:
                    _LOGGER.warning(f"Ungültiger Wert: {actual_power.state}")

            yesterday = (date.today() - timedelta(days=1)).isoformat()
            if yesterday in self.daily_predictions:
                pred_data = self.daily_predictions[yesterday]
                predicted = pred_data.get('predicted', 0)
                actual = pred_data.get('actual', 0)
                
                if actual > 0 and predicted > 0:
                    error = actual - predicted
                    error_percent = (error / actual) * 100
                    _LOGGER.info(f"📚 Learning: Vorhergesagt={predicted:.2f}, Tatsächlich={actual:.2f}, Fehler={error_percent:.1f}%")
                    
                    learning_rate = 0.01
                    self.weights['base'] += learning_rate * (error / self.base_capacity)
                    self.weights['base'] = max(0.5, min(1.5, self.weights['base']))
                    
                    for sensor_type in ['lux', 'temp', 'wind', 'uv']:
                        if sensor_type in pred_data.get('features', {}):
                            sensor_value = pred_data['features'][sensor_type]
                            if sensor_value != 0:
                                self.weights[sensor_type] += learning_rate * (error / actual) * (sensor_value / 100)
                                self.weights[sensor_type] = max(-0.5, min(0.5, self.weights[sensor_type]))
                    
                    if 'fs' in pred_data.get('features', {}):
                        fs_value = pred_data['features']['fs']
                        fs_error_ratio = (fs_value - predicted) / actual if actual > 0 else 0
                        self.weights['fs'] += learning_rate * (error / actual) * (-fs_error_ratio)
                        self.weights['fs'] = max(0.0, min(1.0, self.weights['fs']))
                    
                    self._save_weights()
                    self._calculate_accuracy()
                    self._calibrate_base_capacity()
                    
        except Exception as e:
            _LOGGER.error(f"Fehler beim Midnight Learning: {e}", exc_info=True)

    def _calculate_accuracy(self):
        """Berechne Modell-Genauigkeit."""
        try:
            recent_days = list(self.daily_predictions.items())[-30:]
            errors = []
            
            for k, day in recent_days:
                if 'actual' in day and 'predicted' in day and day['actual'] > 0:
                    mape = abs((day['actual'] - day['predicted']) / day['actual']) * 100
                    errors.append(mape)
            
            if errors:
                avg_error = sum(errors) / len(errors)
                self.accuracy = max(0, 100 - avg_error)
                _LOGGER.info(f"📊 Genauigkeit: {self.accuracy:.1f}%")
        except Exception as e:
            _LOGGER.warning(f"Genauigkeitsberechnung fehlgeschlagen: {e}")

    async def _create_forecast(self):
        """Erstelle neue Prognose."""
        try:
            forecast_data = await self._get_weather_forecast()
            if not forecast_data or len(forecast_data) < 2:
                _LOGGER.warning("⚠️ Keine Wettervorhersage verfügbar")
                return
            
            sensor_data = await self._get_sensor_data()
            heute_kwh = self._predict_day(forecast_data[0], sensor_data, is_today=True)
            morgen_kwh = self._predict_day(forecast_data[1], sensor_data, is_today=False)
            
            today = date.today().isoformat()
            self.daily_predictions[today] = {
                'predicted': heute_kwh,
                'predicted_morgen': morgen_kwh,
                'features': sensor_data,
                'timestamp': datetime.now().isoformat()
            }
            
            self._save_history()
            self.last_forecast_date = date.today()
            
            self.async_set_updated_data({
                "heute": round(heute_kwh, 2),
                "morgen": round(morgen_kwh, 2),
                "genauigkeit": round(self.accuracy, 1),
            })
            
            await self._notify_forecast(heute_kwh, morgen_kwh, self.accuracy)
            _LOGGER.info(f"☀️ Prognose - Heute: {heute_kwh:.2f} kWh, Morgen: {morgen_kwh:.2f} kWh")
            
        except Exception as e:
            _LOGGER.error(f"Fehler beim Erstellen der Prognose: {e}", exc_info=True)

    async def _async_update_data(self):
        """Sammle Daten und triggere Prognose."""
        try:
            today = date.today()
            if self.last_forecast_date != today:
                _LOGGER.info("📊 Erste Prognose des Tages wird erstellt")
                await self._create_forecast()
            else:
                sensor_data = await self._get_sensor_data()
                today_iso = today.isoformat()
                if today_iso in self.daily_predictions:
                    self.daily_predictions[today_iso]['features'] = sensor_data
                    self._save_history()
            
            if not self.data:
                self._load_last_data()

            if self.enable_hourly:
                await self._predict_next_hour()
            
            self.last_update = datetime.now()
            
            return self.data or {"heute": 0, "morgen": 0, "genauigkeit": self.accuracy}
            
        except Exception as e:
            _LOGGER.error(f"Fehler beim Update: {e}", exc_info=True)
            if not self.data:
                self._load_last_data()
            return self.data or {"heute": 0, "morgen": 0, "genauigkeit": self.accuracy}

    async def _get_weather_forecast(self):
        """Hole Wettervorhersage."""
        try:
            response = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {"type": "daily", "entity_id": self.weather_entity},
                blocking=True,
                return_response=True,
            )
            return response.get(self.weather_entity, {}).get("forecast", [])
        except Exception as e:
            _LOGGER.error(f"Fehler beim Abrufen der Wettervorhersage: {e}")
            return []

    async def _get_sensor_data(self) -> Dict[str, float]:
        """Hole Daten von optionalen Sensoren."""
        sensor_data = {}
        try:
            for sensor, key in [
                (self.lux_sensor, 'lux'),
                (self.temp_sensor, 'temp'),
                (self.wind_sensor, 'wind'),
                (self.uv_sensor, 'uv'),
                (self.fs_sensor, 'fs'),
            ]:
                if sensor:
                    state = self.hass.states.get(sensor)
                    if state and state.state not in ['unknown', 'unavailable']:
                        try:
                            sensor_data[key] = float(state.state)
                        except ValueError:
                            sensor_data[key] = 0.0

            inverter_factor = 1.0
            if not self.inverter_power and not self.inverter_daily:
                pass
            else:
                power_on = False
                daily_on = False
                if self.inverter_power:
                    power_state = self.hass.states.get(self.inverter_power)
                    if power_state and power_state.state not in ['unknown', 'unavailable']:
                        try:
                            power_value = float(power_state.state)
                            if power_value > DEFAULT_INVERTER_THRESHOLD:
                                power_on = True
                        except ValueError:
                            power_on = True
                if self.inverter_daily:
                    daily_state = self.hass.states.get(self.inverter_daily)
                    if daily_state and daily_state.state not in ['unknown', 'unavailable']:
                        try:
                            daily_value = float(daily_state.state)
                            if daily_value > 0.1:
                                daily_on = True
                        except ValueError:
                            daily_on = True
                inverter_factor = 1.0 if power_on or daily_on else 0.0
                if inverter_factor == 0.0:
                    await self._notify_inverter_offline()

            sensor_data['inverter_factor'] = inverter_factor

        except Exception as e:
            _LOGGER.warning(f"Fehler beim Lesen der Sensoren: {e}")
            sensor_data['inverter_factor'] = 1.0
        return sensor_data

    def _predict_day(self, forecast: Dict, sensor_data: Dict, is_today: bool) -> float:
        """Erstelle Prognose mit gelernten Gewichten."""
        LUX_MAX_NORM = 100000.0 
        
        try:
            condition = forecast.get('condition', 'cloudy')
            cloud_coverage = forecast.get('cloud_coverage', 50)
            precipitation = forecast.get('precipitation', 0)
            
            weather_factor = WEATHER_FACTORS.get(condition, 0.4)
            if cloud_coverage is not None:
                cloud_factor = 1.0 - (cloud_coverage / 100.0)
                weather_factor *= (0.5 + 0.5 * cloud_factor)
            if precipitation and precipitation > 0:
                weather_factor *= 0.5
            
            prediction_ml = self.base_capacity * weather_factor * self.weights['base']
            
            for sensor_type in ['lux', 'temp', 'wind', 'uv']:
                if sensor_type in sensor_data:
                    sensor_value = sensor_data[sensor_type]
                    
                    if sensor_type == 'lux':
                        norm_value = sensor_value / LUX_MAX_NORM
                        prediction_ml += norm_value * self.weights['lux'] * self.base_capacity * 0.1 
                    else:
                        prediction_ml += sensor_value * self.weights[sensor_type]
            
            if 'inverter_factor' in sensor_data:
                prediction_ml *= sensor_data['inverter_factor']
            
            if is_today and 'fs' in sensor_data:
                fs_value = sensor_data['fs']
                fs_blend_factor = max(0.0, min(1.0, self.weights.get('fs', 0.5)))
                blended_prediction = (prediction_ml * (1 - fs_blend_factor)) + (fs_value * fs_blend_factor)
                prediction_ml = blended_prediction
            
            return max(0, prediction_ml)
        except Exception as e:
            _LOGGER.error(f"Fehler bei Prognose: {e}")
            return 0.0

    async def _notify_forecast(self, today_kwh: float, tomorrow_kwh: float, accuracy: float):
        """Tägliche Prognose-Benachrichtigung."""
        try:
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "☀️ Solar-Prognose",
                    "message": (
                        f"• Heute: {today_kwh:.1f} kWh\n"
                        f"• Morgen: {tomorrow_kwh:.1f} kWh\n"
                        f"• Genauigkeit: {accuracy:.1f}%"
                    ),
                    "notification_id": "solar_forecast_ml_daily"
                }
            )
        except Exception as e:
            _LOGGER.warning(f"Prognose-Benachrichtigung fehlgeschlagen: {e}")


# ========== SENSOR KLASSEN ==========

class NextHourSensor(CoordinatorEntity, SensorEntity):
    """Nächste Stunde Prognose Sensor."""
    def __init__(self, coordinator, key, name):
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{key}"
        self._attr_name = name
        self._key = key
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:clock-fast"

    @property
    def native_value(self):
        return round(self.coordinator.next_hour_pred, 2)

    @property
    def extra_state_attributes(self):
        return {
            "next_hour_start": (datetime.now() + timedelta(hours=1)).strftime("%H:%M"),
        }


class DiagnosticStatusSensor(CoordinatorEntity, SensorEntity):
    """Diagnostic Status Sensor."""
    def __init__(self, coordinator, key, name):
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{key}"
        self._attr_name = name
        self._key = key
        self._attr_state_class = None
        self._attr_icon = "mdi:information-outline"

    @property
    def native_value(self):
        return self.coordinator._get_status_text()

    @property
    def extra_state_attributes(self):
        return {
            "last_update": self.coordinator.last_update.isoformat(),
            "next_learning": "23:00",
            "accuracy": self.coordinator.accuracy,
        }


class SolarForecastSensor(CoordinatorEntity, SensorEntity):
    """Solar Forecast Sensor."""
    def __init__(self, coordinator, day_key, name):
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{day_key}"
        self._attr_name = name
        self._day_key = day_key
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:solar-power"

    @property
    def native_value(self):
        return self.coordinator.data.get(self._day_key)


class SolarAccuracySensor(CoordinatorEntity, SensorEntity):
    """Solar Forecast Accuracy Sensor."""
    def __init__(self, coordinator, key, name):
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{key}"
        self._attr_name = name
        self._key = key
        self._attr_native_unit_of_measurement = "%"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:chart-line-variant"

    @property
    def native_value(self):
        return round(self.coordinator.data.get(self._key, 0.0), 2)


# ✅ FIX: Fehlende ManualForecastButton Klasse
class ManualForecastButton(CoordinatorEntity, ButtonEntity):
    """Button zum manuellen Triggern der Prognose."""
    
    def __init__(self, coordinator, key, name):
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{key}"
        self._attr_name = name
        self._key = key
        self._attr_icon = "mdi:refresh"
        self._attr_device_class = "restart"

    async def async_press(self):
        """Handle button press - trigger forecast."""
        _LOGGER.info("🔄 Manuelle Prognose durch Button ausgelöst")
        try:
            await self.coordinator._create_forecast()
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "✅ Prognose manuell erstellt",
                    "message": (
                        f"Heute: {self.coordinator.data.get('heute', 0):.2f} kWh\n"
                        f"Morgen: {self.coordinator.data.get('morgen', 0):.2f} kWh"
                    ),
                    "notification_id": "solar_forecast_ml_manual"
                }
            )
        except Exception as e:
            _LOGGER.error(f"Fehler beim manuellen Forecast: {e}", exc_info=True)