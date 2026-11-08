from app.models.authority_event import AuthorityEvent
from app.models.fact_type import FACT_TYPE_REGISTRY, FactType, FactTypeRef
from app.models.siming_runtime_state import ObservedSimingEvent


class SimingObservePipeline:
    """司命观测管线：过滤并转换 Authority 事件为司命内部观测事件。

    NOTE: S2 断点（05-待决问题与缺陷登记.md 第四章断点清单）
    当前实现：字符串白名单过滤 event_type（过渡期方案）

    短期方案（Q2-A）：
      - ALLOWED_EVENT_TYPES 保持 frozenset 形式
      - 这些是 aggregated 顶层事件类型，不是 gameplay domain 细分事件
      - 与 S3 (authority_graph_projector) 对齐：都是字符串映射

    长期目标（Q2-C，Phase 2+）：
      - 改为 FactType 枚举订阅
      - 白名单换成 FactType → Siming visibility 契约声明
      - 与 main.py 的 "*" 订阅同步改造

    See: docs/reference/phase1-siming/Q1-Q2-decisions.md
    """

    ALLOWED_FACT_TYPES = frozenset({
        FactType.WORLD_FACT,
        FactType.VISUAL_FACT,
        FactType.ESM_RESULT,
        FactType.CHARACTER_BEHAVIOR,
        FactType.CONVERSATION_RESOLUTION,
        FactType.CONSTRAINT_STATE,
        FactType.POPULATION_CADENCE,
    })
    def observe(self, events: list[AuthorityEvent]) -> list[ObservedSimingEvent]:
        observed: list[ObservedSimingEvent] = []
        for event in events:
            fact_type = FACT_TYPE_REGISTRY.from_event_type(event.event_type)
            if fact_type not in self.ALLOWED_FACT_TYPES and not isinstance(fact_type, FactTypeRef):
                continue
            if not self._is_routed_to_siming(event):
                continue
            observed.append(ObservedSimingEvent.from_authority_event(event))
        return observed

    def _is_routed_to_siming(self, event: AuthorityEvent) -> bool:
        target_ids = {str(target_id) for target_id in event.routing.target_ids}
        if "siming" in target_ids:
            return True
        return event.routing.audience_mode == "broadcast"
