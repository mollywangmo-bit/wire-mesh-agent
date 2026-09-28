"""Export source-level article records for the independent knowledge workbench."""
from __future__ import annotations

import json
import os
from pathlib import Path

import httpx


def build_article_manifest(items: list, *, report_filename: str) -> dict:
    articles = []
    seen_urls: set[str] = set()
    for item in items:
        url = (getattr(item, "url", "") or "").strip()
        if not url or url.startswith("/") or url in seen_urls:
            continue
        seen_urls.add(url)
        articles.append(
            {
                "title": getattr(item, "title", "") or url,
                "url": url,
                "snippet": getattr(item, "snippet", "") or "",
                "source": getattr(item, "source", "") or "",
                "date": getattr(item, "date", "") or "",
                "category": getattr(item, "category", "") or "",
            }
        )
    return {"report_filename": report_filename, "articles": articles}


def write_article_manifest(items: list, output_dir: str | Path, *, report_filename: str) -> Path:
    manifest = build_article_manifest(items, report_filename=report_filename)
    path = Path(output_dir) / report_filename.replace("_report_", "_articles_").replace(".md", ".json")
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def sync_article_manifest(manifest_path: str | Path) -> bool:
    """Best-effort downstream sync; never raises into the report delivery flow."""
    base_url = os.getenv("KNOWLEDGE_WORKBENCH_URL", "").rstrip("/")
    token = os.getenv("KNOWLEDGE_WORKBENCH_ADMIN_TOKEN", "")
    if not base_url or not token:
        return False
    try:
        payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        response = httpx.post(
            f"{base_url}/api/import/articles",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
            timeout=15,
        )
        response.raise_for_status()
        return True
    except Exception as exc:
        print(f"  [知识库文章同步] 跳过: {exc}")
        return False
