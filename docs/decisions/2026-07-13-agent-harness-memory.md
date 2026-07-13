# Decision: Add Persistent Agent Memory Files

Date: 2026-07-13

## Context

The project accumulated important development lessons in conversation:

- PDF strategy changed from WeasyPrint/fpdf2 to Playwright
- monthly labels were wrong
- `--brief` did not work
- artifact success needed explicit tracking
- API trigger endpoints needed token protection

Without persistent project memory, future agents may repeat old mistakes after
context compression or a new session.

## Decision

Add project-level memory files:

```text
AGENTS.md
AGENT_STATE.md
docs/decisions/*.md
```

## File Roles

### `AGENTS.md`

Long-lived operating guide for agents.

Contains:

- project goal
- architecture boundaries
- output contract
- known lessons
- security rules
- lightweight validation commands

### `AGENT_STATE.md`

Shorter current-state tracker.

Contains:

- active goal
- completed work
- current architecture
- recommended next work
- constraints for future agents

### `docs/decisions/*.md`

Architecture decision records.

Contains:

- what was decided
- why
- rejected alternatives
- consequences

## Harness Recommendation

Future harnesses should load context in this order:

1. `AGENTS.md`
2. `AGENT_STATE.md`
3. relevant `docs/decisions/*.md`
4. only files relevant to the current task

Avoid loading the full repository by default.

## Context Compression Strategy

Compress conversation history into stable files:

- stable rules → `AGENTS.md`
- current progress → `AGENT_STATE.md`
- major decisions → `docs/decisions/*.md`
- run-specific status → `wire_mesh_manifest_<run_id>.json`

This keeps agent context small while preserving important project memory.
