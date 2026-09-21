"""Independent FastAPI workbench for archived Wire Mesh research reports."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from knowledge_workbench.store import (
    dashboard_stats,
    get_report,
    import_directory,
    init_db,
    list_reports,
    search_sections,
    trend_summary,
)


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("WIRE_MESH_KB_DB", str(BASE_DIR / "knowledge.db")))
ARCHIVE_DIR = Path(os.getenv("WIRE_MESH_KB_ARCHIVE", "/data/wire-mesh-reports"))
ADMIN_TOKEN = os.getenv("WIRE_MESH_KB_ADMIN_TOKEN")

app = FastAPI(title="丝网行业研报知识库工作台", version="0.1.0")


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=300)


@app.on_event("startup")
def startup() -> None:
    init_db(DB_PATH)


def _excerpt(content: str, length: int = 220) -> str:
    normalized = " ".join(content.split())
    return normalized if len(normalized) <= length else normalized[:length].rstrip() + "..."


def _require_admin(authorization: str | None) -> None:
    if not ADMIN_TOKEN:
        return
    expected = f"Bearer {ADMIN_TOKEN}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Invalid import token")


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>丝网行业研报知识库工作台</title><style>
:root{--ink:#102a43;--muted:#627d98;--line:#d9e2ec;--brand:#0b7285;--wash:#f0f7f7;--card:#fff}
*{box-sizing:border-box}body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;background:#f7fafc;color:var(--ink)}
main{max-width:1120px;margin:auto;padding:42px 22px}header{padding:28px 30px;background:linear-gradient(125deg,#073b4c,#0b7285);color:#fff;border-radius:20px}h1{margin:0;font-size:29px}.sub{margin:10px 0 0;color:#d9f4f1}.notice{font-size:13px;margin-top:16px;color:#c6f6e9}
.grid{display:grid;grid-template-columns:1.25fr .75fr;gap:18px;margin-top:18px}.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:22px;box-shadow:0 5px 16px rgba(15,42,67,.04)}
h2{font-size:18px;margin:0 0 14px}input{width:100%;padding:13px;border:1px solid #bcccdc;border-radius:10px;font-size:15px}button{margin-top:9px;padding:10px 14px;border:0;border-radius:9px;background:var(--brand);color:#fff;cursor:pointer;font-size:14px}.results{margin-top:14px}.item{padding:13px 0;border-bottom:1px solid var(--line)}.item:last-child{border:0}.meta{color:var(--muted);font-size:12px;margin-top:5px}.excerpt{color:#334e68;font-size:14px;line-height:1.6;margin-top:7px}.tag{display:inline-block;background:var(--wash);color:var(--brand);padding:3px 7px;border-radius:99px;font-size:12px;margin:4px 5px 0 0}.stats{display:flex;gap:20px}.number{font-size:30px;font-weight:700}.muted{color:var(--muted)}
@media(max-width:760px){.grid{grid-template-columns:1fr}main{padding:20px 14px}header{padding:24px}h1{font-size:24px}}
</style></head><body><main>
<header><h1>丝网行业研报知识库工作台</h1><p class="sub">把已完成研报沉淀为可检索、可追溯的行业知识。</p><p class="notice">趋势指标基于研报文本提及，不等同于实时市场统计数据。</p></header>
<section class="grid"><div class="card"><h2>知识搜索</h2><input id="search" placeholder="例如：出口关税、原材料成本、欧洲需求"><button onclick="searchReports()">搜索研报</button><div id="search-results" class="results muted">输入关键词后，可查看相关章节与出处。</div></div>
<div class="card"><h2>知识库概览</h2><div class="stats"><div><div id="count" class="number">-</div><div class="muted">已导入报告</div></div><div><div id="latest" class="excerpt">加载中...</div><div class="muted">最新报告</div></div></div></div></section>
<section class="grid"><div class="card"><h2>AI 辅助问答</h2><input id="question" placeholder="例如：近期出口风险有哪些变化？"><button onclick="askQuestion()">基于研报回答</button><div id="answer" class="results muted">回答会附带来源片段；没有证据时会明确提示。</div></div>
<div class="card"><h2>行业信号趋势</h2><div id="trends" class="muted">加载中...</div></div></section>
<section class="card" style="margin-top:18px"><h2>最新研报</h2><div id="reports" class="muted">加载中...</div></section>
</main><script>
const esc=s=>String(s).replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const label={weekly:'周报',weekly_brief:'精简周报',monthly:'月报',price_cost:'成本/价格',demand:'需求',export:'出口',competition:'竞争',policy:'政策',regional:'区域'};
async function json(url,opts){const r=await fetch(url,opts);if(!r.ok)throw new Error('请求失败');return r.json()}
async function load(){try{const [stats,trends,reports]=await Promise.all([json('/api/dashboard'),json('/api/trends'),json('/api/reports')]);document.querySelector('#count').textContent=stats.report_count;document.querySelector('#latest').textContent=stats.latest_report?stats.latest_report.title:'暂无报告';document.querySelector('#trends').innerHTML=trends.length?trends.map(x=>`<span class="tag">${label[x.signal_name]||x.signal_name} ${x.mention_count} 次 / ${x.report_count} 篇</span>`).join(''):'导入研报后显示信号趋势。';document.querySelector('#reports').innerHTML=reports.length?reports.slice(0,8).map(r=>`<div class="item"><strong>${esc(r.title)}</strong><div class="meta">${label[r.report_type]||r.report_type} · ${new Date(r.imported_at).toLocaleDateString()}</div></div>`).join(''):'尚未导入报告。'}catch(e){document.querySelector('#reports').textContent='暂时无法读取知识库。'}}
async function searchReports(){const q=document.querySelector('#search').value.trim();if(!q)return;const box=document.querySelector('#search-results');box.textContent='搜索中...';try{const data=await json('/api/search?q='+encodeURIComponent(q));box.innerHTML=data.length?data.map(x=>`<div class="item"><strong>${esc(x.title)} · ${esc(x.heading)}</strong><div class="excerpt">${esc(x.excerpt)}</div><div class="meta">${label[x.report_type]||x.report_type}</div></div>`).join(''):'没有找到相关研报片段。'}catch(e){box.textContent='搜索暂不可用。'}}
async function askQuestion(){const q=document.querySelector('#question').value.trim();if(!q)return;const box=document.querySelector('#answer');box.textContent='正在检索研报证据...';try{const data=await json('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q})});box.innerHTML=`<div class="excerpt">${esc(data.answer)}</div>`+(data.sources||[]).map(s=>`<div class="item"><strong>${esc(s.title)} · ${esc(s.heading)}</strong><div class="excerpt">${esc(s.excerpt)}</div></div>`).join('')}catch(e){box.textContent='问答暂不可用。'}}
load();
</script></body></html>"""


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "database": str(DB_PATH), "archive_exists": ARCHIVE_DIR.exists()}


@app.get("/api/dashboard")
def dashboard() -> dict:
    return dashboard_stats(DB_PATH)


@app.get("/api/reports")
def reports(limit: int = Query(default=50, ge=1, le=100)) -> list[dict]:
    return list_reports(DB_PATH, limit)


@app.get("/api/reports/{report_id}")
def report_detail(report_id: str) -> dict:
    report = get_report(DB_PATH, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@app.get("/api/search")
def search(q: str = Query(min_length=1, max_length=200)) -> list[dict]:
    return [
        {**result, "excerpt": _excerpt(result["content"])}
        for result in search_sections(DB_PATH, q)
    ]


@app.get("/api/trends")
def trends() -> list[dict]:
    return trend_summary(DB_PATH)


@app.post("/api/import")
def import_reports(authorization: str | None = Header(default=None)) -> dict[str, int]:
    _require_admin(authorization)
    return import_directory(DB_PATH, ARCHIVE_DIR)


@app.post("/api/ask")
def ask(request: AskRequest) -> dict:
    matches = search_sections(DB_PATH, request.question, limit=3)
    if not matches:
        return {
            "answer": "现有研报中没有找到足够证据来回答这个问题。请换一个关键词，或先导入相关研报。",
            "sources": [],
        }
    sources = [
        {
            "report_id": item["report_id"],
            "title": item["title"],
            "heading": item["heading"],
            "excerpt": _excerpt(item["content"], 280),
        }
        for item in matches
    ]
    answer = "以下结论仅基于已检索到的研报片段：" + " ".join(
        f"《{item['title']}》的“{item['heading']}”提到{_excerpt(item['content'], 120)}"
        for item in matches
    )
    return {"answer": answer, "sources": sources}
