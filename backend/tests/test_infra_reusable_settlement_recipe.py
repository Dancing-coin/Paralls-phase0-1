from __future__ import annotations

import pytest

from app.gameplay.models import AppendBatchResult, GameplayFailure, OwnerAuthorizedFragment
from app.gameplay.settlement_plan import AppendDerivedSettlementRecipe
from app.gameplay.shared_contracts import SettlementReceipt


def _fragment(*, fragment_id: str, stream_id: str, owner: str = "authority:one") -> OwnerAuthorizedFragment:
    return OwnerAuthorizedFragment(
        fragment_id=fragment_id,
        owner_principal_ref=owner,
        source_rule_ref=f"rule:{fragment_id}",
        expected_revisions={stream_id: 0},
        event_specs={stream_id: ((f"gameplay.{fragment_id}.settled", {"fragment_id": fragment_id}),)},
        event_visibility_policies={stream_id: ("project",)},
    )


def test_recipe_builds_one_append_batch_for_a_single_owner_without_write_capability() -> None:
    recipe = AppendDerivedSettlementRecipe.from_fragments(
        command_id="command:recipe:single",
        idempotency_principal_ref="world_runtime.caller",
        idempotency_key="recipe:single",
        causation_id="cause:recipe:single",
        correlation_id="corr:recipe:single",
        fragments=(_fragment(fragment_id="one", stream_id="gameplay:one"),),
    )

    assert recipe.batch.expected_stream_revisions == {"gameplay:one": 0}
    assert [item.fragment_id for item in recipe.batch.owner_fragments] == ["one"]
    assert not hasattr(recipe, "append_batch")


def test_recipe_combines_existing_multi_owner_fragments_and_derives_receipt_from_one_result() -> None:
    recipe = AppendDerivedSettlementRecipe.from_fragments(
        command_id="command:recipe:multi",
        idempotency_principal_ref="world_runtime.caller",
        idempotency_key="recipe:multi",
        causation_id="cause:recipe:multi",
        correlation_id="corr:recipe:multi",
        fragments=(
            _fragment(fragment_id="one", stream_id="gameplay:one"),
            _fragment(fragment_id="two", stream_id="gameplay:two", owner="authority:two"),
        ),
    )
    result = AppendBatchResult(
        committed=True,
        transaction_id=recipe.batch.transaction_id,
        command_id=recipe.batch.command_id,
        committed_event_ids=[event.event_id for event in recipe.batch.events],
        resulting_stream_revisions={"gameplay:one": 1, "gameplay:two": 1},
        idempotency_status="new_commit",
    )

    receipt = recipe.receipt_from_append_result(result=result, audit_refs=("audit:recipe",))

    assert recipe.batch.expected_stream_revisions == {"gameplay:one": 0, "gameplay:two": 0}
    assert receipt == SettlementReceipt.from_append_result(result=result, audit_refs=("audit:recipe",))


def test_recipe_rejected_append_result_produces_zero_write_receipt() -> None:
    recipe = AppendDerivedSettlementRecipe.from_fragments(
        command_id="command:recipe:reject",
        idempotency_principal_ref="world_runtime.caller",
        idempotency_key="recipe:reject",
        causation_id="cause:recipe:reject",
        correlation_id="corr:recipe:reject",
        fragments=(_fragment(fragment_id="one", stream_id="gameplay:one"),),
    )
    receipt = recipe.receipt_from_append_result(
        result=AppendBatchResult(
            committed=False,
            transaction_id=recipe.batch.transaction_id,
            command_id=recipe.batch.command_id,
            idempotency_status="rejected",
            failure=GameplayFailure(error_code="revision_conflict", message="revision_conflict", failed_stage="event_store"),
        )
    )

    assert receipt.zero_write is True
    assert receipt.error_code == "revision_conflict"


def test_recipe_rejects_overlapping_owner_streams_before_any_append() -> None:
    with pytest.raises(ValueError, match="settlement_fragment_stream_overlap"):
        AppendDerivedSettlementRecipe.from_fragments(
            command_id="command:recipe:overlap",
            idempotency_principal_ref="world_runtime.caller",
            idempotency_key="recipe:overlap",
            causation_id="cause:recipe:overlap",
            correlation_id="corr:recipe:overlap",
            fragments=(
                _fragment(fragment_id="one", stream_id="gameplay:shared"),
                _fragment(fragment_id="two", stream_id="gameplay:shared", owner="authority:two"),
            ),
        )
