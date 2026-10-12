from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.character_agent.models.simulation_seed import CharacterContinuityCommand
from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.gameplay.event_schema_registry import EventSchemaRegistry, EventSchemaRegistration
from app.gameplay.event_store import DurableGameplayEventStore
from app.gameplay.organization_government_runtime import OrganizationAuthority
from app.gameplay.settlement_plan import build_multi_stream_atomic_event_batch_from_fragments
from app.population_continuity.activation_policy import resolve_participation
from app.population_continuity.member_ledger import (
    MEMBER_LEDGER_OWNER, MemberEntry, PopulationMemberLedger, build_member_entry,
    partition_members, pending_member_results, register_population_member_ledger_schemas,
)
from app.population_continuity.models import WorldModeProfile
from app.population_continuity.roster import PopulationRoster
from app.population_continuity.simulation_contracts import ModuleFieldPolicy, ParticipationPolicy
from app.population_continuity.world import WorldContinuityRuntime
from test_character_simulation_frame import frame, module_definition


ACTORS = ("character:char_a", "character:char_b", "character:char_c")


def ledger_input():
    definition = module_definition().model_copy(update={"field_policies": {
        "fatigue": ModuleFieldPolicy(aggregatable=True, individual_only=False),
        "tags": ModuleFieldPolicy(),
    }})
    participation = resolve_participation(policies=(ParticipationPolicy(
        policy_ref="policy:prototype", revision="1", allowed_tiers=("B0", "B1", "B3"),
        allowed_modules=("needs",), b0_expiry_tick=100, review_tick=100,
    ),), tick=10)
    entries = []
    for index, actor in enumerate(ACTORS):
        actor_definition = definition if index < 2 else module_definition()
        actor_frame = frame(actor_ref=actor, profile_ref=actor, character_revision=0,
            participation=participation, codebook_refs=(("code:care-obligation",) if index == 1 else ()),
            module_definitions=(actor_definition,))
        entries.append(build_member_entry(frame=actor_frame, module_definitions=(actor_definition,)))
    ledger = PopulationMemberLedger(cohort_ref="cohort:test", member_source_ref="roster:test",
        member_source_revision="1", situation_revision="situation:1", ruleset_revision="rules:1",
        partition_revision="partition:1", seed="seed:1", member_entries=tuple(entries))
    return ledger, definition


class LedgerCase:
    def __init__(self, root):
        self.root = root
        self.schemas = EventSchemaRegistry()
        register_population_member_ledger_schemas(self.schemas)
        for name in ("membership_recorded", "role_term_recorded", "shift_offer_recorded", "work_order_recorded"):
            self.schemas.register(EventSchemaRegistration(f"gameplay.organization.{name}", 1, f"schema:{name}:1"))
        self.schemas.register(EventSchemaRegistration("gameplay.organization.commerce_commitment_accepted", 1, "commerce:1"))
        self.store = DurableGameplayEventStore(root / "world.sqlite3", event_schema_registry=self.schemas)
        self.core = CharacterAgentRuntime(storage_root=root / "character")
        self.mode = WorldModeProfile(world_ref="world:ledger", mode="simulation", revision="1",
            cadence_class="population", batch_limit=3, wake_budget=1, catch_up_limit=1, degraded_threshold=3)
        self.roster = PopulationRoster(actor_ids=("char_a", "char_b", "char_c"))
        self.world = WorldContinuityRuntime(store=self.store, mode=self.mode, roster=self.roster)
        ledger, _ = ledger_input()
        self.initial = partition_members(ledger, seed="seed:1", partition_revision="partition:1")
        result = self.world.register_member_ledger(self.initial, continuity_runtime=self.core, idempotency_key="register")
        assert result.committed

    def author_actor_result(self, actor, label):
        result = OrganizationAuthority(store=self.store).record_schedule(command_id=label,
            organization_ref="org:test", recipient_ref=actor, membership_ref=f"membership:{label}",
            assignment_ref=f"assignment:{label}", role="worker", shift_ref=f"shift:{label}",
            operating_window_ref="window:1", work_order_ref=f"work:{label}",
            effective_from="1970-01-01T00:00:00Z", effective_to=None, visibility_scope=f"actor:{actor}")
        assert result.committed
        return result.committed_event_ids[0]

    def commit_actor_result(self, actor, label):
        ref = self.author_actor_result(actor, label)
        recorded = self.world.confirm_member_result(cohort_ref="cohort:test", actor_ref=actor, result_ref=ref,
            expected_revision=self.revision(), idempotency_key=f"confirm:{label}")
        assert recorded.committed
        return ref

    def command(self, actor, ref, *, key=None):
        event = self.store.get_event(ref)
        transaction = self.store.get_transaction(event.transaction_id)
        actual = self.store.get_by_idempotency(transaction.idempotency_record.principal_ref,
                                               transaction.idempotency_record.idempotency_key)
        return CharacterContinuityCommand(command_id=key or f"apply:{ref}", actor_ref=actor,
            expected_character_revision=self.core.get_continuity_revision(actor.removeprefix("character:")),
            from_tick=10, to_tick=11, simulation_tick_cursor=11, source_owner_receipt_refs=(ref,),
            source_revision_vector=dict(actual.resulting_stream_revisions),
            state_delta={"presentation_seed": {"task": "已确认班表"}},
            policy_revision="policy:character-continuity:v1", idempotency_key=key or f"apply:{ref}")

    def consume_for(self, actor, ref, *, apply=True):
        command = self.command(actor, ref)
        if apply:
            assert self.core.apply_character_continuity_command(command).status in {"committed", "idempotent_replay"}
        return self.world.consume_member_result(cohort_ref="cohort:test", actor_ref=actor, result_ref=ref,
            continuity_runtime=self.core, continuity_idempotency_key=command.idempotency_key,
            expected_revision=self.revision(), idempotency_key=f"consume:{ref}")

    def revision(self):
        return self.store.get_stream_head(self.world.member_ledger_stream("cohort:test"))

    def read(self, **kwargs):
        return self.world.read_member_ledger("cohort:test", **kwargs)

    def restart(self):
        self.core.close()
        self.store.close()
        self.store = DurableGameplayEventStore(self.root / "world.sqlite3", event_schema_registry=self.schemas)
        self.core = CharacterAgentRuntime(storage_root=self.root / "character")
        self.world = WorldContinuityRuntime(store=self.store, mode=self.mode, roster=self.roster)

    def close(self):
        self.core.close()
        self.store.close()


@pytest.fixture
def ledger_case(tmp_path):
    case = LedgerCase(tmp_path)
    try:
        yield case
    finally:
        case.close()


def test_cohort_key_boundaries_do_not_replay_another_cohort_receipt(ledger_case):
    other = ledger_case.initial.model_copy(update={"cohort_ref": "cohort:test:confirm"})
    assert ledger_case.world.register_member_ledger(other, continuity_runtime=ledger_case.core,
        idempotency_key="register:other").committed
    source = ledger_case.author_actor_result(ACTORS[0], "key-boundary")
    requests = [("cohort:test", "confirm:event"), (other.cohort_ref, "event")]
    receipts = []
    for cohort, key in requests:
        receipt = ledger_case.world.confirm_member_result(cohort_ref=cohort, actor_ref=ACTORS[0],
            result_ref=source, expected_revision=1, idempotency_key=key)
        assert receipt.committed and receipt.idempotency_status != "duplicate_replayed"
        receipts.append(receipt)
    assert receipts[0].committed_event_ids != receipts[1].committed_event_ids
    ledger_case.restart()
    before = ledger_case.store.get_last_global_sequence()
    for (cohort, key), original in zip(requests, receipts, strict=True):
        assert pending_member_results(ledger_case.world.read_member_ledger(cohort), actor_ref=ACTORS[0]) == (source,)
        replay = ledger_case.world.confirm_member_result(cohort_ref=cohort, actor_ref=ACTORS[0],
            result_ref=source, expected_revision=1, idempotency_key=key)
        assert replay.idempotency_status == "duplicate_replayed"
        assert replay.committed_event_ids == original.committed_event_ids
    assert ledger_case.store.get_last_global_sequence() == before


def test_cohort_root_cannot_occupy_another_cohort_member_stream(ledger_case):
    other = ledger_case.initial.model_copy(update={"cohort_ref": "cohort:test:member:character:char_a"})
    assert ledger_case.world.register_member_ledger(other, continuity_runtime=ledger_case.core,
        idempotency_key="register:other").committed
    assert ledger_case.read() == ledger_case.initial
    source = ledger_case.commit_actor_result(ACTORS[0], "stream-boundary")
    ledger_case.restart()
    assert pending_member_results(ledger_case.read(), actor_ref=ACTORS[0]) == (source,)
    assert ledger_case.world.read_member_ledger(other.cohort_ref) == other


def test_world_cohort_partition_is_an_independent_persistent_identity(ledger_case):
    other = ledger_case.initial.model_copy(update={"cohort_ref": "test"})
    world = WorldContinuityRuntime(store=ledger_case.store, roster=ledger_case.roster,
        mode=ledger_case.mode.model_copy(update={"world_ref": "world:ledger:cohort"}))
    assert world.register_member_ledger(other, continuity_runtime=ledger_case.core,
        idempotency_key="register").committed
    assert world.read_member_ledger("test") == other
    assert ledger_case.read() == ledger_case.initial
    assert world.member_ledger_stream("test") != ledger_case.world.member_ledger_stream("cohort:test")


@pytest.mark.parametrize("operation", ["confirm", "consume"])
@pytest.mark.parametrize("restriction", ["authorization", "roster"])
def test_member_new_writes_recheck_current_actor_scope(ledger_case, operation, restriction):
    source = ledger_case.author_actor_result(ACTORS[0], "scope-check")
    if operation == "consume":
        assert ledger_case.world.confirm_member_result(cohort_ref="cohort:test", actor_ref=ACTORS[0],
            result_ref=source, expected_revision=1, idempotency_key="confirm:scope").committed
        command = ledger_case.command(ACTORS[0], source)
        assert ledger_case.core.apply_character_continuity_command(command).status == "committed"
    restricted = WorldContinuityRuntime(store=ledger_case.store, mode=ledger_case.mode,
        roster=(PopulationRoster(actor_ids=("char_b",)) if restriction == "roster" else ledger_case.roster),
        authorized_actor_refs=(frozenset({ACTORS[1]}) if restriction == "authorization" else None))
    heads = ledger_case.store.get_stream_heads()
    timeline = ledger_case.core.get_session_timeline("char_a")
    with pytest.raises(ValueError, match="member_actor_scope_denied"):
        if operation == "confirm":
            restricted.confirm_member_result(cohort_ref="cohort:test", actor_ref=ACTORS[0], result_ref=source,
                expected_revision=1, idempotency_key="new:scope")
        else:
            restricted.consume_member_result(cohort_ref="cohort:test", actor_ref=ACTORS[0], result_ref=source,
                continuity_runtime=ledger_case.core, continuity_idempotency_key=command.idempotency_key,
                expected_revision=1, idempotency_key="new:scope")
    assert ledger_case.store.get_stream_heads() == heads
    assert ledger_case.core.get_session_timeline("char_a") == timeline


def test_historical_member_replay_does_not_create_a_new_write_after_scope_revocation(ledger_case):
    source = ledger_case.commit_actor_result(ACTORS[0], "historical-scope")
    restricted = WorldContinuityRuntime(store=ledger_case.store, mode=ledger_case.mode,
        roster=ledger_case.roster, authorized_actor_refs=frozenset({ACTORS[1]}))
    heads = ledger_case.store.get_stream_heads()
    replay = restricted.confirm_member_result(cohort_ref="cohort:test", actor_ref=ACTORS[0], result_ref=source,
        expected_revision=1, idempotency_key="confirm:historical-scope")
    assert replay.committed and replay.idempotency_status == "duplicate_replayed"
    with pytest.raises(ValueError, match="member_actor_scope_denied"):
        restricted.confirm_member_result(cohort_ref="cohort:test", actor_ref=ACTORS[0], result_ref=source,
            expected_revision=1, idempotency_key="new:historical-scope")
    assert ledger_case.store.get_stream_heads() == heads


def test_member_replay_rejects_a_misbound_cross_cohort_record(ledger_case, monkeypatch):
    source = ledger_case.commit_actor_result(ACTORS[0], "misbound-record")
    original = ledger_case.store.get_by_idempotency
    receipt = original(MEMBER_LEDGER_OWNER, ledger_case.world._member_operation_key(
        "cohort:test", "confirm:misbound-record"))
    assert receipt is not None
    monkeypatch.setattr(ledger_case.store, "get_by_idempotency", lambda principal, key: receipt)
    heads = ledger_case.store.get_stream_heads()
    with pytest.raises(ValueError, match="member_idempotency_conflict"):
        ledger_case.world.confirm_member_result(cohort_ref="cohort:other", actor_ref=ACTORS[0], result_ref=source,
            expected_revision=1, idempotency_key="confirm:misbound-record")
    assert ledger_case.store.get_stream_heads() == heads


def test_partition_is_order_independent_and_keeps_protected_references():
    ledger, _ = ledger_input()
    reordered = ledger.model_copy(update={"member_entries": tuple(reversed(ledger.member_entries))})
    first = partition_members(ledger, seed="seed:1", partition_revision="partition:1")
    second = partition_members(reordered, seed="seed:1", partition_revision="partition:1")
    assert first == second
    a, b, c = first.member_entries
    assert a.shard_ref == b.shard_ref and c.shard_ref != a.shard_ref
    assert a.aggregatable_field_refs == b.aggregatable_field_refs == ("needs.fatigue",)
    assert c.aggregatable_field_refs == ()
    assert b.protected_code_refs == ("code:care-obligation",)
    assert all("needs.tags" not in entry.aggregatable_field_refs for entry in first.member_entries)
    assert first.distribution_policy == "none" and first.group_cursor == 0


def test_ledger_metadata_is_nested_immutable_and_has_no_private_body():
    ledger, _ = ledger_input()
    with pytest.raises(TypeError):
        ledger.member_entries[0].participation_policy_pins["policy:prototype"] = "forged"
    dumped = json.loads(ledger.model_dump_json())
    dumped["member_entries"][0]["participation_policy_pins"]["policy:prototype"] = "forged"
    assert ledger.member_entries[0].participation_policy_pins["policy:prototype"] == "1"
    assert PopulationMemberLedger.model_validate_json(ledger.model_dump_json()) == ledger
    with pytest.raises(ValidationError):
        MemberEntry(**{**ledger.member_entries[0].model_dump(), "private_memory": {"secret": "hidden"}})


@pytest.mark.parametrize("update", [{"distribution_policy": "mean"}, {"group_cursor": 1},
    {"member_entries": ()}, {"seed": ""}])
def test_unadmitted_distribution_and_invalid_anchors_are_rejected(update):
    ledger, _ = ledger_input()
    with pytest.raises(ValidationError):
        PopulationMemberLedger.model_validate({**ledger.model_dump(), **update})


def test_confirmed_source_cannot_be_assigned_to_another_actor(ledger_case):
    ref = ledger_case.commit_actor_result(ACTORS[0], "result:a")
    before = ledger_case.store.get_last_global_sequence()
    with pytest.raises(ValueError, match="member_result_actor_mismatch"):
        ledger_case.world.confirm_member_result(cohort_ref="cohort:test", actor_ref=ACTORS[1], result_ref=ref,
            expected_revision=ledger_case.revision(), idempotency_key="forged")
    assert ledger_case.store.get_last_global_sequence() == before
    assert pending_member_results(ledger_case.read(), actor_ref=ACTORS[1]) == ()


def test_unknown_report_does_not_change_members_or_business_cursors(ledger_case):
    before = ledger_case.read()
    heads = ledger_case.store.get_stream_heads()
    core = [ledger_case.core.get_continuity_revision(actor.removeprefix("character:")) for actor in ACTORS]
    with pytest.raises(ValueError, match="member_result_unavailable"):
        ledger_case.world.confirm_member_result(cohort_ref="cohort:test", actor_ref=ACTORS[0],
            result_ref="model:daily-supply:report", expected_revision=ledger_case.revision(), idempotency_key="report")
    assert ledger_case.read() == before and ledger_case.store.get_stream_heads() == heads
    assert [ledger_case.core.get_continuity_revision(actor.removeprefix("character:")) for actor in ACTORS] == core


def test_core_receipt_is_required_before_consuming_and_cannot_be_self_signed(ledger_case):
    ref = ledger_case.commit_actor_result(ACTORS[0], "result:a")
    before = ledger_case.store.get_last_global_sequence()
    with pytest.raises(ValueError, match="member_core_receipt_unavailable"):
        ledger_case.consume_for(ACTORS[0], ref, apply=False)
    assert pending_member_results(ledger_case.read(), actor_ref=ACTORS[0]) == (ref,)
    assert ledger_case.store.get_last_global_sequence() == before
    with pytest.raises(TypeError):
        ledger_case.world.consume_member_result(receipt={"status": "committed"})


def test_wrong_core_source_and_stale_ledger_are_zero_write(ledger_case):
    first = ledger_case.commit_actor_result(ACTORS[0], "result:a")
    second = ledger_case.commit_actor_result(ACTORS[1], "result:b")
    command = ledger_case.command(ACTORS[0], second, key="wrong-source")
    assert ledger_case.core.apply_character_continuity_command(command).status == "committed"
    before = ledger_case.store.get_last_global_sequence()
    with pytest.raises(ValueError, match="member_core_source_mismatch"):
        ledger_case.world.consume_member_result(cohort_ref="cohort:test", actor_ref=ACTORS[0], result_ref=first,
            continuity_runtime=ledger_case.core, continuity_idempotency_key=command.idempotency_key,
            expected_revision=ledger_case.revision(), idempotency_key="wrong")
    result = ledger_case.world.confirm_member_result(cohort_ref="cohort:test", actor_ref=ACTORS[1], result_ref=second,
        expected_revision=0, idempotency_key="stale")
    assert not result.committed and result.failure.error_code == "revision_conflict"
    assert ledger_case.store.get_last_global_sequence() == before


def test_registration_cannot_inject_confirmations_or_duplicate_actors(ledger_case):
    before = ledger_case.store.get_last_global_sequence()
    initial = ledger_case.initial
    with pytest.raises(ValidationError):
        PopulationMemberLedger.model_validate({**initial.model_dump(),
            "member_entries": initial.member_entries + (initial.member_entries[0],)})
    with pytest.raises(ValueError, match="member_ledger_already_registered"):
        ledger_case.world.register_member_ledger(initial, continuity_runtime=ledger_case.core, idempotency_key="register-again")
    assert ledger_case.store.get_last_global_sequence() == before


def test_registration_requires_current_core_anchor_and_a_permitted_b0_frame(ledger_case):
    with pytest.raises(ValueError, match="member_b0_participation_denied"):
        build_member_entry(frame=frame(), module_definitions=(module_definition(),))
    initial = ledger_case.initial
    changed = initial.member_entries[0].model_copy(update={"entry_character_revision": 99})
    forged = initial.model_copy(update={"cohort_ref": "cohort:forged",
        "member_entries": (changed, *initial.member_entries[1:])})
    before = ledger_case.store.get_last_global_sequence()
    with pytest.raises(ValueError, match="member_character_anchor_stale"):
        ledger_case.world.register_member_ledger(forged, continuity_runtime=ledger_case.core, idempotency_key="forged-anchor")
    assert ledger_case.store.get_last_global_sequence() == before


def test_consumption_requires_actor_result_order(ledger_case):
    first = ledger_case.commit_actor_result(ACTORS[0], "result:first")
    second = ledger_case.commit_actor_result(ACTORS[0], "result:second")
    command = ledger_case.command(ACTORS[0], second)
    assert ledger_case.core.apply_character_continuity_command(command).status == "committed"
    before = ledger_case.store.get_last_global_sequence()
    with pytest.raises(ValueError, match="member_consumption_out_of_order"):
        ledger_case.consume_for(ACTORS[0], second, apply=False)
    assert pending_member_results(ledger_case.read(), actor_ref=ACTORS[0]) == (first, second)
    assert ledger_case.store.get_last_global_sequence() == before


@pytest.mark.parametrize("expected", [True, -1])
def test_member_boundary_rejects_invalid_expected_revision_without_writes(ledger_case, expected):
    ref = ledger_case.author_actor_result(ACTORS[0], "result:strict")
    before = ledger_case.store.get_last_global_sequence()
    with pytest.raises(ValueError, match="member_revision_invalid"):
        ledger_case.world.confirm_member_result(cohort_ref="cohort:test", actor_ref=ACTORS[0], result_ref=ref,
            expected_revision=expected, idempotency_key="bad-revision")
    assert ledger_case.store.get_last_global_sequence() == before


def test_consumption_revalidates_real_owner_result_revision(ledger_case):
    ref = ledger_case.commit_actor_result(ACTORS[0], "result:pinned")
    command = ledger_case.command(ACTORS[0], ref, key="wrong-revision")
    command = command.model_copy(update={"source_revision_vector": {ledger_case.store.get_event(ref).stream_id: 999}})
    assert ledger_case.core.apply_character_continuity_command(command).status == "committed"
    before = ledger_case.store.get_last_global_sequence()
    with pytest.raises(ValueError, match="member_core_source_revision_mismatch"):
        ledger_case.world.consume_member_result(cohort_ref="cohort:test", actor_ref=ACTORS[0], result_ref=ref,
            continuity_runtime=ledger_case.core, continuity_idempotency_key=command.idempotency_key,
            expected_revision=ledger_case.revision(), idempotency_key="wrong-revision")
    assert ledger_case.store.get_last_global_sequence() == before


def test_single_member_confirmation_writes_only_that_member(ledger_case):
    ref = ledger_case.commit_actor_result(ACTORS[0], "result:bounded")
    events = ledger_case.store.read_events(event_type="population.world.member_ledger_recorded@1")
    recorded = events[-1]
    assert recorded.visibility_policy == "authority_only"
    assert recorded.payload["kind"] == "member" and "ledger" not in recorded.payload
    assert recorded.payload["member"]["actor_ref"] == ACTORS[0]
    assert [item["result_ref"] for item in recorded.payload["confirmed_results"]] == [ref]
    assert ACTORS[1] not in json.dumps(recorded.payload) and ACTORS[2] not in json.dumps(recorded.payload)


def test_organization_commitment_without_actor_cannot_be_distributed(ledger_case):
    authority = OrganizationAuthority(store=ledger_case.store)
    fragment = authority.build_commerce_commitment_fragment(organization_ref="org:test",
        commitment_ref="commitment:pool", counterparty_organization_ref="org:other",
        organization_grant_refs=(), budget_reservation_refs=(), policy_revision="1", expected_revision=0)
    batch = build_multi_stream_atomic_event_batch_from_fragments(command_id="owner:pool",
        idempotency_principal_ref=OrganizationAuthority._PRINCIPAL, idempotency_key="owner:pool",
        causation_id="cause:pool", correlation_id="correlation:pool", fragments=(fragment,))
    actual = ledger_case.store.append_batch(batch)
    assert actual.committed
    before = ledger_case.store.get_last_global_sequence()
    with pytest.raises(ValueError, match="member_result_attribution_unknown"):
        ledger_case.world.confirm_member_result(cohort_ref="cohort:test", actor_ref=ACTORS[0],
            result_ref=actual.committed_event_ids[0], expected_revision=ledger_case.revision(), idempotency_key="pool")
    assert ledger_case.store.get_last_global_sequence() == before
    assert ledger_case.read().group_cursor == 0 and not ledger_case.read().confirmed_results


def test_same_actor_cas_rejects_stale_snapshot_without_losing_competing_result(ledger_case, monkeypatch):
    first = ledger_case.author_actor_result(ACTORS[0], "result:race-first")
    second = ledger_case.author_actor_result(ACTORS[0], "result:race-second")
    original = ledger_case.store.append_batch
    raced = False

    def append(batch):
        nonlocal raced
        if not raced and any(event.event_type == "population.world.member_ledger_recorded@1" for event in batch.events):
            raced = True
            competitor = ledger_case.world.confirm_member_result(cohort_ref="cohort:test", actor_ref=ACTORS[0],
                result_ref=second, expected_revision=ledger_case.revision(), idempotency_key="competitor")
            assert competitor.committed
        return original(batch)

    with monkeypatch.context() as patch:
        patch.setattr(ledger_case.store, "append_batch", append)
        stale = ledger_case.world.confirm_member_result(cohort_ref="cohort:test", actor_ref=ACTORS[0],
            result_ref=first, expected_revision=ledger_case.revision(), idempotency_key="race-first")
    assert not stale.committed and stale.failure.error_code == "revision_conflict"
    assert pending_member_results(ledger_case.read(), actor_ref=ACTORS[0]) == (second,)
    retry = ledger_case.world.confirm_member_result(cohort_ref="cohort:test", actor_ref=ACTORS[0],
        result_ref=first, expected_revision=ledger_case.revision(), idempotency_key="race-first")
    assert retry.committed
    assert pending_member_results(ledger_case.read(), actor_ref=ACTORS[0]) == (first, second)


def test_other_actor_confirmation_does_not_overwrite_or_conflict(ledger_case, monkeypatch):
    first = ledger_case.author_actor_result(ACTORS[0], "result:a")
    second = ledger_case.author_actor_result(ACTORS[1], "result:b")
    original = ledger_case.store.append_batch
    raced = False

    def append(batch):
        nonlocal raced
        if not raced and any(event.event_type == "population.world.member_ledger_recorded@1" for event in batch.events):
            raced = True
            assert ledger_case.world.confirm_member_result(cohort_ref="cohort:test", actor_ref=ACTORS[1],
                result_ref=second, expected_revision=ledger_case.revision(), idempotency_key="other").committed
        return original(batch)

    with monkeypatch.context() as patch:
        patch.setattr(ledger_case.store, "append_batch", append)
        assert ledger_case.world.confirm_member_result(cohort_ref="cohort:test", actor_ref=ACTORS[0],
            result_ref=first, expected_revision=ledger_case.revision(), idempotency_key="first").committed
    assert pending_member_results(ledger_case.read(), actor_ref=ACTORS[0]) == (first,)
    assert pending_member_results(ledger_case.read(), actor_ref=ACTORS[1]) == (second,)


def test_core_receipt_reader_is_isolated_and_detects_corrupt_index(ledger_case, monkeypatch):
    ref = ledger_case.commit_actor_result(ACTORS[0], "result:core-index")
    command = ledger_case.command(ACTORS[0], ref)
    actual = ledger_case.core.apply_character_continuity_command(command)
    read = ledger_case.core.get_character_continuity_receipt("char_a", idempotency_key=command.idempotency_key)
    read.source_revision_vector["forged"] = 999
    assert ledger_case.core.get_character_continuity_receipt("char_a", idempotency_key=command.idempotency_key) == actual
    forged = actual.model_dump(mode="json")
    forged["source_revision_vector"]["forged"] = 999
    with monkeypatch.context() as patch:
        patch.setattr(ledger_case.core._session_store, "read_receipt", lambda *args, **kwargs: forged)
        with pytest.raises(ValueError, match="character_continuity_receipt_invalid"):
            ledger_case.core.get_character_continuity_receipt("char_a", idempotency_key=command.idempotency_key)


def test_result_older_than_consumption_cursor_cannot_reenter_pending(ledger_case):
    old = ledger_case.author_actor_result(ACTORS[0], "result:old")
    new = ledger_case.commit_actor_result(ACTORS[0], "result:new")
    assert ledger_case.consume_for(ACTORS[0], new).committed
    before = ledger_case.store.get_last_global_sequence()
    with pytest.raises(ValueError, match="member_result_before_consumed_cursor"):
        ledger_case.world.confirm_member_result(cohort_ref="cohort:test", actor_ref=ACTORS[0], result_ref=old,
            expected_revision=ledger_case.revision(), idempotency_key="late-old")
    assert ledger_case.store.get_last_global_sequence() == before


def test_joint_core_receipt_consumes_two_real_results_once(ledger_case):
    first = ledger_case.commit_actor_result(ACTORS[0], "result:joint-first")
    second = ledger_case.commit_actor_result(ACTORS[0], "result:joint-second")
    command = ledger_case.command(ACTORS[0], second, key="apply:joint")
    command = command.model_copy(update={"source_owner_receipt_refs": (first, second)})
    assert ledger_case.core.apply_character_continuity_command(command).status == "committed"
    for ref in (first, second):
        result = ledger_case.world.consume_member_result(cohort_ref="cohort:test", actor_ref=ACTORS[0], result_ref=ref,
            continuity_runtime=ledger_case.core, continuity_idempotency_key="apply:joint",
            expected_revision=ledger_case.revision(), idempotency_key=f"joint-consume:{ref}")
        assert result.committed
    assert not pending_member_results(ledger_case.read(), actor_ref=ACTORS[0])
    assert ledger_case.core.get_continuity_revision("char_a") == 1


def test_core_receipt_reader_detects_boolean_index_corruption(ledger_case, monkeypatch):
    ref = ledger_case.commit_actor_result(ACTORS[0], "result:boolean-index")
    command = ledger_case.command(ACTORS[0], ref)
    actual = ledger_case.core.apply_character_continuity_command(command)
    forged = actual.model_dump(mode="json")
    forged["character_revision_after"] = True
    with monkeypatch.context() as patch:
        patch.setattr(ledger_case.core._session_store, "read_receipt", lambda *args, **kwargs: forged)
        with pytest.raises(ValueError, match="character_continuity_receipt_invalid"):
            ledger_case.core.get_character_continuity_receipt("char_a", idempotency_key=command.idempotency_key)
