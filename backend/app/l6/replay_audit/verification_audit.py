from app.verification_audit import evaluate_phase0_audit, evaluate_phase1_slice_audit


class VerificationAuditEntry:
    evaluate_phase0_audit = staticmethod(evaluate_phase0_audit)
    evaluate_phase1_slice_audit = staticmethod(evaluate_phase1_slice_audit)


__all__ = ["VerificationAuditEntry"]
