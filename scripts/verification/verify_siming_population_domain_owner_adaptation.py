from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend" / "tests"))

from app.config import Settings
from app.gameplay.event_store import GameplayEventStore
from app.population_continuity.decision_surface import PopulationCapabilityCatalog
from app.population_continuity.domain_projection_sources import (
    social_population_signal_population_projections,
    tax_pressure_population_projections,
)
from app.population_continuity.vertical import (
    GeneralizedPopulationDecisionFixture,
    SimingLedPopulationFixture,
)
from verify_phase3_common import write_report


RUNTIME_OWNER_CAPABILITIES = {
    "population:organization-production-work-contribution:v1",
    "population:inventory-output-custody:v1",
    "population:social-population-signal:v1",
}
DOMAIN_ADAPTER_CAPABILITIES = RUNTIME_OWNER_CAPABILITIES
TAX_CAPABILITY = "population:tax-pressure:v1"


def _focused_tests() -> tuple[bool, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "backend")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "backend/tests/test_siming_population_domain_owner_runtime.py",
            "backend/tests/test_siming_generalized_population_decision.py",
            "backend/tests/test_siming_population_production_owner_vertical.py",
            "backend/tests/test_siming_population_inventory_vertical.py",
            "backend/tests/test_siming_population_social_signal_vertical.py",
            "backend/tests/test_siming_population_tax_pressure.py",
            "backend/tests/test_siming_population_authorized_cadence_publication.py",
            "backend/tests/test_siming_population_production_replanning.py",
            "backend/tests/test_siming_led_population_seed_continuity.py",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0, result.stdout + result.stderr


def _runtime_owner_ids() -> tuple[set[str], bool, bool]:
    import app.main as runtime_main

    saved_store = runtime_main.gameplay_event_store
    store = GameplayEventStore()
    runtime_main.gameplay_event_store = store
    try:
        with TemporaryDirectory() as directory:
            state = runtime_main.build_runtime_state(
                Settings(heavenly_graph_path=str(Path(directory) / "runtime.sqlite3"))
            )
            try:
                capability = state.siming_runtime._population_capability
                owner_ids = set(capability._owner_executors)
                shares_store = all(
                    executor._authority._store is store
                    for executor in capability._owner_executors.values()
                )
                adapter_contracts_valid = all(
                    getattr(executor, "CAPABILITY_ID", "") == capability_id
                    for capability_id, executor in capability._owner_executors.items()
                )
                legacy_preserved = capability._owner_executor is not None
            finally:
                state.close()
    finally:
        runtime_main.gameplay_event_store = saved_store
    return owner_ids, shares_store and legacy_preserved, adapter_contracts_valid


def _tax_trace_invariants() -> tuple[bool, dict[str, object]]:
    from test_siming_population_authorized_cadence_publication import _tax_runtime_fixture
    from app.population_continuity.siming_contracts import PopulationCadenceInput
    from app.services.siming_population_capability import default_population_read_set_builder

    runtime_main, store, cadence, organization_projection = _tax_runtime_fixture()
    event = runtime_main.publish_authorized_population_cadence(
        cadence=cadence,
        store=store,
        organization_projection=organization_projection,
        room_id="room:task5",
        scene_id="scene:task5",
        zone_id="zone:task5",
        causation_id="task5:tax",
        correlation_id="population:task5:tax",
    )
    if event is None:
        return False, {"reason": "tax_cadence_not_published"}
    read_set = default_population_read_set_builder(
        event, PopulationCadenceInput.from_authority_event(event)
    )
    tax_rows = [
        item for item in read_set.projections if item.payload.get("candidate_kind") == "tax_pressure"
    ]
    audits = runtime_main.siming_audit_writer.find_by_correlation(
        room_id="room:task5", correlation_id="population:task5:tax"
    )
    cycle = next((audit for audit in audits if audit.reason.startswith("population_cycle")), None)
    serialized = json.dumps(
        [item.model_dump(mode="json") for item in tax_rows], sort_keys=True
    )
    source_present = any(item.event_type == "gameplay.economy.tax_obligation_opened" for item in store.read_events())
    trace_valid = (
        source_present
        and bool(tax_rows)
        and cycle is not None
        and f"read_set={read_set.read_set_digest}" in cycle.reason
        and "result=" in cycle.reason
        and "owners=0" in cycle.reason
        and "receipts=0" in cycle.reason
        and all(marker not in serialized for marker in ("amount", "account:", "evidence:"))
        and not any(
            item.event_type in {
                "gameplay.economy.tax_obligation_settled",
                "gameplay.economy.account_debited",
                "gameplay.economy.account_credited",
            }
            for item in store.read_events()
        )
    )
    return trace_valid, {
        "source_present": source_present,
        "cadence_event_id": event.event_id,
        "read_set_digest": read_set.read_set_digest,
        "cycle_reason": cycle.reason if cycle is not None else "",
        "redacted": all(marker not in serialized for marker in ("amount", "account:", "evidence:")),
    }


def main() -> int:
    focused, focused_log = _focused_tests()
    owner_ids, runtime_composition_valid, adapter_contracts_valid = _runtime_owner_ids()
    tax_trace_valid, tax_trace = _tax_trace_invariants()
    catalog = {
        descriptor.capability_id: descriptor
        for descriptor in PopulationCapabilityCatalog.default("policy:harness@1")
    }
    domain_candidates_valid = all(
        capability_id in catalog
        and catalog[capability_id].enabled
        and catalog[capability_id].validate_owner_contract()
        for capability_id in DOMAIN_ADAPTER_CAPABILITIES
    )

    decision_fixture = GeneralizedPopulationDecisionFixture.create()
    competing = decision_fixture.run_scenario("competing_candidates")
    budget_limited = decision_fixture.run_scenario("budget_exhaustion")
    selection_changes = competing["selected"] != budget_limited["selected"]

    private_social = social_population_signal_population_projections(
        population_signal_projection={
            "signal_ref": "signal:private@1",
            "provenance_ref": "provenance:private@1",
            "source_revision_pin": 1,
            "source_stream_ref": "gameplay:social:private",
            "materialization_state": "proposed",
            "visibility_scope": "actor_private",
            "participant_refs": ("character:a", "character:b"),
        },
        scope="actor:self",
    )
    tax = tax_pressure_population_projections(
        tax_obligation_projection={
            "obligation_ref": "obligation:economy:tax:organization:bakery:period:1",
            "actor_ref": "character:steward",
            "source_stream_ref": "gameplay:economy",
            "source_revision_pin": 2,
            "status": "due",
            "assessed_amount_minor": 27,
            "payer_account_id": "account:private",
            "authority_only_evidence_refs": ("evidence:private",),
        },
        scope="public",
    )
    tax_payload = json.dumps(
        tax[0].model_dump(mode="json") if tax else {}, sort_keys=True
    )
    privacy_valid = not private_social and all(
        value not in tax_payload
        for value in (
            "assessed_amount_minor",
            "payer_account_id",
            "authority_only_evidence_refs",
            "account:private",
            "evidence:private",
        )
    )

    seed_fixture = SimingLedPopulationFixture.create()
    seed_evidence = seed_fixture.run()
    receipt_refs = {seed_evidence["owner"]["receipt_ref"]}
    owner_receipts_precede_seeds = bool(seed_fixture.continuity_port.commands) and all(
        set(command.source_owner_receipt_refs) <= receipt_refs
        and bool(command.source_owner_receipt_refs)
        for command in seed_fixture.continuity_port.commands
    )
    replay = seed_evidence["replay"]
    replay_matches = (
        replay["full_equals_checkpoint_tail"]
        and replay["full_hash"] == replay["checkpoint_tail_hash"]
        and replay["character_full_hash"] == replay["character_checkpoint_tail_hash"]
    )
    tax_report_only = (
        TAX_CAPABILITY not in owner_ids
        and "owner_bound_intent" not in catalog[TAX_CAPABILITY].allowed_output_kinds
    )
    only_admitted_reach_owners = owner_ids == RUNTIME_OWNER_CAPABILITIES
    stormnight_outside_cadence = (
        all("stormnight" not in capability_id for capability_id in catalog)
        and all("stormnight" not in capability_id for capability_id in owner_ids)
    )

    checks = {
        "focused_domain_tests": focused,
        "multiple_domain_candidates_remain_valid": domain_candidates_valid,
        "selection_changes_with_policy_budget": selection_changes,
        "only_runtime_admitted_capability_ids_reach_owners": only_admitted_reach_owners,
        "inventory_social_active_from_source_manifests": owner_ids.issuperset(
            {
                "population:inventory-output-custody:v1",
                "population:social-population-signal:v1",
            }
        ),
        "tax_remains_report_only": tax_report_only,
        "private_authority_only_projections_filtered": privacy_valid,
        "owner_receipts_precede_character_core_seeds": owner_receipts_precede_seeds,
        "replay_checkpoint_tail_digests_match": replay_matches,
        "stormnight_action_windows_outside_population_cadence": stormnight_outside_cadence,
        "shared_store_and_legacy_owner_preserved": runtime_composition_valid,
        "runtime_owner_adapter_contracts_match_capability_ids": adapter_contracts_valid,
        "tax_source_to_report_only_trace_is_complete": tax_trace_valid,
    }
    report = {
        "overall_passed": all(checks.values()),
        "harness_checks": checks,
        "runtime_owner_capability_ids": sorted(owner_ids),
        "adapter_capability_ids": sorted(DOMAIN_ADAPTER_CAPABILITIES),
        "report_only_capability_ids": [TAX_CAPABILITY],
        "selection": {
            "competing": competing["selected"],
            "budget_limited": budget_limited["selected"],
        },
        "replay_hash": replay["full_hash"],
        "zero_write": tax_report_only and privacy_valid,
        "focused_log": focused_log,
        "tax_trace": tax_trace,
    }
    return write_report("siming-population-domain-owner-adaptation", report)


if __name__ == "__main__":
    raise SystemExit(main())
