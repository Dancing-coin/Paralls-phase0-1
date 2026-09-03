# Procedural Construction Authoring And View Design

Godot and file authoring both emit schema-validated Canonical JSON drafts.
Only the existing adapter/canonicalizer derives normalized bytes and digests;
the editor cannot activate packages, choose owners, or write gameplay facts.
The flow is `draft -> export -> review -> freeze -> candidate -> exact-one
active binding`.

The editor uses PrimitiveMesh, built-in materials and overlays. Grid footprint
and discrete orientation are authoritative; local offsets, decoration and
visual bindings are not part of occupancy, digest or replay. The view supports
placement, component preview, conflict/result feedback, construction progress,
run monitoring and replay timeline from backend mirror data. Rejected intents
clear speculative state.

The editor additionally exposes a read-only projection summary for facility,
ConstructionJob and ProductionRun statuses, plus a replay-timeline input. These
surfaces consume backend-derived dictionaries only and never create gameplay
facts or reconstruct authority decisions locally.
