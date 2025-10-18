# Changelog

All notable changes to this project will be documented in this file.

## [3.0.1] - 2025-10-19

### 🐛 Bugfixes (Critical Hotfix)
- **CRITICAL:** Fixed `name 'now' is not defined` error in `_create_forecast()`
- **CRITICAL:** Fixed sensors showing 0.0 kWh after Home Assistant restart  
- **Fixed:** Race condition in coordinator initialization
- **Fixed:** Manual forecast button now works correctly

### 🔧 Technical Changes
- Moved `_load_history()` and `_load_last_data()` to run before first coordinator refresh
- Added missing `now = datetime.now()` in night-time check
- Removed duplicate `_initial_setup()` async task call

### 📊 Impact
- ✅ Sensors now retain values after restart
- ✅ Manual forecast button works without errors
- ✅ Improved startup reliability

---

## [3.0.0] - 2025-10-18

### 🎉 Complete Rewrite
**BREAKING CHANGES:** Not compatible with v2.x - Clean installation required!

### ✨ New Features
- **Config Flow UI:** Complete setup via GUI (no more YAML!)
- **Reconfigure Flow:** Change sensors without reinstalling
- **Options Flow:** Toggle notifications and features
- **Button Entity:** Manual forecast trigger
- **Diagnostic Sensor:** Detailed status information
- **Hourly Forecast Sensor:** Short-term predictions (optional)
- **Notification System:** Configurable alerts for forecasts, learning, inverter

### 🧠 Machine Learning Improvements
- **Daily Profile Learning:** Learns typical hourly yield pattern
- **Quick Calibration:** Intelligent kWp-based initial values
- **Improved Accuracy Calculation:** MAPE-based model performance
- **Self-Calibration:** Automatic base capacity adjustment

### 🌤️ Weather Integration
- **Auto-Detection:** Automatically detects weather integration type
- **DWD Support:** Optimized for German Weather Service (preferred!)
- **Multi-Method:** Tries Service API, then Attribute fallback
- **Better Error Handling:** Clear messages when weather unavailable

### 🔌 Sensor Support
- **Current Power Sensor:** For daily profile learning (W)
- **Inverter Monitoring:** Power + Daily sensors for offline detection
- **Optional Sensors:** Lux, Temp, Wind, UV for ML features
- **Forecast.Solar:** Blending with external forecasts

### 🏗️ Architecture
- **DataUpdateCoordinator:** Modern HA design pattern
- **Async First:** All I/O operations are async
- **Clean Unload:** Proper entity cleanup on removal
- **File Storage:** JSON files in custom_components directory

### 📱 User Experience
- **Multi-Language:** German + English (expandable)
- **Descriptions:** Every config option explained
- **Validation:** Input validation with helpful error messages
- **Status Messages:** Detailed diagnostic information

### 🐛 Fixes
- **Night-Time Handling:** Intelligent fix prevents 0 kWh at 6 AM
- **Restart Resilience:** Loads last known values on startup
- **Hourly Recording:** Proper data collection every hour
- **Midnight Learning:** Runs at 23:00 instead of midnight

### 🗑️ Removed
- **YAML Configuration:** Replaced by Config Flow
- **Manual Sensor Creation:** All sensors auto-created
- **Old File Paths:** Now in custom_components directory

### ⚠️ Migration Notes
- Direct upgrade from v2.x NOT possible
- Must remove old integration completely
- Clean installation required
- Previous learned data cannot be migrated

---

## [2.3.0] - 2025-10-15

### Added
- Button for manual forecast updates
- Current power sensor for daily profile learning
- Hourly data collection
- Notification toggles
- Weather auto-detection (DWD priority)

### Improved
- Quick calibration from kWp
- Better error messages
- Sensor removal cleanup

---

## [2.2.0] - 2025-10-10

### Added
- Forecast.Solar blending
- Inverter monitoring
- Better weather condition handling

---

## [2.1.0] - 2025-10-05

### Added
- UV sensor support
- Wind sensor support
- Temperature-based corrections

---

## [2.0.0] - 2025-10-01

### Changed
- Rewrite with better ML model
- Improved accuracy tracking
- Daily learning cycle

---

## [1.1.0] - 2025-09-13

### Added
- Self-learning solar forecast with ML
- Today and tomorrow predictions
- Accuracy tracking sensor
- Optional sensor support (lux, temp, wind, UV)
- kWp configuration for better accuracy
- Energy dashboard integration

### Features
- Learns from actual production data
- Adapts to your installation
- Weather-based predictions
- 14-day calibration period

---

## [1.0.0] - 2025-09-01 (BETA)

### Added
- Initial release
- Basic solar forecasting
- Weather integration
- Manual configuration