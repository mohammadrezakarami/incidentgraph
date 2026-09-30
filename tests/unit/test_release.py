from __future__ import annotations

import json
from pathlib import Path

import pytest

from incidentgraph.release import (
    RESTORE_CONFIRMATION,
    backup_command,
    restore_app,
    restore_command,
    verify_evaluation,
    verify_release,
)


def test_backup_and_restore_commands_are_scoped_to_app_database() -> None:
    backup = backup_command("incidentgraph-test")
    restore = restore_command("incidentgraph-test")

    assert backup[:4] == ["docker", "compose", "-p", "incidentgraph-test"]
    assert "app-db" in backup
    assert "--format=custom" in backup
    assert "--clean" in restore
    assert "--if-exists" in restore
    assert "lab-db" not in backup + restore


def test_restore_rejects_missing_confirmation_before_running_commands(tmp_path: Path) -> None:
    dump = tmp_path / "app.dump"
    dump.write_bytes(b"not-a-real-dump")
    dump.with_suffix(".dump.sha256.json").write_text(
        json.dumps({"sha256": "wrong"}), encoding="utf-8"
    )

    with pytest.raises(ValueError, match=RESTORE_CONFIRMATION):
        restore_app(dump, "incidentgraph-test", "NO")


def test_committed_v4_evaluation_is_complete_and_zero_paid_cost() -> None:
    report = verify_evaluation()

    assert report["status"] == "pass"
    assert report["agent_parts"] == 12
    assert report["agent_records"] == 120
    assert report["targets_failed"] == []
    assert report["reports_reviewed"] == 20
    assert report["paid_cost_usd"] == 0
    assert report["reproduced_from_records"] is True


def test_release_verification_includes_the_phase9_source_and_data_seal() -> None:
    result = verify_release()
    checks = {check["name"]: check for check in result["checks"]}

    assert result["status"] == "pass"
    assert checks["phase9_v4_freeze"]["passed"] is True
