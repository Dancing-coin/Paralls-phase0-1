from app.population_continuity.vertical import ThreeActorCohortContinuityFixture


def test_two_window_three_actor_cohort_closes_under_siming_governance() -> None:
    result = ThreeActorCohortContinuityFixture.create().run()
    assert result["w0"]["status"] == "accepted"
    assert result["w1"]["status"] == "accepted"
    assert result["w0"]["selected"] == [
        "character:char_a",
        "character:char_b",
        "character:char_c",
    ]
    assert result["w1"]["selected"] == result["w0"]["selected"]
    assert result["w0"]["cohort_ref"] == result["w0"]["published_cohort_ref"] == "cohort:bakery:W0"
    assert result["w1"]["cohort_ref"] == result["w1"]["published_cohort_ref"] == "cohort:bakery:W1"
    assert result["w0"]["report_scope"] == result["w1"]["report_scope"] == "organization:summary"
    assert result["owner"]["actor_ref"] == "character:char_a"
    assert result["owner"]["event_family"] == (
        "gameplay.organization.commerce_commitment_accepted"
    )
    assert result["character"]["seeded_actors"] == [
        "character:char_a",
        "character:char_b",
    ]
    assert result["character"]["activation_only_actors"] == ["character:char_c"]
    assert result["replay"]["full_equals_checkpoint_tail"] is True
    assert result["rejections"]["private_zero_write"] is True
    assert result["rejections"]["branch_zero_write"] is True
    assert result["rejections"]["duplicate_mismatch_zero_write"] is True
    assert result["rejections"]["budget_unprocessed_zero_write"] is True


def test_duplicate_w0_replays_owner_and_character_without_progression() -> None:
    fixture = ThreeActorCohortContinuityFixture.create()
    fixture.run_window("W0")
    duplicate = fixture.run_window("W0")
    assert duplicate.owner_receipts[0].idempotency_status == "duplicate_replayed"
    assert duplicate.continuity_receipts[0].status == "idempotent_replay"
    assert fixture.character_runtime.get_continuity_revision("char_a") == 1
    assert fixture.character_runtime.get_continuity_revision("char_b") == 1


def test_char_c_player_input_activates_existing_record_after_cohort_candidate() -> None:
    result = ThreeActorCohortContinuityFixture.create().run()
    assert result["activation"]["status"] == "active"
    assert result["activation"]["existing_record_ref"] == "character:char_c"
    assert result["activation"]["existing_record_ref_before"] == result["activation"]["existing_record_ref_after"]
    assert result["activation"]["new_identity_created"] is False
    assert result["activation"]["same_character_identity"] is True
    assert result["activation"]["actual_player_input_path"] is True


def test_changed_activation_record_ref_cannot_satisfy_same_record_evidence() -> None:
    fixture = ThreeActorCohortContinuityFixture.create()
    original = fixture._run_player_dialogue

    def tampered(target_actor_id: str) -> dict[str, object]:
        result = original(target_actor_id)
        result["receipt"] = {
            **result["receipt"],
            "profile_ref": "character:tampered",
        }
        return result

    fixture._run_player_dialogue = tampered
    result = fixture.run()
    assert result["activation"]["existing_record_ref_before"] != result["activation"]["existing_record_ref_after"]
    assert result["activation"]["new_identity_created"] is True


def test_zero_write_matrix_covers_budget_owner_and_scope_boundaries() -> None:
    result = ThreeActorCohortContinuityFixture.create().run()
    rejections = result["rejections"]
    assert all(
        rejections[key]
        for key in (
            "branch_zero_write",
            "private_zero_write",
            "nested_scope_zero_write",
            "budget_unprocessed_zero_write",
            "duplicate_mismatch_zero_write",
            "missing_owner_zero_write",
            "unknown_zero_write",
        )
    )
    assert result["rejections"]["stale_zero_write"] is True
    assert result["zero_write"] is True
