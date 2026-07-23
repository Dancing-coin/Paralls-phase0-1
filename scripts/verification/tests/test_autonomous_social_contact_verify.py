from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from verify_autonomous_social_contact import _dialogue_source_preserves_agent_initiated_context


def test_dialogue_context_verifier_accepts_context_helper_call_contract() -> None:
    source = """
class DialogueService:
    def generate_utterance(self):
        return self._context(
            actor_id="char_a",
            control_mode="agent_initiated_utterance",
            intent_type="agent_initiated_utterance",
        )
"""

    assert _dialogue_source_preserves_agent_initiated_context(source) is True


def test_dialogue_context_verifier_rejects_generic_dialogue_context() -> None:
    source = """
class DialogueService:
    def generate_utterance(self):
        return self._context(
            actor_id="char_a",
            control_mode="dialogue_service",
            intent_type="dialogue_submit",
        )
"""

    assert _dialogue_source_preserves_agent_initiated_context(source) is False
