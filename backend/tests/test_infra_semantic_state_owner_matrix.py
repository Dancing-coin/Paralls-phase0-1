from app.gameplay.semantic_registry import SemanticRegistry, SemanticRegistryError, StateLifecyclePolicy


def _policy(*, state_ref: str = "state:cold", effect_ref: str = "effect:cold_exposure", owner_ref: str = "actor_gameplay.survival_domain") -> StateLifecyclePolicy:
    return StateLifecyclePolicy(
        state_ref=state_ref,
        effect_ref=effect_ref,
        lifecycle="scheduled",
        revision="1",
        owner_ref=owner_ref,
        stream_pattern="gameplay:survival:{actor_ref}",
        opened_event_type="gameplay.survival.obligation_opened",
        settled_event_type="gameplay.survival.obligation_settled",
        cancelled_event_type="gameplay.survival.obligation_cancelled",
        fragment_builder_ref="SurvivalAuthority.build_state_expiry_fragment",
        projection_scope="project",
    )


def test_registered_state_owner_matrix_returns_exact_survival_row() -> None:
    registry = SemanticRegistry()
    registry.register_state_lifecycle(_policy())

    row = registry.scheduled_state_owner_row(state_ref="state:cold", effect_ref="effect:cold_exposure")

    assert row == _policy()


def test_registered_state_owner_matrix_rejects_effect_state_mismatch() -> None:
    registry = SemanticRegistry()
    registry.register_state_lifecycle(_policy())

    try:
        registry.scheduled_state_owner_row(state_ref="state:cold", effect_ref="effect:heat_exposure")
    except SemanticRegistryError as exc:
        assert str(exc) == "semantic_state_effect_mapping_unregistered"
    else:
        raise AssertionError("effect/state mismatch must not be admitted")


def test_registered_state_owner_matrix_rejects_unregistered_owner_without_registration() -> None:
    registry = SemanticRegistry()

    try:
        registry.register_state_lifecycle(_policy(owner_ref="authority:crop"))
    except SemanticRegistryError as exc:
        assert str(exc) == "semantic_lifecycle_owner_unregistered"
    else:
        raise AssertionError("unregistered owner must not be added to the matrix")


def test_registered_state_owner_matrix_lists_only_registered_rows_deterministically() -> None:
    registry = SemanticRegistry()
    registry.register_state_lifecycle(_policy(state_ref="state:overheated", effect_ref="effect:heat_exposure"))
    registry.register_state_lifecycle(_policy(state_ref="state:cold", effect_ref="effect:cold_exposure"))

    assert tuple(row.state_ref for row in registry.scheduled_state_owner_rows()) == ("state:cold", "state:overheated")


def test_survival_fatigue_row_is_an_explicit_closed_owner_contract() -> None:
    registry = SemanticRegistry()
    policy = _policy(state_ref="state:fatigued", effect_ref="effect:fatigue_exposure")

    registry.register_state_lifecycle(policy)

    assert registry.scheduled_state_owner_row(
        state_ref="state:fatigued", effect_ref="effect:fatigue_exposure"
    ) == policy
    assert registry.scheduled_state_definition(
        state_ref="state:fatigued", effect_ref="effect:fatigue_exposure"
    ).model_dump() == {
        "state_ref": "state:fatigued",
        "stack_policy": "refresh",
        "stack_limit": 1,
        "expiry_policy": "scheduled",
        "dispel_allowed": True,
        "transform_targets": ("state:recovering",),
    }
    row = registry.registered_state_owner_row(
        state_ref="state:fatigued", effect_ref="effect:fatigue_exposure"
    )
    assert row.owner_ref == "actor_gameplay.survival_domain"
    assert row.stream_pattern == "gameplay:survival:{actor_ref}"
