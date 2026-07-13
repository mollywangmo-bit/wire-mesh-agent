# Decision: Use Playwright for PDF Rendering

Date: 2026-07-13

## Context

The project needs high-quality PDF output for reports that are already rendered
as rich HTML.

Earlier attempts:

- WeasyPrint
- fpdf2

## Decision

Use Playwright Chromium to print the HTML report to PDF.

```text
Markdown report
  → html_reporter.py
  → HTML
  → html_to_pdf.py
  → Playwright Chromium
  → PDF
```

## Why

Playwright uses a real Chromium browser engine, so it preserves:

- CSS layout
- Chart.js rendering
- SVG fallback charts
- hyperlinks
- browser-like print output

## Rejected Options

### WeasyPrint

Rejected as default because it failed on macOS due to missing system libraries
such as `libgobject-2.0-0`. It also adds brittle platform-level dependencies.

### fpdf2

Rejected as default because output quality was too low:

- tables became plain text
- links were stripped or degraded
- charts were lost
- visual style did not match HTML

## Consequences

`requirements.txt` must include:

```txt
playwright>=1.60.0
```

Docker must install Chromium:

```dockerfile
RUN python -m playwright install --with-deps chromium
```

Future agents should not reintroduce WeasyPrint or fpdf2 as the default path.
