class CharacterTripleFilter:
    def evaluate_candidate(
        self,
        *,
        candidate: str,
        persona_ok: bool,
        logic_ok: bool,
        gain_loss_score: float,
        persona_notes: list[str] | None = None,
        logic_notes: list[str] | None = None,
        gain_loss_notes: list[str] | None = None,
    ) -> dict[str, object]:
        viability = "rejected"
        if persona_ok and logic_ok:
            if gain_loss_score >= 0.75:
                viability = "highly_compelling"
            elif gain_loss_score >= 0.5:
                viability = "viable"
            elif gain_loss_score >= 0.25:
                viability = "weakly_viable"
        return {
            "candidate": candidate,
            "persona_passed": persona_ok,
            "persona_notes": list(persona_notes or []),
            "logic_passed": logic_ok,
            "logic_notes": list(logic_notes or []),
            "gain_loss_score": gain_loss_score,
            "gain_loss_notes": list(gain_loss_notes or []),
            "viability": viability,
        }
