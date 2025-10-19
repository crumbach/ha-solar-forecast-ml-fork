# Changelog

All notable changes to this project will be documented in this file.

---

## [3.0.8] - 2025-10-19

### 🔒 Data Protection Enhancement

**One-time manual migration required**

#### Improved Data Security

Moved all user data to protected location outside integration folder to ensure permanent data persistence and backup compatibility.

**New Data Location:**
```
/config/solar_forecast_ml/  ✅ Update-safe!
```

**Protected Files:**
- `prediction_history.json` - Your learning history
- `learned_weights.json` - Your ML model parameters
- `hourly_profile.json` - Your generation profile

#### Benefits

- ✅ Data survives all future HACS updates automatically
- ✅ Included in Home Assistant backups
- ✅ Easily accessible via File Editor
- ✅ 100% local - no cloud, no external services

#### Migration Steps

**Before updating:**
1. Backup 3 JSON files from `/config/custom_components/solar_forecast_ml/`

**After updating:**
1. Upload files to `/config/solar_forecast_ml/` (new location)
2. Restart Home Assistant

See [Release Notes](https://github.com/Zara-Toorox/ha-solar-forecast-ml/releases/tag/v3.0.8) for detailed instructions.

#### Technical Changes

- `const.py` - Updated data storage paths
- `README.md` - Version badge updated to 3.0.8
- `manifest.json` - Version 3.0.8

---

## [3.0.6] - 2025-10-19

### Enhancements

#### Optimized Status Display

Simplified status sensor to show only essential information for better readability.

**Before:**
```
Runs normal | Last Forecast: 0.0h ago | Next Learning: 6h | Inverter: Not configured | Accuracy: 0% | Weather: GENERIC (Service) | Profile: Not available
```

**After:**
```
Forecast: 0.0h ago | Learning in: 6h | 0%
```

---

## [3.0.5] - 2025-10-19

### Bug Fixes

#### Weather Integration Detection Failure

Fixed race condition during startup where weather integration detection failed because it ran before weather integration was ready.

**Fix:** Implemented lazy detection with retry mechanism (3 attempts with delays).

---

## [3.0.4] - 2025-10-19

### Critical Bug Fixes

#### Hourly Data Overwrite & Loss on Restart

**Bug 2:** Hourly generation data was overwritten instead of merged.
**Bug 3:** Hourly data collected between 06:00-23:00 was lost on restart.

**Fix:** 
- Changed from `copy()` to `update()` for merging hourly data
- Implemented immediate disk save after each hourly collection

---

## [3.0.3] - 2025-10-19

### Critical Bug Fix

#### Manual Forecast Button Data Loss

Fixed button not loading history before creating forecast, which caused complete data loss.

**Fix:** Added `await coordinator._load_history()` before forecast creation in button.py.

---

## [3.0.2] - 2025-10-19

### Critical Bug Fixes

#### History Data Loss & Night-Time Logic

**Bug 1:** History data was overwritten instead of merged.
**Bug 2:** Morning hours (00:00-04:59) showed 0 kWh incorrectly.

**Fix:**
- Changed to `update()` instead of direct assignment
- Night logic now only sets 0 during evening (21:00-23:59)

---

## [3.0.1] - 2025-10-18

### Fixed
- Fixed coordinator data loading before first refresh
- Improved startup sequence to prevent race conditions

---

## [3.0.0] - 2025-10-18

### Added
- Complete rewrite with improved ML algorithm
- Quick calibration using plant kWp
- Smart weather integration detection (DWD prioritized)
- Hourly profile learning
- Extended JSON data storage
- Multi-language support (German/English)

### Changed
- **BREAKING:** Requires complete removal of previous versions before installation
- New button platform for manual forecast trigger
- Improved night-time detection using sun.sun entity

### Technical
- Async I/O operations
- Better error handling
- HACS compatible
- Professional documentation