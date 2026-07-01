from enum import Enum


class KnowledgeState(str, Enum):
    NOTICED = "noticed"
    SUSPECTED = "suspected"
    TENTATIVELY_BELIEVED = "tentatively_believed"
    BELIEVED = "believed"
    HIGH_CONFIDENCE_BELIEVED = "high_confidence_believed"
    DISPUTED = "disputed"
    ABANDONED = "abandoned"
