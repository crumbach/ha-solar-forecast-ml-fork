# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.2] - 2025-10-19

### 🐛 Critical Bug Fixes

#### Bug #1: History Data Loss (CRITICAL for ML!)
**Problem:** When creating a new forecast (manual button, restart, or scheduled update), the integration was **overwriting** the complete day entry in `prediction_history.json`, causing:
- Loss of `actual` values (collected at 23:00)
- Loss of `hourly_data` (collected hourly throughout the day)
- **Machine Learning unable to learn** (no historical data to train on!)

**Root Cause:** Using direct assignment `self.daily_predictions[today] = {...}` instead of merging.

**Fix:** Changed to `self.daily_predictions[today].update({...})` to preserve existing data:
- ✅ `actual` values are now preserved
- ✅ `hourly_data` is now preserved
- ✅ **ML can now learn and improve accuracy!**

**Impact:** This was preventing the entire ML functionality from working. After this fix, the integration can finally learn from historical data and improve predictions over time.

---

#### Bug #2: False Zero Forecast at Night (UX Issue)
**Problem:** Between 00:00-04:59, "Forecast Today" sensor showed **0 kWh** even though a new day had started and forecast existed.

**Root Cause:** Night-time logic was too aggressive, setting forecast to 0 during **two** time periods:
- 21:00-23:59 ✅ (correct - day is over)
- 00:00-04:59 ❌ (wrong - new day has started!)

**Fix:** Changed night logic to only set 0 during evening hours (21:00-23:59):
- ✅ Morning (00:00-04:59): Shows forecast for new day
- ✅ Evening (21:00-23:59): Shows 0 (day is over)

**Impact:** Better user experience - no more confusing 6 hours of "dead" forecast in the morning.

---

### 📝 Technical Details

**Changed Files:**
- `sensor.py` - Two critical patches applied
- `manifest.json` - Version updated to 3.0.2

**Code Changes:**

1. **In `_create_forecast()` method (line ~850):**
```python
# Before (overwrites everything):
self.daily_predictions[today] = {...}

# After (merges with existing data):
if today not in self.daily_predictions:
    self.daily_predictions[today] = {}
self.daily_predictions[today].update({...})
```

2. **In `_create_forecast()` method (line ~841):**
```python
# Before (both time periods):
if self._is_night_time() and (now.hour < 5 or now.hour >= 21):
    heute_kwh = 0.0

# After (only evening):
if self._is_night_time() and now.hour >= 21:
    heute_kwh = 0.0
```

3. **In `_predict_day()` method (line ~1038):**
```python
# Before:
if self._is_night_time() and is_today:
    return 0.0

# After:
if self._is_night_time() and is_today and datetime.now().hour >= 21:
    return 0.0
```

---

### 🔄 Migration Notes

**No breaking changes** - this is a bug fix release.

**Recommended Actions:**
1. Update to v3.0.2 via HACS
2. Restart Home Assistant
3. Check that your historical data is preserved in `prediction_history.json`
4. Verify that morning forecasts (00:00-04:59) show correct values

---

### 🙏 Credits

Thanks to **@73ymw** for extensive testing and reporting these critical bugs!

---

## [3.0.1] - 2025-10-18

### Fixed
- Fixed coordinator data loading before first refresh
- Improved startup sequence to prevent race conditions

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

---

## [2.x.x] - Legacy Versions

See previous releases for older changelog entries.
