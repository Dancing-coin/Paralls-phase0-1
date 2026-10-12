from __future__ import annotations

import pytest

from app.gameplay.econ1_economy_runtime import OperatingWindow
from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.gameplay.organization_government_runtime import OrganizationAuthority, OperatingWindowDueRequest


@pytest.mark.parametrize("durable", [False, True])
def test_owner_schedule_and_window_results_remain_detached_from_inputs_and_reads(tmp_path, durable) -> None:
    store = DurableGameplayEventStore(tmp_path / "events.sqlite3") if durable else GameplayEventStore()
    owner = OrganizationAuthority(store=store)
    try:
        scheduled = owner.record_schedule(command_id="schedule:isolation", organization_ref="org:isolation",
            recipient_ref="character:char_a", membership_ref="membership:isolation", assignment_ref="assignment:isolation",
            role="worker", shift_ref="shift:isolation", operating_window_ref="window:isolation", work_order_ref="work:isolation",
            effective_from="1970-01-01T00:00:00Z", effective_to=None, visibility_scope="organization:summary")
        authored_window = OperatingWindow(window_ref="window:isolation", organization_ref="org:isolation", opens_at_tick=0,
            closes_at_tick=1, policy_revision="policy:isolation", source_revision=scheduled.committed_event_ids[-1])
        opened = owner.open_operating_window(command_id="open:isolation", idempotency_key="open:isolation",
            causation_id="isolation", correlation_id="isolation", window=authored_window, visibility_scope="project")
        closed = owner.close_operating_window(command_id="close:isolation", idempotency_key="close:isolation",
            causation_id="isolation", correlation_id="isolation", organization_ref="org:isolation",
            window_ref="window:isolation", expected_stream_revision=1, visibility_scope="project")
        request = OperatingWindowDueRequest(command_id="due:isolation", idempotency_key="due:isolation",
            causation_id="isolation", correlation_id="isolation", organization_ref="org:isolation",
            window_ref="window:isolation", expected_stream_revision=2, visibility_scope="project")
        batch_result = owner.record_operating_windows_due_batch((request,))
        due = batch_result.results[request.command_id]
        assert all(result.committed for result in (scheduled, opened, closed, due))
        assert batch_result.append_count == 1
        assert store.get_stream_head("gameplay:organization:window:window:isolation") == 3
        assert len(store.read_events()) == 7

        events = [item.model_dump(mode="json") for item in store.read_events()]
        transactions = [item.model_dump(mode="json") for item in store.read_transactions()]
        outbox = [item.model_dump(mode="json") for item in store.list_outbox()]
        authored_window.__dict__["closes_at_tick"] = 99
        request.__dict__["organization_ref"] = "org:tampered"
        for result in (scheduled, opened, closed, due):
            result.committed_event_ids.clear()
            result.resulting_stream_revisions.clear()
        for event in store.read_events():
            event.payload["organization_ref"] = "org:tampered"
        for transaction in store.read_transactions():
            transaction.events[0].payload["organization_ref"] = "org:tampered"
            transaction.outbox_entries[0].payload_projection["organization_ref"] = "org:tampered"
        for entry in store.list_outbox():
            entry.payload_projection["organization_ref"] = "org:tampered"

        assert [item.model_dump(mode="json") for item in store.read_events()] == events
        assert [item.model_dump(mode="json") for item in store.read_transactions()] == transactions
        assert [item.model_dump(mode="json") for item in store.list_outbox()] == outbox
        assert len(store.get_by_idempotency(owner._PRINCIPAL, "idempotency:schedule:isolation").committed_event_ids) == 4
        assert store.get_by_idempotency(owner._PRINCIPAL, "open:isolation").resulting_stream_revisions == {
            "gameplay:organization:window:window:isolation": 1,
        }
    finally:
        if durable:
            store.close()
