from pathlib import Path

from PySide6.QtCore import QStandardPaths

DATA_DIR_NAME = "RandomDrumSheet_Data"
PRESET_DIR_NAME = "Preset"
SAVES_DIR_NAME = "Saves"
SHEETS_DIR_NAME = "Sheets"


def data_dir() -> Path:
    documents = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
    return Path(documents) / DATA_DIR_NAME


def preset_dir() -> Path:
    return data_dir() / PRESET_DIR_NAME


def saves_dir() -> Path:
    return data_dir() / SAVES_DIR_NAME


def sheets_dir() -> Path:
    return data_dir() / SHEETS_DIR_NAME


def ensure_data_dirs() -> Path:
    for path in (preset_dir(), saves_dir(), sheets_dir()):
        path.mkdir(parents=True, exist_ok=True)
    return data_dir()
