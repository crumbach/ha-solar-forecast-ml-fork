"""Konstanten für die Solar Forecast ML Integration."""

# Domain der Integration
DOMAIN = "solar_forecast_ml"

# Konfigurationsschlüssel (Single Source of Truth)
CONF_POWER_ENTITY = "power_entity"
CONF_WEATHER_ENTITY = "weather_entity"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_PLANT_KWP = "plant_kwp"
CONF_FORECAST_SOLAR = "forecast_solar_sensor"
CONF_INVERTER_POWER = "inverter_power_sensor"
CONF_INVERTER_DAILY = "inverter_daily_yield"
CONF_DIAGNOSTIC = "enable_diagnostic"
CONF_HOURLY = "enable_hourly"
CONF_CURRENT_POWER = "current_power_sensor"
CONF_LUX_SENSOR = "lux_sensor"
CONF_TEMP_SENSOR = "temp_sensor"
CONF_WIND_SENSOR = "wind_sensor"
CONF_UV_SENSOR = "uv_sensor"

# Notification Toggles
CONF_NOTIFY_FORECAST = "notify_forecast"
CONF_NOTIFY_LEARNING = "notify_learning"
CONF_NOTIFY_INVERTER = "notify_inverter"
CONF_NOTIFY_STARTUP = "notify_startup"

# Standardwerte
DEFAULT_UPDATE_INTERVAL = 3600  # 1 Stunde
DEFAULT_BASE_CAPACITY = 10.0
DEFAULT_KWP_TO_KWH_FACTOR = 1.0
DEFAULT_INVERTER_THRESHOLD = 10.0

# Notification Defaults
DEFAULT_NOTIFY_FORECAST = False
DEFAULT_NOTIFY_LEARNING = False
DEFAULT_NOTIFY_INVERTER = False
DEFAULT_NOTIFY_STARTUP = True

# Standard-Gewichte
DEFAULT_WEIGHTS = {
    'base': 1.0,
    'lux': 0.1,
    'temp': 0.05,
    'wind': -0.02,
    'uv': 0.08,
    'fs': 0.5,
}

# Dateipfade (außerhalb von custom_components)
DATA_DIR = "/config/solar_forecast_ml"
WEIGHTS_FILE = f"{DATA_DIR}/learned_weights.json"
HISTORY_FILE = f"{DATA_DIR}/prediction_history.json"
HOURLY_PROFILE_FILE = f"{DATA_DIR}/hourly_profile.json"

# Alte Pfade für die Migration
OLD_DATA_DIR = "/config/custom_components/solar_forecast_ml"
OLD_WEIGHTS_FILE = f"{OLD_DATA_DIR}/learned_weights.json"
OLD_HISTORY_FILE = f"{OLD_DATA_DIR}/prediction_history.json"
OLD_HOURLY_PROFILE_FILE = f"{OLD_DATA_DIR}/hourly_profile.json"

# === HIER IST DIE FEHLENDE KONSTANTE ===
# Wetterfaktoren für die Prognoseberechnung basierend auf HA-Wetter-Conditions
WEATHER_FACTORS = {
    "clear-night": 0.0,
    "cloudy": 0.4,
    "exceptional": 1.0,  # Sonderfall für "exceptional"
    "fog": 0.3,
    "hail": 0.1,
    "lightning": 0.2,
    "lightning-rainy": 0.1,
    "partlycloudy": 0.7,
    "pouring": 0.1,
    "rainy": 0.2,
    "snowy": 0.1,
    "snowy-rainy": 0.1,
    "sunny": 1.0,
    "windy": 0.8,
    "windy-variant": 0.8,
}