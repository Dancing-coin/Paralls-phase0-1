from __future__ import annotations

from econ1_profile_common import run_profile
from app.gameplay.bakery_reference_runtime import BakeryReferenceScenario
from app.gameplay.event_store import GameplayEventStore


def main() -> int:
    store = GameplayEventStore()
    periods = BakeryReferenceScenario.default().run_three_periods(store=store)
    event_types = [event.event_type for event in store.read_events()]
    return run_profile(name="econ1-economy-period-settlement", overall_key="overall_econ1_economy_period_settlement_passed", predecessor="econ1-survival-profile-report.json", checks={"three_periods": len(periods) == 3 and event_types.count("gameplay.economy.business_period_closed") == 3, "purchase_sale_postings": event_types.count("gameplay.economy.purchase_posted") == 3 and event_types.count("gameplay.economy.sale_posted") == 3, "account_transfers": event_types.count("gameplay.economy.account_debited") == 6 and event_types.count("gameplay.economy.account_credited") == 6, "fixed_policy": len({period.policy_revision for period in periods}) == 1})


if __name__ == "__main__":
    raise SystemExit(main())
