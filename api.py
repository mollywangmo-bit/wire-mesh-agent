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

_last_monthly_run = {
    "status": "never_run",
    "started_at": None,
    "finished_at": None,
    "error": None,
}


@app.get("/")
def root():
    """根路径 — 部分部署平台用此做健康检查"""
    return {
        "service": "丝网行业研究 Agent",
        "status": "alive",
        "endpoints": {"/health": "GET", "/run": "POST", "/run/monthly": "POST", "/run/status": "GET"},
    }


@app.post("/")
def root_trigger(background_tasks: BackgroundTasks):
    """根路径 POST — 部分部署平台的 cron 机制发 POST /"""
    return trigger_run(background_tasks)


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
    """执行周报流水线并记录结果"""
    _last_run["status"] = "running"
    _last_run["started_at"] = datetime.now(timezone.utc).isoformat()
    _last_run["error"] = None

    try:
        run_once()
        _last_run["status"] = "success"
    except Exception as exc:
        _last_run["status"] = "failed"
        _last_run["error"] = str(exc)
        print(f"[Agent] 周报流水线执行失败: {exc}", file=sys.stderr)
    finally:
        _last_run["finished_at"] = datetime.now(timezone.utc).isoformat()


@app.post("/run/monthly")
def trigger_monthly(background_tasks: BackgroundTasks):
    """触发月报流水线（每月1号执行）"""
    if _last_monthly_run["status"] == "running":
        return {"status": "skipped", "reason": "月报流水线正在执行中，请稍后再试"}

    background_tasks.add_task(_execute_monthly_pipeline)
    return {"status": "started", "message": "月报流水线已启动，将在后台执行"}


def _execute_monthly_pipeline():
    """执行月报流水线并记录结果"""
    _last_monthly_run["status"] = "running"
    _last_monthly_run["started_at"] = datetime.now(timezone.utc).isoformat()
    _last_monthly_run["error"] = None

    try:
        run_once(period="monthly")
        _last_monthly_run["status"] = "success"
    except Exception as exc:
        _last_monthly_run["status"] = "failed"
        _last_monthly_run["error"] = str(exc)
        print(f"[Agent] 月报流水线执行失败: {exc}", file=sys.stderr)
    finally:
        _last_monthly_run["finished_at"] = datetime.now(timezone.utc).isoformat()


@app.post("/debug/email")
def debug_email():
    """诊断邮件配置 — 发测试邮件并返回结果"""
    try:
        from config import load_config
        from delivery import Delivery
        cfg = load_config()
        # 检查配置状态
        config_status = {
            "smtp_server": bool(cfg.smtp_server),
            "smtp_port": bool(cfg.smtp_port),
            "smtp_user": bool(cfg.smtp_user),
            "smtp_password": bool(cfg.smtp_password),
            "email_to": bool(cfg.email_to),
        }
        delivery = Delivery(cfg)
        ok = delivery.send_email(
            "【诊断邮件】来自 Zeabur 的测试消息。如果收到说明 SMTP 配置正确。",
            prefix="诊断"
        )
        return {
            "config_status": config_status,
            "send_result": ok,
        }
    except Exception as e:
        return {"error": str(e)}
