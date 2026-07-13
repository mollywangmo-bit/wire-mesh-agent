"""
跨周历史去重存储。

用于区分“本周新增变化”和“反复出现的旧内容”。
当前实现是轻量 JSON 文件，适合先解决周报重复问题。
"""
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def _normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\u4e00-\u9fff\u3040-\u30ff]+", " ", text)
    return text.strip()


def _normalize_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    return f"{scheme}://{netloc}{path}"


def fingerprint_item(item) -> str:
    """生成稳定指纹：优先 URL，缺 URL 时用标题+摘要。"""
    url = _normalize_url(getattr(item, "url", "") or "")
    if url:
        base = f"url:{url}"
    else:
        title = _normalize_text(getattr(item, "title", "") or "")
        snippet = _normalize_text((getattr(item, "snippet", "") or "")[:300])
        base = f"text:{title}|{snippet}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


class HistoryStore:
    """JSON-backed seen-item store."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.data: dict[str, Any] = {"items": {}}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
            self.data.setdefault("items", {})
        except Exception:
            self.data = {"items": {}}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def has_seen(self, item) -> bool:
        return fingerprint_item(item) in self.data.get("items", {})

    def seen_count(self, item) -> int:
        fp = fingerprint_item(item)
        entry = self.data.get("items", {}).get(fp, {})
        return int(entry.get("seen_count", 0) or 0)

    def record_items(self, items: list, *, used_fingerprints: set[str] | None = None) -> None:
        """记录本次采集项。

        Args:
            items: NewsItem-like objects.
            used_fingerprints: 本次进入精简版候选/报告的指纹集合。
        """
        used_fingerprints = used_fingerprints or set()
        now = datetime.now().strftime("%Y-%m-%d")
        store = self.data.setdefault("items", {})

        for item in items:
            fp = fingerprint_item(item)
            entry = store.setdefault(
                fp,
                {
                    "first_seen": now,
                    "seen_count": 0,
                    "title": getattr(item, "title", ""),
                    "url": getattr(item, "url", ""),
                    "source": getattr(item, "source", ""),
                    "category": getattr(item, "category", ""),
                },
            )
            entry["last_seen"] = now
            entry["seen_count"] = int(entry.get("seen_count", 0) or 0) + 1
            entry["title"] = getattr(item, "title", "") or entry.get("title", "")
            entry["url"] = getattr(item, "url", "") or entry.get("url", "")
            entry["source"] = getattr(item, "source", "") or entry.get("source", "")
            entry["category"] = getattr(item, "category", "") or entry.get("category", "")
            if fp in used_fingerprints:
                entry["last_used_in_briefing"] = now
