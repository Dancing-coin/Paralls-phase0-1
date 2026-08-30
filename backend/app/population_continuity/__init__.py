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
    PopulationWorldPlan,
    WorldModeProfile,
    WorldModeReceipt,
)
from .world import WorldContinuityRuntime
from .social_input import FrozenSocialPlanningInput, SocialInputValidation
from .source_inputs import HouseholdScheduleInput, OrganizationScheduleInput, FrozenSourceInput, SourceInputValidation
from .capability_input import CapabilityInputValidation, FrozenCapabilityEligibilityInput
from .siming_contracts import PopulationBatchReport, PopulationCadenceInput, PopulationCycleResult, PopulationOwnerReceipt, PopulationProjection, PopulationReadSet
from .owner_adapters import ScheduleGatedSupplyOwnerExecutor

__all__ = [
    "ProfileActivationAuthority",
    "PopulationPlanner",
    "CharacterSeedPlanner",
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
    "PopulationWorldPlan",
    "WorldModeProfile",
    "WorldModeReceipt",
    "FrozenSocialPlanningInput",
    "SocialInputValidation",
    "FrozenSourceInput",
    "HouseholdScheduleInput",
    "OrganizationScheduleInput",
    "SourceInputValidation",
    "CapabilityInputValidation",
    "FrozenCapabilityEligibilityInput",
    "PopulationCadenceInput",
    "PopulationProjection",
    "PopulationReadSet",
    "PopulationOwnerReceipt",
    "PopulationBatchReport",
    "PopulationCycleResult",
    "ScheduleGatedSupplyOwnerExecutor",
]


def __getattr__(name: str):
    if name == "CharacterSeedPlanner":
        from .seed_planner import CharacterSeedPlanner

        return CharacterSeedPlanner
    raise AttributeError(name)
