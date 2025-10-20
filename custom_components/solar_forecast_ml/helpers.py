"""
Helpers for Solar Forecast ML - v3.0.9
Refactored for better maintainability and stability.
"""

import json
import logging
import os
import shutil

# KORREKTUR 1: Importe an den Anfang verschoben und aufgeräumt
from .const import (
    DATA_DIR,
    DEFAULT_BASE_CAPACITY,  # KORREKTUR 2: Fehlender Import hinzugefügt
    HISTORY_FILE,
    HOURLY_PROFILE_FILE,
    OLD_HISTORY_FILE,
    OLD_HOURLY_PROFILE_FILE,
    OLD_WEIGHTS_FILE,
    WEIGHTS_FILE,
)

# KORREKTUR 3: Standard-Logger-Definition
_LOGGER = logging.getLogger(__name__)

# KORREKTUR 4: "Magic Numbers" als Konstanten definiert
_AVG_SUN_HOURS_DE = 3.5
_SYSTEM_EFFICIENCY = 0.85


def _read_history_file(filepath: str) -> dict:
    """Blockierende Hilfsfunktion zum Lesen einer JSON-Datei."""
    if not os.path.exists(filepath):
        return {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        _LOGGER.error(f"Fehler beim Lesen der Datei {filepath}: {e}")
        return {}


def _write_history_file(filepath: str, data: dict):
    """Blockierende Hilfsfunktion zum Speichern einer JSON-Datei."""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except IOError as e:
        _LOGGER.error(f"Fehler beim Speichern der Datei {filepath}: {e}")


def _migrate_data_files():
    """v3.0.8: Migriere JSON-Dateien zu sicherem Speicherort (einmalig, automatisch)."""
    os.makedirs(DATA_DIR, exist_ok=True)
    _LOGGER.debug(f"📁 Data directory: {DATA_DIR}")
    
    migrations = [
        (OLD_HISTORY_FILE, HISTORY_FILE, "prediction_history.json"),
        (OLD_WEIGHTS_FILE, WEIGHTS_FILE, "learned_weights.json"),
        (OLD_HOURLY_PROFILE_FILE, HOURLY_PROFILE_FILE, "hourly_profile.json"),
    ]
    
    migrated_count = 0
    for old_path, new_path, filename in migrations:
        if os.path.exists(old_path) and not os.path.exists(new_path):
            try:
                shutil.copy2(old_path, new_path)
                _LOGGER.info(f"✅ Migrated {filename} to safe location")
                migrated_count += 1
            except Exception as e:
                _LOGGER.error(f"❌ Failed to migrate {filename}: {e}")
        
        # Alte Datei nach erfolgreicher Migration oder wenn neue bereits existiert, aufräumen
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
                _LOGGER.debug(f"🗑️ Removed old {filename}")
            except Exception as e:
                _LOGGER.warning(f"Could not remove old {filename}: {e}")

    if migrated_count > 0:
        _LOGGER.info(f"🎉 Data migration completed! {migrated_count} files moved.")


def calculate_initial_base_capacity(plant_kwp: float) -> float:
    """
    Intelligente Startwert-Berechnung der Basiskapazität basierend auf kWp.
    Formel: kWp × durchschnittliche Sonnenstunden × Systemeffizienz.
    """
    if not isinstance(plant_kwp, (int, float)) or plant_kwp <= 0:
        return DEFAULT_BASE_CAPACITY

    base_capacity = plant_kwp * _AVG_SUN_HOURS_DE * _SYSTEM_EFFICIENCY
    
    # Kapazität auf einen realistischen Bereich begrenzen (Clamping)
    min_capacity = plant_kwp * 2.0
    max_capacity = plant_kwp * 5.0
    clamped_capacity = max(min_capacity, min(max_capacity, base_capacity))
    
    _LOGGER.info(
        f"🏭 Quick-Kalibrierung: kWp={plant_kwp:.2f} → Base Capacity={clamped_capacity:.2f} kWh"
    )
    return clamped_capacity