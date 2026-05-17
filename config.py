"""
丝网行业研究 Agent - 配置模块
"""
import os
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


@dataclass
class Config:
    # LLM
    llm_api_key: str
    llm_base_url: str
    llm_model: str

    # Email
    smtp_server: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    email_from: Optional[str] = None
    email_to: Optional[str] = None

    # Feishu
    feishu_webhook_url: Optional[str] = None

    # WeCom
    wecom_webhook_url: Optional[str] = None

    # Search
    serpapi_api_key: Optional[str] = None

    # Wechat2RSS（公众号 RSS）
    wechat2rss_url: Optional[str] = None
    wechat2rss_token: Optional[str] = None

    # Monitoring targets — 搜索关键词
    search_topics: list[str] = field(default_factory=lambda: [
        # ===== 原材料 =====
        "青山集团 不锈钢 价格",
        "304 316 430 不锈钢价格",
        "LME 镍 价格",
        "铬铁 钼铁 价格 不锈钢",
        "螺纹钢 铜价 价格",

        # ===== 交通设施 =====
        "声屏障 丝网",
        "护栏网 波形护栏板",
        "防眩网",

        # ===== 建筑装饰 =====
        "金刚网 不锈钢丝网",
        "钢筋网 建筑钢筋网片",
        "电焊网",
        "钢板网 冲孔网",

        # ===== 环境保护 =====
        "过滤器 丝网过滤",
        "防风固沙网 抑尘网",

        # ===== 安全防护 =====
        "刀片刺绳 刺绳",
        "防攀爬网 建筑安全网",
        "边坡防护网 环形网",
        "爬架网 建筑防护网",

        # ===== 土工类 =====
        "石笼网 格宾网",
        "土工格栅 土工布 人造草坪",

        # ===== 汽车配件 =====
        "汽车滤清器 滤网",
        "汽车消声器 丝网",
        "汽车水箱防护网 中网护网",

        # ===== 农林种植 =====
        "防雹网 防虫网 农业覆盖网",

        # ===== 居家生活 =====
        "净水器过滤网 空气净化器过滤网",
        "遮阳网 隐形纱窗",
        "丝网工艺品 烧烤网 仓储笼 宠物用网",

        # ===== 石油化工 =====
        "钢格板 复合网",
        "丝网除沫器",
        "石油防砂管",
        "防爆网墙 填料网",
        "席型网 密纹网",

        # ===== 造纸印刷 =====
        "造纸网 印刷网",

        # ===== 矿山开采 =====
        "矿用筛 振动筛网",
        "矿井支护网",

        # ===== 医疗卫生 =====
        "口罩丝 医疗新风过滤器滤网",
        "分样筛 蚀刻网",
        "血管密网支架 介入器械",

        # ===== 航空航天 =====
        "烧结网 烧结毡",
        "金属丝网 燃料过滤器",

        # ===== 国防科技 =====
        "路障车 智能护栏",
        "军事伪装网 军事防爆网",

        # ===== 农林渔业 =====
        "养猪网 海水养殖网 苗床网 牛栏网",

        # ===== 其他特种 =====
        "铜网 音网",
        "稀有金属网 银网 镍网 钨网",
        "服饰用网 胸花 金属网布",
        "体育用网",

        # ===== 丝材料创新 =====
        "超细金属丝 编织 过滤",
        "玻璃纤维 玄武岩纤维 碳纤维 丝网",
        "PTFE PEEK PPS 丝网",
        "Asada Mesh 超细编织",

        # ===== 织机设备 =====
        "Schlatter 金属织机",
        "Asagoe 提花织机",
        "金属丝网织机 国产替代",
        "3D编织 复合材料 技术纺织品",

        # ===== 产业集群 =====
        "河北安平 丝网 产业升级",
        "南通 纺织机械 技术纺织",
        "常州 碳纤维 复材",
    ])

    # 要重点关注的公司/机构
    key_entities: list[str] = field(default_factory=lambda: [
        "青山集团", "山东钢铁", "宝武钢铁",
        "Asada Mesh", "Schlatter", "Asagoe",
        "东方特钢", "德龙镍业",
    ])


def load_config() -> Config:
    """从环境变量加载配置"""
    from dotenv import load_dotenv

    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    return Config(
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
        llm_model=os.getenv("LLM_MODEL", "deepseek-chat"),

        smtp_server=os.getenv("SMTP_SERVER"),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_user=os.getenv("SMTP_USER"),
        smtp_password=os.getenv("SMTP_PASSWORD"),
        email_from=os.getenv("EMAIL_FROM"),
        email_to=os.getenv("EMAIL_TO"),

        feishu_webhook_url=os.getenv("FEISHU_WEBHOOK_URL"),
        wecom_webhook_url=os.getenv("WECOM_WEBHOOK_URL"),

        serpapi_api_key=os.getenv("SERPAPI_API_KEY"),

        wechat2rss_url=os.getenv("WECHAT2RSS_URL"),
        wechat2rss_token=os.getenv("WECHAT2RSS_TOKEN"),
    )
