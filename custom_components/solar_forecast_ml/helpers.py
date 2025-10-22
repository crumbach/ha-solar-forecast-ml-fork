"""
Hilfsfunktionen für die Solar Forecast ML Integration.

Diese Datei enthält unabhängige, wiederverwendbare Funktionen für
Dateioperationen und Berechnungen, die vom Koordinator genutzt werden.

Copyright (C) 2025 Zara-Toorox

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as
published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import logging
import os
import shutil

# --- KORREKTUR (START) ---
# Die Funktionen sind aufgeteilt. Wir brauchen:
# 1. load_json aus util.json
# 2. save_json aus helpers.json
# 3. HomeAssistantError aus exceptions
from homeassistant.util import json as ha_util_json
from homeassistant.helpers import json as ha_helpers_json
from homeassistant.exceptions import HomeAssistantError
# --- KORREKTUR (ENDE) ---

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
    Verwendet ha_util_json.load_json für robustes Laden.
    Gibt ein leeres Dictionary zurück, wenn die Datei nicht existiert oder fehlerhaft ist.
    """
    try:
        # KORREKTUR: Aufruf von ha_util_json.load_json
        return ha_util_json.load_json(filepath, default={})
    except HomeAssistantError as e:
        # KORREKTUR: Direkter Aufruf von HomeAssistantError
        _LOGGER.error(f"Fehler beim Lesen der Datei {filepath} mit ha_json: {e}")
        return {}


def _write_history_file(filepath: str, data: dict):
    """
    Blockierende Hilfsfunktion zum Speichern von Daten in einer JSON-Datei.
    Verwendet ha_helpers_json.save_json für atomare Schreibvorgänge.
    Erstellt das Verzeichnis automatisch und sicher.
    """
    try:
        # KORREKTUR: Aufruf von ha_helpers_json.save_json
        ha_helpers_json.save_json(filepath, data, private=True)
    except HomeAssistantError as e:
        # KORREKTUR: Direkter Aufruf von HomeAssistantError
        _LOGGER.error(f"Fehler beim atomaren Speichern der Datei {filepath}: {e}")


def _migrate_data_files():
    """
    Migriert Lerndateien vom alten Speicherort (innerhalb von custom_components)
    zum neuen, sicheren Speicherort (/config/solar_forecast_ml).
    Diese Funktion wird einmalig beim Start nach einem Update ausgeführt.
    (Diese Funktion bleibt unverändert)
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
                _LOGGER.info(f"✅ Migrated {os.basename(old_path)} to safe location.")
                migrated_count += 1
            except Exception as e:
                _LOGGER.error(f"❌ Failed to migrate {os.path.basename(old_path)}: {e}")
        elif os.path.exists(old_path):
            # Wenn die neue Datei schon existiert, die alte einfach löschen
            try:
                os.remove(old_path)
                _LOGGER.debug(f"🗑️ Removed old data file: {os.basename(old_path)}")
            except Exception as e:
                _LOGGER.warning(f"Could not remove old data file {os.path.basename(old_path)}: {e}")

    if migrated_count > 0:
        _LOGGER.info(f"🎉 Data migration completed! {migrated_count} files moved.")


def calculate_initial_base_capacity(plant_kwp: float) -> float:
    """
    Intelligente Startwert-Berechnung der Basiskapazität basierend auf der Anlagenleistung (kWp).
    Verwendet eine Faustformel und begrenzt den Wert auf einen realistischen Bereich.
    (Diese Funktion bleibt unverändert)
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