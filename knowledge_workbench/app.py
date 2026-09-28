"""Independent FastAPI workbench for archived Wire Mesh research reports."""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from urllib.parse import parse_qs
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from knowledge_workbench.store import (
    dashboard_stats,
    entity_map,
    event_timeline,
    event_feed,
    event_trends,
    get_report,
    import_directory,
    import_markdown_file,
    init_db,
    list_reports,
    search_sections,
    trend_summary,
    opportunity_radar,
    process_all_report_events,
    weekly_changes,
)


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("WIRE_MESH_KB_DB", str(BASE_DIR / "knowledge.db")))
ARCHIVE_DIR = Path(os.getenv("WIRE_MESH_KB_ARCHIVE", "/data/wire-mesh-reports"))
ADMIN_TOKEN = os.getenv("WIRE_MESH_KB_ADMIN_TOKEN")
AUTH_USERNAME = os.getenv("WIRE_MESH_KB_AUTH_USERNAME")
AUTH_PASSWORD = os.getenv("WIRE_MESH_KB_AUTH_PASSWORD")
SESSION_SECRET = os.getenv("WIRE_MESH_KB_SESSION_SECRET")
COOKIE_SECURE = os.getenv("WIRE_MESH_KB_COOKIE_SECURE", "true").lower() == "true"
SESSION_COOKIE = "wire_mesh_kb_session"
SESSION_TTL_SECONDS = 8 * 60 * 60

app = FastAPI(title="丝网行业研报知识库工作台", version="0.1.0")


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=300)


class ImportReportRequest(BaseModel):
    filename: str = Field(min_length=4, max_length=180)
    content: str = Field(min_length=1)


@app.on_event("startup")
def startup() -> None:
    init_db(DB_PATH)


def _excerpt(content: str, length: int = 220) -> str:
    normalized = " ".join(content.split())
    return normalized if len(normalized) <= length else normalized[:length].rstrip() + "..."


def _require_admin(authorization: str | None) -> None:
    if not _has_valid_admin(authorization):
        raise HTTPException(status_code=401, detail="Invalid import token")


def _has_valid_admin(authorization: str | None) -> bool:
    if not ADMIN_TOKEN:
        return False
    return hmac.compare_digest(authorization or "", f"Bearer {ADMIN_TOKEN}")


def _auth_is_configured() -> bool:
    return bool(AUTH_USERNAME and AUTH_PASSWORD and SESSION_SECRET)


def _sign(value: str) -> str:
    assert SESSION_SECRET is not None
    return hmac.new(
        SESSION_SECRET.encode("utf-8"), value.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def _make_session() -> str:
    assert AUTH_USERNAME is not None
    expires_at = int(time.time()) + SESSION_TTL_SECONDS
    payload = f"{AUTH_USERNAME}:{expires_at}"
    return f"{payload}:{_sign(payload)}"


def _has_valid_session(cookie: str | None) -> bool:
    if not cookie or not _auth_is_configured():
        return False
    try:
        username, expires_at_text, signature = cookie.rsplit(":", 2)
        payload = f"{username}:{expires_at_text}"
        return (
            hmac.compare_digest(username, AUTH_USERNAME or "")
            and hmac.compare_digest(signature, _sign(payload))
            and int(expires_at_text) >= int(time.time())
        )
    except (ValueError, TypeError):
        return False


def _login_page(error: bool = False) -> str:
    message = "账号或密码不正确。" if error else ""
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>登录｜丝网研报知识库</title><style>body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#eef5f6;color:#102a43;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}}main{{width:min(390px,calc(100% - 36px));background:#fff;border-radius:18px;padding:32px;box-shadow:0 18px 50px #0b728526}}h1{{font-size:24px;margin:0 0 8px}}p{{color:#627d98;line-height:1.6}}label{{display:block;margin-top:16px;font-size:14px}}input{{width:100%;box-sizing:border-box;margin-top:7px;padding:12px;border:1px solid #bcccdc;border-radius:9px;font-size:15px}}button{{margin-top:22px;width:100%;padding:12px;background:#0b7285;border:0;border-radius:9px;color:#fff;font-size:15px}}.error{{color:#c92a2a;font-size:14px}}</style></head><body><main><h1>丝网研报知识库</h1><p>请输入团队账号后访问研报、搜索与问答功能。</p><form method="post" action="/login"><label>账号<input name="username" autocomplete="username" required></label><label>密码<input name="password" type="password" autocomplete="current-password" required></label><button type="submit">登录</button></form><p class="error">{message}</p></main></body></html>"""


@app.middleware("http")
async def require_login(request: Request, call_next):
    path = request.url.path
    if path in {"/api/health", "/login", "/logout", "/favicon.ico"}:
        return await call_next(request)
    if (path.startswith("/api/import") or path.startswith("/api/intelligence")) and _has_valid_admin(
        request.headers.get("authorization")
    ):
        return await call_next(request)
    if not _auth_is_configured():
        return JSONResponse(
            status_code=503,
            content={"detail": "Login protection has not been configured."},
        )
    if _has_valid_session(request.cookies.get(SESSION_COOKIE)):
        return await call_next(request)
    if path.startswith("/api/"):
        return JSONResponse(status_code=401, content={"detail": "Login required."})
    return RedirectResponse(url="/login", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_page() -> str:
    if not _auth_is_configured():
        raise HTTPException(status_code=503, detail="Login protection has not been configured.")
    return _login_page()


@app.post("/login")
async def login(request: Request):
    if not _auth_is_configured():
        raise HTTPException(status_code=503, detail="Login protection has not been configured.")
    fields = parse_qs((await request.body()).decode("utf-8"), keep_blank_values=True)
    username = fields.get("username", [""])[0]
    password = fields.get("password", [""])[0]
    if not (
        hmac.compare_digest(username, AUTH_USERNAME or "")
        and hmac.compare_digest(password, AUTH_PASSWORD or "")
    ):
        return HTMLResponse(_login_page(error=True), status_code=401)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        SESSION_COOKIE,
        _make_session(),
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
    )
    return response


@app.post("/logout")
def logout() -> RedirectResponse:
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>丝网行业研报知识库工作台</title><style>
:root{--ink:#102a43;--muted:#627d98;--line:#d9e2ec;--brand:#0b7285;--wash:#f0f7f7;--card:#fff}
*{box-sizing:border-box}body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;background:#f7fafc;color:var(--ink)}
main{max-width:1120px;margin:auto;padding:42px 22px}header{padding:28px 30px;background:linear-gradient(125deg,#073b4c,#0b7285);color:#fff;border-radius:20px}h1{margin:0;font-size:29px}.sub{margin:10px 0 0;color:#d9f4f1}.notice{font-size:13px;margin-top:16px;color:#c6f6e9}
.grid{display:grid;grid-template-columns:1.25fr .75fr;gap:18px;margin-top:18px}.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:22px;box-shadow:0 5px 16px rgba(15,42,67,.04)}
h2{font-size:18px;margin:0 0 14px}input{width:100%;padding:13px;border:1px solid #bcccdc;border-radius:10px;font-size:15px}button{margin-top:9px;padding:10px 14px;border:0;border-radius:9px;background:var(--brand);color:#fff;cursor:pointer;font-size:14px}.results{margin-top:14px}.item{padding:13px 0;border-bottom:1px solid var(--line)}.item:last-child{border:0}.report-link{display:block;width:100%;margin:0;padding:0;background:none;color:var(--ink);text-align:left;font-size:15px;font-weight:700}.meta{color:var(--muted);font-size:12px;margin-top:5px}.excerpt{color:#334e68;font-size:14px;line-height:1.6;margin-top:7px}.report-content{white-space:pre-wrap;color:#334e68;line-height:1.8;font-size:14px;max-height:720px;overflow:auto;padding-top:14px}.muted{color:var(--muted)}.analysis-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;margin-top:18px}.research{margin-top:18px}.search-row{display:flex;gap:10px}.search-row button{margin:0;white-space:nowrap}.hotspot-grid,.event-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.hotspot,.event-card{border:1px solid var(--line);border-radius:12px;padding:15px;background:#fbfdfd}.hotspot h3,.event-card h3{margin:0 0 8px;font-size:16px}.tag{display:inline-block;background:var(--wash);color:var(--brand);padding:3px 7px;border-radius:99px;font-size:12px;margin:4px 5px 0 0}.news-link{display:block;width:100%;margin:8px 0 0;padding:0;background:none;color:#334e68;text-align:left;font-size:13px;line-height:1.5}.map-svg{width:100%;height:auto;background:#edf6f6;border-radius:12px}.map-land{fill:#cfe4e4;stroke:#fff;stroke-width:2}.map-bubble{fill:#0b7285;opacity:.78}.map-label{font-size:10px;fill:#102a43}.bar-row{margin:12px 0}.bar-label{display:flex;justify-content:space-between;font-size:13px;margin-bottom:5px}.bar-track{height:10px;background:#e9f0f2;border-radius:10px;overflow:hidden}.bar-fill{height:100%;background:linear-gradient(90deg,#0b7285,#38b2ac);border-radius:10px}.answer-box{padding:14px;background:var(--wash);border-radius:10px;line-height:1.7}.evidence-list{margin-top:12px}.evidence-link{display:block;width:100%;background:none;color:var(--brand);text-align:left;padding:8px 0;margin:0;border-bottom:1px solid var(--line)}
@media(max-width:760px){.grid,.analysis-grid,.hotspot-grid,.event-grid{grid-template-columns:1fr}.search-row{display:block}.search-row button{margin-top:9px;width:100%}main{padding:20px 14px}header{padding:24px}h1{font-size:24px}}
</style></head><body><main>
<header><h1>丝网行业情报工作台</h1><p class="sub">从行业信息中发现变化、验证趋势、识别机会。</p><p class="notice">所有趋势以独立事件计数，且可回溯至原始研报证据。</p></header>
<section class="card research"><h2>智能搜索</h2><p class="muted">输入行业问题，同时获得研报结论和相关原文。</p><div class="search-row"><input id="research-input" placeholder="例如：近期制氢镍网有哪些重要变化？" onkeydown="if(event.key==='Enter')runResearch()"><button onclick="runResearch()">搜索并分析</button></div><div id="research-results" class="results muted">搜索结果会区分结论与原始证据。</div></section>
<section class="card" style="margin-top:18px"><h2>近期热点板块</h2><p class="muted">根据近期独立行业动态归纳，点击新闻可回到对应研报。</p><div id="radar" class="hotspot-grid muted">加载中...</div></section>
<section class="analysis-grid"><div class="card"><h2>区域情报</h2><div id="region-map" class="muted">加载中...</div></div><div class="card"><h2>企业活跃度</h2><div id="company-chart" class="muted">加载中...</div></div></section>
<section class="card" style="margin-top:18px"><h2>近期重要动态</h2><p class="muted">从周报中拆出的独立新闻与行业变化，仅展示最近的重要项目。</p><div id="recent-events" class="event-grid muted">加载中...</div></section>
<section class="card" style="margin-top:18px"><h2>历史研报</h2><p class="muted">点击报告即可查看完整内容。</p><div id="reports" class="muted">加载中...</div></section>
<section id="reader" class="card" style="margin-top:18px;display:none"><button style="float:right;margin:0" onclick="closeReport()">关闭</button><h2 id="report-title">研报原文</h2><div id="report-meta" class="meta"></div><article id="report-content" class="report-content"></article></section>
</main><script>
const esc=s=>String(s).replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const label={weekly:'周报',weekly_brief:'精简周报',monthly:'月报',price_cost:'成本/价格',demand:'需求',export:'出口',competition:'竞争',policy:'政策',regional:'区域'};
const eventLabel={investment:'投资',capacity_expansion:'扩产',new_product:'新品',technology_breakthrough:'技术突破',customer_validation:'客户验证',order:'订单',partnership:'合作',policy:'政策',export:'出口',price_change:'价格变化',market_demand:'市场需求',regulation:'监管',other:'行业动态'};
async function json(url,opts){const r=await fetch(url,opts);if(!r.ok)throw new Error('请求失败');return r.json()}
function renderHotspots(items){return items.slice(0,6).map(x=>`<article class="hotspot"><h3>${esc(x.name)} <span class="tag">${esc(x.status)}</span></h3><div>${x.keywords.map(k=>`<span class="tag">${esc(k)}</span>`).join('')}</div>${x.news.map(n=>`<button class="news-link" onclick="openReport('${n.report_id}')">${esc(n.event_date)}｜${esc(n.title)}</button>`).join('')}</article>`).join('')}
function renderMap(items){const points={中国:[310,115],国内:[310,115],欧洲:[185,90],美国:[62,105],北美:[62,88],东南亚:[318,158],中东:[245,125],拉美:[105,180],非洲:[205,155],日本:[355,112],韩国:[340,110],印度:[275,140]};const max=Math.max(1,...items.map(x=>x.mentions));const bubbles=items.filter(x=>points[x.name]).map(x=>{const [cx,cy]=points[x.name],r=5+13*x.mentions/max;return `<g><circle class="map-bubble" cx="${cx}" cy="${cy}" r="${r}"><title>${esc(x.name)}：${x.mentions} 次</title></circle><text class="map-label" x="${cx+r+3}" y="${cy+3}">${esc(x.name)}</text></g>`}).join('');return `<svg class="map-svg" viewBox="0 0 420 230" aria-label="区域情报地图"><path class="map-land" d="M20 65L85 42 145 63 128 112 88 124 55 102Z M155 55L222 45 268 72 247 109 196 111 170 88Z M169 116L223 112 244 158 215 205 180 176Z M258 62L367 54 397 91 365 132 323 127 294 167 259 139Z M343 167L399 177 389 210 349 204Z"/>${bubbles}</svg><div class="meta">圆点越大，近期研报中的相关动态越多。</div>`}
function renderCompanies(items){if(!items.length)return '暂未识别到稳定的企业实体。';const top=items.slice(0,8),max=Math.max(...top.map(x=>x.mentions));return top.map(x=>`<div class="bar-row"><div class="bar-label"><span>${esc(x.name)}</span><strong>${x.mentions}</strong></div><div class="bar-track"><div class="bar-fill" style="width:${Math.max(8,x.mentions/max*100)}%"></div></div></div>`).join('')}
function renderEvents(events){return events.slice(0,6).map(x=>`<article class="event-card"><div class="meta">${esc(x.event_date)} · ${esc(eventLabel[x.event_type]||'行业动态')}</div><h3>${esc(x.title)}</h3><div>${x.themes.slice(0,3).map(t=>`<span class="tag">${esc(t)}</span>`).join('')}</div>${x.sources[0]?`<button class="news-link" onclick="openReport('${x.sources[0].report_id}')">查看来源研报</button>`:''}</article>`).join('')}
async function load(){try{const [reports,radar,events,entities]=await Promise.all([json('/api/reports'),json('/api/trend-radar'),json('/api/events'),json('/api/analysis/entity-map')]);document.querySelector('#reports').innerHTML=reports.length?reports.map(r=>`<div class="item"><button class="report-link" onclick="openReport('${r.id}')">${esc(r.title)}</button></div>`).join(''):'尚未导入报告。';document.querySelector('#radar').innerHTML=radar.length?renderHotspots(radar):'暂无热点板块。';document.querySelector('#region-map').innerHTML=renderMap(entities.regions);document.querySelector('#company-chart').innerHTML=renderCompanies(entities.companies);document.querySelector('#recent-events').innerHTML=events.length?renderEvents(events):'暂无近期动态。'}catch(e){['reports','radar','region-map','company-chart','recent-events'].forEach(id=>document.querySelector('#'+id).textContent='暂时无法读取数据。')}}
async function openReport(id){const reader=document.querySelector('#reader');document.querySelector('#report-title').textContent='加载报告中...';document.querySelector('#report-content').textContent='';reader.style.display='block';reader.scrollIntoView({behavior:'smooth',block:'start'});try{const report=await json('/api/reports/'+encodeURIComponent(id));document.querySelector('#report-title').textContent=report.title;document.querySelector('#report-meta').textContent=(label[report.report_type]||report.report_type)+' · '+new Date(report.imported_at).toLocaleDateString();document.querySelector('#report-content').textContent=report.content}catch(e){document.querySelector('#report-title').textContent='报告暂时无法读取。'}}
function closeReport(){document.querySelector('#reader').style.display='none'}
async function runResearch(){const q=document.querySelector('#research-input').value.trim();if(!q)return;const box=document.querySelector('#research-results');box.textContent='正在检索研报并组织回答...';try{const [answer,matches]=await Promise.all([json('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q})}),json('/api/search?q='+encodeURIComponent(q))]);const sources=(answer.sources||[]).length?answer.sources:matches.slice(0,5);box.innerHTML=`<div class="answer-box"><strong>结论</strong><div class="excerpt">${esc(answer.answer)}</div></div><div class="evidence-list"><strong>相关原文</strong>${sources.map(s=>`<button class="evidence-link" onclick="openReport('${s.report_id}')">${esc(s.title)} · ${esc(s.heading)}</button>`).join('')||'<div class="meta">没有找到相关证据。</div>'}</div>`}catch(e){box.textContent='搜索暂不可用。'}}
load();
</script></body></html>"""


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "database": str(DB_PATH), "archive_exists": ARCHIVE_DIR.exists()}


@app.get("/api/dashboard")
def dashboard() -> dict:
    return dashboard_stats(DB_PATH)


@app.get("/api/analysis/weekly-changes")
def analysis_weekly_changes() -> dict:
    return weekly_changes(DB_PATH)


@app.get("/api/analysis/opportunity-radar")
def analysis_opportunity_radar() -> list[dict]:
    return opportunity_radar(DB_PATH)


@app.get("/api/analysis/timeline")
def analysis_timeline() -> list[dict]:
    return event_timeline(DB_PATH)


@app.get("/api/analysis/entity-map")
def analysis_entity_map() -> dict:
    return entity_map(DB_PATH)


@app.get("/api/events")
def events(limit: int = Query(default=40, ge=1, le=100)) -> list[dict]:
    return event_feed(DB_PATH, limit)


@app.get("/api/trend-radar")
def trend_radar(days: int = Query(default=28, ge=7, le=365)) -> list[dict]:
    return event_trends(DB_PATH, days)


@app.post("/api/intelligence/rebuild")
def rebuild_intelligence(authorization: str | None = Header(default=None)) -> dict[str, int]:
    _require_admin(authorization)
    return process_all_report_events(DB_PATH)


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


@app.post("/api/import/report")
def import_report(
    request: ImportReportRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, str | bool]:
    """Store one Markdown report in the persistent archive and import it."""
    _require_admin(authorization)
    filename = Path(request.filename).name
    if filename != request.filename or not filename.endswith(".md"):
        raise HTTPException(status_code=400, detail="Only safe .md filenames are allowed.")
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    report_path = ARCHIVE_DIR / filename
    report_path.write_text(request.content, encoding="utf-8")
    return {"filename": filename, "imported": import_markdown_file(DB_PATH, report_path)}


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
