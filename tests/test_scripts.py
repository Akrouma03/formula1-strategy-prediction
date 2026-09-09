"""CLI and export failure paths; no external services or private files."""

import importlib.util
import json

import numpy as np
import pytest

from f1strategy.paths import ROOT


def script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "args",
    [
        ["--race", "Monaco", "--position", "0"],
        ["--race", "Monaco", "--position", "1.5"],
        ["--race", "Monaco", "--position", "1", "--year", "2026"],
        ["--race", "made up", "--position", "1"],
        ["--race", "Monaco", "--position", "1", "--condition", "Snow"],
    ],
)
def test_cli_invalid_scenarios_fail_before_loading_models(args, monkeypatch):
    cli = script("predict")
    monkeypatch.setattr(cli.joblib, "load", lambda _: pytest.fail("Must reject before model loading"))
    with pytest.raises(SystemExit) as exc:
        cli.main(args)
    assert exc.value.code == 2


def test_cli_json_uses_identical_grid_features_for_all_tasks(tmp_path, monkeypatch, capsys):
    cli = script("predict")
    monkeypatch.setattr(cli, "MODELS_DIR", tmp_path)
    for task in cli.TASKS:
        (tmp_path / (task + ".joblib")).touch()
    monkeypatch.setattr(cli.joblib, "load", lambda p: {"task": p.stem, "circuits": ["monaco"]})
    seen = []

    def prediction(artifact, features):
        seen.append(features.copy())
        return np.array(["Wet - Intermediate" if artifact["task"] == "tyre_strategy" else 90.25])

    monkeypatch.setattr(cli, "predict", prediction)
    assert cli.main(["--race", "Monaco", "--position", "3", "--condition", "Wet", "--json"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["grid"] == 3 and output["season"] == 2016
    assert output["predictions"]["lap_time"] == 90.25
    assert len(seen) == 3
    assert all(frame.equals(seen[0]) for frame in seen)
    assert seen[0].iloc[0].positionStart == 3


def test_cli_missing_models_has_actionable_error(tmp_path, monkeypatch, capsys):
    cli = script("predict")
    monkeypatch.setattr(cli, "MODELS_DIR", tmp_path)
    with pytest.raises(SystemExit):
        cli.main(["--race", "Monaco", "--position", "3"])
    assert "scripts/train.py" in capsys.readouterr().err


def test_demo_export_is_deterministic_allowlisted_and_reports_source_anomalies():
    export = script("export_demo")
    first = export.build_demo()
    assert first == export.build_demo()
    json.dumps(first, allow_nan=False)
    for event in first["events"]:
        assert set(event) == {
            "id",
            "name",
            "circuit",
            "year",
            "condition",
            "laps",
            "referencePace",
            "drivers",
            "quality",
            "pace",
        }
        assert all(set(driver) == {"id", "grid", "finish", "stints"} for driver in event["drivers"])
    bahrain = next(e for e in first["events"] if e["circuit"] == "bahrain")
    assert 8 in bahrain["quality"]["duplicateGridSlots"]


def test_export_rejects_stale_report_before_writing(tmp_path, monkeypatch):
    export = script("export_demo")
    report = tmp_path / "metrics.json"
    report.write_text(
        json.dumps(
            {"schema_version": 2, "tasks": dict.fromkeys(export.TASKS, {}), "metadata": {"source_sha256": {}}}
        )
    )
    monkeypatch.setattr(export, "METRICS_JSON", report)
    monkeypatch.setattr(export, "ROOT", tmp_path)
    with pytest.raises(SystemExit, match="source data changed"):
        export.main([])
    assert not (tmp_path / "docs").exists()


@pytest.mark.parametrize("name", [".env", ".env.local", "report.docx", "thesis.pdf", "models/a.joblib"])
def test_public_guard_blocks_private_artifacts(name):
    assert "private artifact" in script("check_public_files").problems(name, b"")


def test_public_guard_detects_secrets_without_echoing_them():
    guard = script("check_public_files")
    synthetic_token = b"ghp_" + b"x" * 36
    assert guard.problems("settings.py", synthetic_token) == ["possible secret"]
    assert guard.problems("reports/metrics.json", b'{"mae": 5.47}') == []
