"""Solar Forecast ML Sensor Platform - v3.0.0 FINAL mit allen Fixes."""
import logging
from datetime import timedelta, datetime, date
import json
import os
from typing import Dict

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import UnitOfEnergy, SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    CoordinatorEntity,
)
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.util import dt as dt_util

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
    CONF_CURRENT_POWER,
    CONF_NOTIFY_FORECAST,
    CONF_NOTIFY_LEARNING,
    CONF_NOTIFY_INVERTER,
    CONF_NOTIFY_STARTUP,
    WEIGHTS_FILE,
    HISTORY_FILE,
    HOURLY_PROFILE_FILE,
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

# ✅ v2.3.0: Quick-Kalibrierung
def calculate_initial_base_capacity(plant_kwp: float, location: str = "DE") -> float:
    """
    Intelligente Startwert-Berechnung basierend auf kWp und Standort.
    
    Formel: kWp × durchschnittliche Sonnenstunden × Systemeffizienz
    """
    if not plant_kwp or plant_kwp <= 0:
        return DEFAULT_BASE_CAPACITY
    
    # Deutschland Durchschnitt: ~3.5 Sonnenstunden/Tag
    avg_sun_hours = 3.5
    
    # Systemeffizienz: ~85% (Verluste durch Wetter, Ausrichtung, Verschattung, etc.)
    system_efficiency = 0.85
    
    base_capacity = plant_kwp * avg_sun_hours * system_efficiency
    
    # Sicherheits-Clamp: Zwischen 2x und 5x kWp
    min_capacity = plant_kwp * 2.0
    max_capacity = plant_kwp * 5.0
    
    clamped_capacity = max(min_capacity, min(max_capacity, base_capacity))
    
    _LOGGER.info(
        f"🏭 Quick-Kalibrierung: kWp={plant_kwp:.2f} → "
        f"Base Capacity={clamped_capacity:.2f} kWh "
        f"(Rohdaten: {base_capacity:.2f} kWh)"
    )
    
    return clamped_capacity

# -------------------------------------------------------------

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Solar Forecast sensors."""
    config = entry.data
    _LOGGER.info(f"Setting up Solar Forecast ML v3.0.0 with config: {config}")
    
    # ✅ v3.0.0 FIX: Erstelle Coordinator
    coordinator = SolarForecastCoordinator(hass, config)
    
    # ✅ v3.0.0 FIX: Speichere Coordinator SOFORT für button.py
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][f"{entry.entry_id}_coordinator"] = coordinator
    
    # 🔧 FIX v3.0.1: Lade Last-Data VOR dem ersten Refresh
    await coordinator._load_history()
    coordinator._load_last_data()
    
    # Jetzt erst refresh
    await coordinator.async_config_entry_first_refresh()
    
    entities = [
        SolarForecastSensor(coordinator, "heute", "Solar Forecast ML Prognose Heute"),
        SolarForecastSensor(coordinator, "morgen", "Solar Forecast ML Prognose Morgen"),
        SolarAccuracySensor(coordinator, "genauigkeit", "Solar Forecast ML Prognose Genauigkeit"),
    ]
    
    if config.get(CONF_DIAGNOSTIC, True):
        entities.append(DiagnosticStatusSensor(coordinator, "status", "Solar Forecast ML Status"))
    
    if config.get(CONF_HOURLY, False):
        entities.append(NextHourSensor(coordinator, "naechste_stunde", "Solar Forecast ML Prognose Nächste Stunde"))
    
    async_add_entities(entities)


class SolarForecastCoordinator(DataUpdateCoordinator):
    """Selbstlernender Coordinator für Solar Forecast - v3.0.0 FINAL."""
    
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
        
        # v2.3.0: Neuer optionaler Sensor für Tagesprofil
        self.current_power_sensor = config.get(CONF_CURRENT_POWER)

        self.lux_sensor = config.get(CONF_LUX_SENSOR)
        self.temp_sensor = config.get(CONF_TEMP_SENSOR)
        self.wind_sensor = config.get(CONF_WIND_SENSOR)
        self.uv_sensor = config.get(CONF_UV_SENSOR)

        self.inverter_power = config.get(CONF_INVERTER_POWER)
        self.inverter_daily = config.get(CONF_INVERTER_DAILY)

        self.enable_diagnostic = config.get(CONF_DIAGNOSTIC, True)
        self.enable_hourly = config.get(CONF_HOURLY, False)
        
        # v2.3.0: Notification Toggles
        self.notify_forecast = config.get(CONF_NOTIFY_FORECAST, False)
        self.notify_learning = config.get(CONF_NOTIFY_LEARNING, False)
        self.notify_inverter = config.get(CONF_NOTIFY_INVERTER, False)
        self.notify_startup = config.get(CONF_NOTIFY_STARTUP, True)

        # ✅ v2.3.0: Quick-Kalibrierung mit kWp
        plant_kwp = config.get(CONF_PLANT_KWP)
        if plant_kwp:
            self.base_capacity = calculate_initial_base_capacity(plant_kwp)
        else:
            self.base_capacity = DEFAULT_BASE_CAPACITY
        
        _LOGGER.info(f"🏭 Base Capacity initialisiert: {self.base_capacity:.2f} kWh")

        self.weights = DEFAULT_WEIGHTS.copy()
        self.daily_predictions = {}
        self.accuracy = 0.0
        self.last_forecast_date = None
        self.last_inverter_notification = None
        self.last_update = datetime.now()
        self.next_hour_pred = 0.0
        
        # v2.3.0: Tagesprofil-Daten
        self.hourly_profile = {}
        self.today_hourly_data = {}
        self.last_hourly_collection = None
        
        # ✅ v2.3.0: Weather Auto-Detection
        self.weather_type = self._detect_weather_type()
        self.forecast_method = None  # Wird beim ersten Aufruf gesetzt
        self.dwd_forecast_attr = None  # Für DWD-spezifische Attribute

        # ✅ v2.3.0 FIX: Initialisiere data mit Defaults
        self.data = {"heute": 0.0, "morgen": 0.0, "genauigkeit": 0.0}

        # ✅ v3.0.0 FIX: Alle I/O-Operationen async machen
        hass.async_create_task(self._async_load_weights())
        hass.async_create_task(self._load_history())
        hass.async_create_task(self._load_hourly_profile())
        
        # 🔧 FIX v3.0.1: _initial_setup wird jetzt in async_setup_entry gemacht
        # hass.async_create_task(self._initial_setup())  # Entfernt! 

        # Zeitplanung
        async_track_time_change(hass, self._morning_forecast, hour=6, minute=0, second=0)
        async_track_time_change(hass, self._midnight_learning, hour=23, minute=0, second=0)
        
        # v2.3.0: Stündliche Datensammlung wenn current_power verfügbar
        if self.current_power_sensor:
            async_track_time_change(hass, self._collect_hourly_data, minute=0, second=0)
            _LOGGER.info("📊 Stündliche Datensammlung aktiviert")

    # ✅ v2.3.0: Weather-Typ Erkennung (DWD-First!)
    def _detect_weather_type(self) -> str:
        """Erkenne Weather-Integration - DWD wird bevorzugt!"""
        entity_id = self.weather_entity.lower()
        
        # Priorität: DWD > Met.no > OpenWeather > Generic
        if 'dwd' in entity_id or 'deutscher_wetterdienst' in entity_id:
            _LOGGER.info("🌤️ Erkannt: DWD Weather (bevorzugt!)")
            return 'dwd'
        elif 'met' in entity_id or 'forecast_home' in entity_id:
            _LOGGER.info("🌤️ Erkannt: Met.no Weather")
            return 'met.no'
        elif 'openweather' in entity_id:
            _LOGGER.info("🌤️ Erkannt: OpenWeatherMap")
            return 'openweathermap'
        else:
            _LOGGER.info("🌤️ Erkannt: Generische Weather-Integration")
            return 'generic'

    # ✅ v2.3.0: Auto-Detection der Forecast-Methode
    async def _detect_forecast_method(self) -> str:
        """Einmalige Auto-Detection der Forecast-Methode."""
        
        _LOGGER.info(f"🔍 Teste Forecast-Methoden für {self.weather_type}...")
        
        # Methode 1: Service (modern, bevorzugt)
        try:
            response = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {"type": "daily", "entity_id": self.weather_entity},
                blocking=True,
                return_response=True,
            )
            
            forecast = response.get(self.weather_entity, {}).get("forecast")
            if not forecast:
                forecast = response.get("forecast")
            
            if forecast and len(forecast) > 0:
                _LOGGER.info("✅ Weather-Methode: get_forecasts Service")
                return "service"
        except Exception as e:
            _LOGGER.debug(f"Service-Methode fehlgeschlagen: {e}")
        
        # Methode 2: Attribut (legacy, Fallback)
        try:
            state = self.hass.states.get(self.weather_entity)
            if state and 'forecast' in state.attributes:
                forecast = state.attributes['forecast']
                if forecast and len(forecast) > 0:
                    _LOGGER.info("✅ Weather-Methode: forecast Attribut (Legacy)")
                    return "attribute"
        except Exception as e:
            _LOGGER.debug(f"Attribut-Methode fehlgeschlagen: {e}")
        
        # Methode 3: DWD-Spezifisch (falls DWD erkannt)
        if self.weather_type == 'dwd':
            try:
                state = self.hass.states.get(self.weather_entity)
                if state:
                    # DWD hat manchmal 'forecast_daily' statt 'forecast'
                    for attr in ['forecast_daily', 'forecast_hourly', 'forecast']:
                        if attr in state.attributes:
                            forecast = state.attributes[attr]
                            if forecast and len(forecast) > 0:
                                _LOGGER.info(f"✅ Weather-Methode: DWD-{attr}")
                                self.dwd_forecast_attr = attr
                                return "dwd_attribute"
            except Exception as e:
                _LOGGER.debug(f"DWD-Methode fehlgeschlagen: {e}")
        
        _LOGGER.error("❌ Keine funktionierende Forecast-Methode gefunden!")
        _LOGGER.error(f"⚠️ Bitte prüfe: {self.weather_entity} ist korrekt konfiguriert?")
        return None

# Fortsetzung von Teil 1...

    # ✅ v2.3.0: Hole Forecast via Service
    async def _get_forecast_via_service(self):
        """Hole Forecast via Service."""
        try:
            response = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {"type": "daily", "entity_id": self.weather_entity},
                blocking=True,
                return_response=True,
            )
            
            forecast = response.get(self.weather_entity, {}).get("forecast")
            if not forecast:
                forecast = response.get("forecast", [])
            
            return forecast
        except Exception as e:
            _LOGGER.error(f"Service-Forecast fehlgeschlagen: {e}")
            # Fallback: Versuche Attribut-Methode
            return await self._get_forecast_via_attribute()

    # ✅ v2.3.0: Hole Forecast via Attribut
    async def _get_forecast_via_attribute(self):
        """Hole Forecast via Attribut."""
        try:
            state = self.hass.states.get(self.weather_entity)
            if state and state.attributes:
                # DWD-Spezifisch: Prüfe verschiedene Attribute
                if self.weather_type == 'dwd' and self.dwd_forecast_attr:
                    return state.attributes.get(self.dwd_forecast_attr, [])
                
                return state.attributes.get('forecast', [])
            return []
        except Exception as e:
            _LOGGER.error(f"Attribut-Forecast fehlgeschlagen: {e}")
            return []

    # ✅ v2.3.0: Hauptmethode für Weather Forecast (mit Auto-Detection)
    async def _get_weather_forecast(self):
        """Hole Wettervorhersage mit Auto-Detection."""
        
        # Beim ersten Aufruf: Erkenne Methode
        if self.forecast_method is None:
            self.forecast_method = await self._detect_forecast_method()
        
        # Nutze erkannte Methode
        if self.forecast_method == "service":
            return await self._get_forecast_via_service()
        elif self.forecast_method == "attribute":
            return await self._get_forecast_via_attribute()
        elif self.forecast_method == "dwd_attribute":
            return await self._get_forecast_via_attribute()
        else:
            _LOGGER.error("❌ Keine Weather-Forecast-Methode verfügbar!")
            return []

    async def _get_next_hour_forecast(self):
        """Hole stündliche Wettervorhersage mit Fallback."""
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
            _LOGGER.warning(f"Stündliche Vorhersage fehlgeschlagen: {e}")
            
            # Fallback: Nutze daily forecast
            try:
                daily_forecast = await self._get_weather_forecast()
                if daily_forecast:
                    _LOGGER.info("⚠️ Nutze Tages- statt Stundenvorhersage")
                    return daily_forecast[0]
            except:
                pass
            
            return None

    # v2.3.0: Nacht-Check
    def _is_night_time(self) -> bool:
        """Prüfe ob es aktuell Nacht ist (Sonnenauf-/untergang)."""
        try:
            now = dt_util.now()
            today = now.date()
            
            sunrise = get_astral_event_date(self.hass, SUN_EVENT_SUNRISE, today)
            sunset = get_astral_event_date(self.hass, SUN_EVENT_SUNSET, today)
            
            if sunrise is None or sunset is None:
                # Fallback: Einfache Zeit-Prüfung
                hour = now.hour
                return hour < 6 or hour >= 21
            
            is_night = now < sunrise or now > sunset
            return is_night
            
        except Exception as e:
            _LOGGER.warning(f"Fehler bei Nacht-Prüfung: {e}, nutze Fallback")
            hour = datetime.now().hour
            return hour < 6 or hour >= 21

    # v2.3.0: Stündliche Datensammlung
    async def _collect_hourly_data(self, now):
        """Sammle stündliche current_power Daten für Tagesprofil-Learning."""
        if not self.current_power_sensor:
            return
        
        try:
            hour = now.hour
            
            if self.last_hourly_collection == hour:
                return
            
            state = self.hass.states.get(self.current_power_sensor)
            if not state or state.state in ['unknown', 'unavailable']:
                _LOGGER.debug(f"⏰ Stunde {hour}: Keine Daten von current_power verfügbar")
                return
            
            try:
                power_w = float(state.state)
                kwh = power_w / 1000.0
                
                self.today_hourly_data[hour] = kwh
                self.last_hourly_collection = hour
                
                _LOGGER.info(f"📊 Stunde {hour}: {kwh:.3f} kWh gesammelt")
                
            except ValueError:
                _LOGGER.warning(f"Ungültiger current_power Wert: {state.state}")
                
        except Exception as e:
            _LOGGER.error(f"Fehler bei stündlicher Datensammlung: {e}", exc_info=True)

    # ✅ v2.3.0 FIX: Lade Hourly Profile mit Initialisierung
    async def _load_hourly_profile(self):
        """Lade gespeichertes Tagesprofil."""
        try:
            profile_data = await self.hass.async_add_executor_job(
                _read_history_file, HOURLY_PROFILE_FILE
            )
            if profile_data:
                self.hourly_profile = profile_data
                _LOGGER.info(f"📈 Tagesprofil geladen: {len(self.hourly_profile)} Stunden")
            else:
                # ✅ FIX: Erstelle leere Datei
                _LOGGER.info("📝 Erstelle initiale hourly_profile.json")
                self._save_hourly_profile()
        except Exception as e:
            _LOGGER.warning(f"Konnte Tagesprofil nicht laden: {e}")
            # ✅ FIX: Bei Fehler trotzdem initialisieren
            self._save_hourly_profile()

    def _save_hourly_profile(self):
        """Speichere Tagesprofil."""
        try:
            self.hass.async_add_executor_job(
                _write_history_file, HOURLY_PROFILE_FILE, self.hourly_profile
            )
            _LOGGER.info("📈 Tagesprofil gespeichert")
        except Exception as e:
            _LOGGER.error(f"Fehler beim Speichern des Tagesprofils: {e}")

    def _calculate_hourly_profile(self):
        """Berechne typisches Tagesprofil aus letzten 30 Tagen."""
        try:
            if not self.daily_predictions:
                _LOGGER.debug("Keine Historie für Tagesprofil-Berechnung")
                return
            
            recent_days = list(self.daily_predictions.items())[-30:]
            hourly_patterns = {}
            
            for date_str, day_data in recent_days:
                if not isinstance(day_data, dict):
                    continue
                
                hourly_data = day_data.get('hourly_data', {})
                daily_total = day_data.get('actual', 0)
                
                if daily_total < 0.5:
                    continue
                
                for hour_str, kwh in hourly_data.items():
                    try:
                        hour = int(hour_str)
                        if kwh > 0:
                            percentage = (kwh / daily_total) * 100.0
                            
                            if hour not in hourly_patterns:
                                hourly_patterns[hour] = []
                            
                            hourly_patterns[hour].append(percentage)
                    except (ValueError, TypeError):
                        continue
            
            new_profile = {}
            for hour, percentages in hourly_patterns.items():
                if len(percentages) >= 3:
                    import statistics
                    new_profile[hour] = {
                        'mean': statistics.mean(percentages),
                        'std': statistics.stdev(percentages) if len(percentages) > 1 else 0,
                        'count': len(percentages),
                        'min': min(percentages),
                        'max': max(percentages)
                    }
            
            if new_profile:
                self.hourly_profile = new_profile
                self._save_hourly_profile()
                _LOGGER.info(
                    f"📈 Tagesprofil aktualisiert: {len(new_profile)} Stunden, "
                    f"basierend auf {len([d for d in recent_days if isinstance(d[1], dict) and d[1].get('actual', 0) > 0.5])} Tagen"
                )
                
        except Exception as e:
            _LOGGER.error(f"Fehler bei Tagesprofil-Berechnung: {e}", exc_info=True)

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
        
        profile_status = "Nicht verfügbar"
        if self.hourly_profile:
            profile_status = f"{len(self.hourly_profile)} Stunden gelernt"
        
        status_emoji = "✅" if hours_since_forecast < 1 else "⚠️"
        return (
            f"{status_emoji} Läuft normal | Letzte Prognose: {hours_since_forecast:.1f}h her | "
            f"Nächstes Learning: {next_learning}h | Inverter: {inverter_status} | "
            f"Genauigkeit: {self.accuracy:.0f}% | Tagesprofil: {profile_status}"
        )

    async def _predict_next_hour(self):
        """Berechne Prognose für nächste Stunde."""
        if not self.enable_hourly:
            return 0.0
        
        # Nacht-Fix
        if self._is_night_time():
            self.next_hour_pred = 0.0
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
        
        if self._is_night_time():
            return 0.0
        
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

    # ✅ v3.0.0 FIX: Async Weights Loading
    async def _async_load_weights(self):
        """Lade gelernte Gewichte aus Datei - ASYNC."""
        try:
            saved_weights = await self.hass.async_add_executor_job(
                _read_history_file, WEIGHTS_FILE
            )
            if saved_weights:
                self.weights.update(saved_weights)
                self.base_capacity = saved_weights.get('base_capacity', self.base_capacity)
                _LOGGER.info(f"💾 Gewichte geladen: {self.weights}")
            else:
                # Erstelle initiale Datei
                _LOGGER.info("📝 Erstelle initiale weights.json")
                await self._async_save_weights()
        except Exception as e:
            _LOGGER.warning(f"Konnte Gewichte nicht laden: {e}")
            # Bei Fehler trotzdem initialisieren
            await self._async_save_weights()

    async def _async_save_weights(self):
        """Speichere gelernte Gewichte - ASYNC."""
        try:
            save_data = self.weights.copy()
            save_data['base_capacity'] = self.base_capacity
            await self.hass.async_add_executor_job(
                _write_history_file, WEIGHTS_FILE, save_data
            )
            _LOGGER.info("💾 Gewichte gespeichert")
        except Exception as e:
            _LOGGER.error(f"Fehler beim Speichern der Gewichte: {e}")

    # Behalte synchrone Version für Callbacks (wird aber nicht im __init__ aufgerufen)
    def _save_weights(self):
        """Speichere gelernte Gewichte - SYNC Wrapper."""
        self.hass.async_create_task(self._async_save_weights())

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
            _LOGGER.info("💾 Historie gespeichert")
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
        except Exception as e:
            _LOGGER.warning(f"Last-State-Laden fehlgeschlagen: {e}")

    async def _initial_setup(self):
        """Initialer Setup."""
        # Warte kurz bis async Loading fertig ist
        await self.hass.async_add_executor_job(lambda: None)  # Yield to event loop
        
        # Jetzt können wir _load_last_data() aufrufen (braucht History)
        self._load_last_data()
        
        self._calibrate_base_capacity()
        
        if self.notify_startup:
            await self._notify_start_success()

    async def _notify_start_success(self):
        """Benachrichtigung über erfolgreichen Start."""
        try:
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "✅ SolarForecastML v3.0.0 erfolgreich gestartet",
                    "message": (
                        f"• Basiskapazität: {self.base_capacity:.2f} kWh\n"
                        f"• Weather-Typ: {self.weather_type}\n"
                        f"• Das Modell lernt täglich (23:00 Uhr) und erstellt Prognosen."
                    ),
                    "notification_id": "solar_forecast_ml_start_success"
                }
            )
            _LOGGER.info("📱 Erfolgreicher Start benachrichtigt")
        except Exception as e:
            _LOGGER.warning(f"Start-Benachrichtigung fehlgeschlagen: {e}")

    async def _notify_inverter_offline(self):
        """Benachrichtigung bei Inverter-Ausfall."""
        if not self.notify_inverter:
            return
        
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
        _LOGGER.info("🌆 Berechne Tagesprognose um 6:00 Uhr...")
        await self._create_forecast()

    async def _midnight_learning(self, now):
        """Lerne um 23:00 Uhr."""
        _LOGGER.info("🌑 Starte Lernprozess um 23:00 Uhr...")
        try:
            today = date.today().isoformat()
            actual_power = self.hass.states.get(self.power_entity)
            
            # Speichere hourly_data in Historie
            if self.today_hourly_data:
                if today not in self.daily_predictions:
                    self.daily_predictions[today] = {}
                self.daily_predictions[today]['hourly_data'] = self.today_hourly_data.copy()
                _LOGGER.info(f"📊 Stündliche Daten für {today} gespeichert: {len(self.today_hourly_data)} Stunden")
                self.today_hourly_data = {}
                self.last_hourly_collection = None
            
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
                    
                    if self.notify_learning:
                        await self._notify_learning_result(yesterday, predicted, actual, error_percent)
            
            # Berechne Tagesprofil
            if self.current_power_sensor:
                self._calculate_hourly_profile()
                    
        except Exception as e:
            _LOGGER.error(f"Fehler beim Midnight Learning: {e}", exc_info=True)

    async def _notify_learning_result(self, date_str: str, predicted: float, actual: float, error_percent: float):
        """Benachrichtigung über Learning-Ergebnis."""
        try:
            if abs(error_percent) < 10:
                emoji = "✅"
                status = "Sehr gut"
            elif abs(error_percent) < 20:
                emoji = "⚠️"
                status = "Akzeptabel"
            else:
                emoji = "❌"
                status = "Hohe Abweichung"
            
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": f"{emoji} Learning-Ergebnis {date_str}",
                    "message": (
                        f"Status: {status}\n"
                        f"• Prognose: {predicted:.2f} kWh\n"
                        f"• Tatsächlich: {actual:.2f} kWh\n"
                        f"• Abweichung: {error_percent:.1f}%\n"
                        f"• Genauigkeit: {self.accuracy:.1f}%"
                    ),
                    "notification_id": "solar_forecast_ml_learning"
                }
            )
        except Exception as e:
            _LOGGER.warning(f"Learning-Benachrichtigung fehlgeschlagen: {e}")

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
            
            # 🔧 FIX v3.0.1: Definiere 'now' zuerst!
            now = datetime.now()
            
            # Intelligenter Nacht-Fix: Nur bei tiefer Nacht (vor 5 Uhr oder nach 21 Uhr)
            if self._is_night_time() and (now.hour < 5 or now.hour >= 21):
                heute_kwh = 0.0
            
            today = date.today().isoformat()
            
            # JSON-Erweiterung
            self.daily_predictions[today] = {
                'predicted': heute_kwh,
                'predicted_morgen': morgen_kwh,
                'features': sensor_data,
                'timestamp': datetime.now().isoformat(),
                'weather_condition': forecast_data[0].get('condition', 'unknown'),
                'cloud_coverage': forecast_data[0].get('cloud_coverage'),
                'temperature': forecast_data[0].get('temperature'),
            }
            
            if self.today_hourly_data:
                self.daily_predictions[today]['hourly_data'] = self.today_hourly_data.copy()
            
            self._save_history()
            self.last_forecast_date = date.today()
            
            self.async_set_updated_data({
                "heute": round(heute_kwh, 2),
                "morgen": round(morgen_kwh, 2),
                "genauigkeit": round(self.accuracy, 1),
            })
            
            if self.notify_forecast:
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
        
        if self._is_night_time() and is_today:
            return 0.0
        
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
        attrs = {
            "last_update": self.coordinator.last_update.isoformat(),
            "next_learning": "23:00",
            "accuracy": self.coordinator.accuracy,
            "weather_type": self.coordinator.weather_type,
            "forecast_method": self.coordinator.forecast_method or "detecting...",
        }
        
        if self.coordinator.hourly_profile:
            attrs["hourly_profile_hours"] = len(self.coordinator.hourly_profile)
        
        return attrs


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
        if self.coordinator.data is None:
            _LOGGER.warning(f"⚠️ coordinator.data ist None für {self._day_key}")
            return 0.0
        return self.coordinator.data.get(self._day_key, 0.0)


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
        if self.coordinator.data is None:
            return 0.0
        return round(self.coordinator.data.get(self._key, 0.0), 2)