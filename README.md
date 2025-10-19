# 🌞 Solar Forecast ML for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![Version](https://img.shields.io/badge/version-3.0.6-blue.svg)](https://github.com/Zara-Toorox/ha-solar-forecast-ml/releases)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Your solar system is unique. Your forecast should be too.**

Traditional solar forecasts rely on generic weather data and fixed algorithms. Solar Forecast ML takes a different approach: it learns YOUR system's specific behavior patterns and continuously adapts to deliver increasingly accurate predictions.

---

## 🎯 What Makes It Different

Most solar forecasts give you a weather-based estimate. Solar Forecast ML goes further:

- **🧠 Learns Your System** - Understands panel orientation, shading patterns, and efficiency characteristics unique to your installation
- **📈 Gets Smarter Daily** - Automatically improves accuracy by comparing predictions with actual yields
- **⏰ Time-Aware Adjustments** - Updates "today" forecast throughout the day as actual production data comes in
- **🌙 Intelligent Night Handling** - Knows when the sun is down, preventing unrealistic overnight predictions
- **🔒 100% Local Processing** - No cloud services required, your data stays on your system
- **🎯 Self-Calibrating** - Minimal configuration needed, the system fine-tunes itself

---

## ✨ Key Features

### Smart Forecasting
- **Daily Predictions** - Accurate forecasts for today and tomorrow
- **Hourly Profiles** *(optional)* - Short-term predictions updated hourly
- **Adaptive Correction** - Real-time adjustment based on current production
- **Accuracy Tracking** - See how well the model performs

### Machine Learning Engine
- **Automatic Learning Cycle** - Runs daily at 23:00 to analyze the day's performance
- **Pattern Recognition** - Learns typical yield patterns (e.g., "noon typically produces 15% of daily total")
- **Weight Optimization** - Adjusts ML parameters based on forecast accuracy
- **Multi-Factor Analysis** - Considers weather conditions, time of day, and historical patterns

### Flexible Integration
- **Multi-Weather Support** - Works with DWD, Met.no, OpenWeatherMap, and generic weather integrations
- **Optional Sensors** - Enhance accuracy with lux, temperature, wind, UV, or current power sensors
- **Energy Dashboard Compatible** - Seamlessly integrates with Home Assistant's energy features
- **Notification System** - Configurable alerts for forecasts and system status

---

## 🧠 How the Learning Works

Solar Forecast ML operates in three progressive phases:

```
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 1: CALIBRATION (Days 1-7)                                │
│  [████░░░░░░░░░░░░░░░░] ~50-70% accuracy                        │
│                                                                  │
│  • Uses kWp-based baseline estimation                           │
│  • Collects first batch of actual production data               │
│  • Establishes weather correlation patterns                     │
│  • Fast initial results with room for improvement               │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  PHASE 2: ACTIVE LEARNING (Days 8-30)                           │
│  [████████████░░░░░░░░] ~70-85% accuracy                        │
│                                                                  │
│  • ML model actively learns from daily comparisons              │
│  • Adjusts weights for weather factors                          │
│  • Identifies system-specific characteristics                   │
│  • Steady accuracy improvements each week                       │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  PHASE 3: OPTIMIZED (Day 30+)                                   │
│  [████████████████████] ~85-95% accuracy                        │
│                                                                  │
│  • Full understanding of daily production profile               │
│  • Recognizes seasonal patterns and trends                      │
│  • Highly accurate time-based corrections                       │
│  • Maximum prediction reliability                               │
└─────────────────────────────────────────────────────────────────┘
```

**The system automatically progresses through these phases** - no manual intervention required. Each day's actual production data makes the next day's forecast more accurate.

---

## 📦 Installation

### Option 1: HACS (Recommended)

1. Open **HACS** in Home Assistant
2. Navigate to **Integrations**
3. Click **⋮** (three dots, top right) → **Custom repositories**
4. Add repository:
   - **URL:** `https://github.com/Zara-Toorox/ha-solar-forecast-ml`
   - **Category:** Integration
5. Click **Add**, then search for "Solar Forecast ML"
6. Click **Download**
7. **Restart Home Assistant**

### Option 2: Manual Installation

1. Download the [latest release](https://github.com/Zara-Toorox/ha-solar-forecast-ml/releases)
2. Extract the ZIP file
3. Copy the `custom_components/solar_forecast_ml` folder to your Home Assistant `config/custom_components/` directory
4. **Restart Home Assistant**

---

## ⚙️ Configuration

### Initial Setup

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for **"Solar Forecast ML"**
4. Complete the setup wizard

### Required Configuration

| Setting | Description | Example | Impact |
|---------|-------------|---------|--------|
| **Weather Entity** | Your weather integration | `weather.home` | Core data source for predictions |
| **Power Entity** | Daily yield sensor (kWh) | `sensor.solar_yield_today` | Learning baseline and accuracy tracking |
| **Plant kWp** | Peak power rating | `5.4` | Initial calibration and scaling |

### Optional Sensors

Adding these sensors improves forecast accuracy by providing additional environmental data:

| Sensor Type | Purpose | Accuracy Impact | Example Entity |
|-------------|---------|-----------------|----------------|
| **Current Power** | Real-time production for hourly profiles | +10-15% | `sensor.inverter_power` |
| **Lux Sensor** | Direct brightness measurement | +5-10% | `sensor.outdoor_illuminance` |
| **Temperature** | Panel efficiency correlation | +3-5% | `sensor.outdoor_temperature` |
| **Wind Speed** | Cooling effect on panels | +2-4% | `sensor.wind_speed` |
| **UV Index** | Additional radiation indicator | +2-3% | `sensor.uv_index` |
| **Forecast.Solar** | Comparative validation | Monitoring | `sensor.energy_production_today` |

**Note:** These sensors are optional. The system works without them but becomes more accurate when available.

---

## 📊 Created Sensors

After setup, the integration creates the following entities:

| Entity ID | Unit | Description | Updates |
|-----------|------|-------------|---------|
| `sensor.solar_forecast_ml_prognose_heute` | kWh | Today's forecast (adjusts during day) | Hourly |
| `sensor.solar_forecast_ml_prognose_morgen` | kWh | Tomorrow's forecast | Daily at 06:00 |
| `sensor.solar_forecast_ml_prognose_genauigkeit` | % | Model accuracy (14-day average) | Daily at 23:00 |
| `sensor.solar_forecast_ml_status` | - | Integration status and info | Real-time |
| `sensor.solar_forecast_ml_prognose_nachste_stunde` | kWh | Next hour prediction *(optional)* | Hourly |
| `button.solar_forecast_ml_manuelle_prognose` | - | Trigger manual forecast update | On demand |

---

## 🕐 Automatic Schedule

The integration runs on an optimized schedule for best results:

| Time | Action | Description |
|------|--------|-------------|
| **06:00** | Morning Forecast | Generates predictions for today and tomorrow based on latest weather data |
| **Hourly** | Data Collection | Records current power production *(if sensor configured)* |
| **Every 4 hours** | Intraday Update | Refines today's forecast based on actual production so far |
| **23:00** | Learning Cycle | Analyzes the day's performance, adjusts ML weights, updates accuracy metrics |

All times respect your Home Assistant's timezone setting.

---

## 🔧 Technical Details

### For Developers

**Architecture:**
- Fully async implementation for efficient operation
- JSON-based persistence for ML weights and historical data
- Modular sensor framework for easy extension
- Coordinator pattern for centralized data management

**Data Storage:**
```
config/custom_components/solar_forecast_ml/
├── learned_weights.json      # ML model parameters
├── prediction_history.json   # Forecast vs actual comparisons
└── hourly_profile.json       # Time-based production patterns
```

**Weather Integration Support:**
- Priority detection (DWD → Met.no → OpenWeatherMap → Generic)
- Automatic fallback if preferred service unavailable
- Supports multiple concurrent weather entities

**API:**
- Service calls for manual forecast triggers
- Reconfiguration flow for easy setting updates
- Event firing for automation integration

---

## 💡 Best Practices

### Maximizing Accuracy

1. **Configure Plant kWp Correctly** - This is your calibration baseline. Check your inverter specs or installation documents.

2. **Add Current Power Sensor** - This single addition provides the most accuracy improvement, enabling hourly profile learning.

3. **Wait for Learning** - Don't judge accuracy in the first week. The system needs time to understand your specific installation.

4. **Monitor Accuracy Trend** - Watch `sensor.solar_forecast_ml_prognose_genauigkeit` over time. It should steadily improve.

5. **Weather Entity Quality** - Use a reliable weather integration. DWD (for Germany) and Met.no (Norway) provide excellent forecast data.

### Understanding Your Forecasts

- **Morning forecast (06:00)** is based purely on weather predictions
- **Daytime updates** incorporate actual production data to refine the "today" estimate
- **Accuracy percentage** is calculated over the past 14 days - newer data weighs more heavily
- **Night-time values** should always be zero or near-zero (intelligent sun.sun integration)

### Use Cases

**Battery Management:**
```yaml
# Charge battery when high solar production is forecast
automation:
  - trigger:
      platform: time
      at: "06:30:00"
    condition:
      condition: numeric_state
      entity_id: sensor.solar_forecast_ml_prognose_heute
      above: 20
    action:
      service: switch.turn_on
      target:
        entity_id: switch.battery_charge_from_grid
```

**Smart Appliances:**
```yaml
# Run dishwasher during forecast peak production
automation:
  - trigger:
      platform: numeric_state
      entity_id: sensor.solar_forecast_ml_prognose_heute
      above: 15
    action:
      service: notify.mobile_app
      data:
        message: "Good solar day forecast - consider running high-power appliances"
```

---

## 🛠️ Troubleshooting

### "Weather method not found" at startup
**Normal behavior!** Weather integrations often load after custom components. The integration will automatically connect within 2 minutes. If the error persists beyond that, verify your weather entity exists.

### Forecast shows 0 kWh at 6:00 AM
This shouldn't happen in v3.0.0+. If you see this:
- Check that `sun.sun` entity exists in your system
- Verify your timezone is set correctly in Home Assistant
- Review logs for any sun position calculation errors

### Hourly data not being collected
Verify these requirements:
1. `enable_hourly` is enabled in integration options
2. `current_power_sensor` is configured
3. Sensor reports power in **Watts (W)**, not kilowatts
4. Collection only occurs at the top of each hour (e.g., 10:00, 11:00)

### Accuracy is 0% or very low
**This is normal initially!** Accuracy is only calculated after the first learning cycle completes. Give the system at least 7 days to establish baseline performance, and 30+ days for optimal results.

### Predictions seem too high/low
Check your **Plant kWp** setting - this is the most common calibration issue. Your kWp should match your system's rated peak power. Also verify your **Power Entity** is reporting cumulative daily yield in kWh.

### Reset and Start Over
If you need to reset the learning data:
1. Go to **Settings** → **Devices & Services** → **Solar Forecast ML**
2. Click **Configure** → **Reset Learning Data**
3. Or manually delete JSON files in `config/custom_components/solar_forecast_ml/`
4. Restart Home Assistant

---

## 🚨 Upgrading from v2.x

**⚠️ v3.0.0 is a complete rewrite with breaking changes.**

If upgrading from any v2.x version:

1. **Backup** your current learned data (optional, for reference)
2. **Remove** the old integration completely via UI
3. **Delete** the folder `/config/custom_components/solar_forecast_ml`
4. **Restart** Home Assistant
5. **Install** v3.0.0 following the installation instructions above
6. **Reconfigure** the integration - settings don't migrate

Direct updates are not supported. The architecture changes require a clean installation.

---

## 🤝 Contributing

Contributions are welcome and appreciated!

**How to contribute:**
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Make your changes with clear, descriptive commits
4. Test thoroughly in your Home Assistant instance
5. Push to your branch (`git push origin feature/AmazingFeature`)
6. Open a Pull Request with detailed description of changes

**Contribution ideas:**
- Additional weather service integrations
- Enhanced ML algorithms
- Multi-inverter support
- Translation improvements
- Documentation enhancements

---

## 📝 Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and detailed changes.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Home Assistant Community** - For feedback and testing
- **HACS Team** - For making custom integration distribution seamless
- **Contributors** - Everyone who has submitted issues, suggestions, and code improvements

---

## 📞 Support & Resources

- **🐛 Bug Reports:** [GitHub Issues](https://github.com/Zara-Toorox/ha-solar-forecast-ml/issues)
- **💬 Feature Requests:** [GitHub Discussions](https://github.com/Zara-Toorox/ha-solar-forecast-ml/discussions)
- **📖 Documentation:** [Wiki](https://github.com/Zara-Toorox/ha-solar-forecast-ml/wiki)
- **📣 Announcements:** [Community Forum](https://community.home-assistant.io/t/solarforecast-ml-v3-0-0-adaptive-and-self-learning-for-pinpoint-solar-predictions/941652)

---

**⭐ If this integration helps you optimize your solar energy usage, please consider giving the project a star on GitHub!**

*Made with ☀️ and 🧠 for the Home Assistant community*