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
    serper_api_key: Optional[str] = None  # Serper.dev Google News API

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

        # ===== 日本产业链 =====
        "浅田メッシュ 金網 精密 織機",
        "日本精線 ステンレス 極細線",
        "津田駒 織機 繊維機械 最新技術",
        "鋼筘 綜絖 産業用繊維資材",
        "日本 金網 業界 動向",
        "Asada Mesh precision wire cloth Japan",
        "Tsudakoma shuttleless loom technology",
        "Japan precision mesh filter technology",

        # ===== 日本精密金属网公司 =====
        "NBC Meshtec 精密 金属 メッシュ",
        "奥谷金網 パンチングメタル フィルター",
        "関西金網 Nippon Filcon 産業用メッシュ",
        "大日金属 金網 精密 織物",
        "阪倉金網 極細線 メッシュ",
        "八尾金網 フィルター メッシュ",
        "松本金網 Matsubara 金網 特殊織",
        "ニチダイ 焼結 金属 フィルター sintered mesh",
        "島精機 編機 ホールガーメント 複合材料",
        "村田機械 3D織り 繊維機械",
        "大洋金網 石油化学 フィルター",
        "三和工業 金網 大阪",

        # ===== 美国丝网公司 =====
        "Gerard Daniel wire mesh filtration North America",
        "W.S. Tyler wire cloth industrial sieve",
        "Newark Wire Cloth filter strainer",
        "Cleveland Wire Cloth industrial mesh",
        "Belleville Wire Cloth aerospace wire mesh",
        "Cambridge International metal conveyor belt wire mesh",
        "Sefar precision woven filtration",

        # ===== 欧洲丝网公司 =====
        "GKD Kufferath technical woven wire mesh Germany",
        "G. Bopp precision wire cloth Switzerland",
        "Haver Boecker wire weaving screening Germany",
        "Dorstener Drahtwerke sintered wire mesh Germany",
        "Russell Finex sieving filtration UK",
        "Locker Group wire mesh UK",
        "Spörl KG stainless steel wire mesh Germany",

        # ===== 产业集群 =====
        "河北安平 丝网 产业升级",
        "南通 纺织机械 技术纺织",
        "常州 碳纤维 复材",
    ])

    # 要重点关注的公司/机构
    key_entities: list[str] = field(default_factory=lambda: [
        # === 中国 ===
        "青山集团", "山东钢铁", "宝武钢铁",
        "东方特钢", "德龙镍业",
        "微创医疗", "MicroPort",

        # === 日本 ===
        "Asada Mesh", "Schlatter", "Asagoe",
        "日本精線", "津田駒", "豊田自動織機",
        "NBC Meshtec", "奥谷金網製作所", "Okutani",
        "Nippon Filcon", "関西金網",
        "Dainichi Kinzoku", "大日金属",
        "YOSHIDA KINZOKU KOGYO", "吉田金属工業",
        "阪倉金網", "Sakakura Wire Mesh",
        "八尾金網製作所", "Yao Wire Mesh",
        "松本金網", "Matsubara Kanaami",
        "ニチダイフィルタ", "Nichidai Filter",
        "島精機製作所", "Shima Seiki",
        "村田機械", "Murata Machinery",
        "大洋金網", "Taiyo Wire Cloth",
        "三和工業", "Mitsuwa Industries",

        # === 美国 ===
        "Gerard Daniel Worldwide",
        "W.S. Tyler",
        "Newark Wire Cloth",
        "Cleveland Wire Cloth",
        "Belleville Wire Cloth",
        "Cambridge International",
        "Sefar",

        # === 欧洲 ===
        "GKD Gebr. Kufferath",
        "G. Bopp",
        "Haver & Boecker",
        "Dorstener Drahtwerke",
        "Russell Finex",
        "Locker Group",
        "Spörl KG",
    ])

    # 报告周期（由 main.py 动态设置）
    period: str = "weekly"  # "weekly" | "monthly"

    # Runtime
    output_dir: str = "/tmp"
    run_token: Optional[str] = None


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
        serper_api_key=os.getenv("SERPER_API_KEY"),

        wechat2rss_url=os.getenv("WECHAT2RSS_URL"),
        wechat2rss_token=os.getenv("WECHAT2RSS_TOKEN"),

        output_dir=os.getenv("OUTPUT_DIR", "/tmp"),
        run_token=os.getenv("RUN_TOKEN"),
    )
