# Agent State

Last updated: 2026-07-13

## Active Goal

Make the report pipeline production-safe and easier for future agents to maintain.

## Current Phase

Report content productization: full archive report vs decision briefing.

## Completed

- Replaced fragile PDF strategy with Playwright HTML → PDF.
- Added DOCX generation through `docx_reporter.py`.
- Updated email delivery to support Word + PDF + HTML attachments.
- Fixed monthly label/file-prefix bug.
- Fixed `--brief` behavior.
- Added configurable `OUTPUT_DIR`.
- Added `RUN_TOKEN` protection for sensitive API endpoints.
- Removed WeasyPrint/fpdf2 from the default path.
- Added `report_variants.py` for weekly/brief/monthly variant construction.
- Added `artifact_renderer.py` for MD/HTML/DOCX/PDF generation.
- Added `manifest_writer.py` for run observability.
- Added this project-memory layer:
  - `AGENTS.md`
  - `AGENT_STATE.md`
  - `docs/decisions/*`
- Split weekly report product definition:
  - Full weekly report = archive/database report
  - Brief weekly report = decision briefing
- Added independent briefing prompt for `精简周报`.
- Adjusted keyword scan so full reports keep coverage while grouping missed keywords.
- Added first-pass cross-week history store (`history_store.py`).
- Added first-pass intelligence scoring/filtering (`intelligence_filter.py`).
- Brief weekly reports now use high-value A/B candidates instead of full raw data.

## Current Architecture

```text
main.py
  ├─ report_variants.py      # build 周报 / 精简周报 / 月报 variants
  ├─ artifact_renderer.py    # render MD / HTML / DOCX / PDF
  ├─ manifest_writer.py      # write run manifest JSON
  └─ delivery.py             # Email / Feishu / WeCom delivery
```

## Pending / Recommended Next Work

1. Tune intelligence scoring with real report feedback:

   - adjust A/B thresholds
   - improve static official-site detection
   - add stronger overseas high-value source rules
   - add domain-specific signals for patents, IR, exhibitions, prices

2. Upgrade `delivery.py` to return structured per-channel delivery results:

   ```json
   {
     "email": {"ok": true, "error": null},
     "feishu": {"ok": false, "error": "webhook missing"},
     "wecom": {"ok": false, "error": "webhook missing"}
   }
   ```

3. Include delivery channel details in `manifest_writer.py`.
4. Add unit tests for:
   - weekly default variants
   - weekly `also_brief=True`
   - weekly `--brief`
   - monthly naming
   - artifact failure handling
   - manifest output structure
5. Consider adding a `README.md` for humans.
6. Consider adding `docs/runbook.md` for deployment and operations.

## Constraints for Future Agents

- Do not modify `collector.py` or `analyzer.py` unless explicitly requested.
- Do not reintroduce WeasyPrint as default.
- Do not send real email without explicit user permission.
- Do not treat print logs as proof of success; inspect artifact results or manifest.
- Keep `main.py` as orchestration only.

## Useful Commands

Syntax check without writing `__pycache__`:

```bash
python3 -c "import ast,pathlib; files=['main.py','artifact_renderer.py','report_variants.py','manifest_writer.py','delivery.py','html_to_pdf.py','api.py','config.py']; [ast.parse(pathlib.Path(n).read_text(encoding='utf-8'), filename=n) for n in files]; print('AST syntax OK')"
```

Variant matrix check:

```bash
python3 -c "from report_variants import build_report_variants as b; kw=dict(llm_report='L',keyword_scan_full='KF',keyword_scan_brief='KB',checklist_text='C'); print([(v.label,v.file_prefix) for v in b(**kw)]); print([(v.label,v.file_prefix) for v in b(**kw, also_brief=True)]); print([(v.label,v.file_prefix) for v in b(**kw, brief=True)]); print([(v.label,v.file_prefix) for v in b(**kw, period='monthly')])"
```
