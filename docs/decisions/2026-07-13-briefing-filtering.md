# Decision: Filter Brief Reports with History and Intelligence Scores

Date: 2026-07-13

## Context

The full weekly report is intentionally a database/archive. It should preserve
keyword coverage and monitoring records.

The brief weekly report has a different purpose: it should surface only the
most valuable weekly changes. Using the full raw dataset caused:

- repeated items across weeks
- official-site static pages being over-interpreted
- low-value source noise
- weaker overseas signal quality

## Decision

Add a lightweight pre-LLM filtering layer for `精简周报`.

```text
all_results
  → history_store.py          # seen-before fingerprints
  → intelligence_filter.py    # A/B/C/D scoring
  → briefing candidates       # A/B only
  → Analyzer.generate_briefing_report()
```

The full weekly report continues to use full raw data.

## Implementation

### `history_store.py`

Records:

- URL/title fingerprints
- first_seen
- last_seen
- seen_count
- last_used_in_briefing

### `intelligence_filter.py`

Scores items using:

- direct wire-mesh industry terms
- substantive event keywords
- numeric evidence
- source quality
- full text availability
- official-site static-page penalties
- cross-week duplicate penalties

Grades:

- A: strong brief candidate
- B: usable brief candidate
- C: archive/full report only
- D: discard or manifest-only

## Consequences

The brief report should become more concise and less repetitive.

The scoring rules are intentionally first-pass heuristics and should be tuned
using real weekly report feedback.
