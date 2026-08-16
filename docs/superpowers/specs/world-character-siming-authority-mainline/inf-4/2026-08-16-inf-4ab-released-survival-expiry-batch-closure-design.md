# INF-4AB Released Survival Expiry Batch Closure

Status: `implemented and independently verified; second exact released-pending owner row`

`ContinuityMergeAuthority.merge_released_survival_state_expiry()` consumes only a released, project-scoped activation pending record and delegates the terminal write to the existing `SurvivalAuthority` fragment on `gameplay:survival:{profile_ref}`. Activation remains evidence-only and receipts stay separate append-derived records.

The closed admission pins profile, world, binding, obligation identity, policy revision, target revision, privacy and `due` state. Unknown, private, stale and terminal inputs are zero-write. This does not create a population truth owner, generic batch merge, branch promotion or complete group simulation.

Evidence: `infra-released-survival-expiry-batch-closure` independently proves
the existing Survival owner path, its distinct append-derived receipt boundary,
duplicate idempotency, revision/privacy/terminal zero-write, and
full/checkpoint-tail replay. The earlier `infra-activation-survival-expiry`
profile remains INF-2B evidence for the original activation-obligation row.
