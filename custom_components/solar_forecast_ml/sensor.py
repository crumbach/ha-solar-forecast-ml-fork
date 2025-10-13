"""Solar Forecast ML Sensor Platform - Selbstlernend mit optionalen Sensoren."""
import logging
from datetime import timedelta, datetime
import json
import os
from typing import Dict

from homeassistant.components.sensor import SensorEntity, SensorStateClass
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
    WEIGHTS_FILE,
    HISTORY_FILE,
    DEFAULT_BASE_CAPACITY,
    DEFAULT_KWP_TO_KWH_FACTOR,
)

_LOGGER = logging.getLogger(__name__)

# Basis-Wetterfaktoren
WEATHER_FACTORS = {
    'sunny': 1.0,
    'partlycloudy': 0.6,
    'cloudy': 0.3,
    'rainy': 0.1,
    'snowy': 0.05,
    'clear-night': 0.0,
    'fog': 0.2,
}

# Standard-Gewichte für zusätzliche Sensoren
DEFAULT_WEIGHTS = {
    'base': 1.0,
    'lux': 0.1,
    'temp': 0.05,
    'wind': -0.02,
    'uv': 0.08,
}

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Solar Forecast sensors."""
    config = entry.data
    
    _LOGGER.info(f"Setting up Solar Forecast ML BETA 1.1 with config: {config}")
    
    coordinator = SolarForecastCoordinator(hass, config)
    
    # Erstelle initiale Prognose
    await coordinator.async_config_entry_first_refresh()
    
    entities = [
        SolarForecastSensor(coordinator, "heute", "Solar Forecast ML Prognose Heute"),
        SolarForecastSensor(coordinator, "morgen", "Solar Forecast ML Prognose Morgen"),
        SolarAccuracySensor(coordinator, "genauigkeit", "Solar Forecast ML Prognose Genauigkeit"),
    ]
    
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
        
        # Optionale Sensoren
        self.lux_sensor = config.get(CONF_LUX_SENSOR)
        self.temp_sensor = config.get(CONF_TEMP_SENSOR)
        self.wind_sensor = config.get(CONF_WIND_SENSOR)
        self.uv_sensor = config.get(CONF_UV_SENSOR)
        
        # Berechne initiale base_capacity aus Anlagengröße
        plant_kwp = config.get(CONF_PLANT_KWP)
        if plant_kwp:
            self.base_capacity = plant_kwp * DEFAULT_KWP_TO_KWH_FACTOR
            _LOGGER.info(f"🏭 Anlagengröße: {plant_kwp} kWp → Initiale Base Capacity: {self.base_capacity:.2f} kWh/Tag")
        else:
            self.base_capacity = DEFAULT_BASE_CAPACITY
            _LOGGER.info(f"⚙️ Keine Anlagengröße angegeben, nutze Default: {self.base_capacity} kWh/Tag")
        
        self.weights = DEFAULT_WEIGHTS.copy()
        self.daily_predictions = {}
        self.accuracy = 0.0
        self.last_forecast_date = None
        
        # Lade gespeicherte Gewichte
        self._load_weights()
        self._load_history()
        
        # Kalibriere Basiskapazität
        self._calibrate_base_capacity()
        
        # Plane Morgen-Prognose (7:00 Uhr)
        async_track_time_change(
            hass, self._morning_forecast, hour=7, minute=0, second=0
        )
        
        # Plane Mitternachts-Learning (00:01 Uhr)
        async_track_time_change(
            hass, self._midnight_learning, hour=0, minute=1, second=0
        )

    def _load_weights(self):
        """Lade gelernte Gewichte aus Datei."""
        try:
            if os.path.exists(WEIGHTS_FILE):
                with open(WEIGHTS_FILE, 'r') as f:
                    saved_weights = json.load(f)
                    self.weights.update(saved_weights)
                    self.base_capacity = self.weights.get('base_capacity', self.base_capacity)
                    _LOGGER.info(f"💾 Gewichte geladen: {self.weights}, Base Capacity: {self.base_capacity} kWh")
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
            _LOGGER.info(f"💾 Gewichte gespeichert: {save_data}")
        except Exception as e:
            _LOGGER.error(f"Fehler beim Speichern der Gewichte: {e}")

    def _load_history(self):
        """Lade Vorhersage-Historie."""
        try:
            if os.path.exists(HISTORY_FILE):
                with open(HISTORY_FILE, 'r') as f:
                    self.daily_predictions = json.load(f)
                    _LOGGER.info(f"📚 Historie geladen: {len(self.daily_predictions)} Einträge")
        except Exception as e:
            _LOGGER.warning(f"Konnte Historie nicht laden: {e}")

    def _save_history(self):
        """Speichere Vorhersage-Historie."""
        try:
            os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
            with open(HISTORY_FILE, 'w') as f:
                json.dump(self.daily_predictions, f, indent=2)
        except Exception as e:
            _LOGGER.error(f"Fehler beim Speichern der Historie: {e}")

    def _calibrate_base_capacity(self):
        """Kalibriere Basiskapazität aus Historie."""
        try:
            if self.daily_predictions:
                actuals = [v['actual'] for v in self.daily_predictions.values() if 'actual' in v and v['actual'] > 0]
                if actuals and len(actuals) >= 7:
                    actuals_sorted = sorted(actuals)
                    index = int(len(actuals_sorted) * 0.9)
                    self.base_capacity = actuals_sorted[index]
                    _LOGGER.info(f"✅ Basiskapazität kalibriert auf {self.base_capacity:.2f} kWh (aus {len(actuals)} Tagen)")
                else:
                    _LOGGER.info(f"⏳ Warte auf mehr Daten für Kalibrierung (aktuell: {len(actuals) if actuals else 0} Tage, benötigt: 7)")
        except Exception as e:
            _LOGGER.warning(f"Kalibrierung fehlgeschlagen: {e}")

    async def _morning_forecast(self, now):
        """Erstelle Prognose um 7:00 Uhr morgens."""
        _LOGGER.info("🌅 Morgen-Prognose wird erstellt (7:00 Uhr)")
        await self._create_forecast()

    async def _midnight_learning(self, now):
        """Lerne um Mitternacht aus dem gestrigen Tag."""
        try:
            yesterday = (datetime.now().date() - timedelta(days=1)).isoformat()
            
            # Hole tatsächlichen Ertrag von gestern
            actual_power = self.hass.states.get(self.power_entity)
            if actual_power and actual_power.state not in ['unknown', 'unavailable']:
                try:
                    actual_value = float(actual_power.state)
                    if yesterday in self.daily_predictions:
                        self.daily_predictions[yesterday]['actual'] = actual_value
                        self._save_history()
                except:
                    pass
            
            if yesterday in self.daily_predictions:
                pred_data = self.daily_predictions[yesterday]
                predicted = pred_data.get('predicted', 0)
                actual = pred_data.get('actual', 0)
                
                if actual > 0 and predicted > 0:
                    error = actual - predicted
                    error_percent = (error / actual) * 100
                    
                    _LOGGER.info(f"📚 Learning von {yesterday}: Vorhergesagt={predicted:.2f} kWh, Tatsächlich={actual:.2f} kWh, Fehler={error_percent:.1f}%")
                    
                    # Passe Gewichte an
                    learning_rate = 0.01
                    
                    # Basisgewicht anpassen
                    self.weights['base'] += learning_rate * (error / self.base_capacity)
                    self.weights['base'] = max(0.5, min(1.5, self.weights['base']))
                    
                    # Sensor-spezifische Gewichte anpassen
                    for sensor_type in ['lux', 'temp', 'wind', 'uv']:
                        if sensor_type in pred_data.get('features', {}):
                            sensor_value = pred_data['features'][sensor_type]
                            if sensor_value != 0:
                                self.weights[sensor_type] += learning_rate * (error / actual) * (sensor_value / 100)
                                self.weights[sensor_type] = max(-0.5, min(0.5, self.weights[sensor_type]))
                    
                    self._save_weights()
                    self._calculate_accuracy()
                    self._calibrate_base_capacity()
                else:
                    _LOGGER.warning(f"⚠️ Kann nicht lernen von {yesterday}: actual={actual}, predicted={predicted}")
                    
        except Exception as e:
            _LOGGER.error(f"Fehler beim Midnight Learning: {e}", exc_info=True)

    def _calculate_accuracy(self):
        """Berechne aktuelle Modell-Genauigkeit."""
        try:
            recent_days = list(self.daily_predictions.values())[-30:]
            errors = []
            
            for day in recent_days:
                if 'actual' in day and 'predicted' in day:
                    actual = day['actual']
                    predicted = day['predicted']
                    if actual > 0:
                        mape = abs((actual - predicted) / actual) * 100
                        errors.append(mape)
            
            if errors:
                avg_error = sum(errors) / len(errors)
                self.accuracy = max(0, 100 - avg_error)
                _LOGGER.info(f"📊 Genauigkeit berechnet: {self.accuracy:.1f}% (basierend auf {len(errors)} Tagen)")
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
            
            heute_kwh = self._predict_day(forecast_data[0], sensor_data)
            morgen_kwh = self._predict_day(forecast_data[1], sensor_data)
            
            today = datetime.now().date().isoformat()
            self.daily_predictions[today] = {
                'predicted': heute_kwh,
                'features': sensor_data,
                'timestamp': datetime.now().isoformat()
            }
            
            self._save_history()
            self.last_forecast_date = datetime.now().date()
            
            self.async_set_updated_data({
                "heute": round(heute_kwh, 2),
                "morgen": round(morgen_kwh, 2),
                "genauigkeit": round(self.accuracy, 1),
            })
            
            _LOGGER.info(f"☀️ Prognose - Heute: {heute_kwh:.2f} kWh, Morgen: {morgen_kwh:.2f} kWh (Genauigkeit: {self.accuracy:.1f}%, Base: {self.base_capacity:.2f} kWh)")
            
        except Exception as e:
            _LOGGER.error(f"Fehler beim Erstellen der Prognose: {e}", exc_info=True)

    async def _async_update_data(self):
        """Sammle Daten."""
        try:
            today = datetime.now().date()
            
            if self.last_forecast_date != today:
                _LOGGER.info("📊 Erste Prognose des Tages wird erstellt")
                await self._create_forecast()
            else:
                sensor_data = await self._get_sensor_data()
                
                today_iso = today.isoformat()
                if today_iso in self.daily_predictions:
                    self.daily_predictions[today_iso]['features'] = sensor_data
                    self._save_history()
                
                _LOGGER.debug(f"📡 Sensordaten gesammelt: {sensor_data}")
            
            return self.data if self.data else {"heute": 0, "morgen": 0, "genauigkeit": self.accuracy}
            
        except Exception as e:
            _LOGGER.error(f"Fehler beim Update: {e}", exc_info=True)
            return {"heute": 0, "morgen": 0, "genauigkeit": self.accuracy}

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
            
            if response and self.weather_entity in response:
                return response[self.weather_entity].get("forecast", [])
            return []
        except Exception as e:
            _LOGGER.error(f"Fehler beim Abrufen der Wettervorhersage: {e}")
            return []

    async def _get_sensor_data(self) -> Dict[str, float]:
        """Hole Daten von optionalen Sensoren."""
        sensor_data = {}
        
        try:
            if self.lux_sensor:
                state = self.hass.states.get(self.lux_sensor)
                if state and state.state not in ['unknown', 'unavailable']:
                    sensor_data['lux'] = float(state.state)
            
            if self.temp_sensor:
                state = self.hass.states.get(self.temp_sensor)
                if state and state.state not in ['unknown', 'unavailable']:
                    sensor_data['temp'] = float(state.state)
            
            if self.wind_sensor:
                state = self.hass.states.get(self.wind_sensor)
                if state and state.state not in ['unknown', 'unavailable']:
                    sensor_data['wind'] = float(state.state)
            
            if self.uv_sensor:
                state = self.hass.states.get(self.uv_sensor)
                if state and state.state not in ['unknown', 'unavailable']:
                    sensor_data['uv'] = float(state.state)
                    
        except Exception as e:
            _LOGGER.warning(f"Fehler beim Lesen der Sensoren: {e}")
        
        return sensor_data

    def _predict_day(self, forecast: Dict, sensor_data: Dict) -> float:
        """Erstelle Prognose mit gelernten Gewichten."""
        try:
            condition = forecast.get('condition', 'cloudy')
            cloud_coverage = forecast.get('cloud_coverage', 50)
            precipitation = forecast.get('precipitation', 0)
            
            weather_factor = WEATHER_FACTORS.get(condition, 0.4)
            
            if cloud_coverage is not None:
                cloud_factor = 1.0 - (cloud_coverage / 100.0)
                weather_factor = weather_factor * (0.5 + 0.5 * cloud_factor)
            
            if precipitation and precipitation > 0:
                weather_factor = weather_factor * 0.5
            
            prediction = self.base_capacity * weather_factor * self.weights['base']
            
            if 'lux' in sensor_data:
                lux_contribution = (sensor_data['lux'] / 1000) * self.weights['lux']
                prediction += lux_contribution
            
            if 'temp' in sensor_data:
                temp_contribution = sensor_data['temp'] * self.weights['temp']
                prediction += temp_contribution
            
            if 'wind' in sensor_data:
                wind_contribution = sensor_data['wind'] * self.weights['wind']
                prediction += wind_contribution
            
            if 'uv' in sensor_data:
                uv_contribution = sensor_data['uv'] * self.weights['uv']
                prediction += uv_contribution
            
            return max(0, prediction)
            
        except Exception as e:
            _LOGGER.error(f"Fehler bei Prognose: {e}")
            return 0.0


class SolarForecastSensor(CoordinatorEntity, SensorEntity):
    """Solar Forecast Sensor."""

    def __init__(self, coordinator, sensor_type, name):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self._attr_name = name
        self._attr_unique_id = f"solar_forecast_ml_prognose_{sensor_type}"
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_icon = "mdi:solar-power"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data.get(self._sensor_type, 0)
        return 0


class SolarAccuracySensor(CoordinatorEntity, SensorEntity):
    """Solar Forecast Accuracy Sensor."""

    def __init__(self, coordinator, sensor_type, name):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self._attr_name = name
        self._attr_unique_id = f"solar_forecast_ml_prognose_{sensor_type}"
        self._attr_native_unit_of_measurement = "%"
        self._attr_icon = "mdi:chart-line-variant"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data.get(self._sensor_type, 0)
        return 0
