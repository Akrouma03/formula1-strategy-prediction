"""Read-only inventory of allowlisted coursework datasets; never reads the report.

Private files are optional. CI and the demo use the checked-in metadata snapshot.
No dataset is rewritten, deduplicated or automatically promoted into training.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlparse
from zipfile import ZipFile
from xml.etree import ElementTree as ET

import pandas as pd

CSV_FILES = [
    "all_race_data.csv",
    "all_race_data_2.csv",
    "Lap Time Data.csv",
    "Race Data.csv",
    "updated_dataset.csv",
    "updated_dataset_2.csv",
    "PositioningData.csv",
    "preprocessed_race_data.csv",
    "Positioning/PositioningData.csv",
    "Positioning/preprocessed_race_data.csv",
    "LapTime Data.csv",
    "preprocessed_tyre_strategy.csv",
    "race_data.csv",
    "Lap Time/cleaned_lap_time_data.csv",
    "F1_data.csv",
    "f1_monaco_telemetry.csv",
]
WORKBOOKS = [
    "all_race_data.xlsx",
    "Updated_Book1.xlsx",
    "Updated_Book1_with_race_info.xlsx",
    "Driver lap times/Book1.xlsx",
    "Time Series Model/Address list.xlsx",
]
PROVENANCE = ["Data Scraping/Race Fans Data Scraping.py", "Data Scraping/Pitwall Data Scraping.py"]
EXPERIMENTS = {
    "Positioning/Positioning LSTM.py": [
        "Full-data preprocessing before random-row split",
        "One-token input, not ordered lap windows",
    ],
    "Tyre Strategy/Tyre Strategy GRU.py": [
        "Randomly generated finalPosition feature",
        "One timestep",
        "Tuner uses final test set",
        "Interactive output uses frequency lookup, not model",
    ],
    "Lap Time/GRU Lap Time.py": [
        "Post-race final position feature",
        "Full-data scaling before random-row split",
        "One timestep",
        "Test set reused for validation",
    ],
}
CANONICAL = {
    "a7e537237258a460dee02423202e497b39cb5f756b375062fbcd74f4181242c6": "data/curated/race_data.csv",
    "7ceb8cef770ab756f8ee6ce97d252d0f14124e45e18b28a9fd5875ef4f7ff434": "data/curated/lap_time_data.csv",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> tuple[pd.DataFrame, str]:
    try:
        return pd.read_csv(path, encoding="utf-8"), "utf-8"
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="latin1"), "latin1"


def profile_csv(path: Path) -> dict:
    frame, encoding = read_csv(path)
    return {
        "rows": len(frame),
        "columns": list(frame.columns),
        "encoding": encoding,
        "exact_duplicate_rows": int(frame.duplicated().sum()),
        "missing_cells": {name: int(value) for name, value in frame.isna().sum().items()},
        "distinct_nonnull": {name: int(value) for name, value in frame.nunique().items()},
    }


def workbook_metadata(path: Path) -> dict:
    # ZIP/XML structure only: no cell values, personal addresses or formulas exported.
    with ZipFile(path) as archive:
        tree = ET.fromstring(archive.read("xl/workbook.xml"))
        return {"sheet_count": len(tree.findall("{*}sheets/{*}sheet")), "status": "metadata_only"}


def readiness(profile: dict) -> dict:
    """A season-aware key is mandatory before a richer table can be joined."""
    columns = set(profile["columns"])
    missing = sorted({"Year", "Race", "Driver", "Lap"} - columns)
    issues = []
    if missing:
        issues.append("Missing key columns: " + ", ".join(missing))
    if profile["exact_duplicate_rows"]:
        issues.append("Exact duplicate rows need source-aware review, not blind deletion")
    issues.append("Event/season provenance and key uniqueness must be verified before integration")
    return {"status": "not_integrated", "issues": issues}


def build_catalogue(source: Path) -> dict:
    source = source.resolve()
    files = []
    missing = []
    for name in CSV_FILES + WORKBOOKS:
        path = source / name
        if not path.is_file():
            missing.append(name)
            continue
        if not path.resolve().is_relative_to(source):
            raise ValueError("Source links must remain inside the supplied archive.")
        digest = sha(path)
        entry = {"path": name, "sha256": digest, "bytes": path.stat().st_size}
        if name in CSV_FILES:
            entry.update(profile_csv(path))
            entry["role"] = "canonical_snapshot" if digest in CANONICAL else "not_used_for_training"
            if digest in CANONICAL:
                entry["public_copy"] = CANONICAL[digest]
            if name == "F1_data.csv":
                entry["readiness"] = readiness(entry)
        else:
            entry.update(workbook_metadata(path))
            entry["role"] = "private_workbook"
        files.append(entry)
    hashes = sorted({f["sha256"] for f in files})
    duplicates = [[f["path"] for f in files if f["sha256"] == digest] for digest in hashes]
    scripts = []
    for name in PROVENANCE:
        path = source / name
        if path.is_file():
            # Only known public source domains. Never export arbitrary URLs or credentials.
            urls = sorted(
                {
                    url
                    for url in re.findall(r"https?://[^\s\x22\x27]+", path.read_text(encoding="utf-8"))
                    if urlparse(url).hostname in {"www.racefans.net", "pitwall.app"}
                }
            )
            scripts.append(
                {
                    "path": name,
                    "sha256": sha(path),
                    "source_url_count": len(urls),
                    "example_urls": urls[:2],
                    "evidence": "URL references in surviving code, not per-row lineage",
                }
            )
    experiments = [
        {"path": name, "sha256": sha(source / name), "status": "excluded_from_benchmark", "reasons": reasons}
        for name, reasons in EXPERIMENTS.items()
        if (source / name).is_file()
    ]
    csvs = [f for f in files if f["path"] in CSV_FILES]
    return {
        "schema_version": 1,
        "scope": "Allowlisted dataset metadata only; private report and workbook contents excluded.",
        "summary": {
            "csv_files": len(csvs),
            "distinct_csv_contents": len({f["sha256"] for f in csvs}),
            "workbooks": len(files) - len(csvs),
        },
        "files": files,
        "byte_identical_groups": [group for group in duplicates if len(group) > 1],
        "missing_files": missing,
        "source_evidence": scripts,
        "legacy_experiments": experiments,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("data/catalogue.json"))
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(args.source_dir.resolve()):
        parser.error("Write the catalogue outside the preserved source archive.")
    result = build_catalogue(args.source_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"]))


if __name__ == "__main__":
    main()
