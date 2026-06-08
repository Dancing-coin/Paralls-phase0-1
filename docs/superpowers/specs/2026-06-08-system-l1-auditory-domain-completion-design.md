# System L1 Auditory Domain Completion Design

## Goal

Define how the current auditory path grows from:

- first formal auditory raw-fact route

to

- a full auditory `System L1` subdomain

for this repository.

## Current State

The repo already has:

- auditory raw-fact structure
- a Godot auditory emitter
- an authority route
- runtime verification evidence that one auditory fact is emitted

That is not yet a full auditory domain.

## Required Completion Questions

This spec must freeze the answers to:

1. what auditory fact types are officially supported
2. what each type means at raw-fact level
3. what propagation semantics are modeled in-repo
4. which auditory facts remain `L1`-only
5. which auditory facts may compile upward into candidate percepts

## Minimum Supported Auditory Fact Set

The repository should stabilize at least:

- `speaker_active`
- `speech_mode_changed`
- `auditory_reachability_changed`
- `ambient_noise_changed`

## Required Raw Fields

Auditory facts should use the shared raw-fact contract plus explicit acoustic fields for:

- loudness band
- speech mode
- reachability
- ambient noise

## Candidate-Compiler Policy

This repository must not silently treat auditory facts as:

- automatically candidate-compilable
- permanently authority-only

It must explicitly choose.

Default recommended policy:

- `ambient_noise_changed`: `L1-only for now`
- `speaker_active` and `auditory_reachability_changed`: candidate-compilable once the repo has a stable coarse hearing rule

## Verification Requirement

To call the auditory domain complete enough:

- the route must exist
- runtime proof must exist
- audit proof must exist
- the candidate policy must be explicit

## Non-Goals

- full eavesdropping logic
- full audibility simulation
- Steam Audio completeness
- role-private hearing conclusions inside `L1`

