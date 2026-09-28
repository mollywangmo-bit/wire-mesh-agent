"""Export and best-effort sync source articles to the knowledge workbench."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import httpx


def build_article_manifest(
    items: list,
    *,
    report_filename: str,
    report_text: str | None = None,
) -> dict:
    cited_urls = None
    if report_text is not None:
        cited_urls = set(re.findall(r"https?://[^\s\)\]>\"']+", report_text))
    articles = []
    seen_urls: set[str] = set()
    for item in items:
        url = (getattr(item, "url", "") or "").strip()
        if (
            not url
            or url.startswith("/")
            or url in seen_urls
            or (cited_urls is not None and url not in cited_urls)
        ):
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


def write_article_manifest(
    items: list,
    output_dir: str | Path,
    *,
    report_filename: str,
    report_text: str | None = None,
) -> Path:
    manifest = build_article_manifest(
        items,
        report_filename=report_filename,
        report_text=report_text,
    )
    path = Path(output_dir) / report_filename.replace("_report_", "_articles_").replace(".md", ".json")
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def sync_knowledge_workbench(report_path: str | Path, manifest_path: str | Path) -> bool:
    """Upload report and source articles without raising into report delivery."""
    base_url = os.getenv("KNOWLEDGE_WORKBENCH_URL", "").rstrip("/")
    token = os.getenv("KNOWLEDGE_WORKBENCH_ADMIN_TOKEN", "")
    if not base_url or not token:
        return False
    try:
        report_path = Path(report_path)
        headers = {"Authorization": f"Bearer {token}"}
        with httpx.Client(timeout=20) as client:
            report_response = client.post(
                f"{base_url}/api/import/report",
                headers=headers,
                json={
                    "filename": report_path.name,
                    "content": report_path.read_text(encoding="utf-8"),
                },
            )
            report_response.raise_for_status()
            article_response = client.post(
                f"{base_url}/api/import/articles",
                headers=headers,
                json=json.loads(Path(manifest_path).read_text(encoding="utf-8")),
            )
            article_response.raise_for_status()
        return True
    except Exception as exc:
        print(f"  [知识库同步] 跳过: {exc}")
        return False
