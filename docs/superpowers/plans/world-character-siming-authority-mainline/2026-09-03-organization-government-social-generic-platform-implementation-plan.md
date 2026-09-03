# Organization / Government / Social Generic Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Author the approved federated Organization/Government/Social generic platform docs.

**Architecture:** The master spec defines the owner federation, closed families,
v3/2.0 compatibility, and explicit materialization rules. The subsystem docs
each bind one closed family to one owner/state-machine/stream slice. No
runtime, manifest, catalog, test, or harness changes are part of this plan.

**Tech Stack:** Markdown.

**Spec:** `docs/superpowers/specs/world-character-siming-authority-mainline/2026-09-03-organization-government-social-generic-platform-design.md`

## Global Constraints

- Organization, Government, and Social remain separate owners.
- Population is signal-only; explicit materialization only.
- Precompiled owner recipes only; no generic writer, router, or coordinator.
- Preserve read-only compatibility for existing narrow rows.
- Do not touch runtime, manifests, catalog, tests, or harness.

---

### Task 1: Master spec and tree README

**Files:**
- Create: `docs/superpowers/specs/world-character-siming-authority-mainline/2026-09-03-organization-government-social-generic-platform-design.md`
- Create: `docs/superpowers/specs/world-character-siming-authority-mainline/organization-government-social-generic/README.md`

**Produce:**
- one master design that names the federated owners, the closed families, the v3/2.0 contract, the explicit materialization rule, and the no-mega-owner boundary
- one short tree README that points to the subsystem docs

- [ ] Write the master design sections for purpose, architecture, global constraints, family portfolio, and acceptance
- [ ] Write the tree README with the nine subsystem entries and the master spec link

### Task 2: Organization family docs

**Files:**
- Create: `docs/superpowers/specs/world-character-siming-authority-mainline/organization-government-social-generic/organization-membership-roster-and-role-state.md`
- Create: `docs/superpowers/specs/world-character-siming-authority-mainline/organization-government-social-generic/organization-work-window-and-assignment-state.md`

**Produce:**
- one doc for organization membership/roster/role state
- one doc for organization work windows, assignment, and completion state

- [ ] Write the organization membership doc with owner boundary, state machine, streams, and compatibility
- [ ] Write the organization work-window doc with owner boundary, state machine, streams, and compatibility

### Task 3: Government family docs

**Files:**
- Create: `docs/superpowers/specs/world-character-siming-authority-mainline/organization-government-social-generic/government-policy-permit-and-inspection-state.md`
- Create: `docs/superpowers/specs/world-character-siming-authority-mainline/organization-government-social-generic/government-notice-resolution-and-acknowledgment-state.md`

**Produce:**
- one doc for policy/permit/inspection
- one doc for notice/acknowledgment/resolution

- [ ] Write the government policy doc with exact stream and state-machine boundaries
- [ ] Write the government notice doc with exact stream and state-machine boundaries

### Task 4: Social, population, and cross-cutting docs

**Files:**
- Create: `docs/superpowers/specs/world-character-siming-authority-mainline/organization-government-social-generic/social-relationship-reputation-and-knowledge-state.md`
- Create: `docs/superpowers/specs/world-character-siming-authority-mainline/organization-government-social-generic/social-shared-expression-attendance-and-visibility-state.md`
- Create: `docs/superpowers/specs/world-character-siming-authority-mainline/organization-government-social-generic/population-signal-and-explicit-materialization-state.md`
- Create: `docs/superpowers/specs/world-character-siming-authority-mainline/organization-government-social-generic/precompiled-owner-recipe-catalog-and-settlement-bridge.md`
- Create: `docs/superpowers/specs/world-character-siming-authority-mainline/organization-government-social-generic/compatibility-replay-and-projection-boundary.md`

**Produce:**
- one social relationship/knowledge doc
- one social shared-expression/attendance doc
- one population signal/materialization doc
- one precompiled recipe bridge doc
- one compatibility and replay doc

- [ ] Write the social relationship doc with public-fact and projection boundaries
- [ ] Write the social shared-expression doc with visibility and participation boundaries
- [ ] Write the population doc with signal-only and explicit-materialization rules
- [ ] Write the recipe bridge doc with pinned recipes and no generic router
- [ ] Write the compatibility doc with read-only baselines and replay expectations

### Task 5: Validation

**Files:**
- Validate only the docs created in this plan

**Produce:**
- whitespace-free markdown
- path coverage for the new subtree

- [ ] Run `git diff --check` against the new docs paths
- [ ] Confirm the new subtree files exist and match the intended names
