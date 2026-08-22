from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
from copy import deepcopy
from typing import Any


_POOL_NAMES = (
    "working_memory",
    "event_memories",
    "observation_memories",
    "knowledge_memories",
    "social_memories",
    "higher_order_memories",
)
_REF_PREFIXES = {
    "working_memory": "working",
    "event_memories": "event",
    "observation_memories": "observation",
    "knowledge_memories": "knowledge",
    "social_memories": "social",
    "higher_order_memories": "higher_order",
}
_TIME_KEYS = ("world_ts", "producer_ts", "event_index")
_TOKEN_RE = re.compile(r"[a-z0-9_:/.-]+", re.IGNORECASE)
_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "at",
        "be",
        "for",
        "gone",
        "happened",
        "is",
        "of",
        "the",
        "to",
        "understand",
        "what",
    }
)


@dataclass(frozen=True)
class MemoryRecallResult:
    memory: dict[str, list[dict[str, object]]]
    metadata: dict[str, object]


class CharacterMemoryRecallPolicy:
    """Select a bounded, auditable memory view for a model context.

    Storage remains complete and queryable. This policy only shapes the copy
    sent to cognition/planning, so truncation cannot become forgetting.
    """

    def __init__(self, *, pool_limit: int = 8, token_budget: int = 1200) -> None:
        if pool_limit < 1:
            raise ValueError("pool_limit must be positive")
        if token_budget < 1:
            raise ValueError("token_budget must be positive")
        self.pool_limit = pool_limit
        self.token_budget = token_budget

    def select(
        self,
        memory: dict[str, object],
        *,
        context: dict[str, object],
    ) -> MemoryRecallResult:
        normalized = {
            key: [deepcopy(item) for item in value if isinstance(item, dict)]
            if isinstance(value, list)
            else []
            for key, value in memory.items()
        }
        for key in _POOL_NAMES:
            normalized.setdefault(key, [])
        if not normalized["knowledge_memories"] and normalized.get("relational_memories"):
            normalized["knowledge_memories"] = self._knowledge_from_relational(
                normalized["relational_memories"]
            )

        terms = self._context_terms(context)
        candidates: list[tuple[float, str, str, dict[str, object]]] = []
        selected_by_pool: dict[str, list[dict[str, object]]] = {}
        for pool in _POOL_NAMES:
            ranked = sorted(
                (
                    (
                        self._score(entry, terms=terms, max_timestamp=self._max_timestamp(normalized[pool])),
                        self._timestamp(entry),
                        str(entry.get("memory_id", "") or entry.get("event_id", "") or ""),
                        entry,
                    )
                    for entry in normalized[pool]
                ),
                key=lambda item: (-item[0], -item[1], item[2]),
            )
            selected = ranked[: self.pool_limit]
            selected_by_pool[pool] = [deepcopy(item[3]) for item in selected]
            candidates.extend(
                (score, pool, memory_id, deepcopy(entry))
                for score, _timestamp, memory_id, entry in selected
            )

        candidates.sort(key=lambda item: (-item[0], -self._timestamp(item[3]), item[2]))
        kept_ids: set[tuple[str, str]] = set()
        estimated_tokens = 0
        truncated = False
        for score, pool, memory_id, entry in candidates:
            entry_tokens = self._estimate_tokens(entry)
            if estimated_tokens + entry_tokens > self.token_budget:
                truncated = True
                continue
            kept_ids.add((pool, memory_id))
            estimated_tokens += entry_tokens

        result_memory: dict[str, list[dict[str, object]]] = {}
        selected_refs: list[str] = []
        for pool in _POOL_NAMES:
            entries = [
                entry
                for entry in selected_by_pool[pool]
                if (pool, self._memory_id(entry)) in kept_ids
            ]
            result_memory[pool] = entries
            selected_refs.extend(
                f"{_REF_PREFIXES[pool]}:{self._memory_id(entry)}"
                for entry in entries
                if self._memory_id(entry)
            )

        # Keep compatibility aliases synchronized with the selected pools.
        if "episodic_memories" in normalized:
            result_memory["episodic_memories"] = deepcopy(result_memory["event_memories"])
        if "relational_memories" in normalized:
            result_memory["relational_memories"] = self._legacy_relational(
                result_memory["knowledge_memories"]
            )

        metadata = {
            "context_hash": self._context_hash(context),
            "selected_memory_refs": selected_refs,
            "selected_counts": {
                pool: len(result_memory[pool]) for pool in _POOL_NAMES
            },
            "pool_limit": self.pool_limit,
            "token_budget": self.token_budget,
            "estimated_tokens": estimated_tokens,
            "truncated": truncated or any(
                len(normalized[pool]) > len(result_memory[pool]) for pool in _POOL_NAMES
            ),
            "attention_targets": self._context_values(context, "attention_targets"),
            "goal_terms": self._context_values(context, "goal_terms"),
        }
        return MemoryRecallResult(memory=result_memory, metadata=metadata)

    def _score(
        self,
        entry: dict[str, object],
        *,
        terms: tuple[str, ...],
        max_timestamp: int,
    ) -> float:
        haystack = self._flatten_text(entry).lower()
        matches = sum(1 for term in terms if term in haystack)
        relevance = min(1.0, matches / max(1, len(terms))) if terms else 0.0
        recency = self._timestamp(entry) / max_timestamp if max_timestamp > 0 else 0.0
        certainty = self._numeric(entry, "confidence", "certainty_score")
        clarity = self._numeric(entry, "clarity_score", "salience_score")
        tension = self._numeric(entry, "unresolved_tension")
        salience = max(clarity, tension)
        return 0.75 * relevance + 0.1 * recency + 0.1 * certainty + 0.05 * salience

    def _context_terms(self, context: dict[str, object]) -> tuple[str, ...]:
        values: list[str] = []
        for key in ("snapshot", "event", "current_goal_state", "interpretation"):
            self._collect_context_strings(context.get(key), values)
        self._collect_context_strings(context.get("attention_targets"), values)
        self._collect_context_strings(context.get("goal_terms"), values)
        terms: list[str] = []
        for value in values:
            lowered = value.strip().lower()
            if lowered and lowered not in terms and not _TOKEN_RE.fullmatch(lowered):
                terms.append(lowered)
            for token in _TOKEN_RE.findall(lowered):
                if len(token) >= 2 and token not in _STOP_WORDS and token not in terms:
                    terms.append(token)
        return tuple(terms)

    def _collect_context_strings(self, value: object, output: list[str]) -> None:
        if isinstance(value, str):
            if value:
                output.append(value)
            return
        if isinstance(value, dict):
            for item in value.values():
                self._collect_context_strings(item, output)
            return
        if isinstance(value, list):
            for item in value:
                self._collect_context_strings(item, output)

    def _context_values(self, context: dict[str, object], key: str) -> list[str]:
        values: list[str] = []
        self._collect_context_strings(context.get(key), values)
        return list(dict.fromkeys(values))

    def _context_hash(self, context: dict[str, object]) -> str:
        relevant = {
            key: context.get(key)
            for key in ("snapshot", "event", "current_goal_state", "interpretation", "attention_targets", "goal_terms")
            if key in context
        }
        encoded = json.dumps(relevant, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def _flatten_text(self, value: object) -> str:
        values: list[str] = []
        self._collect_context_strings(value, values)
        return " ".join(values)

    def _max_timestamp(self, entries: list[dict[str, object]]) -> int:
        return max((self._timestamp(entry) for entry in entries), default=0)

    def _timestamp(self, entry: dict[str, object]) -> int:
        return max((int(entry.get(key, 0) or 0) for key in _TIME_KEYS), default=0)

    def _memory_id(self, entry: dict[str, object]) -> str:
        return str(entry.get("memory_id", "") or entry.get("event_id", "") or entry.get("source_event_id", ""))

    def _numeric(self, entry: dict[str, object], *keys: str) -> float:
        values = [entry.get(key) for key in keys]
        numeric = [float(value) for value in values if isinstance(value, (int, float)) and not isinstance(value, bool)]
        return max(0.0, min(1.0, max(numeric, default=0.0)))

    def _estimate_tokens(self, entry: dict[str, object]) -> int:
        encoded = json.dumps(entry, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
        return max(1, math.ceil(len(encoded) / 4))

    def _legacy_relational(self, entries: list[dict[str, object]]) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        for entry in entries:
            key = str(entry.get("proposition_key", "") or "")
            if not key.startswith("social:"):
                continue
            parts = key.split(":", 2)
            if len(parts) != 3 or not parts[1] or not parts[2]:
                continue
            proposition = str(entry.get("proposition", "") or "")
            prefix = f"{parts[1]}:{parts[2]}="
            value = proposition[len(prefix):] if proposition.startswith(prefix) else proposition
            result.append(
                {
                    "entity_id": parts[1],
                    "belief_type": parts[2],
                    "value": value,
                    "source_event_id": str(entry.get("source_event_id", "") or ""),
                    "producer_ts": int(entry.get("producer_ts", 0) or 0),
                }
            )
        return result

    def _knowledge_from_relational(self, entries: list[dict[str, object]]) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        for entry in entries:
            entity_id = str(entry.get("entity_id", "") or "")
            belief_type = str(entry.get("belief_type", "") or "")
            if not entity_id or not belief_type:
                continue
            value = str(entry.get("value", "") or "")
            result.append(
                {
                    **deepcopy(entry),
                    "memory_id": str(entry.get("memory_id", "") or f"relation:{entity_id}:{belief_type}"),
                    "proposition_key": f"social:{entity_id}:{belief_type}",
                    "proposition": f"{entity_id}:{belief_type}={value}",
                    "confidence": float(entry.get("confidence", 0.65) or 0.65),
                }
            )
        return result


__all__ = ["CharacterMemoryRecallPolicy", "MemoryRecallResult"]
