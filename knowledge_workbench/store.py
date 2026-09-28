"""SQLite-backed ingestion, retrieval, and signal aggregation for the workbench."""
from __future__ import annotations

import hashlib
import re
import sqlite3
from datetime import datetime, timedelta, timezone
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

EVENT_TYPES: dict[str, tuple[str, ...]] = {
    "investment": ("投资", "投资额", "融资"), "capacity_expansion": ("扩产", "投产", "产能", "项目点火"),
    "new_product": ("新品", "推出", "发布", "新产品"), "technology_breakthrough": ("突破", "研发", "专利"),
    "customer_validation": ("验证", "认证", "客户导入"), "order": ("订单", "中标", "招标"),
    "partnership": ("合作", "签约", "联合"), "policy": ("政策", "补贴"), "export": ("出口", "关税", "海外"),
    "price_change": ("涨价", "降价", "价格"), "market_demand": ("需求", "采购", "询盘"),
    "regulation": ("法规", "监管", "反倾销", "合规"),
}
THEME_RULES: dict[str, tuple[str, ...]] = {
    "精密过滤": ("精密过滤", "过滤网", "滤网", "滤材"), "半导体过滤": ("半导体", "晶圆", "高纯过滤"),
    "医疗金属编织": ("医疗", "镍钛", "神经介入", "编织网"), "制氢镍网": ("制氢", "电解槽", "镍网", "氢能"),
    "精密网版": ("网版", "丝印", "电子网版"), "工业过滤": ("工业过滤", "过滤", "分离"),
    "新能源电池网": ("电池", "光伏", "储能"), "高性能材料": ("玄武岩", "高性能纤维", "复合材料"),
}


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
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY, event_date TEXT NOT NULL, detected_date TEXT NOT NULL,
                title TEXT NOT NULL, event_summary TEXT NOT NULL, event_type TEXT NOT NULL,
                evidence_text TEXT NOT NULL, confidence_score REAL NOT NULL,
                relevance_to_wire_mesh TEXT NOT NULL, relevance_to_anping TEXT NOT NULL,
                dedupe_key TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS event_sources (
                event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                report_id TEXT NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
                section_id TEXT REFERENCES sections(id) ON DELETE SET NULL,
                evidence_text TEXT NOT NULL,
                source_title TEXT,
                source_url TEXT,
                source_type TEXT,
                PRIMARY KEY (event_id, report_id, section_id)
            );
            CREATE TABLE IF NOT EXISTS themes (id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, description TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS event_themes (event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE, theme_id TEXT NOT NULL REFERENCES themes(id) ON DELETE CASCADE, PRIMARY KEY(event_id, theme_id));
            CREATE TABLE IF NOT EXISTS event_companies (event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE, name TEXT NOT NULL, PRIMARY KEY(event_id, name));
            CREATE TABLE IF NOT EXISTS event_regions (event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE, name TEXT NOT NULL, PRIMARY KEY(event_id, name));
            CREATE TABLE IF NOT EXISTS processing_jobs (report_id TEXT PRIMARY KEY REFERENCES reports(id) ON DELETE CASCADE, status TEXT NOT NULL, processed_at TEXT, error TEXT);
            CREATE INDEX IF NOT EXISTS idx_events_date_type ON events(event_date DESC, event_type);
            CREATE INDEX IF NOT EXISTS idx_event_sources_report ON event_sources(report_id);
            """
        )
        event_source_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(event_sources)").fetchall()
        }
        for column, declaration in (
            ("source_title", "TEXT"),
            ("source_url", "TEXT"),
            ("source_type", "TEXT"),
        ):
            if column not in event_source_columns:
                conn.execute(f"ALTER TABLE event_sources ADD COLUMN {column} {declaration}")
        for name in THEME_RULES:
            conn.execute("INSERT OR IGNORE INTO themes(id, name, description) VALUES (?, ?, ?)", (_make_id(f"theme:{name}"), name, f"{name}相关行业事件"))
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


def _first_url(text: str) -> str | None:
    match = re.search(r"https?://[^\s\)\]\>\"']+", text)
    return match.group(0).rstrip(".,，。；;") if match else None


def _event_date(report: dict) -> str:
    match = re.search(r"(20\d{2})[-_\s]*(\d{2})[-_\s]*(\d{2})", report["source_path"])
    return "-".join(match.groups()) if match else datetime.now(timezone.utc).date().isoformat()


def _event_type(text: str) -> str:
    for event_type, terms in EVENT_TYPES.items():
        if any(term in text for term in terms):
            return event_type
    return "other"


def _companies(text: str) -> list[str]:
    return sorted(set(re.findall(r"[\u4e00-\u9fffA-Za-z]{2,24}(?:股份有限公司|有限公司|集团)", text)))[:6]


def _themes(text: str) -> list[str]:
    return [name for name, terms in THEME_RULES.items() if any(term in text for term in terms)]


def _event_candidates(heading: str, content: str) -> list[dict]:
    lines = [line.strip() for line in content.splitlines()]
    linked_candidates: list[dict] = []
    linked_descriptions: set[str] = set()
    markdown_link = re.compile(r"\[([^\]]+)\]\((https?://[^\)]+)\)")
    for index, line in enumerate(lines):
        link = markdown_link.search(line)
        if not link:
            continue
        source_title, source_url = link.group(1).strip(), link.group(2).strip()
        description = ""
        for following in lines[index + 1 : index + 4]:
            if not following:
                continue
            if following.startswith(("#", "- ", "* ")) or markdown_link.search(following):
                break
            description = following.strip(" -•\t")
            break
        event_text = description or source_title
        if not any(term in event_text + source_title for terms in EVENT_TYPES.values() for term in terms):
            continue
        if description:
            linked_descriptions.add(description)
        themes = _themes(event_text + " " + source_title)
        linked_candidates.append({
            "title": source_title[:90], "summary": event_text[:260],
            "event_type": _event_type(event_text + " " + source_title),
            "companies": _companies(event_text + " " + source_title),
            "regions": [region for region in REGIONS if region in event_text + source_title],
            "themes": themes, "evidence": event_text, "heading": heading,
            "source_title": source_title, "source_url": source_url,
            "source_type": "wechat" if "mp.weixin.qq.com" in source_url else "web",
        })
    chunks = [part.strip(" -•\t") for part in re.split(r"\n+|(?<=[。！？])", content)]
    candidates = list(linked_candidates)
    for chunk in chunks:
        if markdown_link.search(chunk) or any(chunk in description for description in linked_descriptions) or len(chunk) < 20 or not any(term in chunk for terms in EVENT_TYPES.values() for term in terms):
            continue
        themes = _themes(chunk)
        regions = [region for region in REGIONS if region in chunk]
        candidates.append({
            "title": chunk[:58].rstrip("，。；;"), "summary": chunk[:260], "event_type": _event_type(chunk),
            "companies": _companies(chunk), "regions": regions, "themes": themes, "evidence": chunk,
            "heading": heading, "source_title": None, "source_url": None, "source_type": None,
        })
    return candidates[:12]


def process_report_events(db_path: str | Path, report_id: str, force: bool = False) -> dict[str, int]:
    """Extract rule-based, source-linked events for one report and merge duplicates."""
    init_db(db_path)
    with _connect(db_path) as conn:
        job = conn.execute("SELECT status FROM processing_jobs WHERE report_id = ?", (report_id,)).fetchone()
        if job and job["status"] == "success" and not force:
            return {"created": 0, "merged": 0, "skipped": 1}
        report = conn.execute("SELECT id, title, source_path FROM reports WHERE id = ?", (report_id,)).fetchone()
        sections = conn.execute("SELECT id, heading, content FROM sections WHERE report_id = ?", (report_id,)).fetchall()
        if not report:
            raise ValueError(f"Unknown report {report_id}")
        report_data = dict(report)
        created = merged = 0
        now = datetime.now(timezone.utc).isoformat()
        try:
            for section in sections:
                for candidate in _event_candidates(section["heading"], section["content"]):
                    date = _event_date(report_data)
                    fingerprint = "|".join((candidate["event_type"], date[:7], ",".join(candidate["companies"]), ",".join(candidate["regions"]), ",".join(candidate["themes"]), candidate["title"][:24]))
                    dedupe_key = _make_id(fingerprint)
                    event = conn.execute("SELECT id FROM events WHERE dedupe_key = ?", (dedupe_key,)).fetchone()
                    if event:
                        event_id = event["id"]
                        merged += 1
                    else:
                        event_id = _make_id(f"event:{dedupe_key}")
                        relevance = "high" if candidate["themes"] else "medium"
                        conn.execute("INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (event_id, date, date, candidate["title"], candidate["summary"], candidate["event_type"], candidate["evidence"], 0.8 if candidate["companies"] else 0.6, relevance, relevance, dedupe_key, now))
                        created += 1
                    conn.execute("""INSERT OR IGNORE INTO event_sources
                        (event_id, report_id, section_id, evidence_text, source_title, source_url, source_type)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""", (event_id, report_id, section["id"], candidate["evidence"], candidate["source_title"], candidate["source_url"], candidate["source_type"]))
                    for theme in candidate["themes"]:
                        theme_id = _make_id(f"theme:{theme}")
                        conn.execute("INSERT OR IGNORE INTO event_themes VALUES (?, ?)", (event_id, theme_id))
                    for company in candidate["companies"]:
                        conn.execute("INSERT OR IGNORE INTO event_companies VALUES (?, ?)", (event_id, company))
                    for region in candidate["regions"]:
                        conn.execute("INSERT OR IGNORE INTO event_regions VALUES (?, ?)", (event_id, region))
            conn.execute("INSERT OR REPLACE INTO processing_jobs VALUES (?, 'success', ?, NULL)", (report_id, now))
        except Exception as exc:
            conn.execute("INSERT OR REPLACE INTO processing_jobs VALUES (?, 'failed', ?, ?)", (report_id, now, str(exc)))
            raise
    return {"created": created, "merged": merged, "skipped": 0}


def process_all_report_events(db_path: str | Path) -> dict[str, int]:
    with _connect(db_path) as conn:
        report_ids = [row[0] for row in conn.execute("SELECT id FROM reports")]
    total = {"reports": len(report_ids), "created": 0, "merged": 0, "skipped": 0}
    for report_id in report_ids:
        result = process_report_events(db_path, report_id)
        for key in ("created", "merged", "skipped"):
            total[key] += result[key]
    return total


def rebuild_all_report_events(db_path: str | Path) -> dict[str, int]:
    """Recreate derived event data while preserving reports and their sections."""
    init_db(db_path)
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM event_sources")
        conn.execute("DELETE FROM event_themes")
        conn.execute("DELETE FROM event_companies")
        conn.execute("DELETE FROM event_regions")
        conn.execute("DELETE FROM events")
        conn.execute("DELETE FROM processing_jobs")
    return process_all_report_events(db_path)


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
    process_report_events(db_path, report_id)
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


def event_feed(db_path: str | Path, limit: int = 40) -> list[dict]:
    with _connect(db_path) as conn:
        rows = conn.execute("""SELECT e.*, COUNT(DISTINCT es.report_id) AS source_count
            FROM events e LEFT JOIN event_sources es ON es.event_id=e.id
            GROUP BY e.id ORDER BY e.event_date DESC, e.created_at DESC LIMIT ?""", (limit,)).fetchall()
        result = []
        for row in rows:
            event = dict(row)
            event["themes"] = [x[0] for x in conn.execute("SELECT t.name FROM themes t JOIN event_themes et ON et.theme_id=t.id WHERE et.event_id=?", (event["id"],))]
            event["companies"] = [x[0] for x in conn.execute("SELECT name FROM event_companies WHERE event_id=?", (event["id"],))]
            event["regions"] = [x[0] for x in conn.execute("SELECT name FROM event_regions WHERE event_id=?", (event["id"],))]
            event["sources"] = [dict(x) for x in conn.execute("""SELECT r.id AS report_id, r.title, s.heading,
                es.source_title, es.source_url, es.source_type
                FROM event_sources es JOIN reports r ON r.id=es.report_id
                LEFT JOIN sections s ON s.id=es.section_id WHERE es.event_id=?
                ORDER BY es.source_url IS NULL, r.imported_at DESC""", (event["id"],))]
            event["original_url"] = next((source["source_url"] for source in event["sources"] if source["source_url"]), None) or _first_url(event["evidence_text"])
            result.append(event)
    return result


def event_trends(db_path: str | Path, days: int = 28) -> list[dict]:
    """Theme ranking from distinct events in two equal rolling windows."""
    today = datetime.now(timezone.utc).date()
    recent_start = (today - timedelta(days=days)).isoformat()
    previous_start = (today - timedelta(days=days * 2)).isoformat()
    with _connect(db_path) as conn:
        rows = conn.execute("""SELECT t.name,
            COUNT(DISTINCT CASE WHEN e.event_date >= ? THEN e.id END) AS recent_events,
            COUNT(DISTINCT CASE WHEN e.event_date >= ? AND e.event_date < ? THEN e.id END) AS previous_events,
            COUNT(DISTINCT CASE WHEN e.event_date >= ? THEN ec.name END) AS companies,
            COUNT(DISTINCT CASE WHEN e.event_date >= ? THEN er.name END) AS regions,
            COUNT(DISTINCT CASE WHEN e.event_date >= ? THEN es.report_id END) AS sources
            FROM themes t JOIN event_themes et ON et.theme_id=t.id JOIN events e ON e.id=et.event_id
            LEFT JOIN event_companies ec ON ec.event_id=e.id LEFT JOIN event_regions er ON er.event_id=e.id
            LEFT JOIN event_sources es ON es.event_id=e.id GROUP BY t.id""", (recent_start, previous_start, recent_start, recent_start, recent_start, recent_start)).fetchall()
    trends=[]
    for row in rows:
        item=dict(row); recent=item["recent_events"]; previous=item["previous_events"]
        growth = (recent - previous) / max(previous, 1)
        item["growth_rate"] = round(growth, 2)
        item["status"] = "快速升温" if growth >= 1 and recent >= 2 else "明显上升" if growth >= .5 else "小幅上升" if growth > 0 else "稳定" if growth == 0 else "下降"
        item["evidence_strength"] = "高" if item["sources"] >= 3 else "中" if item["sources"] >= 2 else "低"
        item["keywords"] = list(THEME_RULES.get(item["name"], ()))[:4]
        with _connect(db_path) as conn:
            news = conn.execute("""SELECT e.id, e.event_date, e.title,
                       MIN(es.report_id) AS report_id,
                       (SELECT es2.source_url FROM event_sources es2
                        WHERE es2.event_id=e.id AND es2.source_url IS NOT NULL
                        ORDER BY es2.source_type='wechat' DESC LIMIT 1) AS original_url
                FROM events e
                JOIN event_themes et ON et.event_id=e.id
                JOIN themes t ON t.id=et.theme_id
                LEFT JOIN event_sources es ON es.event_id=e.id
                WHERE t.name=? AND e.event_date>=?
                GROUP BY e.id ORDER BY original_url IS NULL, e.event_date DESC, e.created_at DESC LIMIT 3""",
                (item["name"], recent_start)).fetchall()
        item["news"] = [dict(entry) for entry in news]
        trends.append(item)
    return sorted(trends, key=lambda item: (item["recent_events"], item["growth_rate"], item["sources"]), reverse=True)
