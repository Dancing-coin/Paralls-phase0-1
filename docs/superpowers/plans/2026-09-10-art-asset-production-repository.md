# Art Asset Production Repository Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a standalone Git repository for Blender-based production of Paralls art assets and connect it to the current Godot repository through an explicit, machine-readable documentation index.

**Architecture:** `paralls-art-assets` owns editable Blender sources, production references, export packages, and asset manifests. `paralls-phase-0-demo` remains the runtime authority: it consumes only an explicitly staged package under `assets/active/`, runs character/environment qualification, and never scans the production repository as a Godot project. The connection is a documented sibling-repository contract plus a snapshot of the current archived asset inventory.

**Tech Stack:** Git, Markdown, JSON, Blender source files/GLB exports, Godot 4.6 qualification scenes, existing Python verification tools.

**Spec:** `docs/art-asset-qualification-requirements.md`, `docs/art-resource-swap-workflow.md`, `docs/blender-godot-asset-export-convention.md`

## Global Constraints

- Keep `Unified3DIntegrationValidation` resource-independent and generic.
- Preserve all existing assets in the current repository's `archive/`; do not delete or rewrite them.
- Do not copy `project.godot`, `.godot/`, backend code, or Godot plugins into the production repository.
- Treat `assets/active/` as explicit staging only; an exported pack is not approved until qualification reports pass.
- A v1 ordinary humanoid rig is valid without finger, facial, eye, or FACS bones.
- Gameplay collision and world truth remain runtime-owned, not Blender-model-owned.

### Task 1: Create the production repository

**Files:**
- Create: `../paralls-art-assets/.gitignore`
- Create: `../paralls-art-assets/.gitattributes`
- Create: `../paralls-art-assets/AGENTS.md`
- Create: `../paralls-art-assets/README.md`
- Create: `../paralls-art-assets/production/README.md`
- Create: `../paralls-art-assets/exports/README.md`

**Interfaces:**
- Produces a standalone Git repository with a clear source/export boundary for Blender work.
- Later tasks place requirements, references, and templates into this repository.

- [ ] **Step 1:** Create the repository directory and initialize Git with `main` as the initial branch.
- [ ] **Step 2:** Add repository guidance stating that Blender production is local-art-authoring only and Godot remains the runtime authority.
- [ ] **Step 3:** Add directory conventions for `production/`, `references/`, `templates/`, and versioned `exports/`.
- [ ] **Step 4:** Verify `git status` and repository root identity.

### Task 2: Add production guidance and qualification references

**Files:**
- Create: `../paralls-art-assets/references/current-project-asset-index.md`
- Copy snapshot: `../paralls-art-assets/references/art-asset-qualification-requirements.md`
- Copy snapshot: `../paralls-art-assets/references/art-resource-swap-workflow.md`
- Copy snapshot: `../paralls-art-assets/references/blender-godot-asset-export-convention.md`
- Copy snapshot: `../paralls-art-assets/references/asset-injection-guide.md`
- Copy snapshot: `../paralls-art-assets/references/assets-policy.md`
- Copy snapshot: `../paralls-art-assets/references/character-asset-integration.md`
- Copy snapshot: `../paralls-art-assets/references/character-action-asset-interface.md`
- Copy snapshot: `../paralls-art-assets/references/current-project-asset-inventory.json`

**Interfaces:**
- Documents the current project path, default scene, archive locations, candidate packs, and qualification entry points.
- Snapshots are references for asset authors; the current Godot repository remains the runtime integration source of truth.

- [ ] **Step 1:** Copy the existing qualification and integration guidance without modifying its current-repository meaning.
- [ ] **Step 2:** Write the asset index with exact sibling path, pack IDs, archive status, and handoff path.
- [ ] **Step 3:** Record that existing Crusader Knight, throne-room, Astra, and apartment resources are references/candidates, not approved deliverables.
- [ ] **Step 4:** Verify every referenced current-repository path exists or is explicitly marked as a generated/staging path.

### Task 3: Add Blender authoring and export templates

**Files:**
- Create: `../paralls-art-assets/production/character-pack-guide.md`
- Create: `../paralls-art-assets/production/environment-pack-guide.md`
- Create: `../paralls-art-assets/production/prop-ui-audio-guide.md`
- Create: `../paralls-art-assets/templates/character-pack-manifest.json`
- Create: `../paralls-art-assets/templates/environment-pack-manifest.json`
- Create: `../paralls-art-assets/templates/prop-pack-manifest.json`
- Create: `../paralls-art-assets/templates/export-report.md`
- Create: `../paralls-art-assets/templates/scene-binding.md`

**Interfaces:**
- GPT-6/Blender work starts from the production guides and fills the manifests before export.
- The Godot repository can consume a versioned export directory after explicit staging.

- [ ] **Step 1:** Define units, transforms, naming, material/texture packaging, collision separation, and GLB export rules.
- [ ] **Step 2:** Define v1 character rig/action requirements, including ordinary rig acceptance and optional root motion.
- [ ] **Step 3:** Define environment anchors, collision, navigation, state fixtures, and visibility sampling requirements.
- [ ] **Step 4:** Define asset IDs, versioning, manifest fields, and rejection conditions.
- [ ] **Step 5:** Verify all templates are valid JSON or Markdown and contain no ambiguous placeholder requirements.

### Task 4: Connect both repositories

**Files:**
- Create: `docs/art-asset-production-repository.md`
- Modify: `docs/INDEX.md`
- Create: `art-assets-repository.json`

**Interfaces:**
- `art-assets-repository.json` is the machine-readable link from the Godot repository to the sibling production repository.
- `docs/art-asset-production-repository.md` explains the handoff and qualification sequence.

- [ ] **Step 1:** Add the sibling repository path and role to the current project.
- [ ] **Step 2:** Document export -> explicit staging -> qualification -> approval -> integration.
- [ ] **Step 3:** Add the new document to `docs/INDEX.md`.
- [ ] **Step 4:** Verify the index JSON parses and the current project default scene remains unchanged.

### Task 5: Initialize and verify the new repository

**Files:**
- Modify: `../paralls-art-assets/.git/` via Git commands only.

- [ ] **Step 1:** Run repository-local structural checks and JSON parsing checks.
- [ ] **Step 2:** Create the initial commit containing the production repository scaffold.
- [ ] **Step 3:** Re-run `git status --short --branch` and record the commit ID.
- [ ] **Step 4:** Run current-project focused documentation/static checks and report any pre-existing dirty worktree changes separately.
