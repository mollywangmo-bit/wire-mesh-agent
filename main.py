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
from pathlib import Path

from config import load_config
from collector import Collector
from analyzer import Analyzer
from delivery import Delivery
from artifact_renderer import render_report_artifacts
from history_store import HistoryStore
from intelligence_filter import annotate_items, select_briefing_candidates
from manifest_writer import VariantRunResult, make_run_id, write_manifest
from report_variants import build_report_variants


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
    started_at = datetime.now()
    run_id = make_run_id(period, started_at)

    print("=" * 60)
    print(f"  丝网行业{prefix} Agent")
    print(f"  运行时间: {started_at.strftime('%Y-%m-%d %H:%M')}")
    print(f"  Run ID: {run_id}")
    print("=" * 60)

    # 1. 加载配置
    print(f"\n>>> [1/4] 加载配置...")
    config = load_config()
    config.period = period  # 传递周期到下游模块
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    history = HistoryStore(output_dir / "history_seen.json")
    if not config.llm_api_key:
        print("  ⚠ LLM API Key 未配置，将使用降级方案生成基础报告")

    # 2. 采集数据（一次采集）
    print(f"\n>>> [2/4] 采集行业信息（{period_label}）...")
    collector = Collector(config)
    all_results = collector.collect_all()

    # 2b. 非中文内容翻译为中文摘要（先翻译，再交给 AI 分析）
    print("\n>>> [2b] 批量翻译非中文内容...")
    try:
        collector.batch_translate_non_chinese(all_results)
    except Exception as e:
        print(f"  [翻译] ✗ 出错: {e}")

    raw_data = collector.format_for_analysis(all_results)

    # 为精简版准备高价值候选：跨周重复/静态官网降权，真实变化优先
    annotate_items(all_results, history)
    briefing_candidates = select_briefing_candidates(all_results)
    briefing_raw_data = collector.format_for_analysis(briefing_candidates)
    print(
        f"  [情报筛选] 精简版候选 {len(briefing_candidates)}/{len(all_results)} 条"
    )

    # 保存分析输入（调试用）
    date_str = datetime.now().strftime("%Y-%m-%d")
    raw_path = output_dir / f"wire_mesh_raw_data_{file_prefix}_{date_str}.txt"
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(raw_data)

    # 3. 生成报告（一次 AI 分析）
    print(f"\n>>> [3/4] AI 分析生成{prefix}...")
    analyzer = Analyzer(config)
    llm_report = analyzer.generate_report(raw_data)

    briefing_report = None
    if (brief or also_brief) and not is_monthly:
        print("\n>>> [3b] AI 生成精简决策周报...")
        briefing_report = analyzer.generate_briefing_report(briefing_raw_data)

    # 3c. 关键词扫描
    print("\n>>> [3c] 生成关键词扫描...")
    keyword_scan_full = collector.generate_keyword_scan(all_results, show_keywords=True)
    keyword_scan_brief = collector.generate_keyword_scan(all_results, show_keywords=False)

    checklist_text = collector.checklist.to_text()

    versions = build_report_variants(
        llm_report=llm_report,
        keyword_scan_full=keyword_scan_full,
        keyword_scan_brief=keyword_scan_brief,
        checklist_text=checklist_text,
        briefing_report=briefing_report,
        period=period,
        brief=brief,
        also_brief=also_brief,
    )

    # ── 分别为每个版本生成文件 + 投递 ─────────────────
    delivery = Delivery(config)
    run_results: list[VariantRunResult] = []

    for variant in versions:
        print(f"\n  --- 处理 {variant.label} ---")
        artifacts = render_report_artifacts(
            variant,
            output_dir=output_dir,
            date_str=date_str,
        )

        # 投递（Word + PDF + HTML）
        delivered = delivery.deliver_all(
            variant.text,
            artifacts.docx_path,
            artifacts.pdf_path,
            artifacts.html_path,
            prefix=variant.label,
        )
        run_results.append(
            VariantRunResult(
                variant=variant,
                artifacts=artifacts,
                delivered=delivered,
            )
        )

    manifest_path = write_manifest(
        output_dir=output_dir,
        run_id=run_id,
        period=period,
        started_at=started_at,
        finished_at=datetime.now(),
        results=run_results,
    )
    print(f"\n  Manifest 已写入: {manifest_path}")

    used_fingerprints = {
        getattr(item, "intelligence_fingerprint", "")
        for item in briefing_candidates
        if getattr(item, "intelligence_fingerprint", "")
    }
    history.record_items(all_results, used_fingerprints=used_fingerprints)
    history.save()
    print(f"  历史去重库已更新: {history.path}")

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
