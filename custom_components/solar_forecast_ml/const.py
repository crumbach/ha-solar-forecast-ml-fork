"""Constants for Solar Forecast ML integration."""

DOMAIN = "solar_forecast_ml"

# Pflicht-Konfiguration
CONF_WEATHER_ENTITY = "weather_entity"
CONF_POWER_ENTITY = "power_entity"  # Tages-Ertrag (für Midnight-Learning)
CONF_UPDATE_INTERVAL = "update_interval"

# Optionale Funktionen
CONF_PLANT_KWP = "plant_kwp"
CONF_FORECAST_SOLAR = "forecast_solar_sensor"
CONF_INVERTER_POWER = "inverter_power_sensor"
CONF_INVERTER_DAILY = "inverter_daily_yield"
CONF_DIAGNOSTIC = "enable_diagnostic"
CONF_HOURLY = "enable_hourly"

# Optionale Sensoren
CONF_LUX_SENSOR = "lux_sensor"
CONF_TEMP_SENSOR = "temp_sensor"
CONF_WIND_SENSOR = "wind_sensor"
CONF_UV_SENSOR = "uv_sensor"

# ✅ NEU: Notification Toggles
CONF_NOTIFY_FORECAST = "notify_forecast"  # Tägliche Prognose-Benachrichtigung
CONF_NOTIFY_LEARNING = "notify_learning"  # Learning-Ergebnis-Benachrichtigung
CONF_NOTIFY_INVERTER = "notify_inverter"  # Inverter-Offline-Warnung
CONF_NOTIFY_STARTUP = "notify_startup"    # Start-Benachrichtigung

# Defaults
DEFAULT_UPDATE_INTERVAL = 3600  # 1 Stunde
DEFAULT_BASE_CAPACITY = 10.0    
DEFAULT_KWP_TO_KWH_FACTOR = 1.0
DEFAULT_INVERTER_THRESHOLD = 10.0

# ✅ NEU: Notification Defaults (alle standardmäßig AUS für weniger Spam)
DEFAULT_NOTIFY_FORECAST = False
DEFAULT_NOTIFY_LEARNING = False
DEFAULT_NOTIFY_INVERTER = False
DEFAULT_NOTIFY_STARTUP = True  # Nur Start-Nachricht standardmäßig an

# Datei für gelernte Gewichte
WEIGHTS_FILE = "/config/custom_components/solar_forecast_ml/learned_weights.json"
HISTORY_FILE = "/config/custom_components/solar_forecast_ml/prediction_history.json"

# Standard-Gewichte (inkl. Forecast.Solar 'fs')
DEFAULT_WEIGHTS = {
    'base': 1.0,
    'lux': 0.1,
    'temp': 0.05,
    'wind': -0.02,
    'uv': 0.08,
    'fs': 0.5,
}