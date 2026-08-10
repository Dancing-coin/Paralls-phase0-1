from __future__ import annotations

from app.gameplay.phase4_commerce import CommercialEcosystemScenario


def test_p4d_commercial_ecosystem_uses_existing_owner_refs_and_is_replayable() -> None:
    result = CommercialEcosystemScenario().run()

    assert result.competition.committed
    assert result.customer_demand.committed
    assert result.procurement.committed
    assert result.delivery.committed
    assert result.permit.committed
    assert result.inspection.committed
    assert result.tax.committed
    assert result.credit.committed
    assert result.default.committed
    assert result.structured_reject.zero_write
    assert result.replay_hash.startswith("sha256:")
    assert result.replay_hash == result.checkpoint_tail_hash
    assert result.replay_hash != result.event_log_digest
    assert result.public_view["redaction"] == "account-and-custody-refs-excluded"
    assert result.public_view["competition"] == {
        "winner_order_ref": "order:bakery-a:flour",
        "bakery_b_owner_valid": True,
        "bakery_b_rejection": "quantity_exhausted",
    }
    assert result.no_new_owner_audit == {
        "market_runtime": False,
        "global_scheduler": False,
        "autonomous_organization_writer": False,
        "second_settlement_path": False,
        "unknown_canonical_stream": False,
        "unknown_writer_principal": False,
        "owner_fragment_provenance_missing": False,
    }
