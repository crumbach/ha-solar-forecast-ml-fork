# 🌞 Solar Forecast ML for Home Assistant

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![Version](https://img.shields.io/badge/version-4.2.0-blue.svg)](https://github.com/Zara-Toorox/ha-solar-forecast-ml/releases)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Empower Your Solar System with Adaptive, Self-Learning Forecasts – Tailored to Your Unique Setup for Smarter Energy Management.**

Solar Forecast ML is a self-learning integration for Home Assistant that provides accurate, adaptive solar energy production forecasts. It analyzes historical data, weather conditions, and optional sensors to predict daily yields and optimize energy usage.

---

## Core Features

### Forecasting & Predictions
- **Daily Forecasts**: Predicts today's and tomorrow's total production (kWh) with automatic updates based on real-time weather and production data.
- **Next-Hour Prediction** (optional): Short-term forecast for the upcoming hour, enabled via options.
- **Peak Production Hour**: Identifies the optimal time window for high-energy tasks (e.g., charging batteries).
- **Production Time Window**: Tracks today's active solar production period.

### Machine Learning & Adaptation
- **Daily Learning Cycle**: Runs at 23:00 to compare predictions with actual yields, adjusting model weights for weather factors (e.g., lux, temperature, wind).
- **Accuracy Tracking**: Calculates model precision over the last 30 days (%).
- **Self-Calibration**: Initial base capacity from plant kWp; refines over time using historical patterns.
- **Hybrid Blending**: Optional integration with Forecast.Solar for validation and weighted averaging.

### Integration & Sensors
- **Required**: Weather entity and daily yield sensor (kWh).
- **Optional Sensors**: Current power (W), lux (lx), temperature (°C), wind (km/h), UV index, rain (mm/h), total consumption (kWh for autarky).
- **Autarky Rate**: Computes self-sufficiency percentage (solar vs. total consumption).
- **Average Yield**: 30-day rolling average production (kWh) for monthly/seasonal monitoring.

### User Controls & Notifications
- **Manual Buttons**: Trigger forecasts or learning on demand.
- **Configurable Notifications**: Alerts for startup, forecasts, learning results, and successful adaptations.
- **Diagnostic Status**: Text summary with debug attributes (e.g., last learning timestamp, weights).

---

## Learning Phases

The model progresses through phases for increasing accuracy:

```
Phase 1: Calibration (Days 1-7)          Phase 2: Learning (Days 8-30)            Phase 3: Optimized (Day 31+)
[████░░░░░░░░░░░░░░░░] ~50-70%           [████████████░░░░░░░░] ~70-85%          [████████████████████] ~85-95%
• Baseline from kWp                      • Daily weight adjustments              • Full pattern recognition
• Initial data collection                • Weather factor optimization           • Seasonal trend handling
• Weather correlation setup              • System-specific tuning                • High reliability
```

---

## Installation

### Via HACS (Recommended)
1. Add custom repository in HACS > Integrations: `https://github.com/Zara-Toorox/ha-solar-forecast-ml` (Category: Integration).
2. Search "Solar Forecast ML" and install.
3. Restart Home Assistant.

### Manual
1. Download [latest release](https://github.com/Zara-Toorox/ha-solar-forecast-ml/releases).
2. Copy `custom_components/solar_forecast_ml` to `/config/custom_components/`.
3. Restart Home Assistant.

---

## Configuration

Add via Settings > Devices & Services > + Add Integration > "Solar Forecast ML".

### Required Fields
| Field | Description | Example |
|-------|-------------|---------|
| Weather Entity | Source for forecasts | `weather.openweathermap` |
| Power Entity | Daily solar yield (kWh, resets at midnight) | `sensor.solar_daily_kwh` |

### Optional Fields
| Field | Description | Example |
|-------|-------------|---------|
| Total Consumption | Daily household use (kWh, for autarky) | `sensor.daily_consumption_kwh` |
| Plant kWp | System peak power | `5.4` |
| Current Power | Instant production (W) | `sensor.inverter_power_w` |
| Forecast.Solar Sensor | Alternative prediction (kWh) | `sensor.forecast_solar_today` |
| Lux/Temp/Wind/UV/Rain | Environmental sensors | `sensor.outdoor_lux` |

### Options
| Option | Default | Description |
|--------|---------|-------------|
| Update Interval | 3600s | Polling frequency |
| Enable Diagnostic | True | Status sensor with attributes |
| Enable Hourly | False | Next-hour predictions |
| Notify Startup/Forecast/Learning | True/False/False | Persistent notifications |

---

## Entities

| Entity | Unit | Description | Icon |
|--------|------|-------------|------|
| `sensor.solar_forecast_ml_heute` | kWh | Today's forecast | mdi:solar-power |
| `sensor.solar_forecast_ml_morgen` | kWh | Tomorrow's forecast | mdi:solar-power |
| `sensor.solar_forecast_ml_genauigkeit` | % | Model accuracy | mdi:target-variant |
| `sensor.solar_forecast_ml_status` | - | Status & debug | mdi:information-outline |
| `sensor.solar_forecast_ml_naechste_stunde` | kWh | Next hour (if enabled) | mdi:clock-fast |
| `sensor.solar_forecast_ml_peak_production_hour` | - | Best consumption time | mdi:battery-charging-high |
| `sensor.solar_forecast_ml_production_time` | - | Today's production window | mdi:timer-sand |
| `sensor.solar_forecast_ml_yesterday_deviation` | kWh | Yesterday's error | mdi:chart-bell-curve |
| `sensor.solar_forecast_ml_average_yield` | kWh | 30-day average | mdi:chart-line |
| `sensor.solar_forecast_ml_autarky_today` | % | Self-sufficiency rate | mdi:shield-sun |
| `button.solar_forecast_ml_manual_forecast` | - | Trigger forecast | mdi:refresh-circle |
| `button.solar_forecast_ml_manual_learning` | - | Trigger learning | mdi:brain |

---

## Schedule

| Time | Event | Purpose |
|------|-------|---------|
| 06:00 | Morning Forecast | Daily predictions |
| Hourly (top of hour) | Data Collection | Hourly profiles (if enabled) |
| 23:00 | Learning Cycle | Adjust weights from day's data |

---

## Troubleshooting

- **Zero Forecasts**: Check sun.sun entity and timezone.
- **Low Accuracy**: Wait 7+ days; ensure power entity resets daily.
- **No Hourly Data**: Enable option and configure current power sensor.
- **History Loss**: Manual button now merges – check logs for "History geladen/gespeichert".

---

## Contributing & Support

- **Issues**: [GitHub Issues](https://github.com/Zara-Toorox/ha-solar-forecast-ml/issues)
- **Docs**: [Wiki](https://github.com/Zara-Toorox/ha-solar-forecast-ml/wiki)
- Contributions: Fork, branch, PR with tests.

## License
MIT – see [LICENSE](LICENSE).

---

*Built for the Home Assistant community with adaptive ML for smarter solar management.*