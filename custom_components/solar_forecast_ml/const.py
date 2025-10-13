"""Constants for Solar Forecast ML integration."""

DOMAIN = "solar_forecast_ml"

# Pflicht-Konfiguration
CONF_WEATHER_ENTITY = "weather_entity"
CONF_POWER_ENTITY = "power_entity"
CONF_UPDATE_INTERVAL = "update_interval"

# Optional: Anlagengröße
CONF_PLANT_KWP = "plant_kwp"

# Optionale Sensoren
CONF_LUX_SENSOR = "lux_sensor"
CONF_TEMP_SENSOR = "temp_sensor"
CONF_WIND_SENSOR = "wind_sensor"
CONF_UV_SENSOR = "uv_sensor"

# Defaults
DEFAULT_UPDATE_INTERVAL = 3600  # 1 Stunde
DEFAULT_BASE_CAPACITY = 10.0    # Falls keine Anlagengröße angegeben
DEFAULT_KWP_TO_KWH_FACTOR = 4.5 # Faktor für Umrechnung kWp → kWh/Tag

# Datei für gelernte Gewichte
WEIGHTS_FILE = "/config/custom_components/solar_forecast_ml/learned_weights.json"
HISTORY_FILE = "/config/custom_components/solar_forecast_ml/prediction_history.json"
