"""Pure actor-side episode evaluation; authority and Godot are never called here."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.character_agent.models.embodied_episode import (
    CandidateActionObservation,
    EmbodiedEpisodeRecord,
    EpisodeFailureClass,
)
from app.character_agent.models.turn_context import CharacterTurnContext


class EmbodiedEpisodeService:
    def begin(
        self,
        turn: CharacterTurnContext,
        candidate: CandidateActionObservation,
        pre_capture_ref: str,
    ) -> EmbodiedEpisodeRecord:
        if not pre_capture_ref:
            raise ValueError("episode requires pre-action capture evidence")
        return EmbodiedEpisodeRecord(
            episode_ref=f"episode:{turn.turn_id}:{candidate.candidate_id}",
            turn_id=turn.turn_id,
            actor_id=turn.actor_id,
            candidate=candidate,
            pre_capture_ref=pre_capture_ref,
            evidence_refs=tuple(dict.fromkeys((pre_capture_ref, *candidate.evidence_refs))),
            reobserve_required=candidate.reobserve_required,
        )

    def complete(
        self,
        episode: EmbodiedEpisodeRecord,
        authority_result: Mapping[str, Any] | object | None,
        post_capture_ref: str,
        observed_state: str,
    ) -> EmbodiedEpisodeRecord:
        authority = self._as_mapping(authority_result)
        authority_ref = self._authority_ref(authority)
        authority_status = self._authority_status(authority)
        evidence_refs = tuple(dict.fromkeys((*episode.evidence_refs, authority_ref, post_capture_ref)))
        if not self._is_accepted(authority_status) or not authority_ref:
            return self._failure(
                episode, "authority_rejected", authority_ref, authority_status,
                post_capture_ref, observed_state, evidence_refs,
            )
        if not post_capture_ref:
            return self._failure(
                episode, "perception", authority_ref, authority_status,
                post_capture_ref, observed_state, evidence_refs,
            )
        expected_state = self._expected_state(episode.candidate)
        if expected_state and observed_state != expected_state:
            return self._failure(
                episode, "observation_mismatch", authority_ref, authority_status,
                post_capture_ref, observed_state, evidence_refs,
            )
        return episode.model_copy(update={
            "authority_result_ref": authority_ref,
            "authority_status": authority_status,
            "post_capture_ref": post_capture_ref,
            "observed_state": observed_state,
            "outcome": "confirmed_success",
            "failure_class": None,
            "recovery_candidate": {},
            "evidence_refs": evidence_refs,
            "reobserve_required": False,
        })

    @staticmethod
    def _as_mapping(authority_result: Mapping[str, Any] | object | None) -> Mapping[str, Any]:
        if authority_result is None:
            return {}
        if isinstance(authority_result, Mapping):
            return authority_result
        model_dump = getattr(authority_result, "model_dump", None)
        if callable(model_dump):
            dumped = model_dump(mode="json")
            if isinstance(dumped, Mapping):
                return dumped
        raise ValueError("authority result must be an existing result mapping or model")

    @staticmethod
    def _authority_ref(authority: Mapping[str, Any]) -> str:
        for key in ("result_id", "authority_result_ref", "authority_event_ref", "settlement_id"):
            value = authority.get(key)
            if isinstance(value, str) and value:
                return value
        return ""

    @staticmethod
    def _authority_status(authority: Mapping[str, Any]) -> str:
        for key in ("settlement_status", "resolution_status", "status"):
            value = authority.get(key)
            if isinstance(value, str) and value:
                return value
        return ""

    @staticmethod
    def _is_accepted(status: str) -> bool:
        return status in {"accepted", "applied", "observed"}

    @staticmethod
    def _expected_state(candidate: CandidateActionObservation) -> str:
        for key in ("observed_state", "state", "target_state"):
            value = candidate.expected_observation.get(key)
            if isinstance(value, str):
                return value
        return ""

    def _failure(
        self,
        episode: EmbodiedEpisodeRecord,
        failure_class: EpisodeFailureClass,
        authority_ref: str,
        authority_status: str,
        post_capture_ref: str,
        observed_state: str,
        evidence_refs: tuple[str, ...],
    ) -> EmbodiedEpisodeRecord:
        return episode.model_copy(update={
            "authority_result_ref": authority_ref,
            "authority_status": authority_status,
            "post_capture_ref": post_capture_ref,
            "observed_state": observed_state,
            "outcome": "recovery_required",
            "failure_class": failure_class,
            "recovery_candidate": self.recovery_candidate(episode, failure_class),
            "evidence_refs": evidence_refs,
            "reobserve_required": failure_class in {"perception", "localization", "wrong_target", "stale_scene", "timeout", "observation_mismatch"},
        })

    @staticmethod
    def recovery_candidate(
        episode: EmbodiedEpisodeRecord,
        failure_class: EpisodeFailureClass,
    ) -> dict[str, object]:
        reobserve = failure_class in {"perception", "localization", "wrong_target", "stale_scene", "timeout", "observation_mismatch"}
        return {
            "policy_type": "recovery",
            "failure_class": failure_class,
            "target_ref": episode.candidate.target_ref,
            "semantic_action_id": episode.candidate.semantic_action_id,
            "next_observation_required": reobserve,
            "evidence_refs": list(episode.evidence_refs),
        }


__all__ = ["EmbodiedEpisodeService"]
