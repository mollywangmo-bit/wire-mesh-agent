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
from reporter import generate_pdf


def run_once():
    """执行一次完整的周报流程"""
    print("=" * 60)
    print("  丝网行业研究 Agent")
    print(f"  运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # 1. 加载配置
    print("\n>>> [1/4] 加载配置...")
    config = load_config()
    if not config.llm_api_key:
        print("  ⚠ LLM API Key 未配置，将使用降级方案生成基础报告")

    # 2. 采集数据
    print("\n>>> [2/4] 采集行业信息...")
    collector = Collector(config)
    all_results = collector.collect_all()
    raw_data = collector.format_for_analysis(all_results)

    # 保存原始数据（调试用）
    with open("/tmp/wire_mesh_raw_data.txt", "w", encoding="utf-8") as f:
        f.write(raw_data)

    # 3. 生成报告
    print("\n>>> [3/4] AI 分析生成周报...")
    analyzer = Analyzer(config)
    report = analyzer.generate_report(raw_data)

    # 3b. 追加关键词扫描（第10部分）
    print("\n>>> [3b] 生成关键词扫描...")
    keyword_scan = collector.generate_keyword_scan(all_results)
    report += "\n\n" + keyword_scan

    # 保存报告
    date_str = datetime.now().strftime("%Y-%m-%d")
    report_path = f"/tmp/wire_mesh_weekly_report_{date_str}.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"  报告已保存至: {report_path}")

    # 4. 生成 PDF
    print("\n>>> [4/4] 生成 PDF 并投递...")
    try:
        pdf_path = generate_pdf(report, f"/tmp/wire_mesh_weekly_report_{date_str}.pdf")
        print(f"  PDF 已生成: {pdf_path}")
    except Exception as e:
        print(f"  PDF 生成失败: {e}")
        pdf_path = None

    # 5. 投递报告
    delivery = Delivery(config)
    delivery.deliver_all(report, pdf_path)

    print("\n" + "=" * 60)
    print("  完成！")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="丝网行业研究 Agent")
    parser.add_argument("--test", action="store_true", help="测试模式：仅采集不投递")
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
        run_once()


if __name__ == "__main__":
    main()
