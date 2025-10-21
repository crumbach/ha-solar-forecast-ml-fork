"""
Hilfsfunktionen für die Solar Forecast ML Integration.

Diese Datei enthält unabhängige, wiederverwendbare Funktionen für
Dateioperationen und Berechnungen, die vom Koordinator genutzt werden.
"""

import json
import logging
import os
import shutil

from .const import (
    DATA_DIR,
    DEFAULT_BASE_CAPACITY,
    HISTORY_FILE,
    HOURLY_PROFILE_FILE,
    OLD_HISTORY_FILE,
    OLD_HOURLY_PROFILE_FILE,
    OLD_WEIGHTS_FILE,
    WEIGHTS_FILE,
)

_LOGGER = logging.getLogger(__name__)


def _read_history_file(filepath: str) -> dict:
    """
    Blockierende Hilfsfunktion zum Lesen einer JSON-Datei.
    Gibt ein leeres Dictionary zurück, wenn die Datei nicht existiert oder fehlerhaft ist.
    """
    if not os.path.exists(filepath):
        return {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        _LOGGER.error(f"Fehler beim Lesen der Datei {filepath}: {e}")
        return {}


def _write_history_file(filepath: str, data: dict):
    """
    Blockierende Hilfsfunktion zum Speichern von Daten in einer JSON-Datei.
    Erstellt das Verzeichnis, falls es nicht existiert.
    """
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except IOError as e:
        _LOGGER.error(f"Fehler beim Speichern der Datei {filepath}: {e}")


def _migrate_data_files():
    """
    Migriert Lerndateien vom alten Speicherort (innerhalb von custom_components)
    zum neuen, sicheren Speicherort (/config/solar_forecast_ml).
    Diese Funktion wird einmalig beim Start nach einem Update ausgeführt.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    migrations = [
        (OLD_HISTORY_FILE, HISTORY_FILE),
        (OLD_WEIGHTS_FILE, WEIGHTS_FILE),
        (OLD_HOURLY_PROFILE_FILE, HOURLY_PROFILE_FILE),
    ]
    migrated_count = 0
    for old_path, new_path in migrations:
        if os.path.exists(old_path) and not os.path.exists(new_path):
            try:
                # move statt copy, um die alte Datei direkt zu verschieben
                shutil.move(old_path, new_path)
                _LOGGER.info(f"✅ Migrated {os.path.basename(old_path)} to safe location.")
                migrated_count += 1
            except Exception as e:
                _LOGGER.error(f"❌ Failed to migrate {os.path.basename(old_path)}: {e}")
        elif os.path.exists(old_path):
            # Wenn die neue Datei schon existiert, die alte einfach löschen
            try:
                os.remove(old_path)
                _LOGGER.debug(f"🗑️ Removed old data file: {os.path.basename(old_path)}")
            except Exception as e:
                _LOGGER.warning(f"Could not remove old data file {os.path.basename(old_path)}: {e}")

    if migrated_count > 0:
        _LOGGER.info(f"🎉 Data migration completed! {migrated_count} files moved.")


def calculate_initial_base_capacity(plant_kwp: float) -> float:
    """
    Intelligente Startwert-Berechnung der Basiskapazität basierend auf der Anlagenleistung (kWp).
    Verwendet eine Faustformel und begrenzt den Wert auf einen realistischen Bereich.
    """
    if not isinstance(plant_kwp, (int, float)) or plant_kwp <= 0:
        return DEFAULT_BASE_CAPACITY
        
    avg_sun_hours = 3.5  # Durchschnittliche Sonnenstunden in DE
    system_efficiency = 0.85 # Geschätzte Systemeffizienz
    base_capacity = plant_kwp * avg_sun_hours * system_efficiency
    
    # Begrenzung auf einen sinnvollen Bereich (Clamping)
    min_capacity = plant_kwp * 2.0
    max_capacity = plant_kwp * 5.0
    clamped_capacity = max(min_capacity, min(max_capacity, base_capacity))
    
    _LOGGER.info(f"🏭 Quick-Kalibrierung: kWp={plant_kwp:.2f} → Base Capacity={clamped_capacity:.2f} kWh")
    return clamped_capacity

