# Recovery And Resilience

RecoveryPolicy declares allowed state transitions, rate, threshold and terminal
behavior. Recovery never deletes history, fabricates compensation or reactivates
unrelated owners. Missing evidence, wrong stage, stale policy or changed
duplicate is zero-write.
