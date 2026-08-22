from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


StoryNodeLifecycle = Literal[
    "latent",
    "eligible",
    "selected",
    "staged",
    "active",
    "resolving",
    "resolved",
    "failed",
    "aborted",
    "cooldown",
]


class StrictStoryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class StoryOutcomeEffect(StrictStoryModel):
    target_blueprint_id: str = Field(min_length=1)
    effect: Literal["close_permanently", "mark_unreachable", "make_eligible"]
    reason: str = Field(min_length=1)


class StoryOutcomePort(StrictStoryModel):
    port_id: str = Field(min_length=1)
    required_result_type: str = Field(min_length=1)
    target_ref: str = Field(min_length=1)
    required_state: str = Field(min_length=1)
    outcome_semantic: str = Field(min_length=1)
    effects: list[StoryOutcomeEffect] = Field(default_factory=list)


class StoryNodeBlueprint(StrictStoryModel):
    blueprint_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    prerequisite_fact_refs: list[str] = Field(default_factory=list)
    required_obligation_refs: list[str] = Field(default_factory=list)
    outcome_ports: list[StoryOutcomePort] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_unique_outcome_ports(self) -> "StoryNodeBlueprint":
        port_ids = [port.port_id for port in self.outcome_ports]
        if len(port_ids) != len(set(port_ids)):
            raise ValueError("outcome port IDs must be unique")
        return self


class RuntimeStoryNode(StrictStoryModel):
    node_id: str = Field(min_length=1)
    blueprint_id: str = Field(min_length=1)
    lifecycle: StoryNodeLifecycle
    reachability: Literal["reachable", "unreachable", "unreachable_by_ledger"] = "reachable"
    outcome_port: str | None = Field(default=None, min_length=1)
    outcome_semantic: str | None = Field(default=None, min_length=1)
    closure_reason: str | None = Field(default=None, min_length=1)
    terminal: bool = False
    reopen_policy: Literal["same_instance", "new_causal_basis", "never"] = "same_instance"
    causal_basis_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_closure_contract(self) -> "RuntimeStoryNode":
        is_player_closure = self.closure_reason == "closed_by_player_choice"
        if is_player_closure and (
            self.lifecycle != "aborted" or not self.terminal or self.reopen_policy != "never"
        ):
            raise ValueError(
                "closed_by_player_choice requires lifecycle=aborted, terminal=true, and reopen_policy=never"
            )
        if self.terminal and not is_player_closure:
            raise ValueError("terminal story nodes require closed_by_player_choice")
        if self.reopen_policy == "never" and not self.terminal:
            raise ValueError("reopen_policy=never requires a terminal story node")
        if self.reopen_policy == "new_causal_basis" and not self.causal_basis_refs:
            raise ValueError("new causal story instances require causal_basis_refs")
        return self


class StoryNodeTransitionCommand(StrictStoryModel):
    _ALLOWED_TARGETS: ClassVar[dict[str, set[str]]] = {
        "latent": {"eligible", "aborted"},
        "eligible": {"selected", "aborted"},
        "selected": {"staged", "aborted"},
        "staged": {"active", "aborted"},
        "active": {"resolving", "aborted"},
        "resolving": {"resolved", "failed", "aborted"},
        "resolved": {"cooldown"},
        "failed": {"cooldown"},
        "aborted": {"cooldown"},
        "cooldown": set(),
    }

    node_id: str = Field(min_length=1)
    expected: StoryNodeLifecycle
    target: StoryNodeLifecycle
    reason: str = Field(min_length=1)
    recorded_at: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_lifecycle_transition(self) -> "StoryNodeTransitionCommand":
        if self.target not in self._ALLOWED_TARGETS[self.expected]:
            raise ValueError(
                f"invalid story lifecycle transition: {self.expected} -> {self.target}"
            )
        return self


class NarrativeObligation(StrictStoryModel):
    obligation_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    status: Literal[
        "open",
        "pressured",
        "partially_satisfied",
        "fulfilled",
        "transformed",
        "waived",
        "contradicted",
    ]
    pressure: float = Field(ge=0.0, le=1.0)
    source_fact_refs: list[str] = Field(min_length=1)
    transformed_to_refs: list[str] = Field(default_factory=list)


class NarrativeAttractor(StrictStoryModel):
    attractor_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    required_fact_refs: list[str] = Field(default_factory=list)
    forbidden_terminal_node_refs: list[str] = Field(default_factory=list)
    reachability: Literal["reachable", "blocked", "satisfied"] = "reachable"


class AuthorityStoryOutcome(StrictStoryModel):
    result_type: str = Field(min_length=1)
    target_ref: str = Field(min_length=1)
    current_state: str = Field(min_length=1)
    authority_result_ref: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    recorded_at: int = Field(ge=0)


class StoryOutcomeApplication(StrictStoryModel):
    authority_result_ref: str = Field(min_length=1)
    nodes: dict[str, RuntimeStoryNode]
    graph_transaction_ref: str = Field(min_length=1)


class ObligationTransformResult(StrictStoryModel):
    source: NarrativeObligation
    replacement: NarrativeObligation
    graph_transaction_ref: str = Field(min_length=1)


class StoryDecisionCandidate(StrictStoryModel):
    candidate_id: str = Field(min_length=1)
    runtime_node_ref: str = Field(min_length=1)
    confirmed_fact: bool
    player_choice: bool
    actor_autonomy: bool
    world_feasibility: bool
    safety: bool
    playability_fairness: bool
    open_obligation: bool
    reachable_attractor: bool
    narrative_score: float
    resource_score: float = 0.0


class StoryCandidateRejection(StrictStoryModel):
    candidate_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class StoryCandidateRanking(StrictStoryModel):
    eligible: list[StoryDecisionCandidate] = Field(default_factory=list)
    rejected: list[StoryCandidateRejection] = Field(default_factory=list)
