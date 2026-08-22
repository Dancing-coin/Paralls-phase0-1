from app.models.siming_heavenly_graph import GraphProvenance, HeavenlyGraphScope
from app.models.siming_heavenly_memory import InterventionOutcomeMemoryEntry
from app.models.siming_resource_capability import StagingAck, StagingRequest, StagingResult
from app.services.siming_heavenly_memory import SimingHeavenlyMemoryService
from app.services.siming_story_graph_runtime import SimingStoryGraphRuntime
from app.services.siming_story_obligation_runtime import SimingStoryObligationRuntime


class StoryNodeStagingError(RuntimeError):
    pass


class SimingStoryNodeStaging:
    REQUIRED_ACK_SOURCES = frozenset({"godot", "character", "esm"})
    _STAGING_STATUSES = frozenset({"open", "pressured", "partially_satisfied"})

    def __init__(
        self,
        story: SimingStoryGraphRuntime,
        memory: SimingHeavenlyMemoryService,
        obligations: SimingStoryObligationRuntime,
    ) -> None:
        self._story = story
        self._memory = memory
        self._obligations = obligations

    def complete(
        self,
        request: StagingRequest,
        *,
        acks: list[StagingAck],
    ) -> StagingResult:
        existing = self._read_result(
            scope=request.scope,
            node_id=request.node_id,
            correlation_id=request.correlation_id,
            valid_at=request.recorded_at,
            obligation_id=request.obligation_id,
            realization_signature=request.resource_match.realization_signature,
            staging_recorded_at=request.recorded_at,
        )
        if existing is not None:
            return existing
        if not request.resource_match.accepted:
            raise StoryNodeStagingError("staging requires an accepted resource match")

        failure = self._ack_failure(request, acks)
        if failure is not None:
            return self._abort(
                scope=request.scope,
                node_id=request.node_id,
                obligation_id=request.obligation_id,
                correlation_id=request.correlation_id,
                recorded_at=request.recorded_at,
                realization_signature=request.resource_match.realization_signature,
                reason=failure,
                status="aborted_before_activation",
            )
        return self._stage(request)

    def cancel(
        self,
        *,
        scope: HeavenlyGraphScope,
        node_id: str,
        reason: str,
        correlation_id: str,
        recorded_at: int,
    ) -> StagingResult:
        existing = self._read_result(
            scope=scope,
            node_id=node_id,
            correlation_id=correlation_id,
            valid_at=recorded_at,
            staging_recorded_at=recorded_at,
        )
        if existing is not None:
            return existing
        staged = self._staged_entry(scope=scope, node_id=node_id, valid_at=recorded_at)
        if staged is None:
            raise StoryNodeStagingError("only a staged story node can be cancelled")
        return self._abort(
            scope=scope,
            node_id=node_id,
            correlation_id=correlation_id,
            recorded_at=recorded_at,
            obligation_id=staged.obligation_id or "",
            realization_signature=staged.realization_signature or "",
            reason=reason,
            status="cancelled",
        )

    def _stage(self, request: StagingRequest) -> StagingResult:
        result = self._record(
            scope=request.scope,
            node_id=request.node_id,
            correlation_id=request.correlation_id,
            recorded_at=request.recorded_at,
            obligation_id=request.obligation_id,
            realization_signature=request.resource_match.realization_signature,
            status="staged",
            lifecycle="staged",
            reason="",
        )
        self._transition(
            scope=request.scope,
            node_id=request.node_id,
            obligation_id=request.obligation_id,
            recorded_at=request.recorded_at,
            expected="selected",
            target="staged",
            reason="all_staging_acknowledgements",
            result=result,
        )
        return result

    def _abort(
        self,
        *,
        scope: HeavenlyGraphScope,
        node_id: str,
        obligation_id: str,
        correlation_id: str,
        recorded_at: int,
        realization_signature: str,
        reason: str,
        status: str,
    ) -> StagingResult:
        result = self._record(
            scope=scope,
            node_id=node_id,
            correlation_id=correlation_id,
            recorded_at=recorded_at,
            obligation_id=obligation_id,
            realization_signature=realization_signature,
            status=status,
            lifecycle="aborted",
            reason=reason,
        )
        current = self._story.read_runtime_node(
            scope=scope,
            node_id=node_id,
            valid_at=recorded_at,
        )
        if current is None or current.lifecycle not in {"selected", "staged"}:
            raise StoryNodeStagingError("only selected or staged story nodes can be aborted")
        self._transition(
            scope=scope,
            node_id=node_id,
            obligation_id=obligation_id,
            recorded_at=recorded_at,
            expected=current.lifecycle,
            target="aborted",
            reason=reason,
            result=result,
        )
        return result

    def _transition(
        self,
        *,
        scope: HeavenlyGraphScope,
        node_id: str,
        obligation_id: str,
        recorded_at: int,
        expected: str,
        target: str,
        reason: str,
        result: StagingResult,
    ) -> None:
        outcome = InterventionOutcomeMemoryEntry(
            entry_id=self._entry_id(node_id, result.correlation_id),
            stage="staging",
            correlation_id=result.correlation_id,
            selected_node_ref=node_id,
            realization_signature=result.realization_signature,
            obligation_id=obligation_id,
            staging_status=result.status,
            story_node_lifecycle=result.story_node_lifecycle,
            obligation_status=result.obligation_status,
            staging_recorded_at=recorded_at,
            reason=result.reason,
        )
        self._story.transition_with_intervention_outcome(
            scope=scope,
            node_id=node_id,
            expected=expected,
            target=target,
            reason=reason,
            recorded_at=recorded_at,
            outcome=outcome,
            provenance=GraphProvenance(
                source_kind="runtime_outcome",
                source_ref=f"story_staging:{node_id}",
                causation_id=f"story_staging:{node_id}",
                correlation_id=result.correlation_id,
                producer_system="siming_story_node_staging",
            ),
        )

    def _record(
        self,
        *,
        scope: HeavenlyGraphScope,
        node_id: str,
        correlation_id: str,
        recorded_at: int,
        obligation_id: str,
        realization_signature: str,
        status: str,
        lifecycle: str,
        reason: str,
    ) -> StagingResult:
        obligation_status = self._obligation_status(
            scope=scope,
            obligation_id=obligation_id,
            valid_at=recorded_at,
        )
        result = StagingResult(
            node_id=node_id,
            correlation_id=correlation_id,
            status=status,
            story_node_lifecycle=lifecycle,
            obligation_status=obligation_status,
            realization_signature=realization_signature,
            reason=reason,
        )
        return result

    def _read_result(
        self,
        *,
        scope: HeavenlyGraphScope,
        node_id: str,
        correlation_id: str,
        valid_at: int,
        obligation_id: str | None = None,
        realization_signature: str | None = None,
        staging_recorded_at: int | None = None,
    ) -> StagingResult | None:
        entry = self._memory.get_entry(
            scope=scope,
            entry_id=self._entry_id(node_id, correlation_id),
            valid_at=valid_at,
        )
        if entry is None:
            return None
        if not isinstance(entry, InterventionOutcomeMemoryEntry) or entry.stage != "staging":
            raise StoryNodeStagingError("staging record has an invalid memory payload")
        if entry.selected_node_ref != node_id:
            raise StoryNodeStagingError("staging record has an invalid node reference")
        if (
            obligation_id is not None
            and entry.obligation_id != obligation_id
            or realization_signature is not None
            and entry.realization_signature != realization_signature
            or staging_recorded_at is not None
            and entry.staging_recorded_at != staging_recorded_at
        ):
            raise StoryNodeStagingError("staging correlation was reused with a different request")
        return StagingResult(
            node_id=node_id,
            correlation_id=correlation_id,
            status=entry.staging_status,
            story_node_lifecycle=entry.story_node_lifecycle,
            obligation_status=entry.obligation_status,
            realization_signature=entry.realization_signature,
            reason=entry.reason,
        )

    def _staged_entry(
        self,
        *,
        scope: HeavenlyGraphScope,
        node_id: str,
        valid_at: int,
    ) -> InterventionOutcomeMemoryEntry | None:
        entries = [
            entry
            for entry in self._memory.list_domain(
                scope,
                "intervention_outcome",
                valid_at=valid_at,
            )
            if isinstance(entry, InterventionOutcomeMemoryEntry)
            and entry.stage == "staging"
            and entry.selected_node_ref == node_id
            and entry.staging_status == "staged"
        ]
        if len(entries) > 1:
            raise StoryNodeStagingError("story node has multiple staged records")
        return entries[0] if entries else None

    def _obligation_status(
        self,
        *,
        scope: HeavenlyGraphScope,
        obligation_id: str,
        valid_at: int,
    ) -> str:
        obligation = self._obligations.read(
            scope=scope,
            obligation_id=obligation_id,
            valid_at=valid_at,
        )
        if obligation is None or obligation.status not in self._STAGING_STATUSES:
            raise StoryNodeStagingError("staging requires an open narrative obligation")
        return obligation.status

    def _ack_failure(
        self,
        request: StagingRequest,
        acks: list[StagingAck],
    ) -> str | None:
        if any(ack.correlation_id != request.correlation_id for ack in acks):
            return "staging_ack_correlation_mismatch"
        sources = [ack.source for ack in acks]
        if len(sources) != len(set(sources)):
            return "duplicate_staging_ack"
        if set(sources) != self.REQUIRED_ACK_SOURCES:
            return "missing_staging_ack"
        rejected = sorted(ack.reason or f"{ack.source}_staging_rejected" for ack in acks if not ack.accepted)
        return rejected[0] if rejected else None

    @staticmethod
    def _entry_id(node_id: str, correlation_id: str) -> str:
        return f"story_staging:{node_id}:{correlation_id}"
