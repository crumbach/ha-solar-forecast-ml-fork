# Solar Forecast ML

**Self-Learning Solar Power Forecast Integration for Home Assistant**

Solar Forecast ML is a custom integration that predicts your solar energy production for today, tomorrow, and the next hour using machine learning. It learns from your actual solar data, weather forecasts, and optional sensors, continuously improving its accuracy over time. No YAML required – everything is configured via the intuitive UI Config Flow!

✨ **Features**

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

🚀 **Installation**

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

⚙️ **Configuration**

1. Go to **Settings → Devices & Services**.
2. Click **+ Add Integration**.
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
    device_class: energy
    state_class: total_increasing
    state: "{{ (states('sensor.solar_total_yield') | float - states('sensor.solar_yesterday_yield') | float) | round(2) }}"
```

📊 **Sensors**

| Sensor | Description | Icon |
|--------|-------------|------|
| `sensor.solar_forecast_ml_prognose_heute` | Today's forecast (kWh) | mdi:solar-power |
| `sensor.solar_forecast_ml_prognose_morgen` | Tomorrow's forecast (kWh) | mdi:solar-power |
| `sensor.solar_forecast_ml_prognose_genauigkeit` | Accuracy % (last 30 days) | mdi:chart-line-variant |
| `sensor.solar_forecast_ml_status` (optional) | Status text (e.g., "✅ Running normal \| Inverter: Online") | mdi:information-outline |
| `sensor.solar_forecast_ml_prognose_naechste_stunde` (optional) | Next hour forecast (kWh, night=0) | mdi:clock-fast |

🧠 **How It Works**

- **Days 1-2**: Initial predictions based on weather + plant capacity.
- **Days 3+**: Learns from actual yield (23:00 nightly) – adjusts weights (base, lux, etc.) with 1% learning rate.
- **Forecasts**: Daily at 6 AM (today/tomorrow); hourly updates for next hour (if enabled).
- **Inverter Logic**: Full OR-check (no sensors = no scaling). Offline? Notification + forecast=0.
- **Robustness**: Handles unavailable states, clamps night to 0, retains last value on restart.

**Automation Examples**:
- EV Charge: Trigger if `{{ states('sensor.solar_forecast_ml_prognose_naechste_stunde') | float > 0.5 }}` – "Charge now!"
- Alert: On inverter offline – "Check panels via notification."

## Troubleshooting
- **No Forecast?** Ensure weather entity supports "daily" & "hourly" forecasts (test in Developer Tools > Services > weather.get_forecasts).
- **Accuracy 0%?** New setup – needs 1-2 days of data to learn.
- **Logs**: Search "solar_forecast_ml" in **Settings > System > Logs** – emojis for quick spotting (e.g., "⚠️ No weather data").
- **Inverter Not Scaling?** Check sensors in States; no sensors = full forecasts.

## Changelog
- **v2.1.8 RC1**: Added next-hour sensor, inverter OR-logic, diagnostic status, night clamps, robust fallbacks.
- **v2.1.0**: Base release with self-learning & blending.

Thanks to [Zara-Toorox](https://github.com/Zara-Toorox) for development! Stars, forks, or issues? Welcome! 🌞

[License: MIT](LICENSE)
```

Copy-paste das in GitHub als README.md (Add file > Create new > README.md > Paste > Commit "Add full English README"). Dann ist's ready für Release & HACS. Was denkst du – passt's, oder mehr Details (z.B. Screenshots)? 🚀
