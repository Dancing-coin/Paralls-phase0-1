"""Stateless bakery reference composition over the four Econ-1 owners."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.gameplay.construction_production_runtime import ConstructionProductionAuthority, Facility, Plot, Recipe
from app.gameplay.recipe_production_family import RecipeProductionFailureIntent
from app.gameplay.econ1_economy_runtime import BusinessPeriod, EconomyAuthority, MarketQuote, PurchasePosting, SalePosting, WageAccrual
from app.gameplay.economy_runtime import EconomyAuthorityService, EconomyProjector
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.inventory_runtime import (
    ContainerSpec,
    InventoryAuthorityService,
    InventoryDefinitionRegistry,
    InventoryProjector,
    ItemDefinition,
)
from app.gameplay.organization_government_runtime import GovernmentAuthority, Organization, OrganizationAuthority, Permit, RoleAssignment, WorkerContributionRef
from app.gameplay.contract_runtime import ContractAuthorityService, ContractTermsDefinition, ContractTermsRegistry
from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.survival_runtime import NeedDefinition, NeedState, SurvivalAuthority, SurvivalMode, SurvivalPolicy


@dataclass(frozen=True)
class BakeryReferenceScenario:
    owner_character_ref: str
    organization: Organization
    facility: Facility
    recipe: Recipe
    permit: Permit
    employee_refs: tuple[str, ...] = ()
    period_count: int = 3
    periods: tuple[BusinessPeriod, ...] = field(default_factory=tuple)

    @classmethod
    def default(cls) -> "BakeryReferenceScenario":
        return cls(
            owner_character_ref="character:char_a",
            organization=Organization(organization_ref="org:bakery", jurisdiction_ref="jurisdiction:demo", owner_character_ref="character:char_a"),
            facility=Facility(facility_ref="facility:bakery", plot_ref="plot:bakery", facility_kind="bakery", condition=1),
            recipe=Recipe(
                recipe_ref="recipe:bread:v1",
                inputs={"flour": 2},
                output_item="bread",
                duration_ticks=1,
                failure_policy_mode="release",
                failure_policy_revision="policy:failure:release@1",
            ),
            permit=Permit(permit_ref="permit:bakery", organization_ref="org:bakery", policy_revision="policy:v1", expires_tick=100),
        )

    def with_employee(self, character_ref: str) -> "BakeryReferenceScenario":
        if not character_ref.startswith("character:"):
            raise ValueError("population_simulation_forbidden")
        OrganizationAuthority.assign_role(RoleAssignment(organization_ref=self.organization.organization_ref, character_ref=character_ref, role="employee"), existing_character_refs={character_ref})
        return self.__class__(**{**self.__dict__, "employee_refs": self.employee_refs + (character_ref,)})

    @staticmethod
    def existing_character_refs() -> frozenset[str]:
        """Return refs backed by the repository's existing character profile records.

        Gameplay composition must consume character records that already exist in the
        character-agent profile registry; it must not synthesize NPC state.
        """
        profile_dir = Path(__file__).resolve().parents[3] / "assets" / "characters" / "profiles"
        registry = CharacterProfileRegistry.from_directory(profile_dir)
        return frozenset(f"character:{actor_id}" for actor_id in registry.actor_ids())

    def with_existing_character_employee(self, character_ref: str) -> "BakeryReferenceScenario":
        """Add an employee only when the ref resolves to an existing profile record."""
        if character_ref not in self.existing_character_refs():
            raise ValueError("character_record_required")
        OrganizationAuthority.assign_role(
            RoleAssignment(
                organization_ref=self.organization.organization_ref,
                character_ref=character_ref,
                role="employee",
            ),
            existing_character_refs=set(self.existing_character_refs()),
        )
        return self.__class__(**{**self.__dict__, "employee_refs": self.employee_refs + (character_ref,)})

    def execute_period(
        self,
        sequence: int,
        *,
        survival_mode: SurvivalMode = SurvivalMode.DISABLED,
        store: GameplayEventStore | None = None,
        inject_production_failure: bool = False,
        failure_reason: str = "injected_production_failure",
    ) -> BusinessPeriod:
        if sequence < 1 or sequence > self.period_count:
            raise ValueError("period_out_of_range")
        # Validate all non-mutating period prerequisites before any owner append.
        if self.employee_refs:
            existing_refs = self.existing_character_refs()
            if any(ref not in existing_refs for ref in self.employee_refs):
                raise ValueError("character_record_required")
        if store is not None:
            GovernmentAuthority.require_permit(self.permit, tick=sequence, policy_revision=self.permit.policy_revision)
            self._validate_existing_period_inputs(store)
        run_ref = f"run:bakery:{sequence}"
        if store is None:
            run = ConstructionProductionAuthority.start_run(facility=self.facility, recipe=self.recipe, run_ref=run_ref, tick=sequence)
            ConstructionProductionAuthority.finish_run(run, tick=sequence + 1, recipe=self.recipe)
        else:
            government_authority = GovernmentAuthority(store=store)
            economy_authority = EconomyAuthority(store=store)
            self._require_result(
                ConstructionProductionAuthority(store=store).settle_facility_acquisition(
                    plot=Plot(
                        plot_ref=self.facility.plot_ref,
                        jurisdiction_ref=self.organization.jurisdiction_ref,
                        owner_ref=self.organization.organization_ref,
                    ),
                    facility=self.facility,
                    command_id=f"facility-acquire:{self.facility.facility_ref}",
                    idempotency_key=f"facility-acquire:{self.facility.facility_ref}",
                    causation_id=f"causation:facility:{self.facility.facility_ref}",
                    correlation_id=f"correlation:{self.organization.organization_ref}:facility",
                )
            )
            self._require_result(
                government_authority.settle_permit_verification(
                    permit=self.permit,
                    organization_ref=self.organization.organization_ref,
                    tick=sequence,
                    policy_revision=self.permit.policy_revision,
                    command_id=f"permit-verified:{self.permit.permit_ref}:{sequence}",
                    idempotency_key=f"permit-verified:{self.permit.permit_ref}:{sequence}",
                    causation_id=f"causation:permit:{sequence}",
                    correlation_id=f"correlation:{self.organization.organization_ref}:{sequence}",
                )
            )
            self._require_result(
                economy_authority.settle_purchase(
                    MarketQuote(
                        quote_ref="quote:flour:v1",
                        item_ref="flour",
                        unit_price=2,
                        quantity_limit=2,
                        valid_until_tick=100,
                        public_digest="quote:flour:v1:public",
                    ),
                    PurchasePosting(
                        posting_ref=f"purchase:bakery:{sequence}",
                        quote_ref="quote:flour:v1",
                        buyer_ref=self.organization.organization_ref,
                        quantity=2,
                        total_amount=4,
                    ),
                    tick=sequence,
                    command_id=f"purchase:{self.organization.organization_ref}:quote:flour:v1:{sequence}",
                    idempotency_key=f"purchase:{self.organization.organization_ref}:quote:flour:v1:{sequence}",
                    causation_id=f"causation:purchase:{sequence}",
                    correlation_id=f"correlation:{self.organization.organization_ref}:{sequence}",
                )
            )
            account_service = EconomyAuthorityService(store=store)
            self._ensure_accounts(store, account_service)
            self._require_result(
                account_service.transfer(
                    command_id=f"account-purchase:{sequence}",
                    debit_account_id="account:bakery",
                    credit_account_id="account:supplier",
                    amount=4,
                    idempotency_key=f"account-purchase:{sequence}",
                    causation_id=f"causation:purchase:{sequence}",
                    correlation_id=f"correlation:{self.organization.organization_ref}:{sequence}",
                )
            )
            inventory_service, inventory_registry = self._inventory_service(store)
            self._ensure_inventory_item(
                store=store,
                service=inventory_service,
                registry=inventory_registry,
                item_id=f"item:flour:{sequence}",
                definition_id="item:flour",
                quantity=2,
                command_id=f"inventory-input:{sequence}",
                causation_id=f"causation:purchase:{sequence}",
                correlation_id=f"correlation:{self.organization.organization_ref}:{sequence}",
            )
            reservation_ref = f"reservation:flour:{sequence}"
            self._require_result(
                inventory_service.reserve_item(
                    command_id=f"inventory-reserve:{run_ref}",
                    actor_ref=self.organization.organization_ref,
                    item_id=f"item:flour:{sequence}",
                    reservation_ref=reservation_ref,
                    quantity=self.recipe.inputs["flour"],
                    idempotency_key=f"inventory-reserve:{run_ref}",
                    causation_id=f"causation:{run_ref}",
                    correlation_id=f"correlation:{self.organization.organization_ref}:{sequence}",
                )
            )
            production_authority = ConstructionProductionAuthority(store=store)
            worker_contributions = tuple(
                WorkerContributionRef(
                    actor_ref=employee_ref,
                    assignment_ref=f"assignment:bakery:{employee_ref}",
                    work_order_ref=f"work:bakery:{sequence}",
                    evidence_refs=(),
                    contribution_digest=f"sha256:bakery-work:{sequence}:{employee_ref}",
                )
                for employee_ref in self.employee_refs
            )
            self._require_result(
                production_authority.settle_start_run(
                    facility=self.facility,
                    recipe=self.recipe,
                    run_ref=run_ref,
                    tick=sequence,
                    command_id=f"production-start:{run_ref}",
                    idempotency_key=f"production-start:{run_ref}",
                    causation_id=f"causation:{run_ref}",
                    correlation_id=f"correlation:{self.organization.organization_ref}:{sequence}",
                    reservation_refs=(reservation_ref,),
                    worker_contribution_refs=worker_contributions,
                )
            )
            if inject_production_failure:
                stream_id = f"gameplay:construction_production:{self.facility.facility_ref}"
                run_projection = production_authority.projector()
                run = run_projection.runs[run_ref]
                failure = production_authority.settle_recipe_production_failure(
                    intent=RecipeProductionFailureIntent(
                        facility_ref=self.facility.facility_ref,
                        run_ref=run_ref,
                        tick=sequence + 1,
                        expected_stream_revision=store.get_stream_head(stream_id),
                        expected_facility_revision=run_projection.facilities[self.facility.facility_ref].revision,
                        failure_reason=failure_reason,
                        command_id=f"production-failure:{run_ref}",
                        causation_id=f"causation:{run_ref}:failure",
                        correlation_id=f"correlation:{self.organization.organization_ref}:{sequence}",
                    )
                )
                self._require_result(failure)
                failed_period = BusinessPeriod(
                    period_ref=f"period:bakery:{sequence}:failed",
                    sequence=sequence,
                    policy_revision="policy:v1",
                    revenue=0,
                    cost=4,
                    tax=0,
                )
                self._require_result(
                    government_authority.settle_tax_assessment(
                        organization_ref=self.organization.organization_ref,
                        period_ref=failed_period.period_ref,
                        revenue=0,
                        rate=0.1,
                        policy_revision=failed_period.policy_revision,
                        command_id=f"tax-assessment:tax:{failed_period.period_ref}",
                        idempotency_key=f"tax-assessment:tax:{failed_period.period_ref}",
                        causation_id=f"causation:tax:{sequence}",
                        correlation_id=f"correlation:{self.organization.organization_ref}:{sequence}",
                    )
                )
                self._require_result(
                    economy_authority.settle_period_close(
                        failed_period,
                        command_id=f"period-close:{failed_period.period_ref}",
                        idempotency_key=f"period-close:{failed_period.period_ref}",
                        causation_id=f"causation:period:{sequence}",
                        correlation_id=f"correlation:{self.organization.organization_ref}:{sequence}",
                    )
                )
                return EconomyAuthority.close_period(failed_period)
            finish_result = production_authority.settle_finish_run(
                    production_authority.projector().runs[run_ref],
                    recipe=self.recipe,
                    tick=sequence + 1,
                    command_id=f"production-finish:{run_ref}",
                    idempotency_key=f"production-finish:{run_ref}",
                    causation_id=f"causation:{run_ref}",
                    correlation_id=f"correlation:{self.organization.organization_ref}:{sequence}",
                )
            self._require_result(finish_result)
            if self.employee_refs:
                account_service = EconomyAuthorityService(store=store)
                for employee_ref in self.employee_refs:
                    contract_service = self._contract_service(store)
                    self._require_result(
                        contract_service.create_contract(
                            command_id=f"contract-create:bakery-employment:{employee_ref}",
                            contract_id=f"contract:bakery-employment:{employee_ref}",
                            contract_type="simple_service",
                            terms_ref="terms:bakery:employment:v1",
                            party_refs=(self.organization.organization_ref, employee_ref),
                            idempotency_key=f"contract-create:bakery-employment:{employee_ref}",
                            causation_id="causation:bakery:employment",
                            correlation_id="correlation:bakery:employment",
                        )
                    )
                    self._ensure_account(
                        store,
                        account_service,
                        account_id=f"account:{employee_ref}",
                        owner_ref=employee_ref,
                        initial_balance=0,
                    )
                    contribution = next(value for value in worker_contributions if value.actor_ref == employee_ref)
                    evidence_result = production_authority.record_completed_work_evidence(
                        run_ref=run_ref,
                        contribution=contribution,
                        evidence_ref=f"evidence:production-completed:{run_ref}:{contribution.contribution_digest}",
                        observed_at=f"bakery-period-{sequence}",
                        command_id=f"work-evidence:{sequence}:{employee_ref}",
                        idempotency_key=f"work-evidence:{sequence}:{employee_ref}",
                        causation_id=f"causation:{run_ref}:work",
                        correlation_id=f"correlation:{self.organization.organization_ref}:{sequence}",
                    )
                    self._require_result(evidence_result)
                    evidence_ref = evidence_result.committed_event_ids[0]
                    accrual = WageAccrual(
                        accrual_ref=f"accrual:bakery:{sequence}:{employee_ref}",
                        organization_ref=self.organization.organization_ref,
                        payee_actor_ref=employee_ref,
                        work_evidence_refs=(evidence_ref,),
                        wage_policy_revision="policy:wage:bakery@1",
                        amount=1,
                        status="accrued",
                    )
                    self._require_result(
                        economy_authority.accrue_wage(
                            accrual,
                            completed_evidence_refs={evidence_ref},
                            command_id=f"wage-accrue:{sequence}:{employee_ref}",
                            idempotency_key=f"wage-accrue:{sequence}:{employee_ref}",
                            causation_id=f"causation:{run_ref}:wage",
                            correlation_id=f"correlation:{self.organization.organization_ref}:{sequence}",
                        )
                    )
                    self._require_result(
                        economy_authority.pay_wage(
                            accrual,
                            payer_account_id="account:bakery",
                            payee_account_id=f"account:{employee_ref}",
                            command_id=f"wage-pay:{sequence}:{employee_ref}",
                            idempotency_key=f"wage-pay:{sequence}:{employee_ref}",
                            causation_id=f"causation:{run_ref}:wage",
                            correlation_id=f"correlation:{self.organization.organization_ref}:{sequence}",
                        )
                    )
            self._require_result(
                inventory_service.consume_reservation(
                    command_id=f"inventory-consume:{run_ref}",
                    actor_ref=self.organization.organization_ref,
                    reservation_ref=reservation_ref,
                    idempotency_key=f"inventory-consume:{run_ref}",
                    causation_id=f"causation:{run_ref}",
                    correlation_id=f"correlation:{self.organization.organization_ref}:{sequence}",
                )
            )
            self._require_result(
                inventory_service.record_output_receipt(
                    command_id=f"inventory-output:{run_ref}",
                    actor_ref=self.organization.organization_ref,
                    source_ref=run_ref,
                    item_ref=self.recipe.output_item,
                    item_id=f"item:bread:{sequence}",
                    definition_id="item:bread",
                    container_id="container:bakery:stock",
                    quantity=1,
                    idempotency_key=f"inventory-output:{run_ref}",
                    causation_id=f"causation:{run_ref}",
                    correlation_id=f"correlation:{self.organization.organization_ref}:{sequence}",
                )
            )
            sale_reservation_ref = f"reservation:bread:{sequence}"
            self._require_result(
                inventory_service.reserve_item(
                    command_id=f"inventory-reserve-sale:{run_ref}",
                    actor_ref=self.organization.organization_ref,
                    item_id=f"item:bread:{sequence}",
                    reservation_ref=sale_reservation_ref,
                    quantity=1,
                    idempotency_key=f"inventory-reserve-sale:{run_ref}",
                    causation_id=f"causation:sale:{sequence}",
                    correlation_id=f"correlation:{self.organization.organization_ref}:{sequence}",
                )
            )
            self._require_result(
                inventory_service.consume_reservation(
                    command_id=f"inventory-consume-sale:{run_ref}",
                    actor_ref=self.organization.organization_ref,
                    reservation_ref=sale_reservation_ref,
                    idempotency_key=f"inventory-consume-sale:{run_ref}",
                    causation_id=f"causation:sale:{sequence}",
                    correlation_id=f"correlation:{self.organization.organization_ref}:{sequence}",
                )
            )
            self._require_result(
                economy_authority.settle_sale(
                    SalePosting(
                        posting_ref=f"sale:{self.organization.organization_ref}:{self.recipe.output_item}:{sequence + 1}",
                        seller_ref=self.organization.organization_ref,
                        item_ref=self.recipe.output_item,
                        quantity=1,
                        total_amount=10,
                        demand_digest="demand:aggregate:v1",
                    ),
                    command_id=f"sale:{self.organization.organization_ref}:{self.recipe.output_item}:{sequence + 1}",
                    idempotency_key=f"sale:{self.organization.organization_ref}:{self.recipe.output_item}:{sequence + 1}",
                    causation_id=f"causation:sale:{sequence}",
                    correlation_id=f"correlation:{self.organization.organization_ref}:{sequence}",
                )
            )
            self._require_result(
                account_service.transfer(
                    command_id=f"account-sale:{sequence}",
                    debit_account_id="account:demand",
                    credit_account_id="account:bakery",
                    amount=10,
                    idempotency_key=f"account-sale:{sequence}",
                    causation_id=f"causation:sale:{sequence}",
                    correlation_id=f"correlation:{self.organization.organization_ref}:{sequence}",
                )
            )
        period = BusinessPeriod(
            period_ref=f"period:bakery:{sequence}",
            sequence=sequence,
            policy_revision="policy:v1",
            revenue=10,
            cost=4 + len(self.employee_refs),
            tax=1,
        )
        if store is not None:
            self._require_result(
                government_authority.settle_tax_assessment(
                    organization_ref=self.organization.organization_ref,
                    period_ref=period.period_ref,
                    revenue=period.revenue,
                    rate=0.1,
                    policy_revision=period.policy_revision,
                    command_id=f"tax-assessment:tax:{period.period_ref}",
                    idempotency_key=f"tax-assessment:tax:{period.period_ref}",
                    causation_id=f"causation:tax:{sequence}",
                    correlation_id=f"correlation:{self.organization.organization_ref}:{sequence}",
                )
            )
        if survival_mode not in {SurvivalMode.DISABLED, SurvivalMode.NARRATIVE}:
            if store is None:
                SurvivalAuthority.tick(policy=SurvivalPolicy(policy_ref="survival:food", mode=survival_mode, revision="policy:v1"), definition=NeedDefinition(need_ref="need:food", category="food", decay_per_tick=.1), state=NeedState(need_ref="need:food", value=1, last_tick=sequence - 1), tick=sequence)
            else:
                self._require_result(
                    SurvivalAuthority(store=store).settle_tick(
                        actor_ref=self.owner_character_ref,
                        policy=SurvivalPolicy(policy_ref="survival:food", mode=survival_mode, revision="policy:v1"),
                        definition=NeedDefinition(need_ref="need:food", category="food", decay_per_tick=.1),
                        state=NeedState(need_ref="need:food", value=1, last_tick=sequence - 1),
                        tick=sequence,
                        command_id=f"survival:{self.owner_character_ref}:{sequence}",
                        idempotency_key=f"survival:{self.owner_character_ref}:{sequence}",
                        causation_id=f"causation:survival:{sequence}",
                        correlation_id=f"correlation:{self.owner_character_ref}:{sequence}",
                    )
                )
        if store is not None:
            self._require_result(
                economy_authority.settle_period_close(
                    period,
                    command_id=f"period-close:{period.period_ref}",
                    idempotency_key=f"period-close:{period.period_ref}",
                    causation_id=f"causation:period:{sequence}",
                    correlation_id=f"correlation:{self.organization.organization_ref}:{sequence}",
                )
            )
        return EconomyAuthority.close_period(period)

    def recover_failed_production(
        self,
        *,
        run_ref: str,
        store: GameplayEventStore,
    ) -> object:
        """Explicitly release a failed run's input reservation through Inventory."""
        production = ConstructionProductionAuthority(store=store).projector()
        run = production.runs.get(run_ref)
        if run is None or run.status not in {"released", "lost", "failed"}:
            raise ValueError("bakery_failed_run_required")
        inventory_service, _ = self._inventory_service(store)
        results = []
        for reservation_ref in run.reservation_refs:
            results.append(
                inventory_service.release_reservation(
                    command_id=f"inventory-release:{run_ref}:{reservation_ref}",
                    actor_ref=self.organization.organization_ref,
                    reservation_ref=reservation_ref,
                    idempotency_key=f"inventory-release:{run_ref}:{reservation_ref}",
                    causation_id=f"causation:{run_ref}:recovery",
                    correlation_id=f"correlation:{self.organization.organization_ref}:recovery",
                )
            )
        return results[0] if len(results) == 1 else tuple(results)

    @staticmethod
    def _require_result(result: object) -> None:
        committed = getattr(result, "committed", False)
        status = getattr(result, "idempotency_status", None)
        if not committed and status != "duplicate_replayed":
            raise RuntimeError("bakery_settlement_rejected")

    @staticmethod
    def _ensure_accounts(store: GameplayEventStore, service: EconomyAuthorityService) -> None:
        projection = EconomyProjector().rebuild(store.read_events())
        accounts = (
            ("account:bakery", "org:bakery", 100),
            ("account:supplier", "supplier:flour", 0),
            ("account:demand", "demand:aggregate", 100),
        )
        for account_id, owner_ref, initial_balance in accounts:
            if account_id in projection.accounts:
                continue
            result = service.open_account(
                command_id=f"account-open:{account_id}",
                account_id=account_id,
                owner_ref=owner_ref,
                currency_ref="currency:coin",
                initial_balance=initial_balance,
                idempotency_key=f"account-open:{account_id}",
                causation_id=f"causation:account-open:{account_id}",
                correlation_id="correlation:bakery:accounts",
            )
            BakeryReferenceScenario._require_result(result)
            projection = EconomyProjector().rebuild(store.read_events())

    @staticmethod
    def _contract_service(store: GameplayEventStore) -> ContractAuthorityService:
        terms = ContractTermsRegistry()
        terms.register(
            ContractTermsDefinition(
                "terms:bakery:employment:v1",
                "simple_service",
                2,
                "production-work",
            )
        )
        return ContractAuthorityService(store=store, terms_registry=terms, policy_authorities=set())

    @staticmethod
    def _ensure_account(
        store: GameplayEventStore,
        service: EconomyAuthorityService,
        *,
        account_id: str,
        owner_ref: str,
        initial_balance: int,
    ) -> None:
        projection = EconomyProjector().rebuild(store.read_events())
        if account_id in projection.accounts:
            return
        result = service.open_account(
            command_id=f"account-open:{account_id}",
            account_id=account_id,
            owner_ref=owner_ref,
            currency_ref="currency:coin",
            initial_balance=initial_balance,
            idempotency_key=f"account-open:{account_id}",
            causation_id=f"causation:account-open:{account_id}",
            correlation_id="correlation:bakery:accounts",
        )
        BakeryReferenceScenario._require_result(result)

    @staticmethod
    def _validate_existing_period_inputs(store: GameplayEventStore) -> None:
        """Reject known-invalid caller state before the first period append."""
        economy = EconomyProjector().rebuild(store.read_events())
        bakery_account = economy.accounts.get("account:bakery")
        if bakery_account is not None and bakery_account.balance < 4:
            raise ValueError("economy_insufficient_funds")
        registry = InventoryDefinitionRegistry()
        registry.register_item(ItemDefinition("item:flour", "v1", 1, 1))
        registry.register_item(ItemDefinition("item:bread", "v1", 1, 1))
        inventory = InventoryProjector(registry).rebuild("org:bakery", store.read_events())
        existing_flour = sum(
            item.quantity
            for item in inventory.items.values()
            if item.definition_id == "item:flour"
        )
        if any(item.quantity > 0 for item in inventory.items.values()) and existing_flour < 2:
            raise ValueError("inventory_reservation_insufficient")

    @staticmethod
    def _inventory_service(store: GameplayEventStore) -> tuple[InventoryAuthorityService, InventoryDefinitionRegistry]:
        registry = InventoryDefinitionRegistry()
        registry.register_item(ItemDefinition("item:flour", "v1", 1, 1))
        registry.register_item(ItemDefinition("item:bread", "v1", 1, 1))
        return InventoryAuthorityService(store=store, registry=registry), registry

    def _ensure_inventory_item(
        self,
        *,
        store: GameplayEventStore,
        service: InventoryAuthorityService,
        registry: InventoryDefinitionRegistry,
        item_id: str,
        definition_id: str,
        quantity: int,
        command_id: str,
        causation_id: str,
        correlation_id: str,
    ) -> None:
        stock_container = "container:bakery:stock"
        projection = InventoryProjector(registry).rebuild(self.organization.organization_ref, store.read_events())
        if stock_container not in projection.containers:
            self._require_result(
                service.create_container(
                    command_id="inventory-container:bakery",
                    actor_ref=self.organization.organization_ref,
                    spec=ContainerSpec(stock_container, 1000, 1000, 100),
                    idempotency_key="inventory-container:bakery",
                    causation_id="causation:inventory-container:bakery",
                    correlation_id="correlation:bakery:inventory",
                )
            )
            projection = InventoryProjector(registry).rebuild(self.organization.organization_ref, store.read_events())
        if item_id in projection.items:
            return
        self._require_result(
            service.instantiate(
                command_id=command_id,
                actor_ref=self.organization.organization_ref,
                item_id=item_id,
                definition_id=definition_id,
                quantity=quantity,
                container_id=stock_container,
                idempotency_key=command_id,
                causation_id=causation_id,
                correlation_id=correlation_id,
            )
        )

    def run_three_periods(
        self,
        *,
        survival_mode: SurvivalMode = SurvivalMode.DISABLED,
        store: GameplayEventStore | None = None,
    ) -> tuple[BusinessPeriod, ...]:
        return tuple(
            self.execute_period(index, survival_mode=survival_mode, store=store)
            for index in range(1, self.period_count + 1)
        )


__all__ = ["BakeryReferenceScenario"]
