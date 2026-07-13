"""
报告产物渲染。

统一负责将一个 ReportVariant 输出为 MD / HTML / DOCX / PDF 四类文件。
main.py 不再关心每种格式的具体生成细节。
"""
import os
from dataclasses import dataclass
from pathlib import Path

from report_variants import ReportVariant


@dataclass
class ArtifactResult:
    """单个格式产物的生成结果。"""

    path: Path | None = None
    ok: bool = False
    size_bytes: int = 0
    error: str | None = None


@dataclass
class ReportArtifacts:
    """单个报告版本生成出的文件集合。"""

    md: ArtifactResult
    html: ArtifactResult
    docx: ArtifactResult
    pdf: ArtifactResult

    @property
    def md_path(self) -> Path | None:
        return self.md.path if self.md.ok else None

    @property
    def html_path(self) -> Path | None:
        return self.html.path if self.html.ok else None

    @property
    def docx_path(self) -> Path | None:
        return self.docx.path if self.docx.ok else None

    @property
    def pdf_path(self) -> Path | None:
        return self.pdf.path if self.pdf.ok else None


def _file_size_kb(path: Path) -> float:
    return os.path.getsize(path) / 1024


def _success(path: Path) -> ArtifactResult:
    return ArtifactResult(path=path, ok=True, size_bytes=path.stat().st_size)


def _failure(error: Exception | str) -> ArtifactResult:
    return ArtifactResult(ok=False, error=str(error))


def render_report_artifacts(
    variant: ReportVariant,
    *,
    output_dir: str | Path,
    date_str: str,
) -> ReportArtifacts:
    """为一个报告版本生成全部本地产物。

    Args:
        variant: 报告版本。
        output_dir: 输出目录。
        date_str: 日期字符串，用于文件名。

    Returns:
        已成功生成的 artifact 路径集合。失败的格式为 None。
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts = ReportArtifacts(
        md=ArtifactResult(),
        html=ArtifactResult(),
        docx=ArtifactResult(),
        pdf=ArtifactResult(),
    )

    # 保存 MD
    md_path = output_dir / f"wire_mesh_{variant.file_prefix}_report_{date_str}.md"
    try:
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(variant.text)
        artifacts.md = _success(md_path)
        print(f"  MD 已保存: {md_path}")
    except Exception as e:
        artifacts.md = _failure(e)
        print(f"  MD 保存失败: {e}")

    # 生成 HTML
    try:
        from html_reporter import generate_html_report

        html_path = output_dir / f"wire_mesh_{variant.file_prefix}_report_{date_str}.html"
        generate_html_report(variant.text, html_path)
        artifacts.html = _success(html_path)
        print(f"  HTML 已生成: {html_path} ({_file_size_kb(html_path):.0f} KB)")
    except Exception as e:
        artifacts.html = _failure(e)
        print(f"  HTML 生成失败: {e}")

    # 生成 Word
    try:
        from docx_reporter import generate_docx

        docx_path = output_dir / f"wire_mesh_{variant.file_prefix}_report_{date_str}.docx"
        generate_docx(variant.text, docx_path)
        artifacts.docx = _success(docx_path)
        print(f"  Word 已生成: {docx_path} ({_file_size_kb(docx_path):.0f} KB)")
    except Exception as e:
        artifacts.docx = _failure(e)
        print(f"  Word 生成失败: {e}")

    # 生成 PDF（依赖 HTML）
    if artifacts.html_path:
        try:
            from html_to_pdf import html_to_pdf

            pdf_path = output_dir / f"wire_mesh_{variant.file_prefix}_report_{date_str}.pdf"
            generated_pdf = html_to_pdf(artifacts.html_path, pdf_path)
            artifacts.pdf = _success(Path(generated_pdf)) if generated_pdf else _failure("PDF 未生成")
        except Exception as e:
            artifacts.pdf = _failure(e)
            print(f"  PDF 生成失败: {e}")
    else:
        artifacts.pdf = _failure("HTML 未生成，跳过 PDF")
        print("  PDF 跳过：HTML 未生成")

    return artifacts
