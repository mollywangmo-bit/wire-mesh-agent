"""
丝网行业研究 Agent — Zeabur 部署 API 服务

提供健康检查和定时触发入口：
- GET  /health       — 健康检查
- POST /run          — 触发完整流水线（异步执行）
- GET  /run/status   — 查看最近一次运行状态
"""
import sys
from datetime import datetime, timezone

from fastapi import FastAPI, BackgroundTasks

from main import run_once

app = FastAPI(title="丝网行业研究 Agent")

_last_run = {
    "status": "never_run",
    "started_at": None,
    "finished_at": None,
    "error": None,
}


@app.get("/health")
def health():
    """Zeabur 健康检查"""
    return {
        "status": "alive",
        "last_run_status": _last_run["status"],
        "last_run_at": _last_run["finished_at"],
    }


@app.get("/run/status")
def run_status():
    """查看最近一次运行状态"""
    return _last_run


@app.post("/run")
def trigger_run(background_tasks: BackgroundTasks):
    """触发完整流水线（异步执行，立即返回）"""
    if _last_run["status"] == "running":
        return {"status": "skipped", "reason": "流水线正在执行中，请稍后再试"}

    background_tasks.add_task(_execute_pipeline)
    return {"status": "started", "message": "流水线已启动，将在后台执行"}


def _execute_pipeline():
    """执行流水线并记录结果"""
    _last_run["status"] = "running"
    _last_run["started_at"] = datetime.now(timezone.utc).isoformat()
    _last_run["error"] = None

    try:
        run_once()
        _last_run["status"] = "success"
    except Exception as exc:
        _last_run["status"] = "failed"
        _last_run["error"] = str(exc)
        print(f"[Agent] 流水线执行失败: {exc}", file=sys.stderr)
    finally:
        _last_run["finished_at"] = datetime.now(timezone.utc).isoformat()
