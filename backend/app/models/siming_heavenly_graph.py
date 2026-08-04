from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


GraphSourceKind = Literal[
    "authority_event",
    "world_result",
    "esm_result",
    "character_memory",
    "siming_projection",
    "runtime_outcome",
    "authored_seed",
]
GraphNamespace = Literal[
    "siming_heavenly",
    "actor_private",
    "resource_capability",
]
HeavenlySubgraphDirection = Literal["outgoing", "incoming", "both"]


class HeavenlyGraphScope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    world_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    story_branch_id: str = Field(min_length=1)
    room_id: str | None = Field(default=None, min_length=1)
    scene_id: str | None = Field(default=None, min_length=1)
    graph_namespace: GraphNamespace = "siming_heavenly"
    owner_actor_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_owner_boundary(self) -> "HeavenlyGraphScope":
        if self.graph_namespace == "actor_private" and self.owner_actor_id is None:
            raise ValueError("actor_private scope requires owner_actor_id")
        if self.graph_namespace != "actor_private" and self.owner_actor_id is not None:
            raise ValueError("owner_actor_id is only valid for actor_private scope")
        return self


class GraphValidity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    valid_from: int = Field(ge=0)
    valid_to: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_half_open_interval(self) -> "GraphValidity":
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError("valid_to must be greater than valid_from")
        return self

    def contains(self, valid_at: int) -> bool:
        return self.valid_from <= valid_at and (
            self.valid_to is None or valid_at < self.valid_to
        )


class GraphProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_kind: GraphSourceKind
    source_ref: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    producer_system: str = Field(min_length=1)
    actor_id: str | None = Field(default=None, min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)


class HeavenlyGraphNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(min_length=1)
    node_type: str = Field(min_length=1)
    scope: HeavenlyGraphScope
    validity: GraphValidity
    recorded_at: int = Field(ge=0)
    revision: int = Field(ge=1)
    supersedes_revision: int | None = Field(default=None, ge=1)
    attributes: dict[str, JsonValue] = Field(default_factory=dict)
    provenance: GraphProvenance

    @model_validator(mode="after")
    def validate_revision_chain(self) -> "HeavenlyGraphNode":
        if self.revision == 1 and self.supersedes_revision is not None:
            raise ValueError("revision 1 cannot supersede another revision")
        if self.revision > 1 and self.supersedes_revision != self.revision - 1:
            raise ValueError("revision must supersede its immediate predecessor")
        return self


class HeavenlyGraphRelation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relation_id: str = Field(min_length=1)
    relation_type: str = Field(min_length=1)
    source_node_id: str = Field(min_length=1)
    target_node_id: str = Field(min_length=1)
    scope: HeavenlyGraphScope
    validity: GraphValidity
    recorded_at: int = Field(ge=0)
    revision: int = Field(ge=1)
    supersedes_revision: int | None = Field(default=None, ge=1)
    attributes: dict[str, JsonValue] = Field(default_factory=dict)
    provenance: GraphProvenance

    @model_validator(mode="after")
    def validate_revision_chain(self) -> "HeavenlyGraphRelation":
        if self.revision == 1 and self.supersedes_revision is not None:
            raise ValueError("revision 1 cannot supersede another revision")
        if self.revision > 1 and self.supersedes_revision != self.revision - 1:
            raise ValueError("revision must supersede its immediate predecessor")
        return self


class HeavenlyGraphWriteBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    scope: HeavenlyGraphScope
    nodes: list[HeavenlyGraphNode] = Field(default_factory=list)
    relations: list[HeavenlyGraphRelation] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_batch(self) -> "HeavenlyGraphWriteBatch":
        if not self.nodes and not self.relations:
            raise ValueError("write batch must contain at least one entity")
        for entity in [*self.nodes, *self.relations]:
            if entity.scope != self.scope:
                raise ValueError("every entity must match the batch scope")
        node_revisions = [(node.node_id, node.revision) for node in self.nodes]
        if len(node_revisions) != len(set(node_revisions)):
            raise ValueError("duplicate node revision in write batch")
        relation_revisions = [
            (relation.relation_id, relation.revision) for relation in self.relations
        ]
        if len(relation_revisions) != len(set(relation_revisions)):
            raise ValueError("duplicate relation revision in write batch")
        return self


class HeavenlyGraphWriteResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: str
    idempotency_key: str
    applied: bool
    replayed: bool = False
    node_refs: list[str] = Field(default_factory=list)
    relation_refs: list[str] = Field(default_factory=list)


class HeavenlyNodeQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: HeavenlyGraphScope
    valid_at: int = Field(ge=0)
    recorded_at: int | None = Field(default=None, ge=0)
    node_ids: list[str] = Field(default_factory=list)
    node_types: list[str] = Field(default_factory=list)
    limit: int | None = Field(default=100, ge=1, le=1000)


class HeavenlyRelationQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: HeavenlyGraphScope
    valid_at: int = Field(ge=0)
    recorded_at: int | None = Field(default=None, ge=0)
    relation_ids: list[str] = Field(default_factory=list)
    relation_types: list[str] = Field(default_factory=list)
    source_node_ids: list[str] = Field(default_factory=list)
    target_node_ids: list[str] = Field(default_factory=list)
    limit: int | None = Field(default=100, ge=1, le=1000)


class HeavenlySubgraphResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: HeavenlyGraphScope
    seed_node_ids: list[str]
    valid_at: int = Field(ge=0)
    recorded_at: int | None = Field(default=None, ge=0)
    nodes: list[HeavenlyGraphNode] = Field(default_factory=list)
    relations: list[HeavenlyGraphRelation] = Field(default_factory=list)
    truncated: bool = False


class HeavenlyGraphCheckpointRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    checkpoint_ref: str = Field(min_length=1)
    checkpoint_id: str = Field(min_length=1)
    scope: HeavenlyGraphScope
    valid_at: int = Field(ge=0)
    recorded_at: int = Field(ge=0)


class HeavenlyGraphSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    checkpoint: HeavenlyGraphCheckpointRef
    nodes: list[HeavenlyGraphNode] = Field(default_factory=list)
    relations: list[HeavenlyGraphRelation] = Field(default_factory=list)
