"""
丝网行业研究 Agent — 主入口

运行流程：
1. 加载配置
2. 采集行业信息
3. LLM 分析生成周报
4. 多渠道投递
"""
import os
import sys
import argparse
from datetime import datetime

from config import load_config
from collector import Collector
from analyzer import Analyzer
from delivery import Delivery
from html_reporter import generate_html_report
from docx_reporter import generate_docx
from html_to_pdf import html_to_pdf


def run_once(brief: bool = False, period: str = "weekly", also_brief: bool = False):
    """执行一次完整的周报/月报流程

    Args:
        brief: 精简模式（去附录 + 关键词仅列新闻）
        period: "weekly" | "monthly"
        also_brief: 是否额外生成一份精简版周报（仅 period="weekly" 时生效）
    """
    is_monthly = period == "monthly"
    prefix = "月报" if is_monthly else "周报"
    file_prefix = "monthly" if is_monthly else "weekly"
    period_label = "本月" if is_monthly else "本周"

    print("=" * 60)
    print(f"  丝网行业{prefix} Agent")
    print(f"  运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # 1. 加载配置
    print(f"\n>>> [1/4] 加载配置...")
    config = load_config()
    config.period = period  # 传递周期到下游模块
    if not config.llm_api_key:
        print("  ⚠ LLM API Key 未配置，将使用降级方案生成基础报告")

    # 2. 采集数据（一次采集）
    print(f"\n>>> [2/4] 采集行业信息（{period_label}）...")
    collector = Collector(config)
    all_results = collector.collect_all()
    raw_data = collector.format_for_analysis(all_results)

    # 保存原始数据（调试用）
    date_str = datetime.now().strftime("%Y-%m-%d")
    with open(f"/tmp/wire_mesh_raw_data_{file_prefix}_{date_str}.txt", "w", encoding="utf-8") as f:
        f.write(raw_data)

    # 3. 生成报告（一次 AI 分析）
    print(f"\n>>> [3/4] AI 分析生成{prefix}...")
    analyzer = Analyzer(config)
    llm_report = analyzer.generate_report(raw_data)

    # 3b. 非中文内容翻译为中文摘要（一次翻译）
    print("\n>>> [3b] 批量翻译非中文内容...")
    try:
        collector.batch_translate_non_chinese(all_results)
    except Exception as e:
        print(f"  [翻译] ✗ 出错: {e}")

    # 3c. 关键词扫描
    print("\n>>> [3c] 生成关键词扫描...")
    keyword_scan_full = collector.generate_keyword_scan(all_results, show_keywords=True)
    keyword_scan_brief = collector.generate_keyword_scan(all_results, show_keywords=False)

    checklist_text = collector.checklist.to_text()

    # ── 构建两个版本 ──────────────────────────────────
    versions = []

    # 完整版
    report_full = llm_report + "\n\n" + keyword_scan_full + "\n\n" + checklist_text
    versions.append((report_full, "周报", "weekly"))

    # 精简版（also_brief 时额外生成）
    if also_brief and not is_monthly:
        report_brief = llm_report + "\n\n" + keyword_scan_brief
        versions.append((report_brief, "精简周报", "weekly_brief"))

    # ── 分别为每个版本生成文件 + 投递 ─────────────────
    delivery = Delivery(config)

    for report_text, label, fname_prefix in versions:
        print(f"\n  --- 处理 {label} ---")

        # 保存 MD
        md_path = f"/tmp/wire_mesh_{fname_prefix}_report_{date_str}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        print(f"  MD 已保存: {md_path}")

        # 生成 HTML
        html_path = None
        try:
            html_path = f"/tmp/wire_mesh_{fname_prefix}_report_{date_str}.html"
            generate_html_report(report_text, html_path)
            print(f"  HTML 已生成: {html_path}")
        except Exception as e:
            print(f"  HTML 生成失败: {e}")

        # 生成 Word 文档（python-docx 原生渲染，零系统依赖）
        docx_path = None
        try:
            docx_path = f"/tmp/wire_mesh_{fname_prefix}_report_{date_str}.docx"
            generate_docx(report_text, docx_path)
            size_kb = os.path.getsize(docx_path) / 1024
            print(f"  Word 已生成: {docx_path} ({size_kb:.0f} KB)")
        except Exception as e:
            print(f"  Word 生成失败: {e}")

        # 生成 PDF（Playwright：HTML → Chromium 打印）
        pdf_path = None
        if html_path:
            try:
                pdf_path = f"/tmp/wire_mesh_{fname_prefix}_report_{date_str}.pdf"
                html_to_pdf(html_path, pdf_path)
            except Exception as e:
                print(f"  PDF 生成失败: {e}")

        # 投递（Word + PDF + HTML）
        delivery.deliver_all(report_text, docx_path, pdf_path, html_path, prefix=label)

    print("\n" + "=" * 60)
    print(f"  全部完成（{len(versions)} 个版本）！")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="丝网行业研究 Agent")
    parser.add_argument("--test", action="store_true", help="测试模式：仅采集不投递")
    parser.add_argument("--brief", action="store_true",
                        help="精简模式：去附录 + 关键词扫描仅列新闻")
    args = parser.parse_args()

    if args.test:
        print(">>> 测试模式：仅采集不投递\n")
        config = load_config()
        collector = Collector(config)
        all_results = collector.collect_all()
        raw_data = collector.format_for_analysis(all_results)
        print("\n\n=== 采集结果 ===\n")
        print(raw_data)
    else:
        run_once(brief=args.brief)


if __name__ == "__main__":
    main()
