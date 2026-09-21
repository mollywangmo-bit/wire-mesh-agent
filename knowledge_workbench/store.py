"""SQLite-backed ingestion, retrieval, and signal aggregation for the workbench."""
from __future__ import annotations

import hashlib
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


SIGNALS: dict[str, tuple[str, ...]] = {
    "price_cost": ("价格", "成本", "原材料", "钢材", "不锈钢", "涨价", "降价"),
    "demand": ("需求", "订单", "采购", "询盘", "旺季", "产能利用"),
    "export": ("出口", "关税", "海运", "汇率", "海外", "欧洲", "美国"),
    "competition": ("竞争", "替代", "份额", "产能", "招标", "价格战"),
    "policy": ("政策", "法规", "合规", "反倾销", "环保", "监管"),
    "regional": ("中东", "东南亚", "欧洲", "北美", "拉美", "非洲", "国内"),
}

OPPORTUNITY_THEMES: dict[str, tuple[str, ...]] = {
    "新能源与氢能": ("氢能", "电解槽", "储氢", "新能源", "燃料电池"),
    "高端过滤": ("过滤", "滤网", "滤材", "净化", "分离"),
    "电子与精密制造": ("网版", "电子", "精密", "半导体", "蚀刻"),
    "海外市场": ("出口", "海外", "欧洲", "美国", "东南亚", "中东"),
}
REGIONS = ("中国", "国内", "欧洲", "美国", "北美", "东南亚", "中东", "拉美", "非洲", "日本", "韩国", "印度")
EVENT_TERMS = ("展会", "政策", "法规", "关税", "反倾销", "投产", "签约", "订单", "招标", "发布", "涨价", "降价")


def _connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str | Path) -> None:
    with _connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                report_type TEXT NOT NULL,
                source_path TEXT NOT NULL,
                content_hash TEXT NOT NULL UNIQUE,
                imported_at TEXT NOT NULL,
                content TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sections (
                id TEXT PRIMARY KEY,
                report_id TEXT NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
                heading TEXT NOT NULL,
                position INTEGER NOT NULL,
                content TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS report_signals (
                report_id TEXT NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
                signal_name TEXT NOT NULL,
                mention_count INTEGER NOT NULL,
                PRIMARY KEY (report_id, signal_name)
            );
            CREATE INDEX IF NOT EXISTS idx_reports_type_imported
              ON reports(report_type, imported_at DESC);
            CREATE INDEX IF NOT EXISTS idx_sections_report_position
              ON sections(report_id, position);
            CREATE INDEX IF NOT EXISTS idx_signals_name_report
              ON report_signals(signal_name, report_id);
            """
        )
        conn.execute("PRAGMA optimize")


def classify_report(path: Path) -> str:
    name = path.name.lower()
    if "monthly" in name or "月报" in path.name:
        return "monthly"
    if "brief" in name or "精简" in path.name:
        return "weekly_brief"
    return "weekly"


def title_from_markdown(text: str, path: Path) -> str:
    match = re.search(r"^#\s+(.+?)\s*$", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else path.stem.replace("_", " ")


def split_sections(text: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"^#{2,6}\s+(.+?)\s*$", text, flags=re.MULTILINE))
    if not matches:
        clean = text.strip()
        return [("正文", clean)] if clean else []

    sections: list[tuple[str, str]] = []
    leading = text[: matches[0].start()].strip()
    if leading:
        sections.append(("摘要", leading))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        content = text[match.end() : end].strip()
        if content:
            sections.append((match.group(1).strip(), content))
    return sections


def signal_counts(text: str) -> dict[str, int]:
    return {name: sum(text.count(word) for word in words) for name, words in SIGNALS.items()}


def _make_id(value: str, length: int = 20) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def import_markdown_file(db_path: str | Path, file_path: str | Path) -> bool:
    path = Path(file_path)
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return False
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    report_id = _make_id(digest)
    imported_at = datetime.now(timezone.utc).isoformat()

    with _connect(db_path) as conn:
        existing = conn.execute(
            "SELECT id FROM reports WHERE content_hash = ?", (digest,)
        ).fetchone()
        if existing:
            return False
        conn.execute(
            """INSERT INTO reports
               (id, title, report_type, source_path, content_hash, imported_at, content)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                report_id,
                title_from_markdown(text, path),
                classify_report(path),
                str(path),
                digest,
                imported_at,
                text,
            ),
        )
        for position, (heading, content) in enumerate(split_sections(text)):
            conn.execute(
                "INSERT INTO sections (id, report_id, heading, position, content) VALUES (?, ?, ?, ?, ?)",
                (_make_id(f"{report_id}:{position}"), report_id, heading, position, content),
            )
        for name, count in signal_counts(text).items():
            conn.execute(
                "INSERT INTO report_signals (report_id, signal_name, mention_count) VALUES (?, ?, ?)",
                (report_id, name, count),
            )
    return True


def import_directory(db_path: str | Path, archive_dir: str | Path) -> dict[str, int]:
    init_db(db_path)
    root = Path(archive_dir)
    result = {"scanned": 0, "imported": 0, "skipped": 0}
    if not root.exists():
        return result
    for path in sorted(root.rglob("*.md")):
        result["scanned"] += 1
        if import_markdown_file(db_path, path):
            result["imported"] += 1
        else:
            result["skipped"] += 1
    return result


def list_reports(db_path: str | Path, limit: int = 50) -> list[dict]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """SELECT id, title, report_type, source_path, imported_at,
                      length(content) AS content_length
               FROM reports ORDER BY imported_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_report(db_path: str | Path, report_id: str) -> dict | None:
    with _connect(db_path) as conn:
        report = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
        if not report:
            return None
        sections = conn.execute(
            "SELECT id, heading, position, content FROM sections WHERE report_id = ? ORDER BY position",
            (report_id,),
        ).fetchall()
    data = dict(report)
    data["sections"] = [dict(section) for section in sections]
    return data


def search_sections(db_path: str | Path, query: str, limit: int = 12) -> list[dict]:
    terms = [term for term in re.split(r"\s+", query.strip()) if term]
    if not terms:
        return []
    conditions = " AND ".join("s.content LIKE ?" for _ in terms)
    params: list[object] = [f"%{term}%" for term in terms] + [limit]
    sql = f"""
        SELECT s.id AS section_id, s.heading, s.content, r.id AS report_id,
               r.title, r.report_type, r.imported_at
        FROM sections s JOIN reports r ON r.id = s.report_id
        WHERE {conditions}
        ORDER BY r.imported_at DESC, s.position ASC
        LIMIT ?
    """
    with _connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def trend_summary(db_path: str | Path) -> list[dict]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """SELECT rs.signal_name, COUNT(*) AS report_count,
                      SUM(rs.mention_count) AS mention_count
               FROM report_signals rs
               WHERE rs.mention_count > 0
               GROUP BY rs.signal_name
               ORDER BY mention_count DESC, rs.signal_name"""
        ).fetchall()
    return [dict(row) for row in rows]


def dashboard_stats(db_path: str | Path) -> dict:
    with _connect(db_path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
        latest = conn.execute(
            "SELECT id, title, report_type, imported_at FROM reports ORDER BY imported_at DESC LIMIT 1"
        ).fetchone()
    return {"report_count": total, "latest_report": dict(latest) if latest else None}


def _report_date(report: dict) -> str:
    """Use the report filename date so historical imports retain chronological order."""
    match = re.search(r"(20\d{2})[-_\s]*(\d{2})[-_\s]*(\d{2})", report["source_path"])
    return "-".join(match.groups()) if match else "0000-00-00"


def _reports_in_chronological_order(db_path: str | Path) -> list[dict]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, title, report_type, source_path, content FROM reports"
        ).fetchall()
    return sorted((dict(row) for row in rows), key=_report_date)


def weekly_changes(db_path: str | Path) -> dict:
    reports = [r for r in _reports_in_chronological_order(db_path) if r["report_type"] == "weekly"]
    if not reports:
        return {"latest": None, "previous": None, "changes": []}
    latest = reports[-1]
    previous = reports[-2] if len(reports) > 1 else None
    latest_counts = signal_counts(latest["content"])
    previous_counts = signal_counts(previous["content"]) if previous else {}
    changes = []
    for signal, count in latest_counts.items():
        delta = count - previous_counts.get(signal, 0)
        changes.append({"signal": signal, "count": count, "delta": delta})
    changes.sort(key=lambda item: (abs(item["delta"]), item["count"]), reverse=True)
    return {
        "latest": {"id": latest["id"], "title": latest["title"], "date": _report_date(latest)},
        "previous": ({"id": previous["id"], "title": previous["title"], "date": _report_date(previous)} if previous else None),
        "changes": changes,
    }


def opportunity_radar(db_path: str | Path) -> list[dict]:
    reports = _reports_in_chronological_order(db_path)[-4:]
    result = []
    for theme, terms in OPPORTUNITY_THEMES.items():
        mentions = sum(sum(report["content"].count(term) for term in terms) for report in reports)
        sources = [report["title"] for report in reports if any(term in report["content"] for term in terms)]
        result.append({"theme": theme, "mentions": mentions, "sources": sources})
    return sorted(result, key=lambda item: item["mentions"], reverse=True)


def event_timeline(db_path: str | Path, limit: int = 16) -> list[dict]:
    events: list[dict] = []
    for report in reversed(_reports_in_chronological_order(db_path)):
        lines = [line.strip(" -•\t") for line in report["content"].splitlines()]
        for line in lines:
            if len(line) >= 16 and any(term in line for term in EVENT_TERMS):
                events.append({"date": _report_date(report), "title": report["title"], "text": line[:220]})
                if len(events) >= limit:
                    return events
    return events


def entity_map(db_path: str | Path) -> dict:
    reports = _reports_in_chronological_order(db_path)
    text = "\n".join(report["content"] for report in reports)
    regions = [{"name": region, "mentions": text.count(region)} for region in REGIONS if text.count(region)]
    companies = re.findall(r"[\u4e00-\u9fff]{2,18}(?:股份有限公司|有限公司|集团)", text)
    company_counts: dict[str, int] = {}
    for company in companies:
        company_counts[company] = company_counts.get(company, 0) + 1
    return {
        "regions": sorted(regions, key=lambda item: item["mentions"], reverse=True),
        "companies": [
            {"name": name, "mentions": count}
            for name, count in sorted(company_counts.items(), key=lambda item: item[1], reverse=True)[:12]
        ],
    }
