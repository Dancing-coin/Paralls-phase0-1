from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read_document(*parts: str) -> str:
    return ROOT.joinpath(*parts).read_text(encoding="utf-8")


def test_action_plan_requires_turn_closure_before_semantic_action_work() -> None:
    plan = _read_document(
        "docs",
        "superpowers",
        "plans",
        "2026-09-14-unified-character-action-foundation-and-inf-tag-contract-implementation-plan.md",
    )

    assert "2026-09-23-character-turn-continuity-and-embodied-episode-implementation-plan.md" in plan
    assert "CharacterExecutionContract" in plan
    assert "turn_id`, expected revision, causation/correlation, and idempotency" in plan
    assert "typed recovery and episode evidence | Tasks 13 and 14" in plan
    assert "Tasks 13 and 14 include it in replay and live two-character evidence" in plan
    assert "VLA direct Motor control" not in plan


def test_predecessor_checklist_is_evidence_backed_before_action_work_releases() -> None:
    predecessor = _read_document(
        "docs",
        "superpowers",
        "plans",
        "2026-09-23-character-turn-continuity-and-embodied-episode-implementation-plan.md",
    )
    foundation = _read_document("docs", "character", "character-action-foundation-current-state.md")

    assert "- [x] A canonical turn is created before L1" in predecessor
    assert "- [x] The unified action-foundation plan consumes these contracts" in predecessor
    assert "verify_character_turn_embodied_episode.py" in foundation
    assert ".harness/verification/character-turn-embodied-episode-report.json" in foundation
    assert "82 passed" in foundation
    assert "5711 passed, 28 failed" in foundation
    assert "dependency gate remains conditional" in foundation


def test_runtime_docs_identify_the_canonical_live_turn_and_compatibility_records() -> None:
    runtime = _read_document("docs", "character", "character-agent-runtime-architecture.md")
    mind_core = _read_document("docs", "character", "character-mind-core-status.md")

    assert "CharacterTurnContext is the canonical live turn" in runtime
    assert "completed behavior-turn records" in runtime
    assert "legacy behavior-turn records" in runtime
    assert "CharacterExecutionContract" in runtime
    assert "CharacterAgentL4Adapter" in runtime
    assert "translation-only compatibility input" in runtime
    assert "canonical live turn" in mind_core


def test_release_gate_docs_preserve_advisory_and_evidence_boundaries() -> None:
    runtime = _read_document("docs", "character", "character-agent-runtime-architecture.md")
    foundation = _read_document("docs", "character", "character-action-foundation-current-state.md")

    assert "VLA/provider output is advisory only" in runtime
    assert "must not control a body," in runtime
    assert "CharacterMotor, pose, or authority/world truth" in runtime
    assert "episode is not authority truth" in foundation
    assert "verify_obj_archive_door_physical_embodiment.py" in foundation
    assert ".harness/verification/obj-archive-door-physical-embodiment-report.json" in foundation
    assert "External-asset qualification remains pending" in foundation
