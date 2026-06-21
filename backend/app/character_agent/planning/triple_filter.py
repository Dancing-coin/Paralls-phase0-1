class CharacterTripleFilter:
    def evaluate_candidate(
        self,
        *,
        candidate: str,
        persona_ok: bool,
        logic_ok: bool,
        gain_loss_score: float,
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
            "logic_passed": logic_ok,
            "gain_loss_score": gain_loss_score,
            "viability": viability,
        }
