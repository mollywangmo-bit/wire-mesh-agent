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
    get_report,
    import_directory,
    import_markdown_file,
    init_db,
    list_reports,
    search_sections,
    trend_summary,
    opportunity_radar,
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
    if path.startswith("/api/import") and _has_valid_admin(
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
h2{font-size:18px;margin:0 0 14px}input{width:100%;padding:13px;border:1px solid #bcccdc;border-radius:10px;font-size:15px}button{margin-top:9px;padding:10px 14px;border:0;border-radius:9px;background:var(--brand);color:#fff;cursor:pointer;font-size:14px}.results{margin-top:14px}.item{padding:13px 0;border-bottom:1px solid var(--line)}.item:last-child{border:0}.report-link{display:block;width:100%;margin:0;padding:0;background:none;color:var(--ink);text-align:left;font-size:15px;font-weight:700}.meta{color:var(--muted);font-size:12px;margin-top:5px}.excerpt{color:#334e68;font-size:14px;line-height:1.6;margin-top:7px}.report-content{white-space:pre-wrap;color:#334e68;line-height:1.8;font-size:14px;max-height:720px;overflow:auto;padding-top:14px}.muted{color:var(--muted)}.analysis-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;margin-top:18px}.metric{display:flex;justify-content:space-between;gap:12px;padding:8px 0;border-bottom:1px solid var(--line)}.metric:last-child{border:0}.up{color:#087f5b}.down{color:#c92a2a}.timeline{border-left:2px solid #9cdbd8;padding-left:13px;margin:10px 0}.timeline .meta{margin-bottom:4px}
@media(max-width:760px){.grid,.analysis-grid{grid-template-columns:1fr}main{padding:20px 14px}header{padding:24px}h1{font-size:24px}}
</style></head><body><main>
<header><h1>丝网行业研报知识库工作台</h1><p class="sub">把已完成研报沉淀为可检索、可追溯的行业知识。</p><p class="notice">趋势指标基于研报文本提及，不等同于实时市场统计数据。</p></header>
<section class="grid"><div class="card"><h2>知识搜索</h2><input id="search" placeholder="例如：出口关税、原材料成本、欧洲需求"><button onclick="searchReports()">搜索研报</button><div id="search-results" class="results muted">输入关键词后，可查看相关章节与出处。</div></div>
<div class="card"><h2>AI 辅助问答</h2><input id="question" placeholder="例如：近期出口风险有哪些变化？"><button onclick="askQuestion()">基于研报回答</button><div id="answer" class="results muted">回答会附带来源片段；没有证据时会明确提示。</div></div></section>
<section class="analysis-grid"><div class="card"><h2>本周变化</h2><p id="weekly-caption" class="muted">加载中...</p><div id="weekly-changes" class="muted"></div></div><div class="card"><h2>行业机会雷达</h2><p class="muted">近四期研报中的相关提及强度。</p><div id="radar" class="muted">加载中...</div></div></section>
<section class="analysis-grid"><div class="card"><h2>行业事件时间线</h2><div id="timeline" class="muted">加载中...</div></div><div class="card"><h2>企业与区域地图</h2><p class="muted">基于报告正文提及，不代表市场份额或覆盖全量。</p><div id="entity-map" class="muted">加载中...</div></div></section>
<section class="card" style="margin-top:18px"><h2>历史研报</h2><p class="muted">点击报告即可查看完整内容。</p><div id="reports" class="muted">加载中...</div></section>
<section id="reader" class="card" style="margin-top:18px;display:none"><button style="float:right;margin:0" onclick="closeReport()">关闭</button><h2 id="report-title">研报原文</h2><div id="report-meta" class="meta"></div><article id="report-content" class="report-content"></article></section>
</main><script>
const esc=s=>String(s).replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const label={weekly:'周报',weekly_brief:'精简周报',monthly:'月报',price_cost:'成本/价格',demand:'需求',export:'出口',competition:'竞争',policy:'政策',regional:'区域'};
async function json(url,opts){const r=await fetch(url,opts);if(!r.ok)throw new Error('请求失败');return r.json()}
function metric(name,value,delta){const sign=delta>0?'+':'';const tone=delta>0?'up':delta<0?'down':'';return `<div class="metric"><span>${esc(name)}</span><strong class="${tone}">${value} 次 ${sign}${delta}</strong></div>`}
async function load(){try{const [reports,changes,radar,timeline,entities]=await Promise.all([json('/api/reports'),json('/api/analysis/weekly-changes'),json('/api/analysis/opportunity-radar'),json('/api/analysis/timeline'),json('/api/analysis/entity-map')]);document.querySelector('#reports').innerHTML=reports.length?reports.map(r=>`<div class="item"><button class="report-link" onclick="openReport('${r.id}')">${esc(r.title)}</button></div>`).join(''):'尚未导入报告。';document.querySelector('#weekly-caption').textContent=changes.latest?(changes.latest.date+' 对比 '+(changes.previous?changes.previous.date:'首期报告')):'尚无周报';document.querySelector('#weekly-changes').innerHTML=changes.changes.length?changes.changes.slice(0,5).map(x=>metric(label[x.signal]||x.signal,x.count,x.delta)).join(''):'导入至少一份周报后显示。';document.querySelector('#radar').innerHTML=radar.map(x=>`<div class="metric"><span>${esc(x.theme)}<div class="meta">${esc(x.sources.slice(0,2).join('；')||'暂无提及')}</div></span><strong>${x.mentions} 次</strong></div>`).join('');document.querySelector('#timeline').innerHTML=timeline.length?timeline.map(x=>`<div class="timeline"><div class="meta">${esc(x.date)} · ${esc(x.title)}</div><div class="excerpt">${esc(x.text)}</div></div>`).join(''):'尚未检索到行业事件。';const groups=[['区域',entities.regions],['企业',entities.companies]];document.querySelector('#entity-map').innerHTML=groups.map(([title,items])=>`<div class="item"><strong>${title}</strong><div>${items.length?items.map(x=>`<span class="tag">${esc(x.name)} ${x.mentions}</span>`).join(''):'暂无识别结果'}</div></div>`).join('')}catch(e){['reports','weekly-changes','radar','timeline','entity-map'].forEach(id=>document.querySelector('#'+id).textContent='暂时无法读取数据。')}}
async function openReport(id){const reader=document.querySelector('#reader');document.querySelector('#report-title').textContent='加载报告中...';document.querySelector('#report-content').textContent='';reader.style.display='block';reader.scrollIntoView({behavior:'smooth',block:'start'});try{const report=await json('/api/reports/'+encodeURIComponent(id));document.querySelector('#report-title').textContent=report.title;document.querySelector('#report-meta').textContent=(label[report.report_type]||report.report_type)+' · '+new Date(report.imported_at).toLocaleDateString();document.querySelector('#report-content').textContent=report.content}catch(e){document.querySelector('#report-title').textContent='报告暂时无法读取。'}}
function closeReport(){document.querySelector('#reader').style.display='none'}
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
