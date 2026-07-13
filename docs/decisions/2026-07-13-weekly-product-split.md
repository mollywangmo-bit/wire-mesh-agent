# Decision: Split Weekly Report into Archive and Briefing Products

Date: 2026-07-13

## Context

The user wants two different reading experiences:

1. The full weekly report should remain a complete archive/database.
2. The brief weekly report should be concise, analytical, and decision-oriented.

Trying to make one report both complete and brief created tension:

- full keyword coverage made the report long
- “暂无更新” entries cluttered the reading experience
- foreign official-site checks were sometimes interpreted as industry progress
- brief reports reused the full report body and were not truly brief

## Decision

Treat the weekly outputs as two separate products:

```text
周报 / weekly
  = archive/database report
  = preserves keyword search coverage, monitoring checklist, and source traceability

精简周报 / weekly_brief
  = decision briefing
  = only high-value weekly changes, no keyword scan, no monitoring checklist
```

## Implementation

- `Analyzer.generate_report()` continues to generate the full archive-oriented report.
- `Analyzer.generate_briefing_report()` generates an independent decision briefing.
- `report_variants.py` uses `briefing_report` for `精简周报` instead of reusing the full report.
- `collector.generate_keyword_scan(show_keywords=True)` still records full keyword coverage, but groups missed keywords at category level.
- `collector.generate_keyword_scan(show_keywords=False)` omits missed keywords.

## Full Report Rules

The full weekly report may be long.

It should:

- preserve keyword search coverage
- preserve monitoring checklist output
- keep source links and traceability
- distinguish fixed official-site monitoring from real industry progress

## Brief Report Rules

The brief weekly report should:

- include only high-value changes
- explain why each item matters
- explain the impact on the wire-mesh industry
- omit keyword scans
- omit monitoring checklist
- omit “暂无更新”
- avoid official-site static pages unless they contain a substantive event

## Future Work

Add cross-week history deduplication and intelligence scoring so the brief report
can select A-level information more reliably.
