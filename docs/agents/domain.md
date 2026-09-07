# Domain Docs

This is a single-context repository. Engineering skills should consume domain documentation as follows.

## Before exploring

- Read `CONTEXT.md` at the repository root when it exists.
- Read ADRs under `docs/adr/` that touch the area being changed.
- If these files do not exist, proceed silently. The domain-modeling skill creates them lazily when concepts or decisions are resolved.

## File structure

```text
/
├── CONTEXT.md
├── docs/adr/
└── src/
```

## Vocabulary and ADR conflicts

Use domain terms as defined in `CONTEXT.md`; avoid introducing synonyms when a glossary term exists. If a proposed change conflicts with an ADR, surface the conflict explicitly instead of silently overriding it.
