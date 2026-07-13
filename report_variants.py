"""
报告版本构建。

把“周报 / 精简周报 / 月报”的业务语义从 main.py 中抽离出来，
避免标签、文件前缀、内容拼接散落在流程代码里。
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ReportVariant:
    """一次运行中需要生成和投递的单个报告版本。"""

    text: str
    label: str
    file_prefix: str


def build_report_variants(
    *,
    llm_report: str,
    keyword_scan_full: str,
    keyword_scan_brief: str,
    checklist_text: str,
    briefing_report: str | None = None,
    period: str = "weekly",
    brief: bool = False,
    also_brief: bool = False,
) -> list[ReportVariant]:
    """根据运行模式构建报告版本列表。

    Args:
        llm_report: AI 生成的主体报告。
        briefing_report: 独立生成的决策型精简周报。
        keyword_scan_full: 完整关键词扫描。
        keyword_scan_brief: 兼容旧流程的精简关键词扫描；新精简版默认不再使用。
        checklist_text: 监测清单。
        period: "weekly" 或 "monthly"。
        brief: 仅生成精简周报。仅周报有效。
        also_brief: 额外生成精简周报。仅周报有效。

    Returns:
        要生成的报告版本列表。
    """
    is_monthly = period == "monthly"

    if is_monthly:
        return [
            ReportVariant(
                text=llm_report + "\n\n" + keyword_scan_full + "\n\n" + checklist_text,
                label="月报",
                file_prefix="monthly",
            )
        ]

    if brief:
        return [
            ReportVariant(
                text=briefing_report or llm_report,
                label="精简周报",
                file_prefix="weekly_brief",
            )
        ]

    variants = [
        ReportVariant(
            text=llm_report + "\n\n" + keyword_scan_full + "\n\n" + checklist_text,
            label="周报",
            file_prefix="weekly",
        )
    ]

    if also_brief:
        variants.append(
            ReportVariant(
                text=briefing_report or llm_report,
                label="精简周报",
                file_prefix="weekly_brief",
            )
        )

    return variants
