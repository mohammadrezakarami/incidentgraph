from __future__ import annotations

import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PORTFOLIO_DOCS = (
    "FINAL_TECHNICAL_REPORT.md",
    "DEMO_SCRIPT.md",
    "DIAGRAMS.md",
    "CLAIMS_EVIDENCE.md",
    "TECHNICAL_DEFENSE.md",
    "FINAL_READINESS.md",
)
SCREENSHOTS = (
    "01-report-and-review.png",
    "02-evidence-drilldown.png",
    "03-completed-and-follow-up.png",
)


def _png_size(path: Path) -> tuple[int, int]:
    payload = path.read_bytes()
    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    return struct.unpack(">II", payload[16:24])


def test_required_portfolio_documents_are_present_and_linked() -> None:
    portfolio = ROOT / "docs" / "portfolio"
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for filename in PORTFOLIO_DOCS:
        path = portfolio / filename
        assert path.is_file()
        assert len(path.read_text(encoding="utf-8")) > 500
        assert f"docs/portfolio/{filename}" in readme


def test_diagrams_describe_implemented_architecture_and_state() -> None:
    diagrams = (ROOT / "docs" / "portfolio" / "DIAGRAMS.md").read_text(encoding="utf-8")
    assert "flowchart LR" in diagrams
    assert "stateDiagram-v2" in diagrams
    for node in (
        "ValidateRequest",
        "ResolveContext",
        "PlanObservation",
        "EnforcePolicy",
        "ExecuteTool",
        "NormalizeEvidence",
        "UpdateHypotheses",
        "CheckSufficiency",
        "DraftReport",
        "ValidateReport",
        "HumanReview",
        "Finalize",
    ):
        assert node in diagrams


def test_every_cv_claim_has_evidence_and_scope() -> None:
    claims = (ROOT / "docs" / "portfolio" / "CLAIMS_EVIDENCE.md").read_text(encoding="utf-8")
    assert claims.count("### CV-") == 5
    assert claims.count("**Statement.**") == 5
    assert claims.count("**Implementation evidence.**") == 5
    assert claims.count("**Verification evidence.**") == 5
    assert claims.count("**Scope.**") + claims.count("**Dataset and result scope.**") == 5


def test_sanitized_screenshots_are_real_pngs_with_useful_dimensions() -> None:
    screenshot_root = ROOT / "artifacts" / "portfolio"
    for filename in SCREENSHOTS:
        path = screenshot_root / filename
        assert path.stat().st_size > 50_000
        width, height = _png_size(path)
        assert width >= 1_200
        assert height >= 800


def test_readiness_keeps_non_production_limitations_visible() -> None:
    readiness = (ROOT / "docs" / "portfolio" / "FINAL_READINESS.md").read_text(encoding="utf-8")
    for phrase in (
        "not production-ready",
        "AI-assisted",
        "remote workflow status is not part of the committed local evidence",
        "No public deployment",
        "12 of 12",
    ):
        assert phrase in readiness
