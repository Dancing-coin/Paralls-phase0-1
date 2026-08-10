"""Governed profile-backed population continuity adapters for Phase Three."""

from .activation import ProfileActivationAuthority
from .batch import ContinuityMergeAuthority, PopulationPlanner
from .models import (
    ActivationGrant,
    ActivationProposal,
    ActivationReceipt,
    BatchIntentCandidate,
    ContinuityMergeReceipt,
    DueEvaluationReceipt,
    MergeRejection,
    PopulationBatchPlan,
    WorldModeProfile,
    WorldModeReceipt,
)
from .world import WorldContinuityRuntime

__all__ = [
    "ProfileActivationAuthority",
    "PopulationPlanner",
    "ContinuityMergeAuthority",
    "WorldContinuityRuntime",
    "ActivationGrant",
    "ActivationProposal",
    "ActivationReceipt",
    "BatchIntentCandidate",
    "ContinuityMergeReceipt",
    "DueEvaluationReceipt",
    "MergeRejection",
    "PopulationBatchPlan",
    "WorldModeProfile",
    "WorldModeReceipt",
]
