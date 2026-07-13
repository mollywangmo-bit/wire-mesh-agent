# Decision: Split Pipeline Responsibilities

Date: 2026-07-13

## Context

`main.py` had become responsible for too many concerns:

- collecting data
- translating content
- building weekly/brief/monthly variants
- rendering MD/HTML/DOCX/PDF
- handling partial rendering failure
- sending reports

This made small changes risky. A PDF fix could accidentally break monthly
labels, attachment behavior, or brief report logic.

## Decision

Keep `main.py` as an orchestration layer and split responsibilities into
focused modules:

```text
main.py
  ├─ report_variants.py      # decide 周报 / 精简周报 / 月报 variants
  ├─ artifact_renderer.py    # generate MD / HTML / DOCX / PDF
  ├─ manifest_writer.py      # write run manifest JSON
  └─ delivery.py             # deliver reports
```

## Module Responsibilities

### `report_variants.py`

Builds `ReportVariant` objects.

It owns:

- default weekly variant
- `also_brief=True`
- `--brief`
- monthly naming
- file prefixes

### `artifact_renderer.py`

Builds `ReportArtifacts`.

It owns:

- MD file writing
- HTML generation
- DOCX generation
- PDF generation
- artifact success/error/size tracking

### `manifest_writer.py`

Writes a JSON record for each run.

It owns:

- `run_id`
- period
- duration
- per-variant artifact status
- delivery summary

### `delivery.py`

Sends reports through configured channels.

It owns:

- email attachment handling
- Feishu delivery
- WeCom delivery

## Consequences

Future agents should avoid putting variant logic or rendering details back into
`main.py`.

If a new output format is added, update `artifact_renderer.py` and the manifest
schema, not the main orchestration loop.
