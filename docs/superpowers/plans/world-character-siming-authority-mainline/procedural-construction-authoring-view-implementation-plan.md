# Procedural Authoring/View Implementation Plan

Implement Canonical JSON draft export and a Godot procedural editor/view using
built-in meshes. Tests cover draft round-trip, grid occupancy, rejected intent
rollback and replay timeline. Gate only after headless gates pass; desktop
Godot verification is required for final completion. No visual state writes
back to gameplay truth.

The headless asset contract now covers backend facility/Job/run status mirrors,
replay timeline display input, and speculative-state clearing on projection or
rejection. Godot 4.6.3 headless and desktop smoke scene startup are green
through the dedicated `procedural-construction-editor-runtime` Harness profile.
