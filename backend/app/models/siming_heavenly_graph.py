from __future__ import annotations

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
GraphRecordKind = Literal["fact", "projection", "proposal"]
GraphVisibilityScope = Literal[
    "public",
    "actor_private",
    "siming_internal",
    "authority_only",
    "branch_only",
]
GraphDerivationKind = Literal[
    "authority",
    "projection",
    "inference",
    "correction",
    "retraction",
    "redaction",
]
GraphCorrectionKind = Literal["corrected", "retracted", "redacted"]
GraphCorrectionTargetKind = Literal["node", "relation"]
GraphBranchLifecycleOperation = Literal["fork", "close_node", "discard", "admit"]
GraphBranchStatus = Literal["forked", "discarded", "admitted"]


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
    # ``source_ref`` remains the originating source. Later derivations append
    # their own sources here instead of replacing that typed provenance.
    source_ref_lineage: list[str] = Field(default_factory=list)


class GraphRevisionVector(BaseModel):
    """Monotonic revisions for the streams that influence a graph read."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_revision: int = Field(default=0, ge=0)
    relation_revision: int = Field(default=0, ge=0)
    source_revision: int = Field(default=0, ge=0)
    policy_revision: int = Field(default=0, ge=0)
    branch_revision: int = Field(default=0, ge=0)


class GraphBranchForkRequest(BaseModel):
    """Create an isolated graph branch from one pinned source read set."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_scope: HeavenlyGraphScope
    target_branch_id: str = Field(min_length=1)
    fork_valid_at: int = Field(ge=0)
    fork_recorded_at: int = Field(ge=0)
    source_revision_vector: GraphRevisionVector

    @model_validator(mode="after")
    def validate_target_branch(self) -> "GraphBranchForkRequest":
        if self.target_branch_id == self.source_scope.story_branch_id:
            raise ValueError("fork target branch must differ from source branch")
        return self


class GraphBranchLifecycleRequest(BaseModel):
    """Append a branch state marker; it never deletes graph audit history."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    branch_scope: HeavenlyGraphScope
    operation: GraphBranchLifecycleOperation
    expected_revision_vector: GraphRevisionVector
    node_id: str | None = Field(default=None, min_length=1)
    target_branch_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_operation_fields(self) -> "GraphBranchLifecycleRequest":
        if self.operation == "close_node" and self.node_id is None:
            raise ValueError("close_node requires node_id")
        if self.operation != "close_node" and self.node_id is not None:
            raise ValueError("node_id is only valid for close_node")
        if self.operation == "admit" and self.target_branch_id is None:
            raise ValueError("admit requires target_branch_id")
        if self.operation != "admit" and self.target_branch_id is not None:
            raise ValueError("target_branch_id is only valid for admit")
        return self


class GraphBranchLifecycleMarker(BaseModel):
    """Immutable audit marker for a branch lifecycle transition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    marker_id: str = Field(min_length=1)
    branch_scope: HeavenlyGraphScope
    operation: GraphBranchLifecycleOperation
    recorded_at: int = Field(ge=0)
    revision_vector: GraphRevisionVector
    policy_revision: str = Field(default="policy:v1", min_length=1)
    source_scope: HeavenlyGraphScope | None = None
    source_revision_vector: GraphRevisionVector | None = None
    node_id: str | None = None
    target_branch_id: str | None = None


class GraphBranchDiffLimits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    node_limit: int = Field(default=100, ge=1, le=1000)
    relation_limit: int = Field(default=100, ge=1, le=1000)
    marker_limit: int = Field(default=100, ge=1, le=1000)


class GraphBranchDiffQuery(BaseModel):
    """Compare two explicitly scoped branch snapshots for one reader."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    left_scope: HeavenlyGraphScope
    right_scope: HeavenlyGraphScope
    reader_context: GraphReaderContext
    limits: GraphBranchDiffLimits = Field(default_factory=GraphBranchDiffLimits)

    @model_validator(mode="after")
    def validate_reader_coordinates(self) -> "GraphBranchDiffQuery":
        for scope in (self.left_scope, self.right_scope):
            if (
                scope.world_id != self.reader_context.world_id
                or scope.session_id != self.reader_context.session_id
            ):
                raise ValueError("branch diff scopes must match reader world/session")
        return self


class GraphBranchDiffResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    added_nodes: list[HeavenlyGraphNode] = Field(default_factory=list)
    removed_nodes: list[HeavenlyGraphNode] = Field(default_factory=list)
    changed_nodes: list[HeavenlyGraphNode] = Field(default_factory=list)
    added_relations: list[HeavenlyGraphRelation] = Field(default_factory=list)
    removed_relations: list[HeavenlyGraphRelation] = Field(default_factory=list)
    changed_relations: list[HeavenlyGraphRelation] = Field(default_factory=list)
    lifecycle_markers: list[GraphBranchLifecycleMarker] = Field(default_factory=list)
    left_revision_vector: GraphRevisionVector
    right_revision_vector: GraphRevisionVector
    truncated: bool = False


class GraphSemanticMetadata(BaseModel):
    """Typed semantic admission metadata shared by nodes and relations."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    record_kind: GraphRecordKind = "fact"
    visibility_scope: GraphVisibilityScope = "public"
    derivation_kind: GraphDerivationKind = "authority"
    source_event_refs: tuple[str, ...] = Field(default_factory=tuple)
    source_revision_vector: GraphRevisionVector = Field(default_factory=GraphRevisionVector)
    policy_revision: str = Field(default="policy:legacy", min_length=1)
    scope_digest: str = Field(default="scope:legacy", min_length=1)
    redaction_reason: str | None = Field(default=None, min_length=1)


class GraphReaderContext(BaseModel):
    """Explicit context required by semantic graph readers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reader_principal: str = Field(min_length=1)
    allowed_visibility_scopes: tuple[GraphVisibilityScope, ...] = Field(min_length=1)
    world_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    story_branch_id: str = Field(min_length=1)
    valid_at: int = Field(ge=0)
    recorded_at: int | None = Field(default=None, ge=0)
    policy_revision: str = Field(min_length=1)


class HeavenlyGraphQueryBase(BaseModel):
    """Common bounded, explicitly scoped input for semantic graph readers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    context: GraphReaderContext
    scope: HeavenlyGraphScope | None = None
    include_proposals: bool = False
    limit: int = Field(default=100, ge=1, le=1000)

    @model_validator(mode="after")
    def validate_scope_context(self) -> "HeavenlyGraphQueryBase":
        if self.scope is not None:
            if (
                self.scope.world_id != self.context.world_id
                or self.scope.session_id != self.context.session_id
                or self.scope.story_branch_id != self.context.story_branch_id
            ):
                raise ValueError("query scope must match reader context world/session/branch")
        return self

    def resolved_scope(self) -> HeavenlyGraphScope:
        return self.scope or HeavenlyGraphScope(
            world_id=self.context.world_id,
            session_id=self.context.session_id,
            story_branch_id=self.context.story_branch_id,
        )


class NodeLookupQuery(HeavenlyGraphQueryBase):
    node_ids: list[str] = Field(default_factory=list)
    node_types: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    record_kinds: list[GraphRecordKind] = Field(default_factory=list)


class RelationLookupQuery(HeavenlyGraphQueryBase):
    relation_ids: list[str] = Field(default_factory=list)
    relation_types: list[str] = Field(default_factory=list)
    source_node_ids: list[str] = Field(default_factory=list)
    target_node_ids: list[str] = Field(default_factory=list)


class CausalPathQuery(HeavenlyGraphQueryBase):
    seed_node_ids: list[str] = Field(default_factory=list)
    relation_types: list[str] = Field(default_factory=list)
    max_depth: int = Field(default=2, ge=0, le=8)
    node_limit: int = Field(default=100, ge=1, le=1000)
    relation_limit: int = Field(default=200, ge=1, le=2000)
    max_paths: int = Field(default=20, ge=1, le=200)


class PerspectiveQuery(HeavenlyGraphQueryBase):
    actor_ref: str | None = Field(default=None, min_length=1)
    visibility_scopes: list[GraphVisibilityScope] = Field(default_factory=list)


class ConflictSetQuery(HeavenlyGraphQueryBase):
    subject_ref: str | None = Field(default=None, min_length=1)
    property_key: str | None = Field(default=None, min_length=1)


class BehaviorTurnQuery(HeavenlyGraphQueryBase):
    turn_id: str | None = Field(default=None, min_length=1)
    correlation_id: str | None = Field(default=None, min_length=1)
    actor_id: str | None = Field(default=None, min_length=1)
    stage: str | None = Field(default=None, min_length=1)


class SourceImpactQuery(HeavenlyGraphQueryBase):
    source_ref: str = Field(min_length=1)
    source_revision: int | None = Field(default=None, ge=0)


HeavenlyGraphSemanticQuery = (
    NodeLookupQuery
    | RelationLookupQuery
    | CausalPathQuery
    | PerspectiveQuery
    | ConflictSetQuery
    | BehaviorTurnQuery
    | SourceImpactQuery
)


class HeavenlyGraphQueryResult(BaseModel):
    """Structured semantic read result, including why a read was incomplete."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    nodes: list[HeavenlyGraphNode] = Field(default_factory=list)
    relations: list[HeavenlyGraphRelation] = Field(default_factory=list)
    selected_node_refs: list[str] = Field(default_factory=list)
    selected_relation_refs: list[str] = Field(default_factory=list)
    revision_vector: GraphRevisionVector = Field(default_factory=GraphRevisionVector)
    policy_revision: str = Field(min_length=1)
    scope_digest: str = Field(min_length=1)
    truncated: bool = False
    incomplete_reason: Literal[
        "visibility_denied",
        "stale_read_set",
        "graph_unavailable",
    ] | None = None


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
    semantic_metadata: GraphSemanticMetadata = Field(default_factory=GraphSemanticMetadata)

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
    semantic_metadata: GraphSemanticMetadata = Field(default_factory=GraphSemanticMetadata)

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


class GraphCorrectionRequest(BaseModel):
    """Append-only correction request for one graph record revision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_kind: GraphCorrectionTargetKind
    target_id: str = Field(min_length=1)
    target_revision: int = Field(ge=1)
    correction_kind: GraphCorrectionKind
    source_refs: list[str] = Field(min_length=1)
    semantic_metadata: GraphSemanticMetadata
    expected_revision_vector: GraphRevisionVector | None = None
    scope: HeavenlyGraphScope

    @model_validator(mode="after")
    def validate_source_refs(self) -> "GraphCorrectionRequest":
        if any(not ref for ref in self.source_refs):
            raise ValueError("correction source_refs must be non-empty")
        if len(self.source_refs) != len(set(self.source_refs)):
            raise ValueError("correction source_refs must be unique")
        return self


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
