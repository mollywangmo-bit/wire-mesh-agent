"""
情报评分与精简版候选筛选。

完整版周报仍保留资料库属性；精简版周报只使用高价值增量信息。
"""
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from history_store import HistoryStore, fingerprint_item


SUBSTANTIVE_KEYWORDS = [
    # 中文
    "发布", "推出", "量产", "投产", "扩产", "涨价", "降价", "价格", "订单",
    "中标", "招标", "专利", "财报", "营收", "利润", "并购", "收购",
    "投资", "产能", "新材料", "新产品", "新技术", "展会", "参展",
    "认证", "合作", "签约", "试产", "突破", "研发",
    # English
    "launch", "launched", "release", "released", "patent", "acquisition",
    "acquire", "investment", "capacity", "expansion", "order", "contract",
    "earnings", "revenue", "profit", "exhibition", "expo", "new product",
    "technology", "partnership",
    # Japanese
    "発売", "発表", "量産", "投資", "増産", "特許", "決算", "展示会",
]

LOW_VALUE_KEYWORDS = [
    "官网", "首页", "about us", "company profile", "products", "product catalog",
    "contact", "privacy policy", "cookie", "会社概要", "製品情報", "お問い合わせ",
]

HIGH_VALUE_SOURCES = [
    "businesswire", "prnewswire", "globenewswire", "reuters", "nikkei",
    "technicaltextile", "innovationintextiles", "compositesworld",
    "news.metal.com", "mysteel", "smm", "serper", "bingweb",
]

DIRECT_INDUSTRY_TERMS = [
    "丝网", "金属网", "金属丝", "不锈钢丝", "过滤网", "筛网", "编织网",
    "wire mesh", "wire cloth", "woven wire", "metal mesh", "filter mesh",
    "stainless steel wire", "金網", "メッシュ", "ステンレス線",
]


@dataclass
class IntelligenceScore:
    score: int
    grade: str
    reasons: list[str]
    fingerprint: str
    duplicate: bool = False


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def _contains_any(text: str, keywords: list[str]) -> bool:
    lower = text.lower()
    return any(k.lower() in lower for k in keywords)


def score_item(item, history: HistoryStore | None = None) -> IntelligenceScore:
    """给单条 NewsItem-like 对象打分。"""
    title = getattr(item, "title", "") or ""
    snippet = getattr(item, "snippet", "") or ""
    source = getattr(item, "source", "") or ""
    url = getattr(item, "url", "") or ""
    full_text = getattr(item, "full_text", "") or ""
    text = f"{title} {snippet} {source} {full_text[:800]}"

    score = 0
    reasons: list[str] = []

    if _contains_any(text, DIRECT_INDUSTRY_TERMS):
        score += 25
        reasons.append("industry_term")

    if _contains_any(text, SUBSTANTIVE_KEYWORDS):
        score += 30
        reasons.append("substantive_signal")

    if re.search(r"\d+(\.\d+)?\s*(%|吨|万吨|亿元|万美元|mm|μm|微米|gw|mw)", text.lower()):
        score += 20
        reasons.append("has_numbers")

    domain = _domain(url)
    if any(src in (source + " " + domain).lower() for src in HIGH_VALUE_SOURCES):
        score += 15
        reasons.append("source_quality")

    if full_text:
        score += 10
        reasons.append("has_full_text")

    is_site_monitor = source.startswith("URL/")
    if is_site_monitor:
        score -= 20
        reasons.append("site_monitor")
        if not _contains_any(text, SUBSTANTIVE_KEYWORDS):
            score -= 30
            reasons.append("static_site_no_event")

    if _contains_any(text, LOW_VALUE_KEYWORDS) and not _contains_any(text, SUBSTANTIVE_KEYWORDS):
        score -= 20
        reasons.append("low_value_page")

    duplicate = history.has_seen(item) if history else False
    if duplicate:
        score -= 35
        reasons.append("seen_before")

    score = max(0, min(100, score))
    if score >= 70:
        grade = "A"
    elif score >= 45:
        grade = "B"
    elif score >= 25:
        grade = "C"
    else:
        grade = "D"

    return IntelligenceScore(
        score=score,
        grade=grade,
        reasons=reasons,
        fingerprint=fingerprint_item(item),
        duplicate=duplicate,
    )


def annotate_items(items: list, history: HistoryStore | None = None) -> list:
    """给 items 附加 intelligence_score/intelligence_grade 等动态属性。"""
    for item in items:
        result = score_item(item, history)
        item.intelligence_score = result.score
        item.intelligence_grade = result.grade
        item.intelligence_reasons = result.reasons
        item.intelligence_fingerprint = result.fingerprint
        item.is_duplicate_seen = result.duplicate
    return items


def select_briefing_candidates(items: list, *, max_items: int = 80) -> list:
    """选择精简版候选：A/B 级优先，按分数降序。"""
    candidates = [
        item for item in items
        if getattr(item, "intelligence_grade", "D") in {"A", "B"}
    ]
    candidates.sort(
        key=lambda it: (
            getattr(it, "intelligence_score", 0),
            getattr(it, "date", "") or "",
        ),
        reverse=True,
    )
    return candidates[:max_items]
