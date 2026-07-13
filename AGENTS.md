# Wire Mesh Agent — Agent Operating Guide

This file is the persistent operating guide for coding agents working on this
repository. Read it before making changes.

## Project Goal

This project is a wire-mesh industry intelligence agent.

The pipeline:

1. Collect industry data
2. Translate non-Chinese sources
3. Generate weekly/monthly reports via LLM
4. Render artifacts: MD, HTML, DOCX, PDF
5. Deliver via Email / Feishu / WeCom
6. Write a manifest for observability

## Architecture Boundaries

- `main.py`: orchestration only
- `report_variants.py`: decides weekly / brief weekly / monthly variants
- `artifact_renderer.py`: renders MD / HTML / DOCX / PDF
- `manifest_writer.py`: records run result
- `history_store.py`: records cross-week seen fingerprints
- `intelligence_filter.py`: scores collected items for brief report selection
- `delivery.py`: sends artifacts
- `html_reporter.py`: visual HTML renderer
- `docx_reporter.py`: Word renderer
- `html_to_pdf.py`: Playwright HTML → PDF renderer
- `collector.py`: data collection
- `analyzer.py`: LLM analysis
- `config.py`: environment-driven configuration

Do not put rendering logic back into `main.py`.
Do not put business variant logic into `delivery.py`.
Do not modify `collector.py` or `analyzer.py` unless the task explicitly requires it.

## Current Output Contract

Weekly default:

- Produces one `周报 / weekly` archive/database variant
- Generates MD / HTML / DOCX / PDF
- Sends available Word + PDF + HTML attachments
- Writes a manifest JSON

Weekly with `also_brief=True`:

- Produces `周报 / weekly`
- Produces `精简周报 / weekly_brief`
- Each variant generates MD / HTML / DOCX / PDF
- Each variant is delivered separately
- `周报` is a complete archive/database report and should preserve keyword search coverage.
- `精简周报` is a decision briefing and should not include keyword scan, monitoring checklist, or “暂无更新” filler.

Weekly with `--brief`:

- Produces only `精简周报 / weekly_brief`
- Uses the independent briefing prompt, not the archive report body.

Monthly:

- Produces one `月报 / monthly` variant
- Must not be labeled `周报`

Every run must write:

- `wire_mesh_manifest_<run_id>.json`

## Known Lessons

- WeasyPrint failed because of missing system libraries; do not reintroduce it as the default PDF path.
- fpdf2 generated poor-quality PDFs; keep it out of the main path.
- PDF should be generated from HTML via Playwright Chromium.
- Monthly reports must use label `月报` and file prefix `monthly`.
- `--brief` must produce only `精简周报`.
- Full weekly reports are archive/database reports; brief weekly reports are decision briefings.
- Brief weekly reports should use A/B intelligence candidates from `intelligence_filter.py`, not full raw data.
- Cross-week repeated items should be downgraded via `history_store.py`.
- Artifact success must be based on real file existence and non-zero size.
- Do not claim an attachment exists unless the file exists.
- API trigger endpoints must require `RUN_TOKEN`.
- Translate non-Chinese data before LLM analysis.

## Runtime and Deployment

Important environment variables:

- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL`
- `SMTP_SERVER`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `EMAIL_FROM`
- `EMAIL_TO`
- `RUN_TOKEN`
- `OUTPUT_DIR`
- `SERPER_API_KEY`
- `FEISHU_WEBHOOK_URL`
- `WECOM_WEBHOOK_URL`

Playwright is required for PDF generation:

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

Docker should install Chromium with:

```bash
python -m playwright install --with-deps chromium
```

## Security Rules

- Do not expose `/run`, `/run/monthly`, `/debug/email` without token auth.
- Do not log secrets, API keys, SMTP passwords, or password lengths.
- Do not commit `.env`.
- Do not send real emails unless the user explicitly asks.
- Do not use broad destructive commands.

## Development Workflow for Agents

Before editing:

1. Read `AGENTS.md`
2. Read `AGENT_STATE.md` if present
3. Inspect only files relevant to the task
4. State intended scope
5. Edit only scoped files

After editing:

1. Run lightweight syntax/import checks when possible
2. Avoid real collection, LLM calls, or email delivery unless explicitly requested
3. Update `AGENT_STATE.md` when the task changes persistent project state
4. If a major architecture decision is made, add or update `docs/decisions/*.md`

## Lightweight Checks

Prefer checks that do not call external APIs:

```bash
python3 -c "import ast,pathlib; files=['main.py','artifact_renderer.py','report_variants.py','manifest_writer.py','delivery.py','html_to_pdf.py','api.py','config.py']; [ast.parse(pathlib.Path(n).read_text(encoding='utf-8'), filename=n) for n in files]; print('AST syntax OK')"
```

For variant behavior:

```bash
python3 -c "from report_variants import build_report_variants as b; kw=dict(llm_report='L',keyword_scan_full='KF',keyword_scan_brief='KB',checklist_text='C'); print([(v.label,v.file_prefix) for v in b(**kw)]); print([(v.label,v.file_prefix) for v in b(**kw, also_brief=True)]); print([(v.label,v.file_prefix) for v in b(**kw, brief=True)]); print([(v.label,v.file_prefix) for v in b(**kw, period='monthly')])"
```

## Do Not

- Do not reintroduce WeasyPrint as the default PDF renderer.
- Do not hardcode `/tmp` except as default `OUTPUT_DIR`.
- Do not put artifact rendering back into `main.py`.
- Do not send test emails during normal validation.
- Do not mark a pipeline successful based only on printed logs.
