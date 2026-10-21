# Authenticated World Admin Cadence Revocation Implementation Plan

> **For agentic workers:** Use the approved spec and implement task by task with test-driven development.

**Goal:** Connect a deployment-provisioned, named world-admin credential to the existing Durable cadence revocation owner.

**Architecture:** The FastAPI boundary authenticates a scoped service credential and passes a server-created identity into `RuntimeCadencePublisher` on the runtime execution thread. The publisher retains the original store and receipt contract and records the authenticated subject without storing credential material.

**Tech Stack:** Python, FastAPI, Pydantic, stdlib HMAC/SHA-256, existing GameplayEventStore and Harness.

**Spec:** `docs/superpowers/specs/2026-10-20-world-admin-cadence-revocation-design.md`

## Constraints

- Default-off without a configured credential; no reuse of launcher/session/controller credentials.
- No secret or secret digest in event, report, response, log, or model repr.
- Keep the existing `world_admin` event owner and Durable store; do not add a second authority store.
- Preserve user worktree changes and inherited prohibited verification ranges.

## Task 1: Credential source and verifier

Files: `backend/app/config.py`, `backend/app/services/world_admin_auth_service.py`, `backend/tests/test_world_admin_auth_service.py`.

1. Write failing tests for configured named principal/world/expiry, missing/wrong/short credentials, cross-world and expiry denial, and redacted serialization. Fresh subprocess validation failures from environment loading and nested child-bootstrap settings must not expose credential input in stderr.
2. Add strict `WorldAdminCredentialSettings` loaded from `WORLD_ADMIN_CREDENTIALS_JSON`, and a verifier with `authenticate(token, world_ref, now)` returning only identity metadata.
3. Run the focused tests and confirm zero authority writes for denial.

## Task 2: Durable owner and application boundary

Files: `backend/app/population_continuity/runtime_publication.py`, `backend/app/main.py`, `backend/app/services/runtime_asgi.py`, `backend/app/services/runtime_process.py`, `backend/tests/test_world_admin_cadence_revocation_application.py`, `backend/tests/test_runtime_asgi.py`.

1. Write failing tests for an authenticated HTTP request, default-off, TLS/loopback, invalid/cross-world/expired denial, real owner event identity, exact/changed retry and Durable reopen.
2. Expose the existing publisher through the application driver, authenticate before runtime submission, and append the server-derived identity metadata in `revoke_cadence()`.
3. Verify the existing Inventory owner rejects work after the committed revocation and no denied request writes.
4. Exercise the production ASGI parent and real spawn child: explicitly serialize nested hidden credentials in the existing bootstrap, rebuild the verifier after applying settings, allowlist the named HTTP route, and preserve the observed HTTP/HTTPS scheme. Verify configured/default-off startup and exact receipt replay across a fresh child on the same Durable path.
5. Hold the real runtime queue, then expire/remove/replace the authenticated credential before execution. Require a zero-write 403 from execution-time reauthentication. Keep the same identity pinned; do not silently substitute a replacement principal.

## Task 3: Evidence and documentation

Files: Task1/Task6 verifier allowlists, `docs/10月分析/规格/09-通用时间权限投影与领域服务接入规格.md`, corresponding plan 04, and stage-three closure.

1. Add exact regression selectors to the relevant explicit allowlists without widening claims.
2. Run focused tests, Task1 Inventory profile, Task6 and docs with external `--export-evidence`; inspect run revision and cleanup.
3. Record what the configured service-account path proves and what remains unverified, including live production provisioning and broad grant/revoke lifecycle.
