from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MatrixRow:
    source: str
    owner: str
    status: str


MATRIX = {
    "production_work_contribution": MatrixRow(
        "committed Production evidence + Organization schedule projection",
        "OrganizationAuthority.accept_production_work_contribution",
        "executable_next",
    ),
    "inventory_output_custody": MatrixRow(
        "certified Production output projection",
        "InventoryAuthorityService.settle_production_output_custody",
        "planned",
    ),
    "social_population_signal": MatrixRow(
        "public population signal projection",
        "SocialFactAuthority.record_admitted_population_signal_materialization_proposal",
        "planned",
    ),
    "tax_pressure": MatrixRow(
        "authority-derived Tax obligation summary with amount redacted",
        "Economy/Tax Owner",
        "report_only",
    ),
    "stormnight_action_window": MatrixRow(
        "realtime action-window evidence",
        "InvestigationConflictAuthority",
        "not_population_behavior",
    ),
}


def test_population_domain_owner_admission_matrix_has_explicit_statuses() -> None:
    assert MATRIX["production_work_contribution"].status == "executable_next"
    assert MATRIX["inventory_output_custody"].status == "planned"
    assert MATRIX["social_population_signal"].status == "planned"
    assert MATRIX["tax_pressure"].status == "report_only"
    assert MATRIX["stormnight_action_window"].status == "not_population_behavior"


def test_population_domain_owner_admission_matrix_matches_design_note() -> None:
    design = Path(__file__).parents[2] / "docs" / "superpowers" / "specs" / "world-character-siming-authority-mainline" / "2026-09-07-siming-population-domain-owner-adaptation-design.md"
    text = design.read_text(encoding="utf-8")
    for behavior, row in MATRIX.items():
        assert behavior in text
        assert row.source in text
        assert row.owner in text
        assert f"`{row.status}`" in text


def test_matrix_does_not_admit_a_generic_population_owner_or_writer() -> None:
    design = Path(__file__).parents[2] / "docs" / "superpowers" / "specs" / "world-character-siming-authority-mainline" / "2026-09-07-siming-population-domain-owner-adaptation-design.md"
    text = design.read_text(encoding="utf-8")
    assert "generic population truth owner" in text
    assert "generic writer/router" in text
    assert "second event bus/store" in text
