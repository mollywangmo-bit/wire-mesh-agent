"""
丝网行业研究 Agent - HTML 转 PDF

使用 Playwright（Chromium 真浏览器）将 HTML 报告打印为 PDF，
完整保留 CSS 样式、Chart.js 图表、SVG 回退和超链接。

依赖: pip install playwright && playwright install chromium

与 docx_reporter.py 互补：
  - docx → 可编辑，方便收件人二次加工
  - PDF  → 所见即所得，适合存档和打印
"""
import os
from pathlib import Path
from typing import Optional


def html_to_pdf(html_path: str | Path, output_path: str | Path,
                format: str = "A4") -> str:
    """Convert HTML file to PDF using Playwright (Chromium).

    Args:
        html_path: Path to the input HTML file
        output_path: Path to write the PDF file
        format: Page format (A4, Letter, etc.)

    Returns:
        Path to the generated PDF file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [PDF] ⚠ Playwright 未安装，跳过 PDF 生成")
        print("        pip install playwright && playwright install chromium")
        return str(output_path)

    html_abspath = os.path.abspath(str(html_path))
    if not os.path.exists(html_abspath):
        print(f"  [PDF] ✗ HTML 文件不存在: {html_abspath}")
        return str(output_path)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(f"file://{html_abspath}")

            # 等待 Chart.js 完成渲染
            page.wait_for_timeout(2000)

            page.pdf(
                path=str(output_path),
                format=format,
                print_background=True,
                margin={"top": "0.5cm", "bottom": "0.5cm",
                        "left": "0.5cm", "right": "0.5cm"},
            )
            browser.close()

        size_kb = os.path.getsize(output_path) / 1024
        print(f"  [PDF] ✓ 报告已生成 (Playwright): {output_path} ({size_kb:.0f} KB)")
        return str(output_path)

    except Exception as e:
        print(f"  [PDF] ✗ Playwright 转换失败: {e}")
        return str(output_path)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python html_to_pdf.py <input.html> [output.pdf]")
        sys.exit(1)
    html_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else sys.argv[1].replace(".html", ".pdf")
    path = html_to_pdf(html_path, output_path)
    print(f"PDF: {path}")
