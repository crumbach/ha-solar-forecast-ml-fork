Haha, Mate – klar, ich hab die README nochmal durchgecheckt! 😎 Sie sieht insgesamt **super aus**: Klar strukturiert, engaging, mit Emojis für Punch, und voll HACS/HA-freundlich (Badges, Beispiele, Troubleshooting). Der coole Intro-Text ("Imagine this...") ist 'n Hammer-Hook – macht's sofort ansprechend und hebt den "Why cool?"-Vibe raus. Markdown ist clean (keine Broken-Links, Tabellen passen).

**Kleiner Haken**: Der zweite Absatz ("Solar Forecast ML is a custom integration...") fühlt sich redundant an (fast identisch zum coolen Intro). Ich hab's gemerged/gekürzt, um's knackig zu halten. Und den blauen HA-Button ("Created with Home Assistant") hab ich am Anfang reingetan – das ist der klassische blaue Badge, der zu "my.home-assistant.io" linkt (für Custom Repos super, macht's official-feeling). Hier der korrigierte, final-ready Text (copy-paste direkt in GitHub als README.md-Update):

```markdown
# 🌞 Solar Forecast ML

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub Release](https://img.shields.io/github/release/Zara-Toorox/ha-solar-forecast-ml.svg)](https://github.com/Zara-Toorox/ha-solar-forecast-ml/releases)
[![License](https://img.shields.io/github/license/Zara-Toorox/ha-solar-forecast-ml.svg)](LICENSE)
<a href="https://my.home-assistant.io/redirect/custom_components/?repository=Zara-Toorox/ha-solar-forecast-ml"><img src="https://my.home-assistant.io/badges/created.svg" /></a>

**Self-Learning Solar Power Forecast Integration for Home Assistant**

Imagine this: A custom integration that predicts your solar power for today, tomorrow, and the next hour using machine learning – learning from your real data, weather forecasts, and optional sensors. It gets smarter every day, accuracy climbs, and you save nerves (and electricity bills)! No YAML chaos – everything set up via a slick UI Config Flow. Cool because it doesn't just forecast; it *understands* your setup and brings automations like "EV charge on peak sun" to life. Plug it in, and let the sun work for you!

## ✨ Features

- 🤖 **Self-Learning Algorithm**: Gets smarter every day by adjusting weights from real yield data (midnight learning).
- 📊 **Daily Forecasts**: Today and tomorrow's solar energy production in kWh.
- ⏰ **Next Hour Forecast**: Optional sensor for granular predictions (e.g., for EV charging automations) with night clamps (0 kWh at dark).
- 🎯 **Accuracy Tracking**: Monitors prediction accuracy (%) based on the last 30 days (MAPE error).
- ☁️ **Weather Integration**: Uses your Home Assistant weather entity for daily/hourly forecasts.
- 🔌 **Optional Sensors**: Enhance predictions with lux, temperature, wind, UV, and Forecast.Solar blending.
- ⚙️ **Inverter Checks**: Robust offline detection with OR-logic (Power >10W OR Daily Yield >0.1 kWh = full forecast; else scales to 0 kWh + notification). No sensors? No scaling – keeps full predictions.
- 📋 **Diagnostic Status**: Optional sensor showing "✅ Running normal" with details (last update, next learning, inverter status).
- 📈 **Energy Dashboard Support**: Full integration with HA's energy tab.
- 💾 **Robust Storage**: Last-value hold after restarts, JSON files for weights/history (/config/custom_components/...).

## 🚀 Installation

### HACS (Recommended – Custom Repository)
1. Open HACS in Home Assistant.
2. Go to **Integrations**.
3. Click the three dots (top right) → **Custom repositories**.
4. Add: `https://github.com/Zara-Toorox/ha-solar-forecast-ml`
5. Category: **Integration**.
6. Click **Download**.
7. Restart Home Assistant.

### Manual Installation
1. Download the latest release [ZIP](https://github.com/Zara-Toorox/ha-solar-forecast-ml/releases).
2. Extract and copy the `custom_components/solar_forecast_ml` folder to your HA config directory (`/config/custom_components/solar_forecast_ml`).
3. Restart Home Assistant.

## ⚙️ Configuration

1. Go to **Settings** → **Devices & Services**.
2. Click **"+ Add Integration"**.
3. Search for **"Solar Forecast ML"**.
4. Configure via the UI Flow:
   - **Required**: Weather Entity (e.g., `weather.home` – supports daily/hourly forecasts).
   - **Required**: Solar Energy Sensor (daily yield in kWh, resets at midnight, e.g., `sensor.solar_daily_yield` – total_increasing device class).
   - **Optional**: Plant Capacity (kWp, e.g., 10.5 – improves initial predictions; system learns anyway).
   - **Optional**: Update Interval (seconds, default 3600 – hourly data collection; forecasts daily at 6 AM).
   - **Optional Sensors**: Forecast.Solar (for blending), Lux (illuminance), Temperature, Wind Speed, UV.
   - **Inverter Sensors**: 
     - Power Sensor (current yield in W, e.g., `sensor.solar_current_power` from Fronius/SMA/Anker – checks >10W).
     - Daily Yield (cumulative kWh since midnight, e.g., `sensor.solar_daily_production` – optional for night/backup checks >0.1 kWh).
   - **Toggles**: Enable Diagnostic Status (feedback sensor), Enable Next Hour Forecast (granular sensor).

**Tip**: For missing sensors (e.g., daily yield), create a template sensor:
```
sensor:
  - platform: template
    name: "Daily Inverter Yield"
    unit_of_measurement: "kWh"
    device_class