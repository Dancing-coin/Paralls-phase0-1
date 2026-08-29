from app.character_agent.models.cognition_update import CharacterCognitionUpdate
from app.character_agent.models.dynamic_state import CharacterDynamicState
from app.character_agent.models.event_memory import CharacterEventMemoryRecord
from app.character_agent.models.goal_runtime import (
    CharacterActiveGoalFrame,
    CharacterGoalHint,
    CharacterGoalStateRecord,
)
from app.character_agent.models.higher_order_memory import CharacterHigherOrderMemoryRecord
from app.character_agent.models.knowledge_memory import CharacterKnowledgeMemoryRecord
from app.character_agent.models.memory_record_bundle import CharacterMemoryRecordBundle
from app.character_agent.models.mind_frame import (
    CharacterMindFrame,
    CharacterMindFrameTrigger,
    CognitionWorkspace,
    L2InterpretationView,
    L3PlanningView,
    L4ExecutionView,
    MentalFactorProjectionCard,
    MindDeltaLedger,
    MindFrameLayer,
    MindFrameProvenance,
    WritebackView,
)
from app.character_agent.models.observation_memory import CharacterObservationMemoryRecord
from app.character_agent.models.social_memory import CharacterSocialMemoryRecord
from app.character_agent.models.working_memory_state import CharacterWorkingMemoryState
from app.character_agent.models.simulation_seed import CharacterContinuityCommand, CharacterContinuityReceipt, CharacterMemoryCandidate, CharacterMemoryMaterializationReceipt, CharacterSimulationSeedCandidate

__all__ = [
    "CharacterActiveGoalFrame",
    "CharacterCognitionUpdate",
    "CharacterDynamicState",
    "CharacterEventMemoryRecord",
    "CharacterGoalHint",
    "CharacterGoalStateRecord",
    "CharacterHigherOrderMemoryRecord",
    "CharacterKnowledgeMemoryRecord",
    "CharacterMemoryRecordBundle",
    "CharacterMindFrame",
    "CharacterMindFrameTrigger",
    "CharacterObservationMemoryRecord",
    "CharacterPrivateWorldSnapshot",
    "CharacterSocialMemoryRecord",
    "CharacterWorkingMemoryState",
    "CognitionWorkspace",
    "L2InterpretationView",
    "L3PlanningView",
    "L4ExecutionView",
    "MentalFactorProjectionCard",
    "MindDeltaLedger",
    "MindFrameLayer",
    "MindFrameProvenance",
    "WritebackView",
    "CharacterMemoryCandidate",
    "CharacterSimulationSeedCandidate",
    "CharacterContinuityCommand",
    "CharacterContinuityReceipt",
    "CharacterMemoryMaterializationReceipt",
]


def __getattr__(name: str) -> object:
    if name == "CharacterPrivateWorldSnapshot":
        from app.character_agent.models.private_world_snapshot import CharacterPrivateWorldSnapshot

        return CharacterPrivateWorldSnapshot
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
