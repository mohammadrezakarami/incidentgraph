from __future__ import annotations

from incidentgraph.incident_evaluation import (
    build_fixture,
    heldout_digest,
    validate_fixture,
    verify_fixture,
)


def test_incident_fixture_has_required_distribution_and_group_isolation() -> None:
    cases, labels = build_fixture()

    validate_fixture(cases, labels)

    labels_by_id = {item["case_id"]: item for item in labels}
    for split in ("dev", "heldout"):
        split_cases = [item for item in cases if item["split"] == split]
        counts = {"identifiable": 0, "healthy": 0, "insufficient": 0}
        for item in split_cases:
            counts[labels_by_id[item["case_id"]]["case_type"]] += 1
        assert counts == {"identifiable": 20, "healthy": 5, "insufficient": 5}

    dev_groups = {item["group_id"] for item in cases if item["split"] == "dev"}
    heldout_groups = {item["group_id"] for item in cases if item["split"] == "heldout"}
    assert dev_groups.isdisjoint(heldout_groups)


def test_committed_incident_holdout_is_sealed_and_untouched() -> None:
    result = verify_fixture()

    assert result["status"] == "pass"
    assert result["total_cases"] == 60
    assert result["heldout_evaluated"] is False


def test_incident_holdout_digest_changes_when_a_label_changes() -> None:
    cases, labels = build_fixture()
    original = heldout_digest(cases, labels)
    heldout_label = next(item for item in labels if item["case_id"].startswith("incident-heldout"))
    heldout_label["accepted_mechanisms"] = ["tampered"]

    assert heldout_digest(cases, labels) != original
