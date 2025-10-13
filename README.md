# 🌞 Solar Forecast ML

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub Release](https://img.shields.io/github/release/Zara-Toorox/ha-solar-forecast-ml.svg)](https://github.com/Zara-Toorox/ha-solar-forecast-ml/releases)
[![License](https://img.shields.io/github/license/Zara-Toorox/ha-solar-forecast-ml.svg)](LICENSE)

**Self-learning solar power forecast integration for Home Assistant**

Solar Forecast ML is a custom integration that predicts your solar energy production for today and tomorrow using machine learning. It learns from your actual solar data and continuously improves its accuracy.

## ✨ Features

- 🤖 **Self-learning algorithm** - Gets smarter every day
- 📊 **Two forecasts** - Today and tomorrow's solar energy production
- 🎯 **Accuracy tracking** - Monitor prediction accuracy
- ☁️ **Weather integration** - Uses your Home Assistant weather entity
- 🔌 **Optional sensors** - Enhance predictions with lux, temperature, wind, UV
- ⚙️ **Configurable** - Set your solar plant capacity (kWp)
- 📈 **Energy dashboard** - Full integration support

## 🚀 Installation

### HACS (Custom Repository)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the three dots (top right) → "Custom repositories"
4. Add: `https://github.com/Zara-Toorox/ha-solar-forecast-ml`
5. Category: "Integration"
6. Click "Download"
7. Restart Home Assistant

### Manual Installation

1. Download the latest release
2. Copy `custom_components/solar_forecast_ml` to your HA config directory
3. Restart Home Assistant

## ⚙️ Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **"+ Add Integration"**
3. Search for **"Solar Forecast ML"**
4. Configure:
   - Solar Energy Sensor (cumulative/total_increasing)
   - Weather Entity
   - Plant Capacity (kWp) - optional
   - Optional sensors: Lux, Temperature, Wind, UV

## 📊 Sensors

| Sensor | Description |
|--------|-------------|
| `sensor.solar_forecast_ml_prognose_heute` | Today's forecast (kWh) |
| `sensor.solar_forecast_ml_prognose_morgen` | Tomorrow's forecast (kWh) |
| `sensor.solar_forecast_ml_prognose_genauigkeit` | Accuracy % (14 days) |

## 🧠 How It Works

- **Days 1-2**: Initial predictions
- **Days 3-14**: Learning from your data
- **Day 14+**: Fully optimized

Updates daily at 6:00 AM.

## 📝 Example Automation

```yaml
automation:
  - alias: "Good Solar Day Notification"
    trigger:
      platform: numeric_state
      entity_id: sensor.solar_forecast_ml_prognose_heute
      above: 15
    action:
      service: notify.mobile_app
      data:
        message: "☀️ Great solar day! {{ states('sensor.solar_forecast_ml_prognose_heute') }} kWh expected"
```

## 🐛 Troubleshooting

### No predictions showing
- Check that your solar sensor is working and updating
- Verify your weather entity provides forecast data
- Check logs: Settings → System → Logs

### Predictions are inaccurate
- Wait at least 14 days for full calibration
- Ensure your solar sensor is cumulative (total_increasing)
- Add optional sensors for better accuracy
- Verify your kWp setting

### Reset learning data
Delete these files and restart HA:
- `/config/solar_forecast_weights.json`
- `/config/solar_forecast_history.json`

## 📄 License

MIT License - see [LICENSE](LICENSE)

## 🙏 Support

- 🐛 [Report Issues](https://github.com/Zara-Toorox/ha-solar-forecast-ml/issues)
- 💬 [Discussions](https://github.com/Zara-Toorox/ha-solar-forecast-ml/discussions)

---

**Made with ☀️ for Home Assistant**
