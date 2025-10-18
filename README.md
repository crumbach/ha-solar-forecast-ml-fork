# 🌞 Solar Forecast ML for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![Version](https://img.shields.io/badge/version-3.0.1-blue.svg)](https://github.com/Zara-Toorox/ha-solar-forecast-ml/releases)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Intelligent solar yield forecasting with Machine Learning for Home Assistant**

This integration uses Machine Learning to create accurate predictions for your solar yield. It learns daily from actual yields and automatically adapts to your system.

---

## 🚨 **IMPORTANT - Upgrading from v2.x to v3.0.0**

**v3.0.0 is a complete rewrite!**

⚠️ **BEFORE installation:**

1. **Remove the old integration** completely from Home Assistant
2. **Delete the directory** `/config/custom_components/solar_forecast_ml`
3. **Restart Home Assistant**
4. **Then install v3.0.0** (see below)

**Direct update is NOT possible!**

---

## ✨ **Features**

### **Forecasts**
- 📈 **Today & Tomorrow** - Accurate daily forecasts
- ⏰ **Hourly forecasts** - Short-term predictions (optional)
- 🎯 **Time-based correction** - "Today" forecast adapts during the day
- 🌙 **Intelligent night fix** - No more 0 kWh at 6:00 AM

### **Machine Learning**
- 🧠 **Automatic learning** - Daily at 11:00 PM
- 📊 **Daily profile learning** - Learns typical yield pattern
- 🎯 **Accuracy tracking** - Shows model performance
- 🔄 **Self-calibration** - Adapts to your system

### **Weather Integrations**
- 🇩🇪 **DWD** (German Weather Service) - Preferred
- 🌍 **Met.no** - Norwegian Weather Service
- ☁️ **OpenWeatherMap**
- 🔄 **Generic** - Works with almost all

### **Additional Sensors (Optional)**
- ☀️ Lux sensor (brightness)
- 🌡️ Temperature sensor
- 💨 Wind sensor
- 🔆 UV index sensor
- 📊 Forecast.Solar (comparison)
- ⚡ Current power (for daily profile learning)
- 🔌 Inverter monitoring

---

## 📦 **Installation**

### **Option 1: HACS (Recommended)**

1. Open **HACS** in Home Assistant
2. Go to **Integrations**
3. Click on **⋮** (3 dots top right)
4. Select **Custom repositories**
5. Add:
   - **Repository:** `https://github.com/Zara-Toorox/ha-solar-forecast-ml`
   - **Category:** Integration
6. Click **Add**
7. Search for "Solar Forecast ML"
8. Click **Download**
9. **Restart Home Assistant**

### **Option 2: Manual**

1. Download the [latest release](https://github.com/Zara-Toorox/ha-solar-forecast-ml/releases)
2. Extract the ZIP
3. Copy folder `custom_components/solar_forecast_ml` to `/config/custom_components/`
4. **Restart Home Assistant**

---

## ⚙️ **Configuration**

### **1. Add Integration**

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "**Solar Forecast ML**"
4. Follow the setup wizard

### **2. Required Fields**

| Field | Description | Example |
|------|-------------|---------|
| **Weather Entity** | Your weather integration | `weather.home` |
| **Power Entity** | Sensor with daily yield in kWh | `sensor.solar_yield_today` |
| **Plant kWp** | Peak power of your system | `2.13` |

### **3. Optional Sensors**

All optional sensors improve forecast accuracy:

- **Forecast.Solar** - For comparison
- **Current Power** - For daily profile learning (recommended!)
- **Lux, Temp, Wind, UV** - For ML features

### **4. Notifications**

Enable/disable as needed:
- ✅ Daily forecast (6:00 AM)
- ✅ Learning result (11:00 PM)  
- ⚠️ Inverter offline warning
- ✅ Startup notification

---

## 📊 **Created Sensors**

After setup, the following sensors are created:

| Sensor | Unit | Description |
|--------|------|-------------|
| `sensor.solar_forecast_ml_prognose_heute` | kWh | Today's forecast |
| `sensor.solar_forecast_ml_prognose_morgen` | kWh | Tomorrow's forecast |
| `sensor.solar_forecast_ml_prognose_genauigkeit` | % | Model accuracy |
| `sensor.solar_forecast_ml_status` | - | Integration status |
| `sensor.solar_forecast_ml_prognose_nachste_stunde` | kWh | Next hour (optional) |
| `button.solar_forecast_ml_manuelle_prognose` | - | Manual update |

---

## 🕐 **Schedule**

| Time | Action | Description |
|------|--------|-------------|
| **06:00** | Daily forecast | Creates forecast for today & tomorrow |
| **Hourly** | Data collection | Collects current power (if configured) |
| **23:00** | Learning | Learns from today's yield and adjusts weights |

---

## 📈 **How It Works**

### **Day 1-7: Calibration**
- Uses kWp-based estimation
- Collects first data
- Accuracy increases daily

### **After 1 Week: Learning Active**
- ML model learns from actual values
- Weights are adjusted
- Accuracy > 85%

### **After 30 Days: Daily Profile**
- Knows typical yield pattern
- "At 12 PM: 15% of daily yield"
- Highest precision reached

---

## 🐛 **Troubleshooting**

### **"Weather method not found" at startup**
**Normal!** Weather integration loads later than Solar ML. Works after 2 minutes.

### **Forecast is 0 kWh at 6:00 AM**
If you still have v2.x: Upgrade to v3.0.0! The intelligent night fix prevents this.

### **Hourly data not collected**
Check:
1. `enable_hourly` is activated
2. `current_power_sensor` is configured
3. Sensor provides values in **W** (Watts)
4. Collection runs only at **full hour**

### **Accuracy is 0%**
**Normal** in first days! Accuracy is calculated after first learning cycle.

---

## 📁 **File Structure**

The integration creates the following files in `/config/custom_components/solar_forecast_ml/`:

```
learned_weights.json        # Learned ML weights
prediction_history.json     # Forecasts & actual values
hourly_profile.json        # Daily profile (after 30 days)
```

**Backup recommended!** These files contain your learned model.

---

## 🤝 **Contributing**

Contributions are welcome!

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📝 **Changelog**

See [CHANGELOG.md](CHANGELOG.md) for all changes.

---

## 📄 **License**

MIT License - see [LICENSE](LICENSE) file.

---

## 🙏 **Thanks**

- Home Assistant Community
- HACS Team
- All beta testers and contributors

---

## 📞 **Support**

- 🐛 **Bugs:** [GitHub Issues](https://github.com/Zara-Toorox/ha-solar-forecast-ml/issues)
- 💬 **Discussions:** [GitHub Discussions](https://github.com/Zara-Toorox/ha-solar-forecast-ml/discussions)
- 📖 **Documentation:** [Wiki](https://github.com/Zara-Toorox/ha-solar-forecast-ml/wiki)

---

**⭐ If you like this integration, give the project a star on GitHub!**