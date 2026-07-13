"""
运行清单（manifest）生成。

每次流水线运行结束后写出一份 JSON，记录：
- run_id / period / variants
- 每个版本生成了哪些文件、大小、失败原因
- 每个版本投递是否成功

这份文件是排障和审计的“飞行记录仪”。
"""
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from artifact_renderer import ArtifactResult, ReportArtifacts
from report_variants import ReportVariant


@dataclass
class VariantRunResult:
    """单个报告版本的一次运行结果。"""

    variant: ReportVariant
    artifacts: ReportArtifacts
    delivered: bool


def make_run_id(period: str, started_at: datetime) -> str:
    """生成稳定、可读的 run id。"""
    return f"{started_at.strftime('%Y%m%d_%H%M%S')}_{period}"


def _artifact_to_dict(result: ArtifactResult) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "path": str(result.path) if result.path else None,
        "size_bytes": result.size_bytes,
        "error": result.error,
    }


def write_manifest(
    *,
    output_dir: str | Path,
    run_id: str,
    period: str,
    started_at: datetime,
    finished_at: datetime,
    results: list[VariantRunResult],
) -> Path:
    """写出本次运行 manifest.json。"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "run_id": run_id,
        "period": period,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_seconds": round((finished_at - started_at).total_seconds(), 2),
        "variants": [
            {
                "label": item.variant.label,
                "file_prefix": item.variant.file_prefix,
                "delivered": item.delivered,
                "artifacts": {
                    "md": _artifact_to_dict(item.artifacts.md),
                    "html": _artifact_to_dict(item.artifacts.html),
                    "docx": _artifact_to_dict(item.artifacts.docx),
                    "pdf": _artifact_to_dict(item.artifacts.pdf),
                },
            }
            for item in results
        ],
    }

    manifest_path = output_dir / f"wire_mesh_manifest_{run_id}.json"
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest_path
