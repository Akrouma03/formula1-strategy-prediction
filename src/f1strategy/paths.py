"""Canonical locations for data, trained models and reports."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
MODELS_DIR = ROOT / "models"
REPORTS_DIR = ROOT / "reports"

RACE_DATA = RAW_DIR / "race_data.csv"
LAP_TIME_DATA = RAW_DIR / "lap_time_data.csv"

METRICS_JSON = REPORTS_DIR / "metrics.json"


def ensure_dirs() -> None:
    """Create the output directories if they do not exist yet."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
