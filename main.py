"""
丝网行业研究 Agent — 主入口

运行流程：
1. 加载配置
2. 采集行业信息
3. LLM 分析生成周报
4. 多渠道投递
"""
import sys
import argparse
from datetime import datetime

from config import load_config
from collector import Collector
from analyzer import Analyzer
from delivery import Delivery
from html_reporter import generate_html_report
from html_to_pdf import html_to_pdf


def run_once(brief: bool = False, period: str = "weekly"):
    """执行一次完整的周报/月报流程

    Args:
        brief: 精简模式（去附录 + 关键词仅列新闻）
        period: "weekly" | "monthly"
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

    # 2. 采集数据
    print(f"\n>>> [2/4] 采集行业信息（{period_label}）...")
    collector = Collector(config)
    all_results = collector.collect_all()
    raw_data = collector.format_for_analysis(all_results)

    # 保存原始数据（调试用）
    date_str = datetime.now().strftime("%Y-%m-%d")
    with open(f"/tmp/wire_mesh_raw_data_{file_prefix}_{date_str}.txt", "w", encoding="utf-8") as f:
        f.write(raw_data)

    # 3. 生成报告
    print(f"\n>>> [3/4] AI 分析生成{prefix}...")
    analyzer = Analyzer(config)
    report = analyzer.generate_report(raw_data)

    # 3b. 非中文内容翻译为中文摘要
    print("\n>>> [3b] 批量翻译非中文内容...")
    try:
        collector.batch_translate_non_chinese(all_results)
    except Exception as e:
        print(f"  [翻译] ✗ 出错: {e}")

    # 3c. 追加关键词扫描
    print("\n>>> [3c] 生成关键词扫描...")
    show_keywords = not brief
    keyword_scan = collector.generate_keyword_scan(all_results, show_keywords=show_keywords)
    report += "\n\n" + keyword_scan

    # 3d. 追加监测清单（精简模式下去掉）
    if not brief:
        print("\n>>> [3d] 追加监测清单...")
        report += "\n\n" + collector.checklist.to_text()
    else:
        print("\n>>> [3d] 精简模式，跳过监测清单")

    # 保存报告
    report_path = f"/tmp/wire_mesh_{file_prefix}_report_{date_str}.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"  报告已保存至: {report_path}")

    # 4. 生成 HTML 版本
    print(f"\n>>> [4/4] 生成 HTML 报告（带可视化）...")
    try:
        html_path = generate_html_report(report, f"/tmp/wire_mesh_{file_prefix}_report_{date_str}.html")
        print(f"  HTML 已生成: {html_path}")
    except Exception as e:
        print(f"  HTML 生成失败: {e}")
        html_path = None

    # 5. 生成 PDF（从 HTML 转制）
    print(f"\n>>> [5/5] 生成 PDF...")
    try:
        if html_path:
            pdf_path = html_to_pdf(html_path, f"/tmp/wire_mesh_{file_prefix}_report_{date_str}.pdf",
                                   fallback_md_report=report)
        else:
            from reporter import generate_pdf
            pdf_path = generate_pdf(report, f"/tmp/wire_mesh_{file_prefix}_report_{date_str}.pdf")
        print(f"  PDF 已生成: {pdf_path}")
    except Exception as e:
        print(f"  PDF 生成失败: {e}")
        pdf_path = None

    # 6. 投递报告
    delivery = Delivery(config)
    delivery.deliver_all(report, pdf_path, html_path, prefix=prefix)

    print("\n" + "=" * 60)
    print(f"  {prefix}生成完成！")
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
