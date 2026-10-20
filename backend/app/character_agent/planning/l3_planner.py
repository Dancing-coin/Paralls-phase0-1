from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import json
import os
import re

from pydantic import TypeAdapter

from app.character_agent.gateway.context_builder import CharacterContextBuilder
from app.character_agent.models.cognition_delta import CharacterHigherOrderDelta
from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.character_agent.gateway.laya_provider import LayaSystemOneProvider
from app.character_agent.gateway.memory_recall import CharacterMemoryRecallPolicy, MissingRequiredMemoryEvidence
from app.character_agent.models.turn_context import CharacterTurnContext
from app.character_agent.models.mind_frame import CharacterMindFrame
from app.character_agent.services.character_semantic_recall import CharacterSemanticRecallService
from app.character_agent.models.cognition_delta import CharacterBeliefDelta
from app.character_agent.models.cognition_delta import CharacterSocialDelta
from app.character_agent.models.event_memory import CharacterEventMemoryRecord
from app.character_agent.models.goal_runtime import CharacterGoalHint, CharacterGoalPortfolioEntry, CharacterGoalStateRecord
from app.character_agent.models.higher_order_memory import CharacterHigherOrderMemoryRecord
from app.character_agent.models.knowledge_memory import CharacterKnowledgeMemoryRecord
from app.character_agent.models.memory_record_bundle import CharacterMemoryRecordBundle
from app.character_agent.models.observation_memory import CharacterObservationMemoryRecord
from app.character_agent.models.social_memory import CharacterSocialMemoryRecord
from app.character_agent.models.working_memory_state import CharacterWorkingMemoryState
from app.character_agent.models.behavior_policy import BehaviorPolicyRecord
from app.character_agent.cognition.capability_envelope import CapabilityEnvelope
from app.character_agent.cognition.cognition_policy import CognitionPolicy
from app.character_agent.planning.triple_filter import CharacterTripleFilter
from app.character_agent.profile.personality_projection import PersonalityProjectionResolver
from app.models.character_agent_runtime import CharacterActiveGoalFrame
from app.models.character_agent_runtime import CharacterIntentDecision, CharacterInterpretation, CharacterSuggestionPacket


@dataclass(frozen=True)
class CandidateCompilation:
    """Auditable complete candidate universe and provider-presented subset.

    This is a pure compiler record. It never scores candidates or chooses a
    preferred action; selection remains the provider/L3 responsibility.
    """

    universe: list[dict[str, object]]
    presented: list[dict[str, object]]
    pruned: list[dict[str, object]]
    diagnostics: list[dict[str, object]]
    coverage: dict[str, object]
    digest: str

    @property
    def wire_labels(self) -> list[str]:
        return [str(item.get("wire_label", "") or "") for item in self.presented]

    @property
    def by_wire_label(self) -> dict[str, dict[str, object]]:
        return {
            str(item["wire_label"]): dict(item)
            for item in self.presented
            if str(item.get("wire_label", "") or "")
        }


class CandidateCompiler:
    """Compile lawful action+target combinations into U and P.

    Inputs are deliberately plain mappings so existing registry, affordance,
    execution-contract and MindFrame projections can feed this without a
    second planner or a new wire schema.
    """

    DESCRIPTION_CONTRACT_REVISION = "candidate-semantics:v5:1"
    HISTORICAL_DESCRIPTION_CONTRACT_REVISION = "candidate-semantics:v4:1"

    def __init__(self, *, description_contract_revision: str | None = None) -> None:
        self.description_contract_revision = description_contract_revision or self.DESCRIPTION_CONTRACT_REVISION
        if self.description_contract_revision not in {self.DESCRIPTION_CONTRACT_REVISION, self.HISTORICAL_DESCRIPTION_CONTRACT_REVISION}:
            raise ValueError("unsupported candidate description contract")

    @staticmethod
    def _semantic_description(item: dict[str, object]) -> str:
        """Render the frozen, answer-agnostic candidate description.

        The description is generated from registered action semantics and
        target/condition metadata only.  It never carries grading guidance,
        reviewer rationale, or execution receipts.
        """
        family = str(item.get("action_family", "unknown") or "unknown")
        family_scopes = {
            "observation": "gather perceptible information",
            "communication": "exchange information",
            "movement": "change position or contact distance",
            "combat": "attempt a combat interaction",
            "protection": "reduce exposure",
        }
        # The development aliases are existing intent identifiers, not new
        # authority/registry admissions. Distinguish the observation intents
        # even though L3 groups them into one capability family.
        intent = str(item.get("semantic_intent_id", item.get("action_id", "")) or "")
        intent_scopes = {
            "observe": "gather perceptible information without commitment",
            "inspect_object": "inspect perceptible properties of the referenced object",
            "ask_probe": "request information to reduce uncertainty",
            "defer": "postpone commitment without asserting a world change",
            "pause": "pause commitment without asserting a world change",
            "stay_silent": "withhold speech without asserting a world change",
        }
        observation_aliases = {"observe", "ask_probe", "defer"}
        scope = intent_scopes.get(intent) if family in {"observation", *observation_aliases} else None
        if family in observation_aliases:
            scope = intent_scopes[family]
        if family not in family_scopes and family not in observation_aliases:
            family = "unknown"
        effects = scope or family_scopes.get(family, "unknown intent scope")
        target_refs = item.get("target_refs", {})
        target_parts = []
        if isinstance(target_refs, dict):
            for key in sorted(target_refs):
                if key not in {"target", "actor", "entity", "object", "location", "recipient", "source", "destination"}:
                    continue
                value = target_refs[key]
                ref = value if isinstance(value, str) and re.fullmatch(r"[\w:./#-]{1,160}", value) else "unknown"
                if any(term in ref.lower() for term in ("acceptable", "rationale", "correct", "gold", "score")):
                    ref = "unknown"
                target_parts.append(f"{key}={ref}")
        target = ", ".join(target_parts) or "no explicit target relation"
        conditions = item.get("required_conditions", {})
        precondition_parts = []
        if isinstance(conditions, dict):
            for key in sorted(conditions):
                if key not in {"visibility", "consent", "privacy", "contact", "range", "permission", "availability"}:
                    continue
                value = conditions[key]
                status = value if isinstance(value, str) and value in {"satisfied", "required", "blocked", "unknown", "unavailable"} else "unknown"
                precondition_parts.append(f"{key}={status}")
        preconditions = ", ".join(precondition_parts) or "unknown"
        revision = item.get("description_contract_revision", CandidateCompiler.DESCRIPTION_CONTRACT_REVISION)
        if revision == CandidateCompiler.HISTORICAL_DESCRIPTION_CONTRACT_REVISION:
            return (
                f"{family}: {effects}. Target: {target}. Preconditions: {preconditions}. "
                "Runtime legality/owner permission/execution unverified."
            )
        if revision != CandidateCompiler.DESCRIPTION_CONTRACT_REVISION:
            raise ValueError("unsupported candidate description contract")
        compact_scopes = {
            "observe": "gather perceptible information; no commitment",
            "inspect_object": "inspect perceptible object properties",
            "ask_probe": "request information",
            "defer": "postpone commitment",
            "pause": "pause commitment",
            "stay_silent": "withhold speech",
        }
        if scope:
            effects = compact_scopes.get(family if family in observation_aliases else intent, effects)
        elif family == "movement":
            effects = "change position/contact distance"
        elif family == "combat":
            effects = "attempt combat interaction"
        target = ",".join(target_parts) or "none"
        preconditions = ",".join(precondition_parts) or "unknown"
        return (
            f"{family}: {effects}; target:{target}; requires:{preconditions}; "
            "Runtime legality/owner permission/execution unverified"
        )

    def compile(
        self,
        *,
        candidates: list[dict[str, object]],
        envelope: object | None = None,
        policy: object | None = None,
        visible_targets: set[str] | list[str] | None = None,
    ) -> CandidateCompilation:
        envelope_map = envelope if isinstance(envelope, dict) else getattr(envelope, "model_dump", lambda **_: {})()
        envelope_map = envelope_map if isinstance(envelope_map, dict) else {}
        allowed = {str(item) for item in envelope_map.get("allowed_action_families", []) or []}
        blocked = {str(item) for item in envelope_map.get("blocked_action_families", []) or []}
        policy_map = policy if isinstance(policy, dict) else getattr(policy, "model_dump", lambda **_: {})()
        policy_map = policy_map if isinstance(policy_map, dict) else {}
        reasoning = policy_map.get("reasoning", {})
        if not isinstance(reasoning, dict):
            reasoning = {}
        visible = {str(item) for item in (visible_targets or set())}
        max_count_raw = envelope_map.get("max_candidate_intents")
        if max_count_raw is None:
            max_count_raw = envelope_map.get("cognitive_limits", {}).get("max_candidate_intents") if isinstance(envelope_map.get("cognitive_limits"), dict) else None
        if max_count_raw is None:
            max_count_raw = reasoning.get("max_candidate_intents")
        max_count = int(max_count_raw) if isinstance(max_count_raw, int) and max_count_raw >= 0 else None

        universe: list[dict[str, object]] = []
        diagnostics: list[dict[str, object]] = []
        for index, raw in enumerate(candidates):
            item = dict(raw)
            candidate_id = str(item.get("candidate_id", "") or "")
            family = str(item.get("action_family", "") or "")
            conditions = item.get("required_conditions", {})
            if not candidate_id:
                diagnostics.append({"candidate": item, "reason": "candidate_id_missing"})
                continue
            if not isinstance(item.get("target_refs", {}), dict):
                diagnostics.append({"candidate_id": candidate_id, "reason": "target_refs_invalid"})
                continue
            if isinstance(conditions, dict):
                visibility_status = str(conditions.get("visibility", "satisfied") or "satisfied")
                if visibility_status in {"unknown", "unavailable"}:
                    item["diagnosis"] = {"status": visibility_status, "reason": f"condition_{visibility_status}"}
                if visibility_status == "blocked":
                    item["diagnosis"] = {"status": "blocked", "reason": "condition_blocked"}
            target_refs = item.get("target_refs", {})
            target_values = [str(value) for value in target_refs.values()] if isinstance(target_refs, dict) else []
            if visible_targets is not None and any(target not in visible for target in target_values):
                item["diagnosis"] = {"status": "blocked", "reason": "target_not_visible"}
            wire_label = str(item.get("wire_label", "") or candidate_id)
            if not wire_label or wire_label in {str(existing.get("wire_label", "")) for existing in universe}:
                wire_label = f"{wire_label or candidate_id}#{index + 1}"
            item.setdefault("availability", "available")
            item["candidate_id"] = candidate_id
            item["wire_label"] = wire_label
            item["source_refs"] = [str(ref) for ref in item.get("source_refs", []) or []]
            item.setdefault("target_visibility", "visible" if target_values and (not visible or all(target in visible for target in target_values)) else "none")
            item.setdefault("target_provenance", [])
            item.setdefault("affordance_result", {"status": "available", "reason": "not_provided"})
            item.setdefault("owner_route", "")
            item.setdefault("revision_pins", {})
            item["description_contract_revision"] = self.description_contract_revision
            item["description"] = self._semantic_description(item)
            universe.append(item)

        legal_universe: list[dict[str, object]] = []
        for item in universe:
            family = str(item.get("action_family", "") or "")
            diagnosis = item.get("diagnosis")
            reason = str(diagnosis.get("reason", "") or "") if isinstance(diagnosis, dict) else ""
            if family in blocked:
                diagnostics.append({"candidate_id": item["candidate_id"], "reason": "action_family_blocked"})
                continue
            if allowed and family not in allowed:
                diagnostics.append({"candidate_id": item["candidate_id"], "reason": "action_family_not_allowed"})
                continue
            if reason:
                diagnostics.append({"candidate_id": item["candidate_id"], "reason": reason})
                continue
            availability = str(item.get("availability", "available") or "unknown")
            if availability in {"unknown", "unavailable", "blocked"}:
                diagnostics.append({"candidate_id": item["candidate_id"], "reason": f"availability_{availability}"})
                continue
            legal_universe.append(item)
        universe = legal_universe
        presented: list[dict[str, object]] = []
        pruned: list[dict[str, object]] = []
        for item in universe:
            affordance = item.get("affordance_result")
            if isinstance(affordance, dict) and str(affordance.get("status", "available")) in {"unknown", "unavailable", "blocked"}:
                affordance_reason = str(affordance.get("reason", "affordance_unknown") or "affordance_unknown")
                diagnostics.append({"candidate_id": item["candidate_id"], "reason": affordance_reason})
                pruned.append({"candidate_id": item["candidate_id"], "reason": affordance_reason})
                continue
            if max_count is not None and len(presented) >= max_count:
                pruned.append({"candidate_id": item["candidate_id"], "reason": "max_candidate_intents"})
                continue
            presented.append(item)
        payload = {
            "universe": universe,
            "presented": presented,
            "pruned": pruned,
            "diagnostics": diagnostics,
        }
        digest = "sha256:" + hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        return CandidateCompilation(
            universe=universe,
            presented=presented,
            pruned=pruned,
            diagnostics=diagnostics,
            coverage={
                "universe_count": len(universe),
                "presented_count": len(presented),
                "pruned_count": len(pruned),
                "diagnostic_count": len(diagnostics),
                "coverage_ratio": (len(presented) / len(universe)) if universe else 1.0,
            },
            digest=digest,
        )


@dataclass(frozen=True)
class PreparedCharacterIntentPlan:
    """Owner 局部续执行数据；不保存 runtime、store 或 actor 引用。"""
    request_json: bytes
    interpretation: CharacterInterpretation
    control_mode: str
    snapshot: dict[str, object]
    profile: dict[str, object]
    effective_profile: dict[str, object]
    memory_bundle: CharacterMemoryRecordBundle
    working_memory_state: dict[str, object]
    need_tension_state: dict[str, object]
    dynamic_state: dict[str, object]
    verification: dict[str, object]
    behavior_policy: dict[str, object]
    local_active_goal_tags: list[str]
    active_goal_frame: CharacterActiveGoalFrame
    memory_recall: dict[str, object]
    frozen_candidates: list[dict[str, object]] = field(default_factory=list)
    candidate_mapping: dict[str, dict[str, object]] = field(default_factory=dict)
    candidate_digest: str = ""
    capability_envelope: dict[str, object] = field(default_factory=dict)
    cognition_policy: dict[str, object] = field(default_factory=dict)

    def to_json_value(self) -> dict[str, object]:
        """按明确字段结构冻结续执行帧，不保存运行时引用。"""
        return {'schema_version': 1, 'prepared': TypeAdapter(type(self)).dump_python(self, mode='json')}

    @classmethod
    def from_json_value(cls, value: dict[str, object]) -> 'PreparedCharacterIntentPlan':
        if set(value) != {'schema_version', 'prepared'} or type(value['schema_version']) is not int or value['schema_version'] != 1:
            raise ValueError('character_intent_frame_schema_invalid')
        fields = set(cls.__dataclass_fields__)
        legacy_fields = fields - {'frozen_candidates', 'candidate_mapping', 'candidate_digest',
                                  'capability_envelope', 'cognition_policy'}
        if not isinstance(value['prepared'], dict) or set(value['prepared']) not in (fields, legacy_fields):
            raise ValueError('character_intent_frame_fields_invalid')
        return TypeAdapter(cls).validate_json(json.dumps(value['prepared'], ensure_ascii=False), strict=True)


class CharacterAgentL3Service:
    def __init__(
        self,
        gateway: CharacterModelGateway | None = None,
        memory_recall_policy: CharacterMemoryRecallPolicy | None = None,
        semantic_recall_service: CharacterSemanticRecallService | None = None,
    ) -> None:
        self._gateway = gateway or CharacterModelGateway()
        self._triple_filter = CharacterTripleFilter()
        self._memory_recall_policy = memory_recall_policy or CharacterMemoryRecallPolicy()
        self._semantic_recall_service = semantic_recall_service
        self._consumed_behavior_policy_ids: set[str] = set()

    @staticmethod
    def _candidate_semantic_action(intent: str) -> str:
        return {
            "short_punch": "action:melee.short_punch",
            "unarmed_punch": "action:melee.unarmed_punch",
            "sword_slash": "action:melee.sword_slash",
            "observe": "action:observe",
            "inspect_object": "action:inspect",
            "ask_probe": "action:ask_probe",
            "speak_public": "action:speak",
            "speak_private": "action:speak",
            "share_info": "action:speak",
            "withhold": "action:speak",
            "approach": "action:approach",
            "follow_target": "action:approach",
            "seek_private_distance": "action:approach",
            "withdraw": "action:withdraw",
            "break_contact": "action:withdraw",
            "self_protect": "action:self_protect",
            "stay_silent": "action:observe",
            "pause": "action:observe",
            "defer": "action:observe",
        }.get(intent, f"action:{intent}")

    @staticmethod
    def _candidate_action_family(intent: str) -> str:
        if intent in {"short_punch", "unarmed_punch", "sword_slash"}:
            return "combat"
        if intent in {"speak_public", "speak_private", "share_info", "withhold"}:
            return "communication"
        if intent in {"approach", "follow_target", "seek_private_distance", "withdraw", "break_contact"}:
            return "movement"
        if intent in {"ask_probe", "inspect_object", "observe", "pause", "defer", "stay_silent"}:
            return "observation"
        return "protection"

    def _candidate_records(
        self,
        *,
        intents: list[str],
        interpretation: CharacterInterpretation,
        snapshot: dict[str, object],
        envelope: CapabilityEnvelope,
        policy: CognitionPolicy,
        frame: CharacterMindFrame | None,
        skill_affordance_summary: dict[str, object],
    ) -> list[dict[str, object]]:
        """Expand intent labels into complete action/target records.

        Targeted records are created only from an explicit target catalog. L2's
        attention target and the current player are never used as a target
        source. Missing target records remain diagnostics and cannot enter P.
        """
        raw_catalog = snapshot.get("target_catalog", [])
        catalog = [dict(item) for item in raw_catalog if isinstance(item, dict)] if isinstance(raw_catalog, list) else []
        visible = {
            str(item)
            for item in snapshot.get("visible_target_refs", [])
            if str(item or "")
        } if isinstance(snapshot.get("visible_target_refs", []), list) else set()
        target_required = {
            "inspect_object", "share_info", "speak_private", "follow_target",
            "seek_private_distance", "break_contact", "withdraw", "approach",
            "withhold", "short_punch", "unarmed_punch", "sword_slash",
        }
        frame_pins = {
            "frame_digest": frame.frame_digest,
            "turn_id": frame.turn_id,
            "policy_revision": frame.policy_revision,
            "input_revision_vector": dict(frame.input_revision_vector),
            "memory_revision_vector": dict(frame.memory_revision_vector),
        } if frame is not None else {}
        revision_pins = {
            **frame_pins,
            "envelope_revision": envelope.envelope_revision,
            "envelope_digest": envelope.envelope_digest,
            "capability_revision": envelope.capability_revision,
            "policy_id": policy.policy_id,
            "policy_digest": policy.policy_digest,
            **dict(envelope.revision_pins),
            **dict(policy.revision_pins),
        }
        records: list[dict[str, object]] = []
        for intent in dict.fromkeys(str(item) for item in intents if str(item)):
            family = self._candidate_action_family(intent)
            targets = catalog if intent in target_required else [None]
            if intent in target_required and not targets:
                targets = [None]
            for descriptor in targets:
                descriptor = descriptor if isinstance(descriptor, dict) else {}
                target_ref = str(descriptor.get("target_ref", "") or "")
                candidate_id = intent if not target_ref else f"{intent}:{target_ref}"
                target_refs = {str(k): str(v) for k, v in descriptor.get("target_refs", {}).items()} if isinstance(descriptor.get("target_refs", {}), dict) else {}
                if target_ref and not target_refs:
                    target_refs = {"target": target_ref}
                target_values = list(dict.fromkeys(target_refs.values()))
                condition = dict(descriptor.get("required_conditions", {})) if isinstance(descriptor.get("required_conditions", {}), dict) else {}
                if intent in target_required and not target_values:
                    condition.setdefault("visibility", "blocked")
                    diagnosis = {"status": "blocked", "reason": "target_required"}
                else:
                    diagnosis = dict(descriptor.get("diagnosis", {})) if isinstance(descriptor.get("diagnosis", {}), dict) else {}
                if target_values and "visible_target_refs" in snapshot and any(value not in visible for value in target_values):
                    condition["visibility"] = "blocked"
                    diagnosis = {"status": "blocked", "reason": "target_not_visible"}
                if "supported_intents" in descriptor and intent not in descriptor["supported_intents"]:
                    diagnosis = {"status": "blocked", "reason": "target_action_not_supported"}
                affordance = descriptor.get("affordance_result", {"status": "available", "reason": "registered"})
                if not isinstance(affordance, dict):
                    affordance = {"status": "unknown", "reason": "affordance_invalid"}
                record = {
                    "candidate_id": candidate_id,
                    "wire_label": candidate_id,
                    "semantic_action_id": self._candidate_semantic_action(intent),
                    "semantic_intent_id": intent,
                    "target_refs": target_refs,
                    "target_visibility": str(descriptor.get("target_visibility", "visible" if target_values else "none") or "none"),
                    "target_provenance": list(descriptor.get("target_provenance", []) or []) if isinstance(descriptor.get("target_provenance", []), list) else [],
                    "affordance_result": affordance,
                    "action_family": family,
                    "required_conditions": condition,
                    "owner_route": str(descriptor.get("owner_route", "") or ""),
                    "source_refs": list(descriptor.get("source_refs", []) or []) if isinstance(descriptor.get("source_refs", []), list) else [],
                    "frame_ref": str(descriptor.get("frame_ref", "") or frame_pins.get("frame_digest", "")),
                    "revision_pins": {
                        **revision_pins,
                        **({"target_admission_digest": descriptor["target_admission_digest"]}
                           if descriptor.get("target_admission_digest") else {}),
                        "target_revision_vector": dict(descriptor.get("target_revision_vector", {}))
                        if isinstance(descriptor.get("target_revision_vector", {}), dict) else {},
                    },
                    "diagnosis": diagnosis,
                    "execution_contract": {
                        "semantic_action_id": self._candidate_semantic_action(intent),
                        "semantic_intent_id": intent,
                        "target_refs": target_values,
                        "owner_route": str(descriptor.get("owner_route", "") or ""),
                        "revision_pins": {
                            **revision_pins,
                            **({"target_admission_digest": descriptor["target_admission_digest"]}
                               if descriptor.get("target_admission_digest") else {}),
                            "target_revision_vector": dict(descriptor.get("target_revision_vector", {}))
                            if isinstance(descriptor.get("target_revision_vector", {}), dict) else {},
                        },
                    },
                }
                # An explicit stable affordance summary may provide a richer
                # result for the action family; it can only narrow admission.
                family_affordances = skill_affordance_summary.get("action_affordances", {})
                if isinstance(family_affordances, dict) and family in family_affordances:
                    supplied = family_affordances[family]
                    if isinstance(supplied, dict) and record["affordance_result"].get("status", "unknown") == "available":
                        record["affordance_result"] = supplied
                records.append(record)
        # Keep a safe observation/protection floor first, then surface complete
        # action+target records before lower priority targetless fallbacks so a
        # bounded P still contains lawful targeted choices when available.
        return sorted(
            records,
            key=lambda item: (
                0 if item.get("semantic_intent_id") == "observe" else
                1 if item.get("semantic_intent_id") == "self_protect" else
                2 if bool(item.get("target_refs")) and not item.get("diagnosis") else
                3,
                str(item.get("candidate_id", "")),
            ),
        )

    def _compile_capability_contracts(
        self,
        *,
        interpretation: CharacterInterpretation,
        actor_id: str,
        turn_context: CharacterTurnContext | None,
        profile: dict[str, object],
        effective_profile: dict[str, object],
        snapshot: dict[str, object],
        dynamic_state: dict[str, object],
        skill_affordance_summary: dict[str, object],
    ) -> tuple[CapabilityEnvelope, CognitionPolicy]:
        stable = skill_affordance_summary.get("stable_ability_snapshot") or skill_affordance_summary.get("stable_snapshot") or {
            "actor_id": actor_id,
            "capability_revision": str(skill_affordance_summary.get("capability_revision", f"capability:{actor_id}:prepared")),
            "registry_revision": str(skill_affordance_summary.get("registry_revision", "skills:unknown")),
            "allowed_action_families": list(skill_affordance_summary.get("allowed_action_families", []) or []),
            "blocked_action_families": list(skill_affordance_summary.get("blocked_action_families", []) or []),
            "source_refs": list(skill_affordance_summary.get("source_refs", []) or []),
        }
        turn_id = turn_context.turn_id if turn_context is not None else str(snapshot.get("turn_id", "") or f"prepared:{actor_id}")
        envelope = CapabilityEnvelope.compile(
            actor_id=actor_id,
            turn_id=turn_id,
            profile=effective_profile or profile,
            stable_snapshot=stable,
            dynamic_state=dynamic_state,
            event_domain=str(interpretation.interpretation_type or "") or None,
            allowed_action_families=tuple(skill_affordance_summary.get("allowed_action_families", []) or ()),
            blocked_action_families=tuple(skill_affordance_summary.get("blocked_action_families", []) or ()),
            source_refs=tuple(skill_affordance_summary.get("source_refs", []) or ()),
            revision_pins={
                "policy_revision": str(snapshot.get("policy_revision", "") or ""),
            } if str(snapshot.get("policy_revision", "") or "") else None,
        )
        policy = CognitionPolicy.resolve(
            envelope=envelope,
            profile=effective_profile or profile,
            event_complexity={
                "ambiguity": {"low": 0.1, "medium": 0.5, "high": 1.0}.get(interpretation.ambiguity_level, 0.5),
                "risk": {"low": 0.1, "medium": 0.5, "high": 1.0}.get(interpretation.risk_level, 0.5),
            },
            source_refs=tuple(skill_affordance_summary.get("source_refs", []) or ()),
        )
        return envelope, policy

    def build_intent_plan(
        self,
        *,
        interpretation: CharacterInterpretation,
        control_mode: str,
        snapshot: dict[str, object] | None = None,
        profile: dict[str, object] | None = None,
        effective_profile: dict[str, object] | None = None,
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle | None = None,
        working_memory_state: dict[str, object] | CharacterWorkingMemoryState | None = None,
        current_goal_state: dict[str, object] | CharacterGoalStateRecord | None = None,
        goal_state_history: list[dict[str, object] | CharacterGoalStateRecord] | None = None,
        supervision_state: dict[str, object] | None = None,
        unresolved_tensions: list[dict[str, object]] | None = None,
        background_agenda_state: dict[str, object] | None = None,
        need_tension_state: dict[str, object] | None = None,
        dynamic_state: dict[str, object] | None = None,
        skill_affordance_summary: dict[str, object] | None = None,
        behavior_policy_snapshot: dict[str, object] | None = None,
        turn_context: CharacterTurnContext | None = None,
    ) -> dict[str, object]:
        prepared = self.prepare_intent_plan(
            interpretation=interpretation,
            control_mode=control_mode,
            snapshot=snapshot,
            profile=profile,
            effective_profile=effective_profile,
            memory_bundle=memory_bundle,
            working_memory_state=working_memory_state,
            current_goal_state=current_goal_state,
            goal_state_history=goal_state_history,
            supervision_state=supervision_state,
            unresolved_tensions=unresolved_tensions,
            background_agenda_state=background_agenda_state,
            need_tension_state=need_tension_state,
            dynamic_state=dynamic_state,
            skill_affordance_summary=skill_affordance_summary,
            behavior_policy_snapshot=behavior_policy_snapshot,
            turn_context=turn_context,
        )
        output = self._gateway.complete_prepared_request(prepared.request_json)
        return self.finish_intent_plan(prepared, output)

    def prepare_intent_plan(
        self,
        *,
        interpretation: CharacterInterpretation,
        control_mode: str,
        snapshot: dict[str, object] | None = None,
        profile: dict[str, object] | None = None,
        effective_profile: dict[str, object] | None = None,
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle | None = None,
        working_memory_state: dict[str, object] | CharacterWorkingMemoryState | None = None,
        current_goal_state: dict[str, object] | CharacterGoalStateRecord | None = None,
        goal_state_history: list[dict[str, object] | CharacterGoalStateRecord] | None = None,
        supervision_state: dict[str, object] | None = None,
        unresolved_tensions: list[dict[str, object]] | None = None,
        background_agenda_state: dict[str, object] | None = None,
        need_tension_state: dict[str, object] | None = None,
        dynamic_state: dict[str, object] | None = None,
        skill_affordance_summary: dict[str, object] | None = None,
        behavior_policy_snapshot: dict[str, object] | None = None,
        turn_context: CharacterTurnContext | None = None,
        frame: CharacterMindFrame | None = None,
        capability_envelope: dict[str, object] | None = None,
        cognition_policy: dict[str, object] | None = None,
    ) -> PreparedCharacterIntentPlan:
        interpretation = self._normalize_interpretation(interpretation)
        normalized_snapshot = self._normalize_snapshot(snapshot)
        normalized_profile = self._normalize_profile(profile)
        normalized_effective_profile = self._normalize_profile(effective_profile) or normalized_profile
        normalized_memory_bundle = CharacterContextBuilder.normalize_memory_bundle(memory_bundle)
        normalized_working_memory_state = self._working_memory_state_mapping(working_memory_state)
        normalized_need_tension_state = self._normalize_mapping(need_tension_state)
        normalized_dynamic_state = self._dynamic_state_mapping(
            dynamic_state,
            working_memory_state=normalized_working_memory_state,
        )
        normalized_current_goal_state = self._goal_state_mapping(
            current_goal_state,
            actor_id=interpretation.actor_id,
        )
        behavior_policy = self._behavior_policy_from_snapshot(
            behavior_policy_snapshot,
            actor_id=interpretation.actor_id,
        )
        if not behavior_policy and behavior_policy_snapshot is None:
            behavior_policy = self._legacy_behavior_policy_from_memory(normalized_memory_bundle)
        normalized_skill_affordance_summary = self._normalize_mapping(skill_affordance_summary)
        normalized_skill_affordance_summary.pop("registry", None)
        if capability_envelope is not None or cognition_policy is not None:
            if capability_envelope is None or cognition_policy is None or turn_context is None:
                raise ValueError("cognition_contract_pair_required")
            capability_envelope = CapabilityEnvelope.model_validate(capability_envelope)
            cognition_policy = CognitionPolicy.model_validate(cognition_policy)
            cognition_policy.validate_envelope(
                capability_envelope, actor_id=interpretation.actor_id, turn_id=turn_context.turn_id,
                turn_actor_id=turn_context.actor_id, policy_revision=turn_context.policy_revision,
                source_event_ref=turn_context.source_event_ref,
            )
        else:
            capability_envelope, cognition_policy = self._compile_capability_contracts(
                interpretation=interpretation,
                actor_id=interpretation.actor_id,
                turn_context=turn_context,
                profile=normalized_profile,
                effective_profile=normalized_effective_profile,
                snapshot=normalized_snapshot,
                dynamic_state=normalized_dynamic_state,
                skill_affordance_summary=normalized_skill_affordance_summary,
            )
        recall = self._memory_recall_policy.select(
            normalized_memory_bundle,
            context={
                "actor_id": interpretation.actor_id,
                "turn_id": cognition_policy.turn_id,
                "cognition_policy": cognition_policy.model_dump(mode="json"),
                "snapshot": normalized_snapshot,
                "interpretation": interpretation.model_dump(),
                "current_goal_state": normalized_current_goal_state,
                "profile": normalized_profile,
                "effective_profile": normalized_effective_profile,
            },
            requirements=self._policy_recall_requirements(behavior_policy),
        )
        if recall.metadata.get("missing_required_refs"):
            raise MissingRequiredMemoryEvidence(list(recall.metadata["missing_required_refs"]))
        semantic_recall = None
        if self._semantic_recall_service is not None and turn_context is not None:
            semantic_context = {
                "actor_id": interpretation.actor_id,
                "turn_id": cognition_policy.turn_id,
                "cognition_policy": cognition_policy.model_dump(mode="json"),
                "snapshot": normalized_snapshot,
                "interpretation": interpretation.model_dump(),
                "current_goal_state": normalized_current_goal_state,
                "memory": normalized_memory_bundle,
                "profile": normalized_profile,
                "effective_profile": normalized_effective_profile,
            }
            semantic_recall = self._semantic_recall_service.select(
                interpretation.actor_id, semantic_context, turn_context=turn_context
            )
            recall_metadata = dict(recall.metadata)
            recall_metadata.update(semantic_recall.metadata)
            recall = recall.__class__(memory=semantic_recall.memory, metadata=recall_metadata)
        recalled_memory_bundle = self._memory_record_bundle_model(recall.memory)
        verification = self._verification_context(
            interpretation, normalized_snapshot, recall.memory, normalized_effective_profile,
            self._list_entries(unresolved_tensions),
        )
        normalized_goal_state_history = self._goal_state_history_mappings(
            goal_state_history,
            actor_id=interpretation.actor_id,
        )
        normalized_supervision_state = self._normalize_mapping(supervision_state)
        normalized_unresolved_tensions = self._list_entries(unresolved_tensions)
        normalized_background_agenda_state = self._normalize_mapping(background_agenda_state)
        normalized_skill_affordance_summary = self._normalize_mapping(skill_affordance_summary)
        normalized_skill_affordance_summary.pop("registry", None)
        context_goal_tags = self._model_context_goal_tags(current_goal_state=normalized_current_goal_state)
        context_goal_frame = self._model_context_goal_frame(current_goal_state=normalized_current_goal_state)
        local_active_goal_tags = self._active_goal_tags(
            interpretation=interpretation,
            snapshot=normalized_snapshot,
            memory_bundle=recalled_memory_bundle,
            profile=normalized_profile,
            working_memory_state=normalized_working_memory_state,
            current_goal_state=normalized_current_goal_state,
        )
        active_goal_frame = self._active_goal_frame(
            active_goal_tags=local_active_goal_tags,
            interpretation=interpretation,
            snapshot=normalized_snapshot,
            memory_bundle=recalled_memory_bundle,
            profile=normalized_profile,
            working_memory_state=normalized_working_memory_state,
            current_goal_state=normalized_current_goal_state,
        )
        normalized_skill_affordance_summary = self._normalize_mapping(skill_affordance_summary)
        normalized_skill_affordance_summary.pop("registry", None)
        candidate_intents = self._generate_candidates(interpretation, control_mode)
        if behavior_policy:
            candidate_intents = self._apply_behavior_policy(
                candidate_intents,
                behavior_policy,
                local_affordances=candidate_intents,
            )
        candidate_records = self._candidate_records(
            intents=candidate_intents,
            interpretation=interpretation,
            snapshot=normalized_snapshot,
            envelope=capability_envelope,
            policy=cognition_policy,
            frame=frame,
            skill_affordance_summary=normalized_skill_affordance_summary,
        )
        compilation = CandidateCompiler().compile(
            candidates=candidate_records,
            envelope=capability_envelope,
            policy=cognition_policy,
            visible_targets=set(
                str(item) for item in normalized_snapshot.get("visible_target_refs", [])
                if str(item or "")
            ) if isinstance(normalized_snapshot.get("visible_target_refs", []), list) else None,
        )
        frozen_candidate_intents = compilation.wire_labels
        candidate_mapping = compilation.by_wire_label
        laya_route = bool(os.getenv("CHARACTER_LAYA_ENDPOINT", "").strip())
        request_context = {
            "actor_id": interpretation.actor_id,
            "control_mode": control_mode,
            "interpretation": interpretation.model_dump(),
            "profile": normalized_profile,
            "effective_profile": normalized_effective_profile,
            "need_tension_state": normalized_need_tension_state,
            "dynamic_state": normalized_dynamic_state,
            "snapshot": normalized_snapshot,
            "memory": recall.memory,
            "memory_recall": recall.metadata,
            **({"semantic_recall": semantic_recall.metadata} if semantic_recall is not None else {}),
            **({"semantic_cards": [card.to_payload() for card in semantic_recall.cards]} if semantic_recall is not None else {}),
            "verification": verification,
            "behavior_policy": behavior_policy,
            "working_memory_state": normalized_working_memory_state,
            "active_goal_tags": context_goal_tags,
            "active_goal_frame": context_goal_frame.model_dump(),
            "current_goal_state": normalized_current_goal_state,
            "goal_state_history": normalized_goal_state_history,
            "supervision_state": normalized_supervision_state,
            "unresolved_tensions": normalized_unresolved_tensions,
            "background_agenda_state": normalized_background_agenda_state,
            "skill_affordance_summary": normalized_skill_affordance_summary,
            "candidate_intents": frozen_candidate_intents,
            "frozen_candidates": compilation.presented,
            "candidate_mapping": candidate_mapping,
            "candidate_universe": compilation.universe,
            "candidate_pruned": compilation.pruned,
            "candidate_diagnostics": compilation.diagnostics,
            "candidate_digest": compilation.digest,
            "capability_envelope": capability_envelope.model_dump(mode="json"),
            "cognition_policy": cognition_policy.model_dump(mode="json"),
            "turn_id": cognition_policy.turn_id,
            **({"frame": frame} if frame is not None else {}),
        }
        if laya_route:
            request_context["provider_revision"] = LayaSystemOneProvider.PROVIDER_REVISION
            max_len = os.getenv("CHARACTER_LAYA_INPUT_MAX_LEN", "").strip()
            request_context.update(
                input_budget_required=True,
                max_len=int(max_len) if max_len else LayaSystemOneProvider.DEFAULT_MAX_LEN,
                head_max_len=LayaSystemOneProvider.OPTION_HEAD_MAX_LEN,
            )
        request = self._gateway.prepare_run_request(
            task_kind="l3_planning",
            route_override=("laya" if laya_route else None),
            prepared_recall=recall,
            context=request_context,
        )
        return PreparedCharacterIntentPlan(
            snapshot=deepcopy(normalized_snapshot),
            profile=deepcopy(normalized_profile),
            effective_profile=deepcopy(normalized_effective_profile),
            working_memory_state=deepcopy(normalized_working_memory_state),
            need_tension_state=deepcopy(normalized_need_tension_state),
            dynamic_state=deepcopy(normalized_dynamic_state),
            request_json=CharacterModelGateway.freeze_prepared_request(request),
            interpretation=deepcopy(interpretation),
            control_mode=control_mode,
            memory_bundle=deepcopy(recalled_memory_bundle),
            verification=deepcopy(verification),
            behavior_policy=deepcopy(behavior_policy),
            local_active_goal_tags=deepcopy(local_active_goal_tags),
            active_goal_frame=deepcopy(active_goal_frame),
            memory_recall=deepcopy(recall.metadata),
            frozen_candidates=deepcopy(compilation.presented),
            candidate_mapping=deepcopy(candidate_mapping),
            candidate_digest=compilation.digest,
            capability_envelope=capability_envelope.model_dump(mode="json"),
            cognition_policy=cognition_policy.model_dump(mode="json"),
        )

    def finish_intent_plan(
        self, prepared: PreparedCharacterIntentPlan, output: dict[str, object],
    ) -> dict[str, object]:
        """回到 owner 后消费 policy 并执行本地候选过滤和打分。"""
        candidate_id = str(prepared.behavior_policy.get("candidate_id", "") or "")
        if candidate_id:
            self._consumed_behavior_policy_ids.add(candidate_id)
        return self.plan_intent_completion(prepared, output)

    def plan_intent_completion(
        self, prepared: PreparedCharacterIntentPlan, output: dict[str, object],
    ) -> dict[str, object]:
        """纯计算原候选结果；持久续执行在原提交成功后才消费 policy。"""
        model_output = output
        normalized_snapshot = prepared.snapshot
        normalized_profile = prepared.profile
        normalized_effective_profile = prepared.effective_profile
        normalized_working_memory_state = prepared.working_memory_state
        normalized_need_tension_state = prepared.need_tension_state
        normalized_dynamic_state = prepared.dynamic_state
        interpretation = prepared.interpretation
        control_mode = prepared.control_mode
        recalled_memory_bundle = prepared.memory_bundle
        verification = prepared.verification
        behavior_policy = prepared.behavior_policy
        local_active_goal_tags = prepared.local_active_goal_tags
        active_goal_frame = prepared.active_goal_frame
        local_affordances = self._generate_candidates(interpretation, control_mode)
        candidate_mapping = deepcopy(prepared.candidate_mapping)
        frozen_labels = list(candidate_mapping)
        strict_mapping = bool(str(model_output.get("candidate_digest", "") or "")) or bool(model_output.get("laya_evidence"))
        if strict_mapping:
            self._validate_frozen_choice_output(
                prepared=prepared,
                output=model_output,
                candidate_mapping=candidate_mapping,
            )
        candidates = self._model_owned_candidates(
            model_candidates=model_output.get("candidate_intents", []),
            local_affordances=(frozen_labels if strict_mapping else local_affordances) or local_affordances,
        )
        candidates = self._apply_behavior_policy(
            candidates,
            behavior_policy,
            local_affordances=(frozen_labels if strict_mapping else local_affordances) or local_affordances,
        )
        if not strict_mapping:
            for candidate in candidates:
                candidate_mapping.setdefault(candidate, {
                    "candidate_id": candidate,
                    "wire_label": candidate,
                    "semantic_intent_id": candidate,
                    "semantic_action_id": self._candidate_semantic_action(candidate),
                    "target_refs": {},
                    "target_visibility": "none",
                    "target_provenance": [],
                    "affordance_result": {"status": "compatibility_only", "reason": "legacy_gateway"},
                    "owner_route": "",
                    "revision_pins": {},
                })
        active_goal_tags = self._model_owned_active_goal_tags(
            model_goal_tags=model_output.get("active_goal_tags", []),
            fallback_goal_tags=local_active_goal_tags,
        )
        active_goal_frame_payload = self._model_owned_active_goal_frame(
            model_goal_frame=model_output.get("active_goal_frame", {}),
            fallback_goal_frame=active_goal_frame,
        )
        filter_results = [
            self._score_candidate(
                str(candidate_mapping.get(candidate, {}).get("semantic_intent_id", candidate) or candidate),
                interpretation,
                snapshot=normalized_snapshot,
                memory_bundle=recalled_memory_bundle,
                profile=normalized_profile,
                effective_profile=normalized_effective_profile,
                control_mode=control_mode,
                working_memory_state=normalized_working_memory_state,
                need_tension_state=normalized_need_tension_state,
                dynamic_state=normalized_dynamic_state,
                verification=verification,
            )
            for candidate in candidates
        ]
        for label, result in zip(candidates, filter_results):
            result["candidate"] = label
            if label in candidate_mapping:
                result["candidate_id"] = candidate_mapping[label].get("candidate_id", label)
                result["semantic_action_id"] = candidate_mapping[label].get("semantic_action_id", "")
                result["target_refs"] = candidate_mapping[label].get("target_refs", {})
        return {
            "actor_id": interpretation.actor_id,
            "control_mode": control_mode,
            "active_goal_tags": active_goal_tags,
            "active_goal_frame": active_goal_frame_payload.model_dump(),
            "model_output": model_output,
            "candidates": candidates,
            "filter_results": filter_results,
            "memory_recall": prepared.memory_recall,
            "verification": verification,
            "behavior_policy": behavior_policy,
            "frozen_candidates": deepcopy(prepared.frozen_candidates),
            "candidate_mapping": candidate_mapping,
            "candidate_digest": prepared.candidate_digest,
            "capability_envelope": deepcopy(prepared.capability_envelope),
            "cognition_policy": deepcopy(prepared.cognition_policy),
        }

    @staticmethod
    def _validate_frozen_choice_output(
        *,
        prepared: PreparedCharacterIntentPlan,
        output: dict[str, object],
        candidate_mapping: dict[str, dict[str, object]],
    ) -> None:
        labels = output.get("candidate_intents", [])
        if not isinstance(labels, list):
            raise ValueError("l3 candidate labels are invalid")
        labels = [str(item).strip() for item in labels if str(item).strip()]
        if len(labels) != len(set(labels)):
            raise ValueError("l3 candidate labels must be unique")
        if any(label not in candidate_mapping for label in labels):
            raise ValueError("l3 choice is not in frozen candidate mapping")
        selected = str(output.get("selected_intent", "") or "").strip()
        if selected not in candidate_mapping:
            raise ValueError("l3 choice is not in frozen candidate mapping")
        recommended = output.get("recommended_intents", [])
        if isinstance(recommended, list) and any(str(item) not in candidate_mapping for item in recommended):
            raise ValueError("l3 recommended choice is not in frozen candidate mapping")
        output_digest = str(output.get("candidate_digest", "") or "")
        if output_digest and output_digest != prepared.candidate_digest:
            raise ValueError("l3 candidate revision is stale")
        for label in {selected, *labels}:
            record = candidate_mapping.get(label)
            if not isinstance(record, dict):
                raise ValueError("l3 candidate mapping is invalid")
            diagnosis = record.get("diagnosis")
            if isinstance(diagnosis, dict) and str(diagnosis.get("status", "") or "") in {"blocked", "unknown"}:
                raise ValueError("l3 candidate is blocked")
            visibility = str(record.get("target_visibility", "none") or "none")
            if record.get("target_refs") and visibility not in {"visible", "none"}:
                raise ValueError("l3 target is invalid")
            pins = record.get("revision_pins", {})
            if not isinstance(pins, dict):
                raise ValueError("l3 candidate revision pins are invalid")
            if pins.get("envelope_digest") and pins.get("envelope_digest") != prepared.capability_envelope.get("envelope_digest"):
                raise ValueError("l3 candidate envelope revision is stale")
            if pins.get("policy_digest") and pins.get("policy_digest") != prepared.cognition_policy.get("policy_digest"):
                raise ValueError("l3 candidate policy revision is stale")

    def select_intent(
        self,
        interpretation: CharacterInterpretation,
        *,
        snapshot: dict[str, object] | None = None,
        profile: dict[str, object] | None = None,
        effective_profile: dict[str, object] | None = None,
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle | None = None,
        control_mode: str = "agent_full_auto",
        working_memory_state: dict[str, object] | CharacterWorkingMemoryState | None = None,
        current_goal_state: dict[str, object] | CharacterGoalStateRecord | None = None,
        goal_state_history: list[dict[str, object] | CharacterGoalStateRecord] | None = None,
        supervision_state: dict[str, object] | None = None,
        unresolved_tensions: list[dict[str, object]] | None = None,
        background_agenda_state: dict[str, object] | None = None,
        need_tension_state: dict[str, object] | None = None,
        dynamic_state: dict[str, object] | None = None,
        skill_affordance_summary: dict[str, object] | None = None,
        behavior_policy_snapshot: dict[str, object] | None = None,
        turn_context: CharacterTurnContext | None = None,
    ) -> CharacterIntentDecision:
        plan = self.build_intent_plan(
            interpretation=interpretation,
            control_mode=control_mode,
            snapshot=snapshot,
            profile=profile,
            effective_profile=effective_profile,
            memory_bundle=memory_bundle,
            working_memory_state=working_memory_state,
            current_goal_state=current_goal_state,
            goal_state_history=goal_state_history,
            supervision_state=supervision_state,
            unresolved_tensions=unresolved_tensions,
            background_agenda_state=background_agenda_state,
            need_tension_state=need_tension_state,
            dynamic_state=dynamic_state,
            skill_affordance_summary=skill_affordance_summary,
            behavior_policy_snapshot=behavior_policy_snapshot,
            turn_context=turn_context,
        )
        return self.decision_from_plan(plan, interpretation=interpretation)

    def decision_from_plan(
        self, plan: dict[str, object], *, interpretation: CharacterInterpretation,
    ) -> CharacterIntentDecision:
        model_selected_candidate = str(plan.get("model_output", {}).get("selected_intent", "") or "")
        model_recommended_candidates = self._as_string_list(plan.get("model_output", {}).get("recommended_intents", []))
        planning_status = str(plan.get("model_output", {}).get("planning_status", "") or "model")
        fallback_mode = str(plan.get("model_output", {}).get("fallback_mode", "") or "") or None
        chosen_candidate = self._select_model_owned_candidate(
            candidates=self._ordered_model_candidates(
                selected_candidate=model_selected_candidate,
                recommended_candidates=model_recommended_candidates,
            ),
            available_candidates=plan["candidates"],
            filter_results=plan["filter_results"],
        )
        if chosen_candidate == "":
            raise ValueError("model planning did not produce a locally valid candidate")
        selected_result = self._filter_result_for_candidate(plan["filter_results"], chosen_candidate)
        gain_loss_score = float(selected_result.get("gain_loss_score", 0.0) or 0.0) if selected_result else 0.0
        selected_record = plan.get("candidate_mapping", {}).get(chosen_candidate, {}) if isinstance(plan.get("candidate_mapping", {}), dict) else {}
        selected_record = selected_record if isinstance(selected_record, dict) else {}
        target_refs = selected_record.get("target_refs", {})
        if isinstance(target_refs, dict):
            target_refs = [str(value) for value in target_refs.values() if str(value or "")]
        elif isinstance(target_refs, list):
            target_refs = [str(value) for value in target_refs if str(value or "")]
        else:
            target_refs = []
        semantic_intent = str(selected_record.get("semantic_intent_id", chosen_candidate) or chosen_candidate)
        frozen_choice = bool(plan.get("model_output", {}).get("candidate_digest")) or bool(
            plan.get("model_output", {}).get("laya_evidence"))
        active_goal_frame = plan.get("active_goal_frame", {})
        typed_active_goal_frame = CharacterActiveGoalFrame(
            primary_goal=str(active_goal_frame.get("primary_goal", "") or ""),
            long_term_goal=str(active_goal_frame.get("long_term_goal", "") or ""),
            mid_term_strategy=str(active_goal_frame.get("mid_term_strategy", "") or ""),
            immediate_goal=str(active_goal_frame.get("immediate_goal", "") or ""),
            supporting_goals=self._as_string_list(active_goal_frame.get("supporting_goals", [])),
            blockers=self._as_string_list(active_goal_frame.get("blockers", [])),
            goal_sources=self._as_string_list(active_goal_frame.get("goal_sources", [])),
            urgency=str(active_goal_frame.get("urgency", "low") or "low"),
            dominant_goal_id=str(active_goal_frame.get("dominant_goal_id", "") or ""),
            preserved_goal_ids=self._as_string_list(active_goal_frame.get("preserved_goal_ids", [])),
            suppressed_goal_ids=self._as_string_list(active_goal_frame.get("suppressed_goal_ids", [])),
            goal_arbitration_summary=str(active_goal_frame.get("goal_arbitration_summary", "") or ""),
            goal_portfolio=self._goal_portfolio_entries(active_goal_frame.get("goal_portfolio", [])),
        )
        return CharacterIntentDecision(
            actor_id=interpretation.actor_id,
            selected_intent=semantic_intent if frozen_choice else self._map_candidate_to_intent(semantic_intent),
            persona_passed=bool(selected_result and selected_result.get("persona_passed")),
            logic_passed=bool(selected_result and selected_result.get("logic_passed")),
            gain_loss_passed=gain_loss_score >= 0.5,
            rationale=str(plan.get("model_output", {}).get("why_this_now", "") or interpretation.interpreted_summary),
            primary_goal=typed_active_goal_frame.primary_goal,
            long_term_goal=typed_active_goal_frame.long_term_goal,
            mid_term_strategy=typed_active_goal_frame.mid_term_strategy,
            immediate_goal=typed_active_goal_frame.immediate_goal,
            supporting_goals=list(typed_active_goal_frame.supporting_goals),
            blockers=list(typed_active_goal_frame.blockers),
            goal_sources=list(typed_active_goal_frame.goal_sources),
            urgency=typed_active_goal_frame.urgency,
            active_goal_frame=typed_active_goal_frame,
            planning_status=planning_status if planning_status in {"model", "continuity_floor"} else "model",
            fallback_mode=fallback_mode,
            semantic_action_id=str(selected_record.get("semantic_action_id", "") or "") or None,
            target_refs=target_refs,
            candidate_id=str(selected_record.get("candidate_id", chosen_candidate) or chosen_candidate),
            candidate_digest=str(plan.get("candidate_digest", "") or "") or None,
            candidate_revision_pins=dict(selected_record.get("revision_pins", {})) if isinstance(selected_record.get("revision_pins", {}), dict) else {},
            owner_route=str(selected_record.get("owner_route", "") or ""),
        )

    def build_suggestion_packet(
        self,
        *,
        interpretation: CharacterInterpretation,
        control_mode: str,
        snapshot: dict[str, object] | None = None,
        profile: dict[str, object] | None = None,
        effective_profile: dict[str, object] | None = None,
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle | None = None,
        working_memory_state: dict[str, object] | CharacterWorkingMemoryState | None = None,
        current_goal_state: dict[str, object] | CharacterGoalStateRecord | None = None,
        goal_state_history: list[dict[str, object] | CharacterGoalStateRecord] | None = None,
        supervision_state: dict[str, object] | None = None,
        unresolved_tensions: list[dict[str, object]] | None = None,
        background_agenda_state: dict[str, object] | None = None,
        need_tension_state: dict[str, object] | None = None,
        dynamic_state: dict[str, object] | None = None,
        skill_affordance_summary: dict[str, object] | None = None,
        behavior_policy_snapshot: dict[str, object] | None = None,
    ) -> dict[str, object]:
        interpretation = self._normalize_interpretation(interpretation)
        normalized_snapshot = self._normalize_snapshot(snapshot)
        normalized_profile = self._normalize_profile(profile)
        normalized_memory_bundle = CharacterContextBuilder.normalize_memory_bundle(
            self._memory_bundle_mapping(memory_bundle)
        )
        plan = self.build_intent_plan(
            interpretation=interpretation,
            control_mode=control_mode,
            snapshot=normalized_snapshot,
            profile=normalized_profile,
            effective_profile=effective_profile,
            memory_bundle=normalized_memory_bundle,
            working_memory_state=working_memory_state,
            current_goal_state=current_goal_state,
            goal_state_history=goal_state_history,
            supervision_state=supervision_state,
            unresolved_tensions=unresolved_tensions,
            background_agenda_state=background_agenda_state,
            need_tension_state=need_tension_state,
            dynamic_state=dynamic_state,
            skill_affordance_summary=skill_affordance_summary,
            behavior_policy_snapshot=behavior_policy_snapshot,
        )
        return self.suggestion_from_plan(
            plan, interpretation=interpretation, snapshot=normalized_snapshot,
            memory_bundle=normalized_memory_bundle,
        )

    def suggestion_from_plan(
        self, plan: dict[str, object], *, interpretation: CharacterInterpretation,
        snapshot: dict[str, object] | None = None,
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle | None = None,
    ) -> dict[str, object]:
        interpretation = self._normalize_interpretation(interpretation)
        normalized_snapshot = self._normalize_snapshot(snapshot)
        normalized_memory_bundle = CharacterContextBuilder.normalize_memory_bundle(
            self._memory_bundle_mapping(memory_bundle)
        )
        relational_memories = self._list_entries(normalized_memory_bundle.get("relational_memories"))
        guarded_relation_note = self._guarded_relational_note(
            str(interpretation.attention_target or ""),
            relational_memories,
        )
        model_output = plan.get("model_output", {})
        active_goal_frame = plan.get("active_goal_frame", {})
        planning_status = str(model_output.get("planning_status", "") or "model")
        fallback_mode = str(model_output.get("fallback_mode", "") or "") or None
        recommended = self._valid_model_recommended_intents(
            model_output=model_output,
            available_candidates=plan["candidates"],
            filter_results=plan["filter_results"],
        )
        if planning_status == "continuity_floor" or not recommended:
            return self._continuity_floor_suggestion_packet(
                interpretation=interpretation,
                active_goal_frame=active_goal_frame,
                snapshot=normalized_snapshot,
                guarded_relation_note=guarded_relation_note,
            )
        risk_notes = self._as_string_list(model_output.get("risk_notes", []))
        if not risk_notes and guarded_relation_note:
            risk_notes = [guarded_relation_note]
        if not risk_notes:
            risk_notes = [
                str(result["candidate"])
                for result in plan["filter_results"]
                if result["viability"] == "rejected"
            ]
        if not risk_notes and isinstance(normalized_snapshot.get("recent_constraint_results"), list):
            risk_notes = [str(item) for item in normalized_snapshot.get("recent_constraint_results", []) if str(item)]
        why_this_now = str(model_output.get("why_this_now", "") or "")
        if why_this_now == "" or why_this_now == interpretation.interpreted_summary:
            why_this_now = (
                self._recent_world_change_summary(normalized_snapshot)
                or self._recent_constraint_summary(normalized_snapshot)
                or guarded_relation_note
                or self._vigilance_summary(normalized_snapshot)
                or self._distraction_summary(normalized_snapshot)
                or interpretation.interpreted_summary
            )
        packet = CharacterSuggestionPacket(
            actor_id=interpretation.actor_id,
            control_mode="player_priority_assisted",
            producer_ts=0,
            causation_id="",
            correlation_id="",
            recommended_intents=recommended,
            risk_notes=risk_notes,
            primary_goal=str(active_goal_frame.get("primary_goal", "") or ""),
            long_term_goal=str(active_goal_frame.get("long_term_goal", "") or ""),
            mid_term_strategy=str(active_goal_frame.get("mid_term_strategy", "") or ""),
            supporting_goals=self._as_string_list(active_goal_frame.get("supporting_goals", [])),
            blockers=self._as_string_list(active_goal_frame.get("blockers", [])),
            goal_sources=self._as_string_list(active_goal_frame.get("goal_sources", [])),
            urgency=str(active_goal_frame.get("urgency", "low") or "low"),
            belief_cues=self._belief_cues(interpretation),
            higher_order_cues=self._higher_order_cues(interpretation),
            dynamic_pressure=self._dynamic_pressure_summary(interpretation),
            urge_vector="social_probe" if interpretation.attention_target else "hold",
            social_read=interpretation.interpretation_type,
            why_this_now=why_this_now,
            role_consistency_hint=str(
                model_output.get("role_consistency_hint", "")
                or interpretation.inner_prompt_candidate
                or self._recent_world_change_summary(normalized_snapshot)
                or self._recent_constraint_summary(normalized_snapshot)
                or guarded_relation_note
                or self._vigilance_summary(normalized_snapshot)
                or self._distraction_summary(normalized_snapshot)
                or interpretation.interpreted_summary
            ),
            reasoning_trace_summary=str(interpretation.reasoning_trace_summary or interpretation.inner_prompt_candidate or ""),
            planning_status=planning_status if planning_status in {"model", "continuity_floor"} else "model",
            fallback_mode=fallback_mode,
        )
        return packet.model_dump(exclude_none=True)

    def _valid_model_recommended_intents(
        self,
        *,
        model_output: dict[str, object],
        available_candidates: list[str],
        filter_results: list[dict[str, object]],
    ) -> list[str]:
        ordered_candidates = self._ordered_model_candidates(
            selected_candidate=str(model_output.get("selected_intent", "") or ""),
            recommended_candidates=self._as_string_list(model_output.get("recommended_intents", [])),
        )
        recommended: list[str] = []
        for candidate in ordered_candidates:
            if candidate == "":
                continue
            if candidate not in {str(item) for item in available_candidates}:
                continue
            result = self._filter_result_for_candidate(filter_results, candidate)
            if result is None or str(result.get("viability", "") or "") == "rejected":
                continue
            mapped = self._map_candidate_to_intent(candidate)
            if mapped not in recommended:
                recommended.append(mapped)
        return recommended

    def _model_owned_candidates(
        self,
        *,
        model_candidates: object,
        local_affordances: list[str],
    ) -> list[str]:
        candidate_list = [str(item) for item in model_candidates] if isinstance(model_candidates, list) else []
        deduped_model_candidates: list[str] = []
        for candidate in candidate_list:
            if candidate != "" and candidate not in deduped_model_candidates:
                deduped_model_candidates.append(candidate)
        if deduped_model_candidates:
            return deduped_model_candidates
        return local_affordances

    def _behavior_policy_from_snapshot(
        self,
        snapshot: dict[str, object] | None,
        *,
        actor_id: str,
    ) -> dict[str, object]:
        if not isinstance(snapshot, dict) or snapshot.get("actor_id") != actor_id:
            return {}
        raw_record = snapshot.get("record")
        if not isinstance(raw_record, dict):
            return {}
        try:
            record = BehaviorPolicyRecord.model_validate(raw_record)
        except ValueError:
            return {}
        if record.actor_id != actor_id or record.status != "accepted" or not record.evidence_refs:
            return {}
        return record.model_dump(mode="json")

    def _legacy_behavior_policy_from_memory(
        self, memory_bundle: dict[str, list[dict[str, object]]]
    ) -> dict[str, object]:
        for entry in reversed(memory_bundle.get("working_memory", [])):
            if entry.get("event_type") != "character_policy_candidate_event":
                continue
            payload = entry.get("payload", {})
            if not isinstance(payload, dict) or payload.get("status") != "candidate_only":
                continue
            candidate_id = str(payload.get("candidate_id", "") or "")
            if not candidate_id or candidate_id in self._consumed_behavior_policy_ids:
                continue
            return {
                "candidate_id": candidate_id,
                "policy_type": str(payload.get("policy_type", "") or ""),
                "failed_intent": str(payload.get("failed_intent", "") or ""),
                "hypothesis": str(payload.get("hypothesis", "") or ""),
                "status": "active_for_next_decision",
            }
        return {}

    def _apply_behavior_policy(
        self,
        candidates: list[str],
        behavior_policy: dict[str, object],
        *,
        local_affordances: list[str],
    ) -> list[str]:
        if behavior_policy.get("policy_type") != "recovery":
            return candidates
        failed_intent = str(behavior_policy.get("failed_intent", "") or "")
        if failed_intent == "":
            return candidates
        filtered = [candidate for candidate in candidates if candidate != failed_intent]
        return filtered or [candidate for candidate in local_affordances if candidate != failed_intent]

    @staticmethod
    def _policy_recall_requirements(behavior_policy: dict[str, object]) -> dict[str, int] | None:
        if behavior_policy.get("policy_type") != "recall":
            return None
        return {"minimum_pool_limit": 2, "minimum_token_budget": 1600}

    def _model_owned_active_goal_tags(
        self,
        *,
        model_goal_tags: object,
        fallback_goal_tags: list[str],
    ) -> list[str]:
        if not isinstance(model_goal_tags, list):
            return fallback_goal_tags
        normalized: list[str] = []
        for item in model_goal_tags:
            tag = str(item or "").strip()
            if tag != "" and tag not in normalized:
                normalized.append(tag)
        return normalized or fallback_goal_tags

    def _model_owned_active_goal_frame(
        self,
        *,
        model_goal_frame: object,
        fallback_goal_frame: CharacterActiveGoalFrame,
    ) -> CharacterActiveGoalFrame:
        if not isinstance(model_goal_frame, dict) or not model_goal_frame:
            return fallback_goal_frame
        primary_goal = str(model_goal_frame.get("primary_goal", "") or "")
        if primary_goal == "":
            return fallback_goal_frame
        return CharacterActiveGoalFrame(
            primary_goal=primary_goal,
            long_term_goal=str(model_goal_frame.get("long_term_goal", "") or ""),
            mid_term_strategy=str(model_goal_frame.get("mid_term_strategy", "") or ""),
            immediate_goal=str(model_goal_frame.get("immediate_goal", "") or primary_goal),
            supporting_goals=self._as_string_list(model_goal_frame.get("supporting_goals", [])),
            blockers=self._as_string_list(model_goal_frame.get("blockers", [])),
            goal_sources=self._as_string_list(model_goal_frame.get("goal_sources", [])),
            urgency=str(model_goal_frame.get("urgency", "low") or "low"),
            dominant_goal_id=str(model_goal_frame.get("dominant_goal_id", "") or ""),
            preserved_goal_ids=self._as_string_list(model_goal_frame.get("preserved_goal_ids", [])),
            suppressed_goal_ids=self._as_string_list(model_goal_frame.get("suppressed_goal_ids", [])),
            goal_arbitration_summary=str(model_goal_frame.get("goal_arbitration_summary", "") or ""),
            goal_portfolio=self._goal_portfolio_entries(model_goal_frame.get("goal_portfolio", [])),
        )

    def _model_context_goal_tags(self, *, current_goal_state: dict[str, object]) -> list[str]:
        if current_goal_state:
            tags: list[str] = []
            dominant_goal = str(current_goal_state.get("primary_goal", "") or "")
            if dominant_goal != "":
                tags.append(dominant_goal)
            for goal in self._as_string_list(current_goal_state.get("supporting_goals", [])):
                if goal not in tags:
                    tags.append(goal)
            for entry in self._goal_portfolio_dicts(current_goal_state.get("goal_portfolio", [])):
                goal = str(entry.get("goal", "") or "")
                if goal != "" and goal not in tags:
                    tags.append(goal)
            if tags:
                return tags
        return ["preserve_continuity"]

    def _model_context_goal_frame(self, *, current_goal_state: dict[str, object]) -> CharacterActiveGoalFrame:
        if current_goal_state and str(current_goal_state.get("primary_goal", "") or "") != "":
            return self._active_goal_frame_from_mapping(current_goal_state)
        return CharacterActiveGoalFrame(
            primary_goal="preserve_continuity",
            long_term_goal="preserve_continuity",
            mid_term_strategy="hold_position",
            immediate_goal="preserve_continuity",
            supporting_goals=[],
            blockers=[],
            goal_sources=["local_context_shell"],
            urgency="low",
            dominant_goal_id="goal_preserve_continuity",
            preserved_goal_ids=[],
            suppressed_goal_ids=[],
            goal_arbitration_summary="continuity shell active while no persisted goal state is available",
            goal_portfolio=[
                CharacterGoalPortfolioEntry(
                    goal_id="goal_preserve_continuity",
                    goal="preserve_continuity",
                    horizon="long",
                    status="active",
                    priority=0.5,
                    urgency="low",
                    source="local_context_shell",
                )
            ],
        )

    def _continuity_floor_suggestion_packet(
        self,
        *,
        interpretation: CharacterInterpretation,
        active_goal_frame: dict[str, object],
        snapshot: dict[str, object],
        guarded_relation_note: str,
    ) -> dict[str, object]:
        recommended_intent = self._continuity_floor_suggestion_intent(
            snapshot=snapshot,
            guarded_relation_note=guarded_relation_note,
        )
        why_this_now = (
            self._recent_constraint_summary(snapshot)
            or guarded_relation_note
            or self._vigilance_summary(snapshot)
            or self._distraction_summary(snapshot)
            or self._recent_world_change_summary(snapshot)
            or "model planning unavailable; continuity floor active"
        )
        role_consistency_hint = (
            guarded_relation_note
            or self._recent_constraint_summary(snapshot)
            or self._vigilance_summary(snapshot)
            or self._distraction_summary(snapshot)
            or "continuity floor"
        )
        packet = CharacterSuggestionPacket(
            actor_id=interpretation.actor_id,
            control_mode="player_priority_assisted",
            producer_ts=0,
            causation_id="",
            correlation_id="",
            recommended_intents=[recommended_intent],
            risk_notes=[note for note in [guarded_relation_note, self._recent_constraint_summary(snapshot)] if note != ""],
            primary_goal=str(active_goal_frame.get("primary_goal", "") or "preserve_continuity"),
            long_term_goal=str(active_goal_frame.get("long_term_goal", "") or "preserve_continuity"),
            mid_term_strategy=str(active_goal_frame.get("mid_term_strategy", "") or "hold_position"),
            supporting_goals=self._as_string_list(active_goal_frame.get("supporting_goals", [])),
            blockers=self._as_string_list(active_goal_frame.get("blockers", [])),
            goal_sources=self._as_string_list(active_goal_frame.get("goal_sources", [])) or ["continuity_floor"],
            urgency=str(active_goal_frame.get("urgency", "low") or "low"),
            belief_cues=self._belief_cues(interpretation),
            higher_order_cues=self._higher_order_cues(interpretation),
            dynamic_pressure=self._dynamic_pressure_summary(interpretation),
            urge_vector="preserve_continuity",
            social_read="continuity_floor",
            why_this_now=why_this_now,
            role_consistency_hint=role_consistency_hint,
            reasoning_trace_summary=str(interpretation.reasoning_trace_summary or "continuity_floor"),
            planning_status="continuity_floor",
            fallback_mode="continuity_floor",
        )
        return packet.model_dump(exclude_none=True)

    def _continuity_floor_suggestion_intent(
        self,
        *,
        snapshot: dict[str, object],
        guarded_relation_note: str,
    ) -> str:
        if guarded_relation_note != "":
            return "self_protect"
        if isinstance(snapshot.get("recent_constraint_results"), list) and snapshot.get("recent_constraint_results"):
            return "self_protect"
        return "stay_silent"

    def _ordered_model_candidates(
        self,
        *,
        selected_candidate: str,
        recommended_candidates: list[str],
    ) -> list[str]:
        ordered: list[str] = []
        if selected_candidate != "":
            ordered.append(selected_candidate)
        for candidate in recommended_candidates:
            if candidate != "" and candidate not in ordered:
                ordered.append(candidate)
        return ordered

    def _select_model_owned_candidate(
        self,
        *,
        candidates: list[str],
        available_candidates: list[str],
        filter_results: list[dict[str, object]],
    ) -> str:
        available = {str(candidate) for candidate in available_candidates}
        for candidate in candidates:
            if candidate not in available:
                continue
            result = self._filter_result_for_candidate(filter_results, candidate)
            if result is None:
                continue
            if str(result.get("viability", "") or "") == "rejected":
                continue
            return candidate
        return ""

    def _generate_candidates(
        self,
        interpretation: CharacterInterpretation,
        control_mode: str,
    ) -> list[str]:
        candidates = ["observe", "inspect_object", "self_protect"]
        if interpretation.interpretation_type == "combat_threat" and interpretation.attention_target:
            candidates.append("short_punch")
        candidates.extend(["pause", "defer", "withhold"])
        if interpretation.attention_target:
            candidates.extend(
                [
                    "ask_probe",
                    "share_info",
                    "speak_private",
                    "follow_target",
                    "seek_private_distance",
                    "break_contact",
                    "withdraw",
                    "approach",
                ]
            )
        if interpretation.opportunity_level in {"medium", "high"}:
            candidates.append("speak_public")
        if control_mode == "player_priority_assisted":
            candidates.append("stay_silent")
        return candidates

    def _score_candidate(
        self,
        candidate: str,
        interpretation: CharacterInterpretation,
        *,
        snapshot: dict[str, object],
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle,
        profile: dict[str, object],
        effective_profile: dict[str, object],
        control_mode: str,
        working_memory_state: dict[str, object],
        need_tension_state: dict[str, object],
        dynamic_state: dict[str, object],
        verification: dict[str, object] | None = None,
    ) -> dict[str, object]:
        persona_ok = True
        persona_notes: list[str] = []
        logic_ok, logic_notes = self._evaluate_logic(
            candidate,
            interpretation,
            snapshot=snapshot,
            memory_bundle=memory_bundle,
            profile=profile,
            control_mode=control_mode,
            working_memory_state=working_memory_state,
        )
        gain_loss_score, gain_loss_notes = self._score_gain_loss(
            candidate,
            interpretation,
            snapshot=snapshot,
            memory_bundle=memory_bundle,
            profile=profile,
            effective_profile=effective_profile,
            control_mode=control_mode,
            working_memory_state=working_memory_state,
            need_tension_state=need_tension_state,
            dynamic_state=dynamic_state,
            verification=verification,
        )
        return self._triple_filter.evaluate_candidate(
            candidate=candidate,
            persona_ok=persona_ok,
            logic_ok=logic_ok,
            gain_loss_score=gain_loss_score,
            persona_notes=persona_notes,
            logic_notes=logic_notes,
            gain_loss_notes=gain_loss_notes,
        )

    def _evaluate_logic(
        self,
        candidate: str,
        interpretation: CharacterInterpretation,
        *,
        snapshot: dict[str, object],
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle,
        profile: dict[str, object],
        control_mode: str,
        working_memory_state: dict[str, object] | None = None,
    ) -> tuple[bool, list[str]]:
        notes: list[str] = []
        attention_target = str(interpretation.attention_target or "")
        _ = snapshot
        _ = interpretation
        _ = memory_bundle
        _ = profile
        _ = working_memory_state

        if candidate == "inspect_object":
            if not (attention_target.startswith("obj_") or attention_target.startswith("env_")):
                notes.append("inspect_object requires an object-like or environment-like target")
        elif candidate == "ask_probe":
            if attention_target == "":
                notes.append("ask_probe requires an attention target")
        elif candidate == "share_info":
            if attention_target == "":
                notes.append("share_info requires an attention target")
        elif candidate == "stay_silent":
            if control_mode != "player_priority_assisted":
                notes.append("stay_silent requires assisted control")
        elif candidate == "seek_private_distance":
            if attention_target == "":
                notes.append("seek_private_distance requires an attention target")
        elif candidate == "break_contact":
            if attention_target == "":
                notes.append("break_contact requires an attention target")
        elif candidate == "follow_target":
            if attention_target == "":
                notes.append("follow_target requires an attention target")
        elif candidate == "approach":
            if attention_target == "":
                notes.append("approach requires an attention target")
        elif candidate == "withhold":
            if attention_target == "":
                notes.append("withhold requires someone or something to withhold around")

        return not notes, notes

    def _score_gain_loss(
        self,
        candidate: str,
        interpretation: CharacterInterpretation,
        *,
        snapshot: dict[str, object],
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle,
        profile: dict[str, object],
        effective_profile: dict[str, object],
        control_mode: str,
        working_memory_state: dict[str, object] | None = None,
        need_tension_state: dict[str, object] | None = None,
        dynamic_state: dict[str, object] | None = None,
        verification: dict[str, object] | None = None,
    ) -> tuple[float, list[str]]:
        _ = interpretation
        _ = snapshot
        _ = memory_bundle
        _ = profile
        _ = control_mode
        base_scores = {
            "observe": 0.6,
            "inspect_object": 0.42,
            "ask_probe": 0.5,
            "share_info": 0.5,
            "speak_public": 0.5,
            "self_protect": 0.45,
            "stay_silent": 0.35,
            "pause": 0.5,
            "defer": 0.5,
            "withhold": 0.5,
            "speak_private": 0.5,
            "follow_target": 0.5,
            "seek_private_distance": 0.5,
            "break_contact": 0.5,
            "withdraw": 0.5,
            "approach": 0.5,
        }
        score = base_scores.get(candidate, 0.3)
        notes: list[str] = []
        if verification and candidate in verification.get("recommended_intents", []):
            score += .15 * float(verification["analytical_control"])
            notes.append("personality_projection=verification")
        dynamic_signal = self._dynamic_state_mapping(dynamic_state, working_memory_state=working_memory_state)
        affect_signal = self._affect_state_mapping(dynamic_signal)
        approach_bias = self._positive_approach_bias(affect_signal)
        if candidate in {"share_info", "speak_private", "approach", "follow_target"} and approach_bias > 0.0:
            score += approach_bias
            notes.append("positive_affect_bias=approach")
        elif candidate == "self_protect" and approach_bias > 0.0:
            score -= min(0.12, approach_bias)
            notes.append("positive_affect_penalty=self_protect")
        personality_projection = self._normalize_mapping(
            effective_profile.get("personality_projection")
        )
        if candidate == "defer":
            deescalation_bias = self._bounded_float(
                personality_projection.get("conflict_deescalation_bias")
            )
            deescalation_bonus = max(0.0, deescalation_bias - 0.5) * 0.2
            if deescalation_bonus > 0.0:
                score += deescalation_bonus
                notes.append("personality_projection=conflict_deescalation_bias")
        need_signal = self._normalize_mapping(need_tension_state)
        dominant_need = str(need_signal.get("dominant_need", "") or "")
        dominant_need_pressure = self._dominant_need_pressure(need_signal)
        if dominant_need_pressure <= 0.0:
            return self._clamp(score), notes
        dominant_need_weight = self._need_weight(effective_profile or profile, dominant_need)
        stress_load = self._bounded_float(dynamic_signal.get("stress_load"))
        vigilance_level = self._bounded_float(dynamic_signal.get("vigilance_level"))
        social_pressure = self._bounded_float(dynamic_signal.get("social_pressure"))
        masking_pressure = self._bounded_float(dynamic_signal.get("masking_pressure"))
        protective_pressure = max(stress_load, vigilance_level, social_pressure, masking_pressure)

        if candidate == "self_protect":
            pressure_bias = (0.25 * dominant_need_pressure * dominant_need_weight) + (0.15 * protective_pressure)
            if pressure_bias > 0.0:
                score += pressure_bias
                notes.append("pressure_bias=self_protect")
        elif candidate in {"observe", "ask_probe", "share_info", "speak_public", "approach", "follow_target"}:
            pressure_penalty = (0.12 * dominant_need_pressure * dominant_need_weight) + (0.08 * protective_pressure)
            if pressure_penalty > 0.0:
                score -= pressure_penalty
                notes.append("pressure_penalty=exposure")

        return self._clamp(score), notes

    def _verification_context(self, interpretation, snapshot, memory, profile, unresolved_tensions=()) -> dict[str, object]:
        target = interpretation.attention_target
        if not target:
            return {}
        visible_targets = snapshot.get("current_attention_targets", [])
        available = target == snapshot.get("current_focus_target") or target in visible_targets
        if not available:
            return {}
        recommended = ["ask_probe"] if target.startswith("char_") else ["observe", "inspect_object"]
        projection = PersonalityProjectionResolver().resolve(profile)
        for record in memory.get("knowledge_memories", []):
            claim = record.get("claim") if isinstance(record, dict) else None
            if isinstance(claim, dict) and claim.get("subject_ref") == target and record.get("state") in {"disputed", "stale"}:
                return {"subject_ref": target, "reason": record["state"], "source_ref": claim.get("source_ref"),
                        "recommended_intents": recommended, "analytical_control": projection["analytical_control"]}
        # 沿用运行时传入的本人未决事项；不另造只在测试快照中存在的失败列表。
        for failure in unresolved_tensions:
            if (isinstance(failure, dict) and failure.get("category") == "constraint_result"
                    and failure.get("status", "active") == "active" and failure.get("target_ref") == target
                    and failure.get("source_event_id")):
                if any(isinstance(record, dict) and isinstance(record.get("claim"), dict)
                    and record["claim"].get("subject_ref") == target
                    and record.get("state") == "high_confidence_believed"
                    and record["claim"].get("valid_at", 0) >= failure.get("last_reinforced_ts", 0)
                    for record in memory.get("knowledge_memories", [])):
                    continue
                return {"subject_ref": target, "reason": "failed_interaction", "source_ref": failure["source_event_id"],
                        "recommended_intents": recommended, "analytical_control": projection["analytical_control"]}
        return {}

    def _map_candidate_to_intent(self, candidate: str) -> str:
        mapping = {
            "observe": "observe",
            "inspect_object": "observe_target",
            "ask_probe": "ask_probe",
            "share_info": "share_info",
            "withhold": "observe_target",
            "pause": "observe_target",
            "defer": "observe_target",
            "speak_private": "share_info",
            "follow_target": "observe_target",
            "seek_private_distance": "observe_target",
            "break_contact": "physiology_hint",
            "withdraw": "physiology_hint",
            "approach": "observe_target",
            "speak_public": "speak_public",
            "self_protect": "physiology_hint",
            "short_punch": "short_punch",
            "stay_silent": "observe_target",
        }
        return mapping.get(candidate, "observe_target")

    def _is_guarded_relational_target(self, attention_target: str, relational_memories: list[object]) -> bool:
        if attention_target == "":
            return False
        for entry in relational_memories:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("entity_id", "") or "") != attention_target:
                continue
            if str(entry.get("belief_type", "") or "") != "trust_level":
                continue
            if str(entry.get("value", "") or "") == "guarded":
                return True
        return False

    def _guarded_relational_note(self, attention_target: str, relational_memories: list[object]) -> str:
        if self._is_guarded_relational_target(attention_target, relational_memories):
            return f"guarded relation with {attention_target}"
        return ""

    def _filter_result_for_candidate(
        self,
        filter_results: list[dict[str, object]],
        candidate: str,
    ) -> dict[str, object] | None:
        for result in filter_results:
            if str(result.get("candidate", "") or "") == candidate:
                return result
        return None

    def _normalize_snapshot(self, snapshot: dict[str, object] | None) -> dict[str, object]:
        if not isinstance(snapshot, dict):
            return {}
        return dict(snapshot)

    def _normalize_profile(self, profile: dict[str, object] | None) -> dict[str, object]:
        if not isinstance(profile, dict):
            return {}
        return dict(profile)

    def _normalize_mapping(self, value: dict[str, object] | None) -> dict[str, object]:
        if not isinstance(value, dict):
            return {}
        return dict(value)

    def _dynamic_state_mapping(
        self,
        value: dict[str, object] | None,
        *,
        working_memory_state: dict[str, object] | None = None,
    ) -> dict[str, object]:
        if isinstance(value, dict) and value:
            return dict(value)
        if isinstance(working_memory_state, dict):
            dynamic_state = working_memory_state.get("dynamic_state")
            if isinstance(dynamic_state, dict):
                return dict(dynamic_state)
        return {}

    def _affect_state_mapping(self, dynamic_state: dict[str, object]) -> dict[str, object]:
        affect_state = dynamic_state.get("affect_state")
        if isinstance(affect_state, dict):
            return dict(affect_state)
        return {}

    def _positive_approach_bias(self, affect_state: dict[str, object]) -> float:
        trust = self._bounded_float(affect_state.get("trust"))
        affection = self._bounded_float(affect_state.get("affection"))
        gratitude = self._bounded_float(affect_state.get("gratitude"))
        confidence = self._bounded_float(affect_state.get("confidence"))
        calm = self._bounded_float(affect_state.get("calm"))
        return min(0.18, (trust + affection + gratitude + confidence + calm) * 0.04)

    def _list_entries(self, value: object) -> list[dict[str, object]]:
        if not isinstance(value, list):
            return []
        return [entry for entry in value if isinstance(entry, dict)]

    def _goal_portfolio_dicts(self, value: object) -> list[dict[str, object]]:
        return [entry.model_dump() for entry in self._goal_portfolio_entries(value)]

    def _goal_portfolio_entries(self, value: object) -> list[CharacterGoalPortfolioEntry]:
        if not isinstance(value, list):
            return []
        entries: list[CharacterGoalPortfolioEntry] = []
        for item in value:
            if isinstance(item, CharacterGoalPortfolioEntry):
                entries.append(item)
                continue
            if not isinstance(item, dict):
                continue
            goal_id = str(item.get("goal_id", "") or "")
            goal = str(item.get("goal", "") or "")
            source = str(item.get("source", "") or "model")
            if goal_id == "" or goal == "":
                continue
            entries.append(
                CharacterGoalPortfolioEntry(
                    goal_id=goal_id,
                    goal=goal,
                    horizon=str(item.get("horizon", "mid") or "mid"),
                    status=str(item.get("status", "active") or "active"),
                    priority=self._as_float(item.get("priority"), 0.5),
                    urgency=str(item.get("urgency", "low") or "low"),
                    source=source,
                    target_ref=str(item.get("target_ref", "") or ""),
                    blockers=self._as_string_list(item.get("blockers", [])),
                    supporting_evidence=self._as_string_list(item.get("supporting_evidence", [])),
                )
            )
        return entries

    def _goal_state_mapping(
        self,
        value: dict[str, object] | CharacterGoalStateRecord | None,
        *,
        actor_id: str,
    ) -> dict[str, object]:
        if isinstance(value, CharacterGoalStateRecord):
            payload = value.model_dump()
        elif isinstance(value, dict):
            payload = dict(value)
        else:
            return {}
        if str(payload.get("primary_goal", "") or "") == "":
            return {}
        payload.setdefault("actor_id", actor_id)
        return CharacterGoalStateRecord(
            actor_id=str(payload.get("actor_id", actor_id) or actor_id),
            primary_goal=str(payload.get("primary_goal", "") or ""),
            long_term_goal=str(payload.get("long_term_goal", "") or ""),
            mid_term_strategy=str(payload.get("mid_term_strategy", "") or ""),
            immediate_goal=str(payload.get("immediate_goal", "") or str(payload.get("primary_goal", "") or "")),
            supporting_goals=self._as_string_list(payload.get("supporting_goals", [])),
            blockers=self._as_string_list(payload.get("blockers", [])),
            goal_sources=self._as_string_list(payload.get("goal_sources", [])),
            urgency=str(payload.get("urgency", "low") or "low"),
            dominant_goal_id=str(payload.get("dominant_goal_id", "") or ""),
            preserved_goal_ids=self._as_string_list(payload.get("preserved_goal_ids", [])),
            suppressed_goal_ids=self._as_string_list(payload.get("suppressed_goal_ids", [])),
            goal_arbitration_summary=str(payload.get("goal_arbitration_summary", "") or ""),
            goal_portfolio=self._goal_portfolio_entries(payload.get("goal_portfolio", [])),
            transition_kind=str(payload.get("transition_kind", "initial") or "initial"),
            transition_reason_tags=self._as_string_list(payload.get("transition_reason_tags", [])),
        ).model_dump()

    def _goal_state_history_mappings(
        self,
        value: list[dict[str, object] | CharacterGoalStateRecord] | None,
        *,
        actor_id: str,
    ) -> list[dict[str, object]]:
        normalized: list[dict[str, object]] = []
        for item in value or []:
            mapping = self._goal_state_mapping(item, actor_id=actor_id)
            if mapping:
                normalized.append(mapping)
        return normalized

    def _active_goal_frame_from_mapping(self, value: dict[str, object]) -> CharacterActiveGoalFrame:
        primary_goal = str(value.get("primary_goal", "") or "")
        return CharacterActiveGoalFrame(
            primary_goal=primary_goal,
            long_term_goal=str(value.get("long_term_goal", "") or ""),
            mid_term_strategy=str(value.get("mid_term_strategy", "") or ""),
            immediate_goal=str(value.get("immediate_goal", "") or primary_goal),
            supporting_goals=self._as_string_list(value.get("supporting_goals", [])),
            blockers=self._as_string_list(value.get("blockers", [])),
            goal_sources=self._as_string_list(value.get("goal_sources", [])),
            urgency=str(value.get("urgency", "low") or "low"),
            dominant_goal_id=str(value.get("dominant_goal_id", "") or ""),
            preserved_goal_ids=self._as_string_list(value.get("preserved_goal_ids", [])),
            suppressed_goal_ids=self._as_string_list(value.get("suppressed_goal_ids", [])),
            goal_arbitration_summary=str(value.get("goal_arbitration_summary", "") or ""),
            goal_portfolio=self._goal_portfolio_entries(value.get("goal_portfolio", [])),
        )

    def _dict_entry(self, value: object) -> dict[str, object]:
        if not isinstance(value, dict):
            return {}
        return value

    def _as_float(self, value: object, default: float) -> float:
        if isinstance(value, bool):
            return default
        if isinstance(value, (int, float)):
            return float(value)
        return default

    def _bounded_float(self, value: object) -> float:
        return self._clamp(self._as_float(value, 0.0))

    def _clamp(self, value: float) -> float:
        if value < 0.0:
            return 0.0
        if value > 1.0:
            return 1.0
        return value

    def _as_string_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value]

    def _need_weight(self, profile: dict[str, object], need_key: str) -> float:
        layer = profile.get("need_hierarchy_layer", {})
        if not isinstance(layer, dict):
            return 0.0
        weights = layer.get("effective_weights", layer.get("base_weights", {}))
        if not isinstance(weights, dict):
            return 0.0
        return self._bounded_float(weights.get(need_key))

    def _dominant_need_pressure(self, need_tension_state: dict[str, object]) -> float:
        dominant_need = str(need_tension_state.get("dominant_need", "") or "")
        if dominant_need == "":
            return 0.0
        return self._bounded_float(need_tension_state.get(f"{dominant_need}_pressure"))

    def _recent_world_change_summary(self, snapshot: dict[str, object] | None) -> str:
        if not isinstance(snapshot, dict):
            return ""
        value = snapshot.get("recent_world_changes", [])
        if not isinstance(value, list) or not value:
            return ""
        return str(value[-1] or "")

    def _recent_constraint_summary(self, snapshot: dict[str, object] | None) -> str:
        if not isinstance(snapshot, dict):
            return ""
        value = snapshot.get("recent_constraint_results", [])
        if not isinstance(value, list) or not value:
            return ""
        return str(value[-1] or "")

    def _vigilance_summary(self, snapshot: dict[str, object] | None) -> str:
        if not isinstance(snapshot, dict):
            return ""
        vigilance_level = str(snapshot.get("vigilance_level", "") or "")
        if vigilance_level == "elevated":
            return "heightened vigilance"
        return ""

    def _distraction_summary(self, snapshot: dict[str, object] | None) -> str:
        if not isinstance(snapshot, dict):
            return ""
        distraction_level = str(snapshot.get("distraction_level", "") or "")
        if distraction_level == "elevated":
            return "uncertain signal"
        return ""

    def _belief_cues(self, interpretation: CharacterInterpretation) -> list[str]:
        cues: list[str] = []
        for delta in interpretation.belief_deltas:
            if isinstance(delta, CharacterBeliefDelta):
                proposition_key = delta.proposition_key
                state = delta.state
            else:
                proposition_key = str(delta.get("proposition_key", "") or "")
                state = str(delta.get("state", "") or "")
            if proposition_key == "":
                continue
            cues.append(f"{proposition_key}={state}" if state else proposition_key)
        return cues

    def _active_goal_tags(
        self,
        *,
        interpretation: CharacterInterpretation,
        snapshot: dict[str, object],
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle,
        profile: dict[str, object],
        working_memory_state: dict[str, object],
        current_goal_state: dict[str, object],
    ) -> list[str]:
        _ = interpretation
        _ = memory_bundle
        _ = profile
        _ = working_memory_state
        _ = snapshot
        if current_goal_state:
            tags = self._model_context_goal_tags(current_goal_state=current_goal_state)
            if tags:
                return tags
        return ["preserve_continuity"]

    def _active_goal_frame(
        self,
        *,
        active_goal_tags: list[str],
        interpretation: CharacterInterpretation,
        snapshot: dict[str, object],
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle,
        profile: dict[str, object],
        working_memory_state: dict[str, object],
        current_goal_state: dict[str, object],
    ) -> CharacterActiveGoalFrame:
        if current_goal_state and str(current_goal_state.get("primary_goal", "") or "") != "":
            return self._active_goal_frame_from_mapping(current_goal_state)
        _ = memory_bundle
        _ = profile
        _ = working_memory_state
        primary_goal = "preserve_continuity"
        blockers: list[str] = []
        if isinstance(snapshot.get("recent_constraint_results"), list) and snapshot.get("recent_constraint_results"):
            blockers.append("recent_constraint_pressure")
        urgency = "high" if interpretation.risk_level in {"medium", "high"} or blockers else "low"
        long_term_goal = "preserve_continuity"
        supporting_goals: list[str] = []
        goal_sources = ["local_fallback"]
        mid_term_strategy = "hold_position"
        return CharacterActiveGoalFrame(
            primary_goal=primary_goal,
            long_term_goal=long_term_goal,
            mid_term_strategy=mid_term_strategy,
            immediate_goal=primary_goal,
            supporting_goals=supporting_goals,
            blockers=blockers,
            goal_sources=goal_sources,
            urgency=urgency,
            dominant_goal_id="goal_preserve_continuity",
            preserved_goal_ids=[],
            suppressed_goal_ids=[],
            goal_arbitration_summary="continuity floor shell keeps a single low-risk goal active",
            goal_portfolio=[
                CharacterGoalPortfolioEntry(
                    goal_id="goal_preserve_continuity",
                    goal="preserve_continuity",
                    horizon="long",
                    status="active",
                    priority=0.5,
                    urgency=urgency,
                    source="local_fallback",
                    blockers=blockers,
                    supporting_evidence=active_goal_tags,
                )
            ],
        )

    def _higher_order_cues(self, interpretation: CharacterInterpretation) -> list[str]:
        cues: list[str] = []
        for delta in interpretation.higher_order_deltas:
            if isinstance(delta, CharacterHigherOrderDelta):
                meta_belief = delta.meta_belief
            else:
                meta_belief = str(delta.get("meta_belief", "") or "")
            if meta_belief:
                cues.append(meta_belief)
        return cues

    def _dynamic_pressure_summary(self, interpretation: CharacterInterpretation) -> str:
        dynamic_state_delta = interpretation.dynamic_state_delta.as_mapping()
        if not dynamic_state_delta:
            return ""
        ordered_keys = ["vigilance_level", "distraction_level", "stress_load", "social_pressure", "masking_pressure"]
        parts: list[str] = []
        for key in ordered_keys:
            if key in dynamic_state_delta:
                parts.append(f"{key}={dynamic_state_delta[key]}")
        for key, value in dynamic_state_delta.items():
            if key in ordered_keys:
                continue
            parts.append(f"{key}={value}")
        return "|".join(parts)

    def _normalize_interpretation(self, interpretation: CharacterInterpretation) -> CharacterInterpretation:
        normalized_belief_deltas = [self._belief_delta_model(item) for item in interpretation.belief_deltas]
        normalized_social_deltas = [self._social_delta_model(item) for item in interpretation.social_deltas]
        normalized_higher_order_deltas = [self._higher_order_delta_model(item) for item in interpretation.higher_order_deltas]
        normalized_goal_hints = [self._goal_hint_model(item) for item in interpretation.goal_hints]
        return CharacterInterpretation(
            actor_id=interpretation.actor_id,
            interpreted_summary=interpretation.interpreted_summary,
            interpretation_type=interpretation.interpretation_type,
            salience_score=interpretation.salience_score,
            ambiguity_level=interpretation.ambiguity_level,
            risk_level=interpretation.risk_level,
            opportunity_level=interpretation.opportunity_level,
            attention_target=interpretation.attention_target,
            inner_prompt_candidate=interpretation.inner_prompt_candidate,
            belief_deltas=normalized_belief_deltas,
            social_deltas=normalized_social_deltas,
            higher_order_deltas=normalized_higher_order_deltas,
            dynamic_state_delta=interpretation.dynamic_state_delta,
            goal_hints=normalized_goal_hints,
            reasoning_trace_summary=interpretation.reasoning_trace_summary,
        )

    def _belief_delta_model(self, value: object) -> CharacterBeliefDelta:
        if isinstance(value, CharacterBeliefDelta):
            return value
        if isinstance(value, dict):
            return CharacterBeliefDelta(
                proposition_key=str(value.get("proposition_key", "") or ""),
                proposition=str(value.get("proposition", "") or ""),
                state=str(value.get("state", "suspected") or "suspected"),
                confidence=float(value.get("confidence", 0.0) or 0.0),
            )
        return CharacterBeliefDelta(proposition_key=str(value or "").strip())

    def _social_delta_model(self, value: object) -> CharacterSocialDelta:
        if isinstance(value, CharacterSocialDelta):
            return value
        if isinstance(value, dict):
            return CharacterSocialDelta(
                entity_id=str(value.get("entity_id", "") or ""),
                trust_baseline=float(value.get("trust_baseline", 0.5) or 0.5),
                suspicion_baseline=float(value.get("suspicion_baseline", 0.0) or 0.0),
                intimacy=float(value.get("intimacy", 0.0) or 0.0),
                dependency=float(value.get("dependency", 0.0) or 0.0),
                unresolved_tension=float(value.get("unresolved_tension", 0.0) or 0.0),
                shared_secret_refs=[
                    str(ref)
                    for ref in value.get("shared_secret_refs", [])
                    if str(ref)
                ]
                if isinstance(value.get("shared_secret_refs", []), list)
                else [],
            )
        return CharacterSocialDelta(entity_id=str(value or "").strip())

    def _higher_order_delta_model(self, value: object) -> CharacterHigherOrderDelta:
        if isinstance(value, CharacterHigherOrderDelta):
            return value
        if isinstance(value, dict):
            return CharacterHigherOrderDelta(
                subject_actor_id=str(value.get("subject_actor_id", "") or ""),
                proposition_key=str(value.get("proposition_key", "") or ""),
                meta_belief=str(value.get("meta_belief", "") or ""),
                confidence=float(value.get("confidence", 0.0) or 0.0),
            )
        return CharacterHigherOrderDelta(subject_actor_id="", meta_belief=str(value or "").strip())

    def _goal_hint_model(self, value: object) -> CharacterGoalHint:
        if isinstance(value, CharacterGoalHint):
            return value
        if isinstance(value, dict):
            return CharacterGoalHint(
                goal=str(value.get("goal", "") or ""),
                source=str(value.get("source", "") or "model"),
                strength=float(value.get("strength", 0.5) or 0.5),
                evidence_tags=[
                    str(tag)
                    for tag in value.get("evidence_tags", [])
                    if str(tag)
                ]
                if isinstance(value.get("evidence_tags", []), list)
                else [],
            )
        return CharacterGoalHint(goal=str(value or "").strip(), source="model", strength=0.5, evidence_tags=[])

    def _normalized_memory_bundle(
        self,
        value: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle | None,
    ) -> dict[str, list[dict[str, object]]]:
        return CharacterContextBuilder.normalize_memory_bundle(value)

    def _memory_record_bundle_model(
        self,
        value: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle | None,
    ) -> CharacterMemoryRecordBundle:
        if isinstance(value, CharacterMemoryRecordBundle):
            return value
        bundle = self._normalized_memory_bundle(value)
        return CharacterMemoryRecordBundle(
            event_memories=[self._event_memory_record_model(item) for item in bundle.get("event_memories", [])],
            observation_memories=[
                self._observation_memory_record_model(item) for item in bundle.get("observation_memories", [])
            ],
            knowledge_memories=[self._knowledge_memory_record_model(item) for item in bundle.get("knowledge_memories", [])],
            social_memories=[self._social_memory_record_model(item) for item in bundle.get("social_memories", [])],
            higher_order_memories=[
                self._higher_order_memory_record_model(item) for item in bundle.get("higher_order_memories", [])
            ],
        )

    def _event_memory_record_model(self, value: object) -> CharacterEventMemoryRecord:
        if isinstance(value, CharacterEventMemoryRecord):
            return value
        entry = self._dict_entry(value)
        return CharacterEventMemoryRecord(
            memory_id=str(entry.get("memory_id", "") or ""),
            actor_id=str(entry.get("actor_id", "") or ""),
            event_id=str(entry.get("event_id", "") or ""),
            source_event_id=str(entry.get("source_event_id", "") or ""),
            world_ts=int(entry.get("world_ts", 0) or 0),
            event_type=str(entry.get("event_type", "") or ""),
            summary=str(entry.get("summary", "") or ""),
            clarity_score=self._as_float(entry.get("clarity_score"), 0.0),
            certainty_score=self._as_float(entry.get("certainty_score"), 0.0),
            refs=self._as_string_list(entry.get("refs", [])),
        )

    def _observation_memory_record_model(self, value: object) -> CharacterObservationMemoryRecord:
        if isinstance(value, CharacterObservationMemoryRecord):
            return value
        entry = self._dict_entry(value)
        return CharacterObservationMemoryRecord(
            memory_id=str(entry.get("memory_id", "") or ""),
            actor_id=str(entry.get("actor_id", "") or ""),
            source_event_id=str(entry.get("source_event_id", "") or ""),
            world_ts=int(entry.get("world_ts", 0) or 0),
            observed_entity_id=str(entry.get("observed_entity_id", "") or ""),
            observation_type=str(entry.get("observation_type", "") or ""),
            observation_summary=str(entry.get("observation_summary", "") or ""),
            clarity_score=self._as_float(entry.get("clarity_score"), 0.0),
            certainty_score=self._as_float(entry.get("certainty_score"), 0.0),
            distortion_tags=self._as_string_list(entry.get("distortion_tags", [])),
            refs=self._as_string_list(entry.get("refs", [])),
        )

    def _knowledge_memory_record_model(self, value: object) -> CharacterKnowledgeMemoryRecord:
        if isinstance(value, CharacterKnowledgeMemoryRecord):
            return value
        entry = self._dict_entry(value)
        return CharacterKnowledgeMemoryRecord(
            memory_id=str(entry.get("memory_id", "") or ""),
            actor_id=str(entry.get("actor_id", "") or ""),
            proposition_key=str(entry.get("proposition_key", "") or ""),
            proposition=str(entry.get("proposition", "") or ""),
            state=str(entry.get("state", "") or ""),
            confidence=self._as_float(entry.get("confidence"), 0.0),
            source_event_id=str(entry.get("source_event_id", "") or ""),
            producer_ts=int(entry.get("producer_ts", 0) or 0),
        )

    def _social_memory_record_model(self, value: object) -> CharacterSocialMemoryRecord:
        if isinstance(value, CharacterSocialMemoryRecord):
            return value
        entry = self._dict_entry(value)
        return CharacterSocialMemoryRecord(
            memory_id=str(entry.get("memory_id", "") or ""),
            actor_id=str(entry.get("actor_id", "") or ""),
            entity_id=str(entry.get("entity_id", "") or ""),
            trust_baseline=self._as_float(entry.get("trust_baseline"), 0.0),
            suspicion_baseline=self._as_float(entry.get("suspicion_baseline"), 0.0),
            intimacy=self._as_float(entry.get("intimacy"), 0.0),
            dependency=self._as_float(entry.get("dependency"), 0.0),
            unresolved_tension=self._as_float(entry.get("unresolved_tension"), 0.0),
            shared_secret_refs=self._as_string_list(entry.get("shared_secret_refs", [])),
            source_event_id=str(entry.get("source_event_id", "") or ""),
            producer_ts=int(entry.get("producer_ts", 0) or 0),
        )

    def _higher_order_memory_record_model(self, value: object) -> CharacterHigherOrderMemoryRecord:
        if isinstance(value, CharacterHigherOrderMemoryRecord):
            return value
        entry = self._dict_entry(value)
        return CharacterHigherOrderMemoryRecord(
            memory_id=str(entry.get("memory_id", "") or ""),
            actor_id=str(entry.get("actor_id", "") or ""),
            subject_actor_id=str(entry.get("subject_actor_id", "") or ""),
            proposition_key=str(entry.get("proposition_key", "") or ""),
            meta_belief=str(entry.get("meta_belief", "") or ""),
            confidence=self._as_float(entry.get("confidence"), 0.0),
            source_event_id=str(entry.get("source_event_id", "") or ""),
            producer_ts=int(entry.get("producer_ts", 0) or 0),
        )

    def _working_memory_state_mapping(
        self,
        value: dict[str, object] | CharacterWorkingMemoryState | None,
    ) -> dict[str, object]:
        if isinstance(value, CharacterWorkingMemoryState):
            return value.model_dump()
        if isinstance(value, dict):
            return dict(value)
        return {}

    def _memory_bundle_mapping(
        self,
        value: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle | None,
    ) -> dict[str, list[dict[str, object]]]:
        if isinstance(value, CharacterMemoryRecordBundle):
            return {
                "event_memories": [item.model_dump() for item in value.event_memories],
                "observation_memories": [item.model_dump() for item in value.observation_memories],
                "knowledge_memories": [item.model_dump() for item in value.knowledge_memories],
                "social_memories": [item.model_dump() for item in value.social_memories],
                "higher_order_memories": [item.model_dump() for item in value.higher_order_memories],
            }
        if isinstance(value, dict):
            return dict(value)
        return {}
