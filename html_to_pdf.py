"""
丝网行业研究 Agent - HTML 转 PDF

使用 WeasyPrint 将 HTML 报告转换为 PDF，
保留样式、超链接和 SVG fallback 图表。

若 WeasyPrint 不可用，fallback 到 fpdf2 (reporter.py)。
"""
from pathlib import Path
from typing import Optional
import warnings


def html_to_pdf(html_path: str | Path, output_path: str | Path,
                fallback_md_report: Optional[str] = None) -> str:
    """Convert HTML file to PDF using WeasyPrint.

    Args:
        html_path: Path to the input HTML file (from html_reporter)
        output_path: Path to write the PDF file
        fallback_md_report: Optional markdown report text for fpdf2 fallback

    Returns:
        Path to the generated PDF file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Try WeasyPrint first
    try:
        import weasyprint
        html = weasyprint.HTML(filename=str(html_path))
        html.write_pdf(str(output_path))
        print(f"  [PDF] ✓ 报告已生成 (WeasyPrint): {output_path}")
        return str(output_path)

    except ImportError:
        print("  [PDF] ⚠ WeasyPrint 未安装，使用 fpdf2 降级方案")
        print("        pip install weasyprint 可启用高质量 PDF 输出")
    except Exception as e:
        print(f"  [PDF] ⚠ WeasyPrint 转换失败 ({e})，使用 fpdf2 降级方案")

    # Fallback: use fpdf2 (reporter.py)
    if fallback_md_report:
        try:
            from reporter import generate_pdf
            return generate_pdf(fallback_md_report, output_path)
        except Exception as e2:
            print(f"  [PDF] ✗ fpdf2 降级也失败: {e2}")

    warnings.warn(f"PDF 生成失败: {output_path}")
    return str(output_path)
