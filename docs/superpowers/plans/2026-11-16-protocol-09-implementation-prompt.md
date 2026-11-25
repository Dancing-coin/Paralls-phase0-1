# Protocol 09 完整 ESM 提案契约实施提示词

## 任务目标

将 **Protocol 09（司命与 ESM 协作协议）** 从单阶段直接请求升级到三阶段协商协议。

---

## 背景

**当前状态**：
- 司命发出 `siming.environment_request` → ESM 立即结算 → 返回 `esm_result_event`
- 无可行性预判，无协商空间，无法探测约束面

**目标架构**：
```
司命提案 → ESM 可行性评估（不执行）→ 司命决定 → 正式请求 → ESM 执行 → 结果
```

**关键约束**：
- ✅ 不依赖 Owner 重构（可立即开始）
- ✅ 必须向后兼容（保留旧路径）
- ✅ 可行性评估不能触发状态变更
- ✅ 全后端回归必须绿灯（10093+ passed）

---

## 实施计划

详见：`docs/superpowers/plans/2026-11-16-protocol-09-full-esm-proposal-contract.md`

---

## 具体任务

### Phase 1：数据模型（1-2 天）

**新增文件**：`backend/app/models/`

1. `environment_proposal.py`：
```python
from dataclasses import dataclass

@dataclass
class EnvironmentProposal:
    proposal_id: str
    candidate_ref: str
    decision_ref: str
    room_id: str
    scene_id: str
    zone_id: str
    target_environment_id: str
    goal: str  # "create_opportunity", "reduce_visibility", "increase_tension"
    requested_change_type: str  # "light_level_drop", "noise_level_rise", ...
    requested_strength: str  # "weak", "medium", "strong"
    constraints_known: list[str]
    fallback_options: list[dict]
    producer_ts: int
    causation_id: str
    correlation_id: str
```

2. `feasibility_response.py`：
```python
@dataclass
class FeasibilityResponse:
    response_id: str
    proposal_ref: str
    feasible: bool
    constraints: list[str]  # ["cooldown_active", "material_incompatible"]
    estimated_effect: dict  # {"light_level_drop": 0.2, "duration": 30}
    alternative_suggestions: list[dict]
    producer_ts: int
    causation_id: str
    correlation_id: str
```

3. `constraint_probe.py`：
```python
@dataclass
class ConstraintProbe:
    probe_id: str
    target_environment_id: str
    constraint_type: str  # "cooldown", "material", "spatial", "resource"
    producer_ts: int
    causation_id: str
    correlation_id: str
```

4. `esm_execution_state.py`：
```python
@dataclass
class ExecutionConfirmation:
    confirmation_id: str
    request_ref: str
    execution_state: str  # "confirmed", "partial", "aborted"
    rollback_token: str | None
    producer_ts: int
    causation_id: str
    correlation_id: str
```

**验收**：
- 每个模型有对应测试文件 `test_<model>.py`
- 序列化/反序列化测试通过
- 所有字段验证正确

---

### Phase 2：ESM 侧可行性评估（3-4 天）

**修改文件**：`backend/app/services/esm_service.py`

**新增方法**：

```python
class ESMService:
    def evaluate_proposal(
        self, proposal: EnvironmentProposal
    ) -> FeasibilityResponse:
        """评估提案可行性，不执行状态变更。
        
        检查内容：
        1. 目标环境是否存在
        2. 冷却时间是否满足
        3. 材质约束是否允许
        4. 资源是否充足
        5. 空间条件是否满足
        
        返回：
        - feasible=True：估算效果（不保证执行时一致）
        - feasible=False：约束说明 + 可选的替代方案
        """
        # 1. 查询当前环境状态（只读）
        env_state = self._get_environment_state(
            proposal.room_id, 
            proposal.target_environment_id
        )
        
        # 2. 检查冷却
        if self._is_on_cooldown(proposal.target_environment_id):
            return FeasibilityResponse(
                response_id=f"feasibility:{proposal.proposal_id}",
                proposal_ref=proposal.proposal_id,
                feasible=False,
                constraints=["cooldown_active"],
                estimated_effect={},
                alternative_suggestions=[],
                producer_ts=proposal.producer_ts,
                causation_id=proposal.causation_id,
                correlation_id=proposal.correlation_id,
            )
        
        # 3. 检查材质约束
        if not self._check_material_compatibility(
            env_state, proposal.requested_change_type
        ):
            return FeasibilityResponse(
                response_id=f"feasibility:{proposal.proposal_id}",
                proposal_ref=proposal.proposal_id,
                feasible=False,
                constraints=["material_incompatible"],
                estimated_effect={},
                alternative_suggestions=self._suggest_alternatives(proposal),
                producer_ts=proposal.producer_ts,
                causation_id=proposal.causation_id,
                correlation_id=proposal.correlation_id,
            )
        
        # 4. 估算效果（基于当前状态 + 历史数据）
        estimated_effect = self._estimate_effect(env_state, proposal)
        
        return FeasibilityResponse(
            response_id=f"feasibility:{proposal.proposal_id}",
            proposal_ref=proposal.proposal_id,
            feasible=True,
            constraints=[],
            estimated_effect=estimated_effect,
            alternative_suggestions=[],
            producer_ts=proposal.producer_ts,
            causation_id=proposal.causation_id,
            correlation_id=proposal.correlation_id,
        )
    
    def probe_constraints(
        self, probe: ConstraintProbe
    ) -> ConstraintStateResult:
        """返回当前约束面状态，不触发任何状态机。"""
        constraints = {}
        
        if probe.constraint_type in ("cooldown", "all"):
            constraints["cooldown"] = self._get_cooldown_state(
                probe.target_environment_id
            )
        
        if probe.constraint_type in ("material", "all"):
            constraints["material"] = self._get_material_constraints(
                probe.target_environment_id
            )
        
        if probe.constraint_type in ("resource", "all"):
            constraints["resource"] = self._get_resource_availability(
                probe.target_environment_id
            )
        
        return ConstraintStateResult(
            state_id=f"constraint_state:{probe.probe_id}",
            probe_ref=probe.probe_id,
            active_constraints=constraints,
            cooldown_remaining=constraints.get("cooldown", {}).get("remaining", 0),
        )
    
    def execute_with_confirmation(
        self, request: EnvironmentRequest
    ) -> tuple[ExecutionConfirmation, EnvironmentResult]:
        """执行请求并返回可回滚的确认令牌（Phase 2 可选）。"""
        # 当前版本：直接调用现有 resolve_environment_request
        # 未来版本：支持事务性回滚
        resolution, result = self.resolve_environment_request(request)
        
        confirmation = ExecutionConfirmation(
            confirmation_id=f"exec_confirm:{request.request_id}",
            request_ref=request.request_id,
            execution_state="confirmed" if resolution.success else "aborted",
            rollback_token=None,  # Phase 2: 实现快照 token
            producer_ts=request.producer_ts,
            causation_id=request.causation_id,
            correlation_id=request.correlation_id,
        )
        
        return confirmation, result
```

**验收**：
- `test_esm_proposal_evaluation.py`：
  - 可行提案返回 `feasible=True` + 估算效果
  - 冷却中提案返回 `feasible=False` + "cooldown_active"
  - 材质不兼容返回 `feasible=False` + "material_incompatible"
  - 探测不触发状态变更（前后状态一致）
  - 20 条测试用例

---

### Phase 3：司命侧决策循环（2-3 天）

**新增文件**：`backend/app/services/siming_proposal_tracker.py`

```python
from dataclasses import dataclass
from typing import Dict

@dataclass
class ProposalRecord:
    proposal_id: str
    output: SimingOutput
    submitted_at: int
    feasibility_response: FeasibilityResponse | None = None
    status: str = "pending"  # "pending", "feasible", "infeasible", "aborted", "executed"
    abort_reason: str | None = None

class SimingProposalTracker:
    """跟踪提案→可行性→请求的完整生命周期"""
    
    def __init__(self):
        self._proposals: Dict[str, ProposalRecord] = {}
    
    def register_proposal(
        self, proposal_id: str, output: SimingOutput, submitted_at: int
    ) -> None:
        self._proposals[proposal_id] = ProposalRecord(
            proposal_id=proposal_id,
            output=output,
            submitted_at=submitted_at,
        )
    
    def update_feasibility(self, response: FeasibilityResponse) -> None:
        record = self._proposals.get(response.proposal_ref)
        if record is None:
            return
        
        record.feasibility_response = response
        record.status = "feasible" if response.feasible else "infeasible"
    
    def should_proceed(self, proposal_id: str, current_ts: int) -> bool:
        """判断提案是否应该继续执行。
        
        条件：
        1. 提案存在且状态为 feasible
        2. 窗口未超时（< 5 秒）
        3. 可行性响应中的估算效果仍然有价值
        """
        record = self._proposals.get(proposal_id)
        if record is None or record.status != "feasible":
            return False
        
        # 检查窗口超时
        if current_ts - record.submitted_at > 5000:  # 5 秒窗口
            record.status = "aborted"
            record.abort_reason = "window_expired"
            return False
        
        # 检查估算效果是否仍有价值（可选：业务逻辑）
        # 例如：如果是为了创造机会，机会窗口是否仍开放
        
        return True
    
    def abort_proposal(self, proposal_id: str, reason: str) -> None:
        record = self._proposals.get(proposal_id)
        if record is None:
            return
        
        record.status = "aborted"
        record.abort_reason = reason
    
    def mark_executed(self, proposal_id: str) -> None:
        record = self._proposals.get(proposal_id)
        if record is None:
            return
        
        record.status = "executed"
    
    def cleanup_old_proposals(self, current_ts: int, max_age: int = 60000) -> None:
        """清理超过 1 分钟的旧提案"""
        to_remove = [
            pid for pid, record in self._proposals.items()
            if current_ts - record.submitted_at > max_age
        ]
        for pid in to_remove:
            del self._proposals[pid]
```

**修改文件**：`backend/app/services/siming_event_producer.py`

```python
class SimingEventProducer:
    def emit_environment_proposal(
        self, output: SimingOutput
    ) -> AuthorityEvent:
        """发出提案而非直接请求"""
        proposal_id = f"proposal:{output.producer_ts}:{output.causation_id}"
        proposal = EnvironmentProposal(
            proposal_id=proposal_id,
            candidate_ref=output.payload.get("candidate_ref", ""),
            decision_ref=output.payload.get("decision_ref", ""),
            room_id=output.room_id,
            scene_id=output.scene_id,
            zone_id=output.zone_id,
            target_environment_id=str(output.payload.get("target_environment_id", "")),
            goal=str(output.payload.get("goal", "create_opportunity")),
            requested_change_type=str(output.payload.get("requested_change_type", "")),
            requested_strength=str(output.payload.get("requested_strength", "medium")),
            constraints_known=list(output.payload.get("constraints_known", [])),
            fallback_options=list(output.payload.get("fallback_options", [])),
            producer_ts=output.producer_ts,
            causation_id=output.causation_id,
            correlation_id=output.correlation_id,
        )
        
        # 发布到总线
        event = AuthorityEvent(
            event_id=f"siming.environment_proposal:{proposal_id}",
            event_type="siming.environment_proposal",
            producer_ts=output.producer_ts,
            room_id=output.room_id,
            scene_id=output.scene_id,
            zone_id=output.zone_id,
            source=AuthorityEventSource(
                layer="L2", system="siming.orchestrator", actor_id=None
            ),
            routing=AuthorityEventRouting(
                audience_mode="targeted",
                routing_mode="event_type",
                target_ids=["esm"],
            ),
            priority=output.priority,
            ttl=output.ttl,
            durability=output.durability,
            causation_id=output.causation_id,
            correlation_id=output.correlation_id,
            payload=proposal.__dict__,
        )
        
        self._bus.publish(event)
        return event
```

**修改文件**：`backend/app/services/siming_runtime.py`

```python
class SimingRuntime:
    def __init__(self, ...):
        # 现有初始化
        self._proposal_tracker = SimingProposalTracker()
    
    def _handle_feasibility_response(
        self, response: FeasibilityResponse
    ) -> None:
        """收到可行性响应后，决定是否发出正式请求"""
        
        # 更新跟踪器
        self._proposal_tracker.update_feasibility(response)
        
        # 判断是否继续
        current_ts = int(time.time() * 1000)
        if not response.feasible:
            self._proposal_tracker.abort_proposal(
                response.proposal_ref, 
                f"infeasible: {', '.join(response.constraints)}"
            )
            return
        
        if not self._proposal_tracker.should_proceed(response.proposal_ref, current_ts):
            return
        
        # 发出正式请求
        self._emit_formal_request(response)
        self._proposal_tracker.mark_executed(response.proposal_ref)
    
    def _emit_formal_request(self, response: FeasibilityResponse) -> None:
        """基于可行性响应发出正式环境请求"""
        # 从跟踪器取回原始 output
        record = self._proposal_tracker._proposals.get(response.proposal_ref)
        if record is None:
            return
        
        output = record.output
        
        # 构造 EnvironmentRequest（复用现有逻辑）
        request = EnvironmentRequest(
            request_id=f"request:{response.proposal_ref}",
            room_id=output.room_id,
            scene_id=output.scene_id,
            zone_id=output.zone_id,
            source={"system": "siming", "proposal_ref": response.proposal_ref},
            target_entity_refs={"environment_ids": [str(output.payload.get("target_environment_id", ""))]},
            goal=str(output.payload.get("goal", "")),
            requested_change_type=str(output.payload.get("requested_change_type", "")),
            requested_strength=str(output.payload.get("requested_strength", "medium")),
            reason_tag="siming_environment_request",
            producer_ts=output.producer_ts,
            causation_id=output.causation_id,
            correlation_id=output.correlation_id,
        )
        
        # 通过 ESM service 执行（复用现有通道）
        resolution, environment_result = self._esm_service.resolve_environment_request(request)
        
        # 发布结果到总线（复用现有逻辑）
        self._publish_world_result_authority_event(resolution, source_event=request)
```

**验收**：
- `test_siming_proposal_lifecycle.py`：
  - 提案→可行→请求→结算 完整闭环
  - 提案→不可行→中止（不发请求）
  - 提案→可行但窗口已关闭→中止
  - 并发多个提案互不干扰
  - 15 条测试用例

---

### Phase 4：总线订阅与路由（1 天）

**修改文件**：`backend/app/main.py`

```python
# 司命侧订阅（新增）
authority_event_bus.subscribe(
    "siming.environment_proposal", 
    _handle_siming_environment_proposal
)
authority_event_bus.subscribe(
    "siming.constraint_probe", 
    _handle_siming_constraint_probe
)

# ESM 侧订阅（新增）
authority_event_bus.subscribe(
    "esm.feasibility_response", 
    _handle_esm_feasibility_response
)
authority_event_bus.subscribe(
    "esm.constraint_state", 
    _handle_esm_constraint_state
)

# 处理函数
def _handle_siming_environment_proposal(event: AuthorityEvent) -> None:
    """ESM 处理司命提案：评估可行性，不执行"""
    proposal = EnvironmentProposal(**event.payload)
    response = esm_service.evaluate_proposal(proposal)
    
    # 发布可行性响应
    response_event = AuthorityEvent(
        event_id=f"esm.feasibility_response:{response.response_id}",
        event_type="esm.feasibility_response",
        producer_ts=response.producer_ts,
        room_id=proposal.room_id,
        scene_id=proposal.scene_id,
        zone_id=proposal.zone_id,
        source=AuthorityEventSource(
            layer="L1", system="esm", actor_id=None
        ),
        routing=AuthorityEventRouting(
            audience_mode="targeted",
            routing_mode="event_type",
            target_ids=["siming"],
        ),
        priority="p1",
        ttl=None,
        durability="replayable",
        causation_id=response.causation_id,
        correlation_id=response.correlation_id,
        payload=response.__dict__,
    )
    authority_event_bus.publish(response_event)

def _handle_esm_feasibility_response(event: AuthorityEvent) -> None:
    """司命处理 ESM 可行性响应"""
    response = FeasibilityResponse(**event.payload)
    siming_runtime._handle_feasibility_response(response)

def _handle_siming_constraint_probe(event: AuthorityEvent) -> None:
    """ESM 处理约束探测"""
    probe = ConstraintProbe(**event.payload)
    result = esm_service.probe_constraints(probe)
    
    # 发布约束状态
    state_event = AuthorityEvent(
        event_id=f"esm.constraint_state:{result.state_id}",
        event_type="esm.constraint_state",
        producer_ts=probe.producer_ts,
        room_id=event.room_id,
        scene_id=event.scene_id,
        zone_id=event.zone_id,
        source=AuthorityEventSource(
            layer="L1", system="esm", actor_id=None
        ),
        routing=AuthorityEventRouting(
            audience_mode="targeted",
            routing_mode="event_type",
            target_ids=["siming"],
        ),
        priority="p1",
        ttl=None,
        durability="replayable",
        causation_id=probe.causation_id,
        correlation_id=probe.correlation_id,
        payload=result.__dict__,
    )
    authority_event_bus.publish(state_event)

def _handle_esm_constraint_state(event: AuthorityEvent) -> None:
    """司命处理约束状态（可选：用于优化决策）"""
    # Phase 2: 利用约束状态优化提案时机
    pass
```

**验收**：
- `test_protocol_09_full_integration.py`：
  - 端到端消息流转
  - 超时处理（提案 5 秒内未收到可行性响应）
  - 并发提案互不干扰
  - 10 条测试用例

---

### Phase 5：向后兼容（1 天）

**策略**：保留单阶段路径作为"快速通道"

**修改文件**：`backend/app/services/siming_event_producer.py`

```python
# 配置开关
SIMING_USE_PROPOSAL_PROTOCOL = os.getenv(
    "SIMING_USE_PROPOSAL_PROTOCOL", "true"
).lower() == "true"

class SimingEventProducer:
    def emit_environment_intervention(
        self, output: SimingOutput, *, use_proposal: bool | None = None
    ) -> AuthorityEvent:
        """统一入口：根据配置选择单阶段或三阶段协议"""
        if use_proposal is None:
            use_proposal = SIMING_USE_PROPOSAL_PROTOCOL
        
        if use_proposal:
            return self.emit_environment_proposal(output)
        else:
            # 旧路径：直接发请求
            return self._emit_direct_request(output)
    
    def _emit_direct_request(self, output: SimingOutput) -> AuthorityEvent:
        """单阶段直接请求（向后兼容）"""
        # 复用现有 _to_authority_event 逻辑
        event = self._to_authority_event(output)
        self._bus.publish(event)
        return event
```

**验收**：
- 旧测试全部通过（`test_siming_esm_protocol_stub.py` 等）
- 环境变量 `SIMING_USE_PROPOSAL_PROTOCOL=false` 时走旧路径
- 环境变量 `SIMING_USE_PROPOSAL_PROTOCOL=true` 时走新路径

---

## 验收标准

**必须通过**：
- [ ] 司命能发出 `siming.environment_proposal`
- [ ] ESM 能接收并返回 `esm.feasibility_response`
- [ ] 可行性评估不触发状态变更
- [ ] 不可行提案正确中止，不发正式请求
- [ ] 可行提案能转为 `siming.environment_request` 并执行
- [ ] 约束探测返回当前约束面，不触发副作用
- [ ] 全后端回归绿灯：`python -m pytest backend/tests/ -q` → **10093+ passed**
- [ ] 旧测试全部通过（向后兼容）

**性能要求**：
- 提案→可行性响应延迟 < 50ms
- 可行性评估 CPU 开销 < 正式执行的 10%

---

## 关键注意事项

1. **可行性评估必须是只读操作**：
   - 不能触发状态机
   - 不能修改环境参数
   - 不能消耗资源
   - 不能启动冷却

2. **提案生命周期管理**：
   - 超时 5 秒的提案自动中止
   - 定期清理超过 1 分钟的旧提案
   - 并发提案通过 `proposal_id` 隔离

3. **向后兼容**：
   - 保留旧路径作为快速通道
   - 默认启用新协议
   - 通过环境变量切换

4. **错误处理**：
   - 可行性响应超时 → 中止提案
   - ESM 不可用 → 降级到旧路径（可选）
   - 格式错误的提案 → 拒绝并记录

---

## 参考文档

- 实施计划：`docs/superpowers/plans/2026-11-16-protocol-09-full-esm-proposal-contract.md`
- 协议定义：`docs/reference/phase1-siming/09-司命与 ESM 协作协议.md`
- 司命架构：`.harness/SIMING-ARCHITECTURE.md`

---

## 提交要求

每完成一个 Phase：
1. 运行局部测试：`pytest backend/tests/test_<module>.py -v`
2. 提交：`git commit -m "feat(protocol-09): Phase N - <description>"`
3. Phase 5 完成后运行全后端回归：`pytest backend/tests/ -q`
4. 全部通过后推送：`git push origin main`

---

## 预期工作量

- Phase 1：1-2 天
- Phase 2：3-4 天
- Phase 3：2-3 天
- Phase 4：1 天
- Phase 5：1 天
- **总计**：8-11 天
