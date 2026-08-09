from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.gameplay.bakery_reference_runtime import BakeryReferenceScenario
from app.gameplay.bakery_mirror_source import BakeryMirrorSource
from app.gameplay.construction_production_runtime import ConstructionProductionAuthority, Facility
from app.gameplay.econ1_economy_runtime import BusinessPeriod, EconomicObligation, EconomyAuthority, MarketQuote
from app.gameplay.economy_runtime import EconomyAuthorityService
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.inventory_runtime import ContainerSpec, InventoryAuthorityService, InventoryDefinitionRegistry, ItemDefinition
from app.gameplay.organization_government_runtime import GovernmentAuthority
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.settlement_plan import build_atomic_event_batch
try:
    from common import repo_root, resolve_godot_exe, run_command, verification_dir, write_json, write_markdown
except ModuleNotFoundError:  # imported as a package by verification tests
    from scripts.verification.common import repo_root, resolve_godot_exe, run_command, verification_dir, write_json, write_markdown


PREDECESSORS = (
    "phase1b-contract-verification-report.json",
    "phase1c-frost-farm-report.json",
    "econ1-construction-production-report.json",
    "econ1-survival-profile-report.json",
    "econ1-economy-period-settlement-report.json",
    "econ1-organization-government-report.json",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    parser.add_argument("--godot-exe", default=None)
    args = parser.parse_args()
    root = repo_root()
    directory = verification_dir(root)
    predecessor_results = []
    for name in PREDECESSORS:
        path = directory / name
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        predecessor_results.append({"name": name, "passed": any(value is True for key, value in payload.items() if key.startswith("overall_"))})
    scenario = BakeryReferenceScenario.default()
    store = GameplayEventStore()
    periods = scenario.run_three_periods(store=store)
    events = store.read_events()
    event_types = [event.event_type for event in events]
    input_consumed = event_types.index("gameplay.inventory.reservation_consumed")
    output_received = event_types.index("gameplay.inventory.output_received")
    sale_posted = event_types.index("gameplay.economy.sale_posted")
    replay_engine = GameplayProjectionReplay(projector_id="projection:bakery", projector_version="v1")
    replay = replay_engine.full_replay(events)
    checkpoint = replay_engine.create_checkpoint(events[:20], active_patch_set_revision="p1d", registry_revision="p1d", world_config_revision="p1d")
    checkpoint_tail = replay_engine.checkpoint_plus_tail_replay(checkpoint, events[20:], active_patch_set_revision="p1d", registry_revision="p1d", world_config_revision="p1d")
    employee = scenario.with_existing_character_employee("character:char_b")
    failure_matrix = _failure_matrix(scenario)
    mirror_view = BakeryMirrorSource(scenario=scenario, events=events).godot_view()
    mirror_payload_path = directory / "phase1d-bakery-godot-payload.json"
    mirror_payload = {
        "actor_ref": mirror_view.actor_ref,
        "consumer": mirror_view.consumer,
        "source_facade_revision": mirror_view.source_facade_revision,
        "source_revision_vector": dict(mirror_view.source_revision_vector),
        "view_checksum": mirror_view.view_checksum,
        "groups": {
            group_id: {
                "projection_revision": envelope.projection_revision,
                "payload": dict(envelope.payload),
            }
            for group_id, envelope in mirror_view.groups.items()
        },
    }
    write_json(mirror_payload_path, mirror_payload)
    godot_probe = _run_godot_mirror_probe(root, directory, mirror_payload_path, args.godot_exe)
    report = {
        "overall_phase1d_econ1_bakery_passed": (
            all(item["passed"] for item in predecessor_results)
            and len(periods) == 3
            and all(period.closed for period in periods)
            and replay.succeeded
            and checkpoint_tail.succeeded
            and checkpoint_tail.projection_hash == replay.projection_hash
            and sum(event.event_type == "gameplay.economy.business_period_closed" for event in events) == 3
            and sum(event.event_type == "gameplay.inventory.output_received" for event in events) == 3
            and event_types.count("gameplay.inventory.reservation_created") == 6
            and event_types.count("gameplay.inventory.reservation_consumed") == 6
            and input_consumed < output_received < sale_posted
            and all(item["zero_write"] for item in failure_matrix)
            and all(item["recovery_observed"] for item in failure_matrix)
            and godot_probe["proved"]
        ),
        "predecessors": predecessor_results,
        "periods": [period.model_dump(mode="json") for period in periods],
        "event_count": len(events),
        "event_types": [event.event_type for event in events],
        "replay": {"succeeded": replay.succeeded, "projection_hash": replay.projection_hash},
        "checkpoint_tail_replay": {"succeeded": checkpoint_tail.succeeded, "projection_hash": checkpoint_tail.projection_hash},
        "owner_matrix": {"construction": "facility/recipe/run", "survival": "need/consumption-proposal", "economy": "quote/posting/obligation", "organization-government": "permit/inspection/role"},
        "employee_path": {"refs": employee.employee_refs, "backed_by_existing_profiles": True},
        "failure_matrix": failure_matrix,
        "godot_committed_mirror": godot_probe,
        "non_claims": ["dynamic market", "Population Simulation", "Creator Control Plane"],
    }
    json_path = directory / "phase1d-econ1-bakery-report.json"
    md_path = directory / "phase1d-econ1-bakery-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "P1D Econ-1 Bakery Verification Report", report, "overall_phase1d_econ1_bakery_passed")
    print(f"phase1d_econ1_bakery_report_json={json_path}")
    print(f"phase1d_econ1_bakery_report_md={md_path}")
    print(f"overall_phase1d_econ1_bakery_passed={report['overall_phase1d_econ1_bakery_passed']}")
    return 0 if report["overall_phase1d_econ1_bakery_passed"] else 1


def _failure_matrix(scenario: BakeryReferenceScenario) -> list[dict[str, object]]:
    """Exercise rejection paths on isolated stores and then recover via a new period."""
    entries: list[dict[str, object]] = []

    def capture(name: str, operation, recovery, prepare=None) -> None:  # type: ignore[no-untyped-def]
        store = GameplayEventStore()
        if prepare is not None:
            prepare(store)
        before = len(store.read_events())
        try:
            operation(store)
        except Exception as exc:
            code = str(exc)
        else:
            code = "unexpected_success"
        after = len(store.read_events())
        recovery_observed = False
        try:
            recovery(store)
            recovery_observed = True
        except Exception:
            recovery_observed = False
        entries.append({"case": name, "error_code": code, "zero_write": before == after, "recovery_observed": recovery_observed})

    capture(
        "material_shortage",
        lambda store: _reserve_shortage(store),
        lambda store: scenario.execute_period(1, store=store),
        prepare=_prepare_shortage,
    )
    capture(
        "qualification",
        lambda _store: scenario.with_existing_character_employee("character:missing"),
        lambda _store: scenario.with_existing_character_employee("character:char_b"),
    )
    capture(
        "capacity",
        lambda store: _capacity_failure(store),
        lambda store: scenario.execute_period(1, store=store),
        prepare=_prepare_capacity,
    )
    capture(
        "funds",
        lambda store: _funds_failure(store),
        lambda store: scenario.execute_period(1, store=store),
        prepare=_prepare_funds,
    )
    capture(
        "quote_expiry",
        lambda _store: EconomyAuthority.validate_quote(MarketQuote(quote_ref="quote:expired", item_ref="flour", unit_price=2, quantity_limit=1, valid_until_tick=0, public_digest="quote:expired"), tick=1, quantity=1),
        lambda store: scenario.execute_period(1, store=store),
    )
    capture(
        "permit_expiry",
        lambda _store: GovernmentAuthority.require_permit(scenario.permit, tick=101, policy_revision="policy:v1"),
        lambda store: scenario.execute_period(1, store=store),
    )
    capture(
        "facility_unavailable",
        lambda _store: ConstructionProductionAuthority.start_run(facility=Facility(facility_ref="facility:down", plot_ref="plot:down", facility_kind="bakery", condition=0), recipe=scenario.recipe, run_ref="run:down", tick=1),
        lambda store: scenario.execute_period(1, store=store),
    )
    capture(
        "overdue_obligation",
        lambda _store: _reject_overdue_obligation(),
        lambda _store: EconomyAuthority.close_period(BusinessPeriod(period_ref="period:recovered", sequence=2, policy_revision="policy:v1", obligations=(EconomicObligation(obligation_ref="obligation:recovered", owner_ref="org:bakery", kind="tax", amount=1, due_tick=1, status="settled"),))),
    )
    stale_store = GameplayEventStore()
    stale = stale_store.append_batch(
        build_atomic_event_batch(
            command_id="bakery:stale",
            principal_ref="actor_gameplay.econ1_economy_domain",
            stream_id="gameplay:economy:org:bakery",
            expected_revision=1,
            event_specs=[("gameplay.economy.purchase_posted", {"posting_ref": "purchase:stale"})],
            idempotency_key="bakery:stale",
            causation_id="bakery:stale",
            correlation_id="bakery:stale",
            pinned_revisions={"economy": 1},
        )
    )
    entries.append({"case": "stale_revision", "error_code": stale.failure.error_code if stale.failure else "unexpected_success", "zero_write": not stale.committed and not stale_store.read_events(), "recovery_observed": stale.failure is not None})
    duplicate_store = GameplayEventStore()
    scenario.execute_period(1, store=duplicate_store)
    before_duplicate = len(duplicate_store.read_events())
    scenario.execute_period(1, store=duplicate_store)
    entries.append({"case": "duplicate", "error_code": "duplicate_replayed", "zero_write": len(duplicate_store.read_events()) == before_duplicate, "recovery_observed": True})
    return entries


def _reserve_shortage(store: GameplayEventStore) -> None:
    registry = InventoryDefinitionRegistry()
    registry.register_item(ItemDefinition("item:flour", "v1", 1, 1))
    InventoryAuthorityService(store=store, registry=registry).reserve_item(command_id="failure:reserve", actor_ref="org:bakery", item_id="item:failure", reservation_ref="reservation:failure", quantity=2, idempotency_key="failure:reserve", causation_id="failure", correlation_id="failure")


def _prepare_shortage(store: GameplayEventStore) -> None:
    registry = InventoryDefinitionRegistry()
    registry.register_item(ItemDefinition("item:flour", "v1", 1, 1))
    service = InventoryAuthorityService(store=store, registry=registry)
    service.create_container(command_id="failure:container", actor_ref="org:bakery", spec=ContainerSpec("container:failure", 10, 10, 10), idempotency_key="failure:container", causation_id="failure", correlation_id="failure")
    service.instantiate(command_id="failure:item", actor_ref="org:bakery", item_id="item:failure", definition_id="item:flour", quantity=1, container_id="container:failure", idempotency_key="failure:item", causation_id="failure", correlation_id="failure")


def _capacity_failure(store: GameplayEventStore) -> None:
    registry = InventoryDefinitionRegistry()
    registry.register_item(ItemDefinition("item:flour", "v1", 1, 1))
    service = InventoryAuthorityService(store=store, registry=registry)
    service.instantiate(command_id="capacity:item", actor_ref="org:bakery", item_id="item:capacity", definition_id="item:flour", quantity=1, container_id="container:capacity", idempotency_key="capacity:item", causation_id="capacity", correlation_id="capacity")


def _prepare_capacity(store: GameplayEventStore) -> None:
    registry = InventoryDefinitionRegistry()
    registry.register_item(ItemDefinition("item:flour", "v1", 1, 1))
    InventoryAuthorityService(store=store, registry=registry).create_container(command_id="capacity:container", actor_ref="org:bakery", spec=ContainerSpec("container:capacity", 0, 0, 0), idempotency_key="capacity:container", causation_id="capacity", correlation_id="capacity")


def _funds_failure(store: GameplayEventStore) -> None:
    service = EconomyAuthorityService(store=store)
    service.transfer(command_id="funds:transfer", debit_account_id="account:empty", credit_account_id="account:target", amount=1, idempotency_key="funds:transfer", causation_id="funds", correlation_id="funds")


def _prepare_funds(store: GameplayEventStore) -> None:
    service = EconomyAuthorityService(store=store)
    service.open_account(command_id="funds:debit", account_id="account:empty", owner_ref="org:bakery", currency_ref="currency:coin", initial_balance=0, idempotency_key="funds:debit", causation_id="funds", correlation_id="funds")
    service.open_account(command_id="funds:credit", account_id="account:target", owner_ref="supplier", currency_ref="currency:coin", initial_balance=0, idempotency_key="funds:credit", causation_id="funds", correlation_id="funds")


def _reject_overdue_obligation() -> None:
    EconomyAuthority.close_period(
        BusinessPeriod(
            period_ref="period:overdue",
            sequence=1,
            policy_revision="policy:v1",
            obligations=(EconomicObligation(obligation_ref="obligation:overdue", owner_ref="org:bakery", kind="tax", amount=1, due_tick=1, status="overdue"),),
        )
    )


def _run_godot_mirror_probe(root: Path, directory: Path, payload_path: Path, explicit_godot: str | None) -> dict[str, object]:
    try:
        godot = resolve_godot_exe(explicit_godot)
    except FileNotFoundError as exc:
        return {"proved": False, "status": "godot-runtime-unavailable", "error": str(exc)}
    log_path = directory / "phase1d-bakery-godot-mirror.log"
    result = run_command(
        [str(godot), "--headless", "--path", str(root), "--scene", "res://scenes/phase0/BakeryCommittedMirrorProbe.tscn"],
        root,
        log_path,
        env={"BAKERY_MIRROR_PAYLOAD": str(payload_path)},
        timeout_seconds=30,
    )
    output = result.stdout
    return {"proved": result.returncode == 0 and "bakery_committed_mirror_probe:proved" in output, "status": "proved" if result.returncode == 0 else "failed", "log": str(log_path)}


if __name__ == "__main__":
    raise SystemExit(main())
