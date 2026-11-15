"""Validate Siming projection lineage, without granting domain authority."""
from dataclasses import dataclass

from app.models.siming_narrative import NarrativeStateSnapshot
from app.models.siming_runtime_state import StateTreeSnapshot
from app.services.siming_global_situation import SimingGlobalSituationSnapshot


@dataclass(frozen=True)
class StateInconsistency:
    category: str
    entity_id: str
    detail: str


class SimingConsistencyError(ValueError):
    def __init__(self, findings: list[StateInconsistency]) -> None:
        self.findings = tuple(findings)
        super().__init__(f"siming_state_inconsistent:{findings}")


class SimingConsistencyValidator:
    def validate(
        self, tree: StateTreeSnapshot, global_situation: SimingGlobalSituationSnapshot,
        narrative: NarrativeStateSnapshot, *, current_tick: int,
        narrative_revision: int,
    ) -> list[StateInconsistency]:
        findings = []
        def report(category, entity, detail):
            findings.append(StateInconsistency(category, entity, detail))

        actor = tree.character.summary.get("target_actor_id")
        actors = {str(actor)} if actor else set()
        scope = (tree.room_id, tree.scene_id, tree.zone_id)
        for name, snapshot in (("global_situation", global_situation), ("narrative_core", narrative)):
            if (snapshot.room_id, snapshot.scene_id, snapshot.zone_id) != scope:
                report("scope_mismatch", name, "projection scope differs from state tree")
            if set(snapshot.actor_ids) != actors:
                report("actor_state", name, "projected actor targets differ from state tree")
            if snapshot.world_ts != tree.world_ts:
                report("tick_mismatch", name, "source world time differs from state tree")
        for name, tick in (("state_tree", tree.sim_tick_ts), ("global_situation", global_situation.sim_tick_ts)):
            if tick != current_tick:
                report("tick_mismatch", name, f"projection tick {tick} != {current_tick}")
        if narrative.sim_tick_ts - narrative.world_ts != narrative_revision:
            report("revision_drift", "narrative_core", "local narrative clock disagrees with room revision")
        if not tree.source_event_id or tree.source_event_id not in global_situation.authority_event_refs:
            report("event_missing", "global_situation", "source event not recorded")
        if not tree.source_event_id or narrative.source_event_id != tree.source_event_id:
            report("event_missing", "narrative_core", "source event differs from state tree")
        if (narrative.causation_id, narrative.correlation_id) != (tree.causation_id, tree.correlation_id):
            report("event_missing", "narrative_core", "causation or correlation differs from state tree")
        # TODO: Phase 2: verify historical event lineage and complete Owner revision vectors.
        return findings

    def is_consistent(self, *args, **kwargs) -> bool:
        return not self.validate(*args, **kwargs)
