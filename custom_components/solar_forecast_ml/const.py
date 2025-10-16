"""Constants for Solar Forecast ML integration."""

DOMAIN = "solar_forecast_ml"

# Pflicht-Konfiguration
CONF_WEATHER_ENTITY = "weather_entity"
CONF_POWER_ENTITY = "power_entity" # Tages-Ertrag (für Midnight-Learning)
CONF_UPDATE_INTERVAL = "update_interval"

# Optionale Funktionen
CONF_PLANT_KWP = "plant_kwp"
CONF_FORECAST_SOLAR = "forecast_solar_sensor"
CONF_INVERTER_POWER = "inverter_power_sensor"  # Neu: Current Power für einfachen On/Off-Check
CONF_INVERTER_DAILY = "inverter_daily_yield"   # Neu: Optional Daily für robustere Checks
CONF_DIAGNOSTIC = "enable_diagnostic"  # Neu: Toggle für Status-Sensor
CONF_HOURLY = "enable_hourly"  # Neu: Toggle für nächste Stunde Prognose

# Optionale Sensoren
CONF_LUX_SENSOR = "lux_sensor"
CONF_TEMP_SENSOR = "temp_sensor"
CONF_WIND_SENSOR = "wind_sensor"
CONF_UV_SENSOR = "uv_sensor"

# Defaults
DEFAULT_UPDATE_INTERVAL = 3600  # 1 Stunde
DEFAULT_BASE_CAPACITY = 10.0    
DEFAULT_KWP_TO_KWH_FACTOR = 1.0 # KORREKTUR: Faktor 1.0 für stündliche kW-Basis (war 4.5)
DEFAULT_INVERTER_THRESHOLD = 10.0  # Neu: Min-Watt für "on"

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
    'fs': 0.5, # Blend-Faktor für Forecast.Solar
}