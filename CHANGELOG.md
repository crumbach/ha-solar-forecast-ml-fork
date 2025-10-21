# Changelog

All notable changes to this project will be documented in this file.

---

## [4.2.0] - 2025-10-21

### 🔧 Bug Fixes & Stability Improvements

#### Critical Data Protection
- **History Overwrite Prevention**: Fixed manual forecast button (`async_manual_forecast`) and learning cycles to always load existing `prediction_history.json` before writing, ensuring no data loss or duplicates. Added merge logic and debug logs for "History geladen/gespeichert" to track entry counts.
- **Duplicate Entry Safeguard**: Explicit checks in `_create_forecast` and `_save_history` prevent multiple entries for the same day, avoiding JSON corruption.

#### UI & Entity Enhancements
- **Improved Entity Sorting**: Replaced visible numeric prefixes with entity categories (`DIAGNOSTIC` for status/accuracy/deviation, `CONFIG` for peak/production/average/autarky) for logical grouping in the HA entities list. Prognoses remain in the main group for prominence.
- **Clean Entity Names**: Removed all visible prefixes and duplicates (e.g., "Autarkiegrad Heute" instead of "Autarkiegrad Heuteute") for better readability.

### ✨ New Features

#### Extended Monitoring Sensors
Added 6 new sensors for comprehensive system monitoring and optimization:
- **Autarky Rate Sensor**: Calculates daily self-sufficiency percentage (solar production vs. total consumption) – enables energy independence tracking.
- **Average Yield Sensor**: 30-day rolling average production (kWh) for monthly/seasonal performance analysis.
- **Production Time Sensor**: Tracks the active solar production window (e.g., "09:00 - 17:00") for scheduling.
- **Peak Production Hour Sensor**: Highlights the best hour for high-load tasks (e.g., EV charging).
- **Yesterday Deviation Sensor**: Shows forecast error in kWh for the previous day – aids in model validation.
- **Diagnostic Status Sensor**: Enhanced with real-time status, emojis, and debug attributes (e.g., last learning, weights).

#### Weather & Sensor Enhancements
- **Rain Sensor Support**: New optional rain sensor (mm/h) integration – reduces predictions by 50% during rain (>0.1 mm/h) for more realistic forecasts in wet conditions.
- **UI Improvements**: Cleaner forms in config/reconfigure (prefilled values, number selector for kWp); entity list now grouped by category for intuitive navigation.

**No breaking changes** – safe upgrade from v4.0.0. Test manual buttons and check logs for history integrity.

---

## [4.0.0] - 2025-10-20

### 🚀 Major Refactor & Modularization

**Breaking Changes:** This version requires a complete reinstallation or HACS update. Existing data remains preserved (via migration from v3.0.8), but test the integration after updating.

#### Complete Modular Rewrite

The entire integration has been broken down from a monolithic `sensor.py` into separate, maintainable modules. This massively improves readability, testability, and future extensibility.

**New Structure:**
- `init.py` - Central setup and unload logic
- `button.py` - Dedicated button platform for manual forecasts
- `config_flow.py` - Extended ConfigFlow with Reconfigure and OptionsFlow (incl. notification toggles)
- `const.py` - Single Source of Truth for all constants (e.g., WEATHER_FACTORS, paths)
- `coordinator.py` - Core logic (forecast, learning, hourly) as DataUpdateCoordinator
- `helpers.py` - Utility functions (JSON-IO, migration, base-capacity calc) with v3.0.9 fixes
- `sensor.py` - Sensor platform with base class and conditional entities (e.g., Diagnostic/NextHour)
- `manifest.json` - Updated to v4.0.0, with "silver" Quality Scale and weather dependency

#### Enhancements

- **AST-based Refactoring Pipeline:** Automated code splitting and optimization (used internally for development).
- **Extended Diagnostic Sensor:** Now shows detailed attributes (e.g., last_update, weights_summary, forecast_method).
- **Robust Error Handling:** Try-Except in all critical paths (e.g., sensor reads, forecast calls) with logging.
- **Performance Optimizations:** Lazy detection with retries, merge logic for history/hourly data (no overwrites).
- **Version Consistency:** All files tagged with v4.0 (e.g., model in sensors: "v4.0 Refactored").

#### Benefits

- ✅ Better Maintainability: Each file has clear responsibility
- ✅ Scalability: Easier to add new features (e.g., extended ML weights)
- ✅ HA-Conformant: Full support for config reconfiguration and options flow

#### Migration Steps

**Handled Automatically (from v3.0.8):**
- Data files remain in `/config/solar_forecast_ml/` (update-safe).
- No manual steps needed – integration loads history/weights automatically.

**Recommended:**
1. Backup your HA config (for safety).
2. Update via HACS: Search for "Solar Forecast ML" and update to v4.0.0.
3. Restart HA and check the diagnostic sensor for "✅ Status".

See [Release Notes](https://github.com/Zara-Toorox/ha-solar-forecast-ml/releases/tag/v4.0.0) for detailed instructions and screenshots.

#### Technical Changes

- Full AST-based code splitting (from monolithic setup).
- Extended docstrings and inline comments for clarity.
- `README.md` - Badge to v4.0.0, extended installation guide.
- Tests recommended: Simulate forecasts with mock weather.

---

## [3.0.8] - 2025-10-19

### 🔒 Data Protection Enhancement

**One-time manual migration required**

#### Improved Data Security

Moved all user data to protected location outside integration folder to ensure permanent data persistence and backup compatibility.

**New Data Location:**