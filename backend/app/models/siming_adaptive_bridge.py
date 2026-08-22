from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.siming_resource_capability import ResourceRealizationRequest


AdaptiveBridgePattern = Literal[
    "private_confrontation",
    "consequence_reveal",
    "relationship_shift",
    "alternative_opportunity",
    "delayed_payoff",
    "aftermath",
]


class StrictBridgeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AdaptiveBridgeNodeProposal(StrictBridgeModel):
    proposal_id: str = Field(min_length=1)
    pattern: AdaptiveBridgePattern
    correlation_id: str = Field(min_length=1)
    causal_gap_ref: str = Field(min_length=1)
    title: str = Field(min_length=1)
    target_actor_id: str | None = Field(default=None, min_length=1)
    supporting_fact_refs: list[str] = Field(min_length=1)
    required_actor_memory_refs: list[str] = Field(default_factory=list)
    obligation_refs: list[str] = Field(default_factory=list)
    attractor_refs: list[str] = Field(default_factory=list)
    realization_request: ResourceRealizationRequest
    autonomy_reason: str = Field(min_length=1)


class SimingLlmProposalAudit(StrictBridgeModel):
    provider: str = Field(min_length=1)
    route_id: str = Field(min_length=1)
    model: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    latency_ms: int = Field(ge=0)
    response_artifact_hash: str = Field(min_length=1)


class GeneratedAdaptiveBridgeProposalBatch(StrictBridgeModel):
    proposals: list[AdaptiveBridgeNodeProposal]
    audit: SimingLlmProposalAudit


class AdaptiveBridgeValidationResult(StrictBridgeModel):
    accepted: bool
    proposal_id: str = Field(min_length=1)
    reason_codes: list[str] = Field(default_factory=list)
    graph_transaction_ref: str | None = Field(default=None, min_length=1)
    runtime_node_ref: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def require_commit_refs_for_acceptance(self) -> "AdaptiveBridgeValidationResult":
        if self.accepted and (
            self.graph_transaction_ref is None or self.runtime_node_ref is None
        ):
            raise ValueError("accepted bridge result requires graph and runtime node references")
        if not self.accepted and (self.graph_transaction_ref or self.runtime_node_ref):
            raise ValueError("rejected bridge result cannot include commit references")
        return self
