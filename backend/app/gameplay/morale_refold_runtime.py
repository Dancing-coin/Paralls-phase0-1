"""Morale refolds from committed garrison and LifeState history."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Callable, Mapping

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, GameplayEvent, GameplayFailure
from app.gameplay.owner_runtime_base import replay_duplicate
from app.gameplay.organization_government_social_platform_runtime import (
    OrganizationGarrisonRosterSnapshot,
    organization_garrison_roster_at,
)
from app.gameplay.pool_runtime import PoolAuthorityService, PoolDefinition, PoolError, PoolProjector


_MORALE_PRINCIPAL = "actor_gameplay.morale_domain"
_LIFE_EVENT = "gameplay.character.life_state_changed"
_LIFE_PRINCIPALS = {
    "alive": "authority:character:life-state:presence-admission",
    "dead": "authority:character:life-state",
}


def calculate_morale_percentage(
    living_count: int, member_count: int, decimal_places: int | None = None,
) -> Decimal:
    if (
        type(living_count) is not int
        or type(member_count) is not int
        or member_count <= 0
        or not 0 <= living_count <= member_count
        or (
            decimal_places is not None
            and (type(decimal_places) is not int or decimal_places < 0)
        )
    ):
        raise ValueError("morale_refold_input_invalid")
    percentage = Decimal(living_count * 100) / Decimal(member_count)
    if decimal_places is None:
        return percentage
    return percentage.quantize(Decimal(1).scaleb(-decimal_places), rounding=ROUND_HALF_UP)


class MoraleRefoldAuthority:
    """Commit one siege morale Pool refold for each canonical casualty event."""

    def __init__(
        self,
        *,
        store: GameplayEventStore,
        definitions: Mapping[tuple[str, str], PoolDefinition],
        refold_resolver: Callable[[int, int], Decimal] = calculate_morale_percentage,
    ) -> None:
        if not definitions:
            raise ValueError("morale_refold_definition_invalid")
        for (organization_ref, role_ref), definition in definitions.items():
            if (
                not organization_ref.startswith("organization:")
                or not role_ref.startswith("role:")
                or definition.lower != Decimal("0")
                or definition.upper != Decimal("100")
                or definition.aggregation_mode != "distribution"
                or definition.refold_model_ref != "morale_refold@1"
            ):
                raise ValueError("morale_refold_definition_invalid")
        self.store = store
        self._definitions = dict(definitions)
        self._refold_resolver = refold_resolver
        self._pool = PoolAuthorityService(
            store=store,
            definitions=tuple(self._definitions.values()),
            owner_ref=_MORALE_PRINCIPAL,
            principal_ref=_MORALE_PRINCIPAL,
        )

    def initialize(
        self,
        *,
        organization_ref: str,
        role_ref: str,
        command_id: str,
        idempotency_key: str,
    ) -> AppendBatchResult:
        definition = self._definition(organization_ref, role_ref)
        return self._pool.initialize(
            definition=definition,
            command_id=command_id,
            idempotency_key=idempotency_key,
            causation_id=f"morale-init:{organization_ref}:{role_ref}",
            correlation_id=f"siege:{organization_ref}",
        )

    def refold_after_casualty(self, *, death_event_id: str) -> AppendBatchResult:
        try:
            death = self.store.get_event(death_event_id)
        except KeyError:
            return self._reject(death_event_id, "morale_death_source_unknown")
        if not self._valid_death(death):
            return self._reject(death_event_id, "morale_death_source_invalid")

        principal = _MORALE_PRINCIPAL
        command_id = f"morale-refold:{death.event_id}"
        idempotency_key = command_id
        idempotency_record = self.store.get_idempotency_record(principal, idempotency_key)
        if idempotency_record is not None:
            try:
                prior = replay_duplicate(
                    self.store,
                    principal=principal,
                    idempotency_key=idempotency_key,
                    payload_digest=idempotency_record.payload_digest,
                    error_factory=PoolError,
                    missing_result_code="morale_idempotency_missing_result",
                    transaction_mismatch_code="morale_replay_transaction_mismatch",
                    event_count_mismatch_code="morale_replay_event_count_mismatch",
                    event_missing_code="morale_replay_event_missing",
                    expected_event_types=("gameplay.pool.adjusted",),
                    expected_command_id=command_id,
                    expected_transaction_id=f"tx:{command_id}",
                )
            except PoolError as exc:
                return self._reject(command_id, str(exc))
            if prior is not None:
                return prior

        actor_ref = death.payload.get("actor_ref")
        selected: tuple[tuple[str, str], PoolDefinition] | None = None
        roster: OrganizationGarrisonRosterSnapshot | None = None
        for key, definition in self._definitions.items():
            snapshot = organization_garrison_roster_at(
                self.store,
                organization_ref=key[0],
                role_ref=key[1],
                global_sequence=death.global_sequence,
            )
            if snapshot is not None and actor_ref in snapshot.member_refs:
                if selected is not None:
                    return self._reject(command_id, "morale_garrison_ambiguous")
                selected, roster = (key, definition), snapshot
        if selected is None or roster is None:
            return self._reject(command_id, "morale_input_unknown")

        states: dict[str, str] = {}
        input_pins = {roster.source_stream_id: roster.source_stream_revision}
        current_reads = {
            roster.source_stream_id: self.store.get_stream_head(roster.source_stream_id),
        }
        for member_ref in roster.member_refs:
            stream_id = f"gameplay:character:life:{member_ref}"
            history = [
                event for event in self.store.read_stream(stream_id)
                if event.global_sequence <= death.global_sequence
            ]
            state = self._life_state_at(member_ref, history)
            if state is None:
                return self._reject(command_id, "morale_input_unknown")
            states[member_ref] = state[0]
            input_pins[stream_id] = state[1]
            current_reads[stream_id] = self.store.get_stream_head(stream_id)

        if states.get(actor_ref) != "dead":
            return self._reject(command_id, "morale_death_not_in_roster_history")

        definition = selected[1]
        if not self.store.read_stream(definition.fact_type):
            initialized = self.initialize(
                organization_ref=selected[0][0],
                role_ref=selected[0][1],
                command_id=f"morale-init:{selected[0][0]}:{selected[0][1]}",
                idempotency_key=f"morale-init:{selected[0][0]}:{selected[0][1]}",
            )
            if not initialized.committed:
                return initialized
        target = self._refold_resolver(
            sum(state == "alive" for state in states.values()), len(states),
        )
        projection = PoolProjector().rebuild(
            self.store.read_stream(definition.fact_type),
            definitions={definition.fact_type: definition},
        )
        return self._pool.adjust(
            fact_type=definition.fact_type,
            delta=target - projection.value,
            reason_code="manual_authority",
            command_id=command_id,
            idempotency_key=idempotency_key,
            expected_revision=projection.source_revision,
            causation_id=death.event_id,
            correlation_id=f"siege:{selected[0][0]}",
            model_ref="morale_refold@1",
            input_revision_vector=input_pins,
            read_stream_revisions=current_reads,
            event_time=death.event_time,
        )

    def projection(self, fact_type: str):
        definition = next((row for row in self._definitions.values() if row.fact_type == fact_type), None)
        if definition is None:
            raise PoolError("pool_fact_type_unknown")
        return PoolProjector().rebuild(
            self.store.read_stream(fact_type),
            definitions={fact_type: definition},
        )

    def _definition(self, organization_ref: str, role_ref: str) -> PoolDefinition:
        try:
            return self._definitions[(organization_ref, role_ref)]
        except KeyError as exc:
            raise PoolError("morale_garrison_unknown") from exc

    def _valid_death(self, event: GameplayEvent) -> bool:
        actor_ref = event.payload.get("actor_ref")
        return (
            event.event_type == _LIFE_EVENT
            and event.schema_version in (1, 2)
            and event.visibility_policy == "project"
            and event.payload.get("to_state") == "dead"
            and isinstance(actor_ref, str)
            and actor_ref.startswith("character:")
            and event.stream_id == f"gameplay:character:life:{actor_ref}"
            and self.store.transaction_owns_event(
                transaction_id=event.transaction_id,
                event_id=event.event_id,
                principal_ref=_LIFE_PRINCIPALS["dead"],
            )
        )

    def _life_state_at(
        self, member_ref: str, events: list[GameplayEvent]
    ) -> tuple[str, int] | None:
        if not events:
            return None
        state = "unknown"
        previous_sequence = 0
        previous_revision = 0
        for event in events:
            target = event.payload.get("to_state")
            principal = _LIFE_PRINCIPALS.get(target)
            if (
                event.event_type != _LIFE_EVENT
                or event.schema_version not in (1, 2)
                or event.visibility_policy != "project"
                or event.stream_id != f"gameplay:character:life:{member_ref}"
                or event.payload.get("actor_ref") != member_ref
                or target not in {"alive", "dead"}
                or event.payload.get("from_state") != state
                or event.global_sequence <= previous_sequence
                or event.stream_revision != previous_revision + 1
                or not self.store.transaction_owns_event(
                    transaction_id=event.transaction_id,
                    event_id=event.event_id,
                    principal_ref=principal,
                )
            ):
                return None
            state = target
            previous_sequence = event.global_sequence
            previous_revision = event.stream_revision
        return state, previous_revision

    @staticmethod
    def _reject(command_id: str, code: str) -> AppendBatchResult:
        return AppendBatchResult(
            committed=False,
            transaction_id=f"transaction:{command_id}",
            command_id=command_id,
            idempotency_status="rejected",
            failure=GameplayFailure(
                error_code=code,
                message=code,
                failed_stage="morale_refold",
            ),
        )
