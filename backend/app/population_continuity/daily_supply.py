"""单分片日供给的固定纯计算；不读取或改变世界事实。"""
from app.models.social_model import (
    DAILY_SUPPLY_DIMENSIONS, DailySupplyReport, FrozenModelInput, ModelComputation, SocialModelTemplate,
)


def daily_supply_template() -> SocialModelTemplate:
    return SocialModelTemplate()


def calculate_daily_supply(inputs: FrozenModelInput, *, budget_units: int) -> ModelComputation:
    inputs = FrozenModelInput.model_validate(inputs)
    if type(budget_units) is not int or not 0 <= budget_units <= 100:
        raise ValueError("model_budget_invalid")
    data = inputs.data
    required = (data.qualification_confirmed, data.route_open, data.process_open,
                data.arrival_delay_ticks, data.deadline_tick)
    if any(value is None for value in required):
        return ModelComputation(status="context_insufficient", work_units=0,
            diagnostics=("required_context_unknown",))
    # 八个固定检查点各消耗一单位；预算不足不交付部分覆盖率。
    for used, _ in enumerate(DAILY_SUPPLY_DIMENSIONS):
        if used >= budget_units:
            return ModelComputation(status="budget_exhausted", work_units=used)
    reasons = []
    if not data.qualification_confirmed:
        reasons.append("qualification_denied")
    if not data.route_open:
        reasons.append("route_closed")
    if not data.process_open:
        reasons.append("process_closed")
    if inputs.vector.from_tick + data.arrival_delay_ticks > data.deadline_tick:
        reasons.append("deadline_missed")
    capacity = data.window_capacity_units * data.capacity_factor_bps // 10000
    base = 0 if reasons else min(data.confirmed_supply_units, capacity)
    low = base * data.delivery_ratio_bps[0] // 10000
    high = (base * data.delivery_ratio_bps[1] + 9999) // 10000
    demand_min, demand_max = data.demand_units
    if demand_max == 0:
        coverage = None
        reasons.append("not_required")
    elif high == 0:
        coverage = (0, 0)
    else:
        coverage = (min(10000, 10000 * low // demand_max),
            10000 if demand_min == 0 else min(10000, (10000 * high + demand_min - 1) // demand_min))
    shortage = high < demand_max
    if shortage:
        reasons.append("supply_shortfall")
    return ModelComputation(status="ok", work_units=8, report=DailySupplyReport(
        shard_ref=inputs.shard_ref, from_tick=inputs.vector.from_tick, to_tick=inputs.vector.to_tick,
        demand_units=data.demand_units, confirmed_supply_units=data.confirmed_supply_units,
        reachable_supply_units=(low, high), coverage_bps=coverage,
        blocking_reasons=tuple(sorted(set(reasons))),
        upgrade_categories=tuple(sorted(set(data.protected_categories))) if shortage else (),
        input_digest=inputs.vector.input_digest, source_revisions=inputs.vector.source_revisions,
        expiry_tick=min(inputs.vector.expiry_tick, *(card.expiry_tick for card in inputs.cards)),
    ))
