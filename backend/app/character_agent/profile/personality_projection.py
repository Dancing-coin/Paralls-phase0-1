from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final


PERSONALITY_PROJECTION_KEYS: Final[tuple[str, ...]] = (
    "social_approach_bias",
    "empathic_attunement",
    "analytical_control",
    "courage_bias",
    "strategic_planning",
    "manipulative_tendency",
    "conflict_deescalation_bias",
    "procedural_discipline",
    "public_assertion_bias",
    "avoidance_bias",
    "trust_repair_bias",
    "privacy_guard_bias",
    "stress_vulnerability",
)


class PersonalityProjectionResolver:
    def resolve(self, profile: Mapping[str, object] | None) -> dict[str, float]:
        source = profile if isinstance(profile, Mapping) else {}
        personality_layer = self._mapping(source.get("personality_layer"))
        facets = self._mapping(personality_layer.get("facets"))
        conversation = self._mapping(source.get("conversation_personality_layer"))
        temperament = self._mapping(source.get("temperament_response_layer"))

        openness = self._mapping(facets.get("openness"))
        conscientiousness = self._mapping(facets.get("conscientiousness"))
        extraversion = self._mapping(facets.get("extraversion"))
        agreeableness = self._mapping(facets.get("agreeableness"))
        neuroticism = self._mapping(facets.get("neuroticism"))
        baseline_temperament = self._mapping(temperament.get("baseline_temperament"))
        conflict_style = self._mapping(temperament.get("conflict_style"))
        trust_dynamics = self._mapping(temperament.get("trust_dynamics"))
        expression_bias = self._mapping(temperament.get("expression_bias"))

        empathic_attunement = self._weighted_sum(
            (
                (0.55, self._facet_or_legacy(agreeableness, "compassion", source, "empathy")),
                (0.20, self._value(agreeableness, "cooperativeness")),
                (0.15, self._value(openness, "ambiguity_tolerance")),
                (0.10, self._legacy_trait(source, "empathy")),
            )
        )
        social_approach_bias = self._weighted_sum(
            (
                (0.40, self._facet_or_legacy(extraversion, "social_energy", source, "sociability")),
                (0.25, self._value(extraversion, "warmth")),
                (0.20, self._value(conversation, "social_openness")),
                (0.15, self._value(agreeableness, "trust")),
            )
        )
        analytical_control = self._weighted_sum(
            (
                (
                    0.40,
                    self._facet_or_legacy(conscientiousness, "deliberation", source, "rationality"),
                ),
                (0.25, self._value(conscientiousness, "orderliness")),
                (0.20, self._value(openness, "ambiguity_tolerance")),
                (0.15, self._invert(self._value(neuroticism, "volatility"))),
            )
        )
        courage_bias = self._weighted_sum(
            (
                (0.35, self._invert(self._value(neuroticism, "anxiety"))),
                (0.25, self._value(extraversion, "assertiveness")),
                (0.20, self._value(conscientiousness, "persistence")),
                (0.20, self._value_commitment_strength(source)),
            )
        )
        if "courage" in self._mapping(source.get("trait_vector_layer")) and not personality_layer:
            courage_bias = self._weighted_sum(
                (
                    (0.60, self._legacy_trait(source, "courage")),
                    (0.40, courage_bias),
                )
            )

        strategic_planning = self._weighted_sum(
            (
                (
                    0.35,
                    self._facet_or_legacy(conscientiousness, "deliberation", source, "scheming"),
                ),
                (0.25, self._value(openness, "ambiguity_tolerance")),
                (0.20, analytical_control),
                (0.20, self._value(baseline_temperament, "impulse_control")),
            )
        )
        manipulative_tendency = self._weighted_sum(
            (
                (0.35, self._invert(self._value(agreeableness, "cooperativeness"))),
                (0.25, self._invert(self._value(agreeableness, "compassion"))),
                (0.20, self._value(baseline_temperament, "dominance")),
                (0.20, self._invert(self._value(conversation, "deception_control"))),
            )
        )
        if "scheming" in self._mapping(source.get("trait_vector_layer")) and not personality_layer:
            scheming = self._legacy_trait(source, "scheming")
            strategic_planning = self._weighted_sum(((0.70, scheming), (0.30, strategic_planning)))
            manipulative_tendency = self._weighted_sum(((0.45, scheming), (0.55, manipulative_tendency)))

        conflict_deescalation_bias = self._weighted_sum(
            (
                (0.35, self._value(agreeableness, "cooperativeness")),
                (0.30, self._facet_or_legacy(agreeableness, "compassion", source, "empathy")),
                (0.15, self._value(conflict_style, "mediation_tendency")),
                (0.10, self._value(baseline_temperament, "impulse_control")),
                (0.10, self._value(conversation, "deception_control")),
            )
        )
        procedural_discipline = self._weighted_sum(
            (
                (0.40, self._value(conscientiousness, "orderliness")),
                (0.25, self._value(conscientiousness, "dutifulness")),
                (
                    0.20,
                    self._facet_or_legacy(conscientiousness, "deliberation", source, "rationality"),
                ),
                (0.15, self._procedural_training_modifier(source)),
            )
        )
        stress_vulnerability = self._weighted_sum(
            (
                (0.45, self._value(neuroticism, "anxiety")),
                (0.25, self._value(neuroticism, "vulnerability")),
                (0.20, self._value(baseline_temperament, "emotional_reactivity")),
                (0.10, self._invert(self._value(baseline_temperament, "recovery_speed"))),
            )
        )
        public_assertion_bias = self._weighted_sum(
            (
                (0.35, self._value(extraversion, "assertiveness")),
                (0.25, self._value(baseline_temperament, "dominance")),
                (0.20, courage_bias),
                (0.20, self._invert(self._value(conversation, "privacy_sensitivity"))),
            )
        )
        avoidance_bias = self._weighted_sum(
            (
                (0.35, self._value(neuroticism, "anxiety")),
                (0.25, self._value(conflict_style, "avoidance_tendency")),
                (0.20, self._value(conversation, "privacy_sensitivity")),
                (0.20, self._invert(courage_bias)),
            )
        )
        trust_repair_bias = self._weighted_sum(
            (
                (0.30, self._facet_or_legacy(agreeableness, "compassion", source, "empathy")),
                (0.25, self._value(agreeableness, "trust")),
                (0.20, self._value(trust_dynamics, "forgiveness_threshold")),
                (0.15, self._value(baseline_temperament, "attachment")),
                (0.10, empathic_attunement),
            )
        )
        privacy_guard_bias = self._weighted_sum(
            (
                (0.40, self._value(conversation, "privacy_sensitivity")),
                (0.25, self._value(conscientiousness, "dutifulness")),
                (0.20, self._virtue_privacy_strength(source)),
                (
                    0.15,
                    self._first_available(
                        expression_bias,
                        "facial_control",
                        "expression_control",
                    ),
                ),
            )
        )

        return {
            "social_approach_bias": social_approach_bias,
            "empathic_attunement": empathic_attunement,
            "analytical_control": analytical_control,
            "courage_bias": courage_bias,
            "strategic_planning": strategic_planning,
            "manipulative_tendency": manipulative_tendency,
            "conflict_deescalation_bias": conflict_deescalation_bias,
            "procedural_discipline": procedural_discipline,
            "public_assertion_bias": public_assertion_bias,
            "avoidance_bias": avoidance_bias,
            "trust_repair_bias": trust_repair_bias,
            "privacy_guard_bias": privacy_guard_bias,
            "stress_vulnerability": stress_vulnerability,
        }

    def _mapping(self, value: object) -> Mapping[str, object]:
        return value if isinstance(value, Mapping) else {}

    def _value(self, source: Mapping[str, object], key: str, default: float = 0.5) -> float:
        return self._bounded_float(source.get(key), default)

    def _first_available(self, source: Mapping[str, object], *keys: str) -> float:
        for key in keys:
            if key in source:
                return self._value(source, key)
        return 0.5

    def _bounded_float(self, value: object, default: float = 0.5) -> float:
        if isinstance(value, bool):
            return default
        if isinstance(value, (int, float)):
            return self._clamp(float(value))
        return default

    def _invert(self, value: float) -> float:
        return self._clamp(1.0 - value)

    def _weighted_sum(self, parts: Sequence[tuple[float, float]]) -> float:
        return self._clamp(sum(weight * value for weight, value in parts))

    def _legacy_trait(
        self,
        profile: Mapping[str, object],
        key: str,
        default: float = 0.5,
    ) -> float:
        trait_vector = self._mapping(profile.get("trait_vector_layer"))
        return self._value(trait_vector, key, default)

    def _facet_or_legacy(
        self,
        facets: Mapping[str, object],
        facet_key: str,
        profile: Mapping[str, object],
        legacy_key: str,
    ) -> float:
        if facet_key in facets:
            return self._value(facets, facet_key)
        return self._legacy_trait(profile, legacy_key)

    def _procedural_training_modifier(self, profile: Mapping[str, object]) -> float:
        capabilities = self._mapping(profile.get("capability_constraint_layer"))
        skills = capabilities.get("skills", [])
        domains = capabilities.get("knowledge_domains", [])
        terms = self._lower_terms(skills) + self._lower_terms(domains)
        procedural_terms = ("procedure", "procedural", "protocol", "routine", "discipline")
        if any(term in item for item in terms for term in procedural_terms):
            return 0.7
        return 0.5

    def _value_commitment_strength(self, profile: Mapping[str, object]) -> float:
        values = self._mapping(profile.get("virtue_value_layer"))
        priorities = values.get("value_priorities", [])
        red_lines = values.get("red_lines", [])
        count = len(self._lower_terms(priorities)) + len(self._lower_terms(red_lines))
        if count >= 4:
            return 0.7
        if count >= 2:
            return 0.6
        return 0.5

    def _virtue_privacy_strength(self, profile: Mapping[str, object]) -> float:
        values = self._mapping(profile.get("virtue_value_layer"))
        terms = (
            self._lower_terms(values.get("value_priorities", []))
            + self._lower_terms(values.get("red_lines", []))
            + self._lower_terms(values.get("forbidden_behaviors", []))
        )
        if any(
            marker in item
            for item in terms
            for marker in ("privacy", "private", "secret", "confidence", "confidential")
        ):
            return 0.75
        return 0.5

    def _lower_terms(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).lower() for item in value if str(item)]

    def _clamp(self, value: float) -> float:
        return min(1.0, max(0.0, round(value, 6)))


def resolve_personality_projection(profile: Mapping[str, object] | None) -> dict[str, float]:
    return PersonalityProjectionResolver().resolve(profile)
