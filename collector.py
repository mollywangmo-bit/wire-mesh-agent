"""
丝网行业研究 Agent - 数据采集模块

混合策略：
1. Bing News — 中英文新闻精准搜索（含深度抓取）
2. URL Monitor — 固定网站内容监控
3. RSS/微信公众号订阅
"""
import time
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from feedparser import parse as parse_feed

from config import Config


# ============================================================
# 监控清单 — 所有被监测的公司/网站/关键词
# 这份清单会作为附录出现在每周报告中
# ============================================================

MONITOR_MANIFEST = {
    "原材料企业与平台": [
        {"name": "我的钢铁网", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "上海有色网", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "青山实业", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "我要不锈钢", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "长江有色金属网", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "国际镍协会", "type": "公众号", "sources": ["Bing News（话题覆盖）", "Wechat2RSS"]},
        {"name": "钢研华普", "type": "公众号", "sources": ["Bing News（话题覆盖）", "Wechat2RSS"]},
        {"name": "青山集团 (Tsingshan Group)", "type": "企业", "sources": ["Bing News"]},
        {"name": "宝武钢铁", "type": "企业", "sources": ["Bing News"]},
        {"name": "德龙镍业", "type": "企业", "sources": ["Bing News"]},
        {"name": "东方特钢", "type": "企业", "sources": ["Bing News"]},
    ],
    "丝材料创新": [
        {"name": "纺织导报", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "碳纤维及其复合材料技术", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "复合材料前沿", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "先进微纳纤维复合材料研究荟", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "NTMT纺织新材料", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "材料科学与工程", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "易丝帮", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "Advanced Fiber Materials", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "中国玻璃纤维工业协会", "type": "公众号", "sources": ["Bing News（话题覆盖）", "Wechat2RSS"]},
        {"name": "生物医用纺织材料", "type": "公众号", "sources": ["Bing News（话题覆盖）", "Wechat2RSS"]},
    ],
    "应用领域": [
        {"name": "过滤与分离", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "氢能前沿", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "电池中国", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "航空航天制造技术", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "传感器技术", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "医疗装备", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "上海雷卯电磁兼容", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "半导体材料与工艺设备", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "神介资讯", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "医疗器械创新网", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "微创医疗", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "乐普医疗", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "心脉医疗", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "建筑工业化", "type": "公众号", "sources": ["Bing News（话题覆盖）", "Wechat2RSS"]},
    ],
    "交通设施": [
        {"name": "声屏障 护栏网 行业", "type": "行业", "sources": ["Bing News"]},
        {"name": "波形护栏板 防眩网 市场", "type": "行业", "sources": ["Bing News"]},
        {"name": "中国公路学会", "type": "公众号", "sources": ["Bing News（话题覆盖）"]},
    ],
    "建筑装饰": [
        {"name": "金刚网 钢筋网 行业", "type": "行业", "sources": ["Bing News"]},
        {"name": "钢板网 冲孔网 电焊网", "type": "行业", "sources": ["Bing News"]},
        {"name": "中国建筑装饰协会", "type": "公众号", "sources": ["Bing News（话题覆盖）"]},
    ],
    "环境保护": [
        {"name": "中国环保产业协会", "type": "公众号", "sources": ["Bing News（话题覆盖）"]},
        {"name": "过滤器 丝网过滤 行业", "type": "行业", "sources": ["Bing News"]},
        {"name": "防风固沙网 环保工程", "type": "行业", "sources": ["Bing News"]},
    ],
    "安全防护": [
        {"name": "刀片刺绳 刺绳 行业", "type": "行业", "sources": ["Bing News"]},
        {"name": "防攀爬网 边坡防护网", "type": "行业", "sources": ["Bing News"]},
        {"name": "建筑安全网 爬架网 环形网", "type": "行业", "sources": ["Bing News"]},
    ],
    "土工类": [
        {"name": "石笼网 格宾网 行业", "type": "行业", "sources": ["Bing News"]},
        {"name": "土工格栅 土工布 人造草坪", "type": "行业", "sources": ["Bing News"]},
        {"name": "中国土工合成材料工程协会", "type": "公众号", "sources": ["Bing News（话题覆盖）"]},
    ],
    "汽车配件": [
        {"name": "汽车滤清器 滤网 行业", "type": "行业", "sources": ["Bing News"]},
        {"name": "汽车消声器 水箱防护网", "type": "行业", "sources": ["Bing News"]},
        {"name": "汽车中网护网 改装", "type": "行业", "sources": ["Bing News"]},
    ],
    "农林种植": [
        {"name": "防雹网 防虫网 农业", "type": "行业", "sources": ["Bing News"]},
        {"name": "中国农技推广", "type": "公众号", "sources": ["Bing News（话题覆盖）"]},
    ],
    "居家生活": [
        {"name": "净水器过滤网 空气净化器过滤网", "type": "行业", "sources": ["Bing News"]},
        {"name": "遮阳网 隐形纱窗 行业", "type": "行业", "sources": ["Bing News"]},
        {"name": "丝网工艺品 烧烤网 仓储笼", "type": "行业", "sources": ["Bing News"]},
        {"name": "宠物用网 筐篮 行业", "type": "行业", "sources": ["Bing News"]},
    ],
    "石油化工": [
        {"name": "钢格板 复合网 行业", "type": "行业", "sources": ["Bing News"]},
        {"name": "丝网除沫器 石油防砂管", "type": "行业", "sources": ["Bing News"]},
        {"name": "防爆网墙 填料网 席型网 密纹网", "type": "行业", "sources": ["Bing News"]},
        {"name": "中国石油和化工工业联合会", "type": "公众号", "sources": ["Bing News（话题覆盖）"]},
    ],
    "造纸印刷": [
        {"name": "造纸网 行业", "type": "行业", "sources": ["Bing News"]},
        {"name": "印刷网 丝印 行业", "type": "行业", "sources": ["Bing News"]},
        {"name": "中国造纸协会", "type": "公众号", "sources": ["Bing News（话题覆盖）"]},
    ],
    "矿山开采": [
        {"name": "矿用筛 振动筛网 行业", "type": "行业", "sources": ["Bing News"]},
        {"name": "矿井支护网 矿山安全", "type": "行业", "sources": ["Bing News"]},
        {"name": "新乡振动筛分过滤产业博览会", "type": "公众号", "sources": ["Wechat2RSS"]},
    ],
    "医疗卫生": [
        {"name": "口罩丝 医疗新风过滤", "type": "行业", "sources": ["Bing News"]},
        {"name": "分样筛 蚀刻网 医疗器械", "type": "行业", "sources": ["Bing News"]},
        {"name": "血管密网支架 介入器械", "type": "行业", "sources": ["Bing News"]},
        {"name": "医疗器械创新网", "type": "公众号", "sources": ["Wechat2RSS"]},
    ],
    "航空航天": [
        {"name": "烧结网 烧结毡 过滤", "type": "行业", "sources": ["Bing News"]},
        {"name": "金属丝网 航空燃料过滤器", "type": "行业", "sources": ["Bing News"]},
        {"name": "航空航天制造技术", "type": "公众号", "sources": ["Wechat2RSS"]},
    ],
    "国防科技": [
        {"name": "路障车 智能护栏 军事", "type": "行业", "sources": ["Bing News"]},
        {"name": "军事伪装网 军事防爆网", "type": "行业", "sources": ["Bing News"]},
        {"name": "国防科技工业", "type": "公众号", "sources": ["Bing News（话题覆盖）"]},
    ],
    "农林渔业": [
        {"name": "养猪网 海水养殖网 行业", "type": "行业", "sources": ["Bing News"]},
        {"name": "苗床网 牛栏网 农业设施", "type": "行业", "sources": ["Bing News"]},
    ],
    "其他特种丝网": [
        {"name": "铜网 音网 稀有金属网", "type": "行业", "sources": ["Bing News"]},
        {"name": "服饰用网 胸花 体育用网", "type": "行业", "sources": ["Bing News"]},
    ],
    "织机与装备": [
        {"name": "纺织机械", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "中国纺织报", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "针织工业", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "纺织器材在线", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "金属加工", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "中国纺机协会", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "纺织机械60s", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "丝印电子印刷技术学习研究会", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "织造印染产业大脑", "type": "公众号", "sources": ["Bing News（话题覆盖）", "Wechat2RSS"]},
        {"name": "Schlatter Group", "type": "企业", "sources": ["URL: schlattergroup.com", "Bing News"]},
    ],
    "产业集群区域": [
        {"name": "南通发布", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "常州发布", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "浙江经信", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "苏州工信", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "吾爱盛泽", "type": "公众号", "sources": ["Bing News（话题覆盖）", "Wechat2RSS"]},
        {"name": "新乡振动行业协会", "type": "公众号", "sources": ["Bing News（话题覆盖）", "Wechat2RSS"]},
        {"name": "河北安平 — 丝网之都", "type": "集群", "sources": ["Bing News"]},
    ],
    "学术与研究": [
        {"name": "知社学术圈", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "环球科学科研圈", "type": "公众号", "sources": ["Bing News（话题覆盖）", "Wechat2RSS"]},
        {"name": "中国科学报", "type": "公众号", "sources": ["Bing News（话题覆盖）", "Wechat2RSS"]},
        {"name": "机经网", "type": "公众号", "sources": ["Bing News（话题覆盖）", "Wechat2RSS"]},
        {"name": "先进制造业", "type": "公众号", "sources": ["Wechat2RSS"]},
    ],
    "全球展会与活动": [
        {"name": "杜塞尔多夫展览", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "法兰克福全球纺织品展会", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "中外会展", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "亚洲过滤与分离工业展览会", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "CMEF中国国际医疗器械博览会", "type": "公众号", "sources": ["Wechat2RSS"]},
        {"name": "慕尼黑展览", "type": "公众号", "sources": ["Bing News（话题覆盖）", "Wechat2RSS"]},
        {"name": "中国会展", "type": "公众号", "sources": ["Bing News（话题覆盖）", "Wechat2RSS"]},
        {"name": "国际纺织机械展览会", "type": "公众号", "sources": ["Bing News（话题覆盖）", "Wechat2RSS"]},
        {"name": "广东省缝制设备商会", "type": "公众号", "sources": ["Bing News（话题覆盖）", "Wechat2RSS"]},
        {"name": "上海国际纺织工业展", "type": "公众号", "sources": ["Bing News（话题覆盖）", "Wechat2RSS"]},
        {"name": "新乡振动筛分过滤产业博览会", "type": "公众号", "sources": ["Bing News（话题覆盖）", "Wechat2RSS"]},
        {"name": "科隆国际五金博览会", "type": "公众号", "sources": ["Bing News（话题覆盖）", "Wechat2RSS"]},
        {"name": "IFAT Munich", "type": "展会", "sources": ["Bing News"]},
        {"name": "Techtextil", "type": "展会", "sources": ["Bing News"]},
        {"name": "JEC World", "type": "展会", "sources": ["Bing News"]},
        {"name": "安平国际丝网博览会", "type": "展会", "sources": ["Bing News"]},
    ],
    "日本产业链": [
        {"name": "Asada Mesh", "type": "企业", "sources": ["URL", "Bing News"]},
        {"name": "日本精線 (Nippon Seisen)", "type": "企业", "sources": ["URL", "Bing News"]},
        {"name": "津田駒 (Tsudakoma)", "type": "企业", "sources": ["URL", "Bing News"]},
        {"name": "豊田自動織機 (Toyota Industries)", "type": "企业", "sources": ["Bing News"]},
        {"name": "鋼筘・ヘルド・綜絖 繊維資材産業", "type": "行业", "sources": ["Bing News"]},
        {"name": "日本金網産業", "type": "行业", "sources": ["Bing News"]},
    ],
}

# ============================================================
# 关键词扫描 — 按分类精确匹配产品词，生成新闻列举清单
# 用于周报第10部分，区别于 LLM 行业分析
# ============================================================

KEYWORD_SCAN_GROUPS = [
    ("交通设施", ["声屏障", "护栏网", "防眩网", "波形护栏板"]),
    ("建筑装饰", ["金刚网", "钢筋网", "电焊网", "钢板网", "冲孔网"]),
    ("环境保护", ["过滤器 丝网", "防风固沙网"]),
    ("安全防护", ["刀片刺绳", "刺绳", "防攀爬网", "边坡防护网", "建筑安全网", "环形网", "爬架网"]),
    ("土工类", ["石笼网", "土工格栅", "土工布", "人造草坪"]),
    ("汽车配件", ["汽车滤清器", "汽车消声器", "水箱防护网", "中网护网"]),
    ("农林种植", ["防雹网", "防虫网"]),
    ("居家生活", ["净水器过滤网", "遮阳网", "空气净化器过滤网", "丝网工艺品", "隐形纱窗", "仓储笼", "烧烤网", "宠物用网"]),
    ("石油化工", ["钢格板", "复合网 丝网", "丝网除沫器", "石油防砂管", "防爆网墙", "填料网", "席型网", "密纹网"]),
    ("造纸印刷", ["造纸网", "印刷网 丝印"]),
    ("矿山开采", ["矿用筛", "矿井支护网", "振动筛网"]),
    ("医疗卫生", ["医药筐", "口罩 熔喷 过滤", "医疗新风过滤器", "分样筛 检验筛", "蚀刻网 精密蚀刻", "血管 支架 密网 编织"]),
    ("航空航天", ["烧结网 烧结毡 高温过滤", "烧结毡 过滤材料", "航空 燃料过滤器 液压"]),
    ("国防科技", ["路障车 防暴 路障", "智能护栏 主动防护", "军事 伪装网 隐蔽", "军事 防爆网 爆炸防护"]),
    ("农林渔业", ["养猪网 畜牧 围栏", "海水 养殖网 渔业 网箱", "苗床网 育苗 园艺", "牛栏网 牧场 围栏"]),
    ("其他", ["铜网 紫铜 黄铜", "音网 网罩 音响", "稀有金属网 贵金属网", "银网 镍网 钨网", "服饰 网布 服装 金属网眼", "体育 用网 球网 运动防护"]),
    ("日本产业链", ["浅田メッシュ 精密 金網", "日本精線 ステンレス 鋼線", "津田駒 織機 最新技術", "鋼筘 綜絖 ヘルド", "Asada Mesh Japan", "Tsudakoma loom"]),
]

# 所有被监测的 URL
URL_MONITOR_LIST = [
    {"url": "https://www.schlattergroup.com/en/wire-weaving", "name": "Schlatter Wire Weaving", "category": "设备"},
    {"url": "https://www.asada-mesh.co.jp/",               "name": "Asada Mesh",            "category": "丝材料"},
    {"url": "https://www.nipponseisen.co.jp/",             "name": "日本精線",              "category": "日本产业链"},
    {"url": "https://www.tsudakoma.co.jp/",                "name": "津田駒",                "category": "日本产业链"},
    {"url": "https://www.mysteel.com/",                    "name": "Mysteel 我的钢铁",      "category": "原材料"},
    {"url": "https://www.smm.cn/",                         "name": "SMM 上海有色网",        "category": "原材料"},
    {"url": "https://www.technicaltextile.net/",           "name": "Technical Textile",     "category": "丝材料"},
    {"url": "https://www.lme.com/metals/non-ferrous/nickel", "name": "LME Nickel",          "category": "原材料"},
    # 新分类
    {"url": "https://www.dowcpc.com/",                     "name": "中国过滤分离网",        "category": "环境保护"},
    {"url": "https://www.cqv.chinamae.com/",              "name": "振动筛分信息网",        "category": "矿山开采"},
    {"url": "https://www.chinapaper.net/",                "name": "中国造纸网",            "category": "造纸印刷"},
    {"url": "https://www.ccmsa.net.cn/",                  "name": "中国建筑装饰协会",      "category": "建筑装饰"},
]

# Bing News 查询（中英文混合）
BING_NEWS_QUERIES = [
    # 原材料 — 仅中国相关
    ("不锈钢 镍 价格 行情", "原材料"),
    ("青山 不锈钢 价格 市场", "原材料"),
    ("304 316 不锈钢 价格 现货", "原材料"),

    # 丝材料
    ("ultrafine metal woven wire cloth mesh", "丝材料"),
    ("glass fiber basalt fiber aramid woven", "丝材料"),
    ("PTFE PEEK PPS filtration mesh", "丝材料"),
    ("不锈钢丝 超细 编织", "丝材料"),

    # 应用
    ("wire mesh filtration environmental technology", "应用"),
    ("hydrogen electrolyzer mesh electrode catalyst", "应用"),
    ("metal mesh EMI shielding flexible sensor", "应用"),
    ("wire screen aerospace composite", "应用"),

    # 交通设施
    ("声屏障 公路 铁路 隔音 市场 2026", "交通设施"),
    ("护栏网 波形护栏板 高速公路 招标", "交通设施"),
    ("防眩网 公路防眩 设施 行业", "交通设施"),

    # 建筑装饰
    ("金刚网 不锈钢 窗纱 防盗", "建筑装饰"),
    ("钢筋网 建筑网片 混凝土 加固", "建筑装饰"),
    ("钢板网 冲孔网 装饰 幕墙 行业", "建筑装饰"),
    ("电焊网 建筑 铁丝网 行业", "建筑装饰"),

    # 环境保护
    ("丝网 过滤器 除尘 环保 设备", "环境保护"),
    ("防风固沙网 沙障 治沙 工程", "环境保护"),
    ("废气 废水 过滤 丝网 环保 行业", "环境保护"),

    # 安全防护
    ("刀片刺绳 刺绳 围栏 防护 市场", "安全防护"),
    ("防攀爬网 爬架网 建筑 安全 防护", "安全防护"),
    ("边坡防护网 环形网 地质灾害 防护", "安全防护"),
    ("建筑安全网 密目网 施工 安全", "安全防护"),

    # 土工类
    ("石笼网 格宾网 河道 治理 工程", "土工类"),
    ("土工格栅 加筋 路基 土工布", "土工类"),
    ("人造草坪 体育场 绿化 行业", "土工类"),

    # 汽车配件
    ("汽车 滤清器 滤芯 无纺布 滤纸 行业", "汽车配件"),
    ("汽车 消声器 排气 系统 丝网", "汽车配件"),
    ("汽车 水箱 防护网 中网 改装", "汽车配件"),

    # 农林种植
    ("防雹网 防虫网 果园 农业 覆盖", "农林种植"),
    ("农业 园艺 遮阳网 大棚 温室", "农林种植"),

    # 居家生活
    ("净水器 过滤网 前置 过滤器 行业", "居家生活"),
    ("空气净化器 HEPA 过滤网 市场", "居家生活"),
    ("遮阳网 户外 遮阳 防晒 市场", "居家生活"),
    ("隐形纱窗 金刚网 纱窗 家装", "居家生活"),
    ("丝网 工艺品 金属 编织 装饰", "居家生活"),
    ("烧烤网 户外 烧烤 工具 运动", "居家生活"),
    ("仓储笼 金属 收纳 货架 行业", "居家生活"),

    # 石油化工
    ("钢格板 复合网 平台 踏步 行业", "石油化工"),
    ("丝网 除沫器 塔器 填料 化工", "石油化工"),
    ("石油 防砂管 筛管 完井 设备", "石油化工"),
    ("防爆网 墙 填料 网 石油 化工 安全", "石油化工"),
    ("席型网 密纹网 过滤 精度 行业", "石油化工"),

    # 造纸印刷
    ("造纸网 聚酯网 造纸 设备 行业", "造纸印刷"),
    ("印刷网 丝印 网版 印刷 精密", "造纸印刷"),

    # 矿山开采
    ("矿用 筛 振动筛 筛分 设备 矿山", "矿山开采"),
    ("矿井 支护网 煤矿 安全 金属网", "矿山开采"),

    # 医疗卫生
    ("医用 口罩 熔喷布 过滤 材料", "医疗卫生"),
    ("医疗 新风 系统 过滤网 医院", "医疗卫生"),
    ("分样筛 检验 筛 实验室 设备", "医疗卫生"),
    ("蚀刻网 精密 金属 蚀刻 医疗", "医疗卫生"),
    ("血管 支架 密网 编织 介入 医疗器械", "医疗卫生"),

    # 航空航天
    ("烧结网 烧结毡 高温 过滤 材料", "航空航天"),
    ("航空 燃料 过滤器 液压 过滤", "航空航天"),
    ("金属丝网 航天 复合材料 结构", "航空航天"),

    # 国防科技
    ("路障车 防暴 路障 安全 防护", "国防科技"),
    ("智能护栏 主动 防护 安全 系统", "国防科技"),
    ("军事 伪装网 隐蔽 侦察 防护", "国防科技"),
    ("军事 防爆网 爆炸 防护 设施", "国防科技"),

    # 农林渔业
    ("养猪网 养殖 围栏 畜牧 行业", "农林渔业"),
    ("海水 养殖网 渔业 捕捞 网箱", "农林渔业"),
    ("苗床网 育苗 园艺 农业 设施", "农林渔业"),
    ("牛栏网 牧场 围栏 养殖 行业", "农林渔业"),

    # 其他特种
    ("铜网 编织 过滤 紫铜 黄铜", "其他特种"),
    ("音网 音响 喇叭 金属 网罩", "其他特种"),
    ("稀有金属网 银网 镍网 钨网", "其他特种"),
    ("服饰 网布 胸花 金属 网眼 服装", "其他特种"),
    ("体育 用网 球网 防护 运动 器材", "其他特种"),

    # 日本产业链
    ("浅田メッシュ 金網 精密 織機 製造", "日本产业链"),
    ("日本精線 ステンレス 極細線 金網", "日本产业链"),
    ("津田駒 織機 最新 技術 繊維機械", "日本产业链"),
    ("鋼筘 綜絖 ヘルド 繊維資材 製造", "日本产业链"),
    ("Asada Mesh ultra fine wire cloth Japan", "日本产业链"),
    ("Tsudakoma shuttleless loom technology", "日本产业链"),
    ("Japan precision mesh filter technology industry", "日本产业链"),
    ("Toyota Industries textile machinery 2026", "日本产业链"),

    # 设备
    ("Schlatter wire weaving machine technology", "设备"),
    ("3D weaving composite jacquard", "设备"),
    ("technical textile weaving machinery", "设备"),
    ("金属丝网 织机", "设备"),

    # 产业集群
    ("河北安平 丝网 产业", "产业集群"),
    ("常州 碳纤维 复材 产业", "产业集群"),
    ("南通 纺织机械 技术纺织品", "产业集群"),
    ("山东 玻纤 玄武岩纤维", "产业集群"),

    # 全球展会
    ("IFAT Munich filtration environment 2026", "展会"),
    ("wire cable exhibition Düsseldorf 2026", "展会"),
    ("Techtextil technical textile exhibition", "展会"),
    ("安平国际丝网博览会 2026", "展会"),
    ("JEC World composites exhibition 2026", "展会"),
    ("filtration separation exhibition China 2026", "展会"),
    ("Hannover Messe industrial trade fair 2026", "展会"),

    # 公众号补充监测
    ("镍 不锈钢 协会 市场", "原材料"),
    ("玻璃纤维 行业 市场", "丝材料"),
    ("生物医用 纺织 材料 研究", "丝材料"),
    ("建筑工业化 装配式 建筑", "应用"),
    ("盛泽 纺织 丝绸 市场", "产业集群"),
    ("新乡 振动筛 行业", "产业集群"),
    ("环球科学 科研 科学 进展", "学术"),
    ("科学报 科技 前沿", "学术"),
    ("机械工业 经济 运行", "学术"),
    ("慕尼黑 展览 电子 设备", "展会"),
    ("会展 行业 展览 动态", "展会"),
    ("纺织机械 展览会 2026", "展会"),
    ("缝制设备 纺织 工业 展会", "展会"),
    ("上海 纺织工业 展览 2026", "展会"),
    ("筛分 过滤 博览会 新乡", "展会"),
    ("五金 博览会 科隆 2026", "展会"),
]


class NewsItem:
    def __init__(self, title: str, url: str, snippet: str, source: str,
                 date: Optional[str] = None, category: str = "",
                 full_text: Optional[str] = None):
        self.title = title
        self.url = url
        self.snippet = snippet
        self.source = source
        self.date = date or datetime.now().strftime("%Y-%m-%d")
        self.category = category
        self.full_text = full_text  # 深度抓取后的全文

    def to_dict(self) -> dict:
        return {
            "title": self.title, "url": self.url,
            "snippet": self.snippet, "source": self.source,
            "date": self.date, "category": self.category,
            "full_text": self.full_text,
        }

    def __repr__(self):
        return f"[{self.source}] {self.title}"


class DeepFetcher:
    """深度抓取：获取文章全文"""

    def __init__(self):
        self._headers = {
            "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/120.0.0.0 Safari/537.36"),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

    def fetch_full_text(self, url: str, max_chars: int = 2000) -> Optional[str]:
        """抓取文章页面并提取正文"""
        try:
            with httpx.Client(follow_redirects=True, timeout=15) as client:
                resp = client.get(url, headers=self._headers)
                if resp.status_code != 200:
                    return None

                soup = BeautifulSoup(resp.text, "html.parser")

                # 移除脚本/样式
                for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                    tag.decompose()

                # 尝试提取正文（优先 article 标签）
                article = soup.find("article") or soup.find("[role=main]") or soup.find("body")
                if article:
                    text = article.get_text(separator="\n", strip=True)
                else:
                    text = soup.get_text(separator="\n", strip=True)

                # 清理空白行
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                text = "\n".join(lines)

                return text[:max_chars]

        except Exception:
            return None


class BingNewsSource:
    """Bing 新闻搜索 + 深度抓取"""

    def __init__(self, config: Config, deep_fetcher: DeepFetcher):
        self.config = config
        self.fetcher = deep_fetcher
        self._headers = {
            "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                           "AppleWebKit/537.36"),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

    def fetch(self, client: httpx.Client) -> list[NewsItem]:
        items = []

        for query, category in BING_NEWS_QUERIES:
            try:
                resp = client.get(
                    "https://www.bing.com/news/search",
                    params={"q": query, "count": 5},
                    headers=self._headers,
                    timeout=20,
                )
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")

                for card in soup.select(".news-card")[:5]:
                    # 取原标题、URL、摘要
                    title_el = card.select_one(".title")
                    if not title_el:
                        continue

                    title = title_el.get_text(strip=True)

                    # 真实 URL：优先 data-url，其次 title a
                    real_url = card.get("data-url") or card.get("url") or ""
                    if not real_url:
                        title_link = card.select_one("a.title")
                        if title_link:
                            real_url = title_link.get("href", "")

                    # 摘要
                    snippet_el = card.select_one(".snippet")
                    snippet = snippet_el.get_text(strip=True) if snippet_el else ""

                    # 来源名
                    author = card.get("data-author", "")

                    # 时间
                    date_str = ""
                    date_el = card.select_one(".ns_sc_tm")
                    if date_el:
                        date_str = date_el.get_text(strip=True)

                    # 噪音过滤
                    if self._is_noise(title, snippet):
                        continue

                    items.append(NewsItem(
                        title=title, url=real_url, snippet=snippet,
                        source=f"BingNews/{author}" if author else "BingNews",
                        date=date_str, category=category,
                    ))

                time.sleep(0.5)

            except Exception as e:
                print(f"  [BingNews] ✗ {query[:25]} — {e}")

        # === 深度抓取：对高质量来源展开全文 ===
        print(f"  [深度抓取] 对高质量条目展开全文...")
        deep_count = 0
        for item in items:
            # 只对特定源做深度抓取
            deep_sources = ["Yahoo Finance", "Nature", "EurekAlert",
                           "Reuters", "CompositesWorld", "The Engineer",
                           "news.metal.com", "finance.sina.com.cn",
                           "CompositesWorld"]
            if any(s.lower() in item.source.lower() or s.lower() in item.url.lower() for s in deep_sources):
                if item.url and not item.url.startswith("/"):
                    full = self.fetcher.fetch_full_text(item.url)
                    if full:
                        item.full_text = full
                        deep_count += 1
                    time.sleep(1)

        if deep_count:
            print(f"  [深度抓取] ✓ 成功展开 {deep_count} 篇")

        return items

    def _is_noise(self, title: str, snippet: str) -> bool:
        text = (title + " " + snippet).lower()
        noise = ["recipe", "game", "movie", "sport", "music",
                 "亚马逊", "淘宝", "京东", "拼多多", "游戏", "电影", "旅游", "美食"]
        return any(kw in text for kw in noise)


class URLMonitor:
    """固定 URL 监控"""

    def __init__(self, config: Config):
        self.config = config
        self._headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

    def fetch(self, client: httpx.Client) -> list[NewsItem]:
        items = []
        for target in URL_MONITOR_LIST:
            try:
                resp = client.get(
                    target["url"], headers=self._headers,
                    timeout=20, follow_redirects=True,
                )
                if resp.status_code != 200:
                    print(f"  [URL] ✗ {target['name']} — HTTP {resp.status_code}")
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                page_title = soup.title.get_text(strip=True) if soup.title else ""
                text = soup.get_text(separator=" ", strip=True)[:500]

                items.append(NewsItem(
                    title=f"[{target['name']}] {page_title[:100]}",
                    url=target["url"],
                    snippet=text[:300],
                    source=f"URL/{target['name']}",
                    category=target["category"],
                ))
                print(f"  [URL] ✓ {target['name']}")
                time.sleep(1)
            except Exception as e:
                print(f"  [URL] ✗ {target['name']} — {e}")

        return items


class RSSFeedsSource:
    """RSS / 微信公众号 RSS 订阅

    通过自部署的 Wechat2RSS 服务获取公众号文章：
      https://github.com/ttttmr/Wechat2RSS
    配置方式：在 .env 中设置 WECHAT2RSS_URL 和 WECHAT2RSS_TOKEN
    """

    def __init__(self, config: Config):
        self.config = config
        self._name_to_category = {}
        for section, items in MONITOR_MANIFEST.items():
            for item in items:
                self._name_to_category[item["name"]] = section

    def _get_feed_list(self, client: httpx.Client) -> list[dict]:
        """从 Wechat2RSS API 获取所有订阅的 feed 列表"""
        url = f"{self.config.wechat2rss_url}/list?k={self.config.wechat2rss_token}"
        resp = client.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [])

    def fetch(self, client: httpx.Client) -> list[NewsItem]:
        if not self.config.wechat2rss_url or not self.config.wechat2rss_token:
            print("  [RSS] Wechat2RSS 未配置，跳过")
            return []

        items = []
        base_url = self.config.wechat2rss_url.rstrip("/")
        token = self.config.wechat2rss_token

        # 获取 feed 列表
        try:
            feeds = self._get_feed_list(client)
        except Exception as e:
            print(f"  [RSS] ✗ 无法获取 Wechat2RSS feed 列表: {e}")
            return []

        print(f"  [RSS] Wechat2RSS 返回 {len(feeds)} 个订阅源")

        for feed in feeds:
            fid = feed["id"]
            feed_url = f"{base_url}/feed/{fid}.xml?k={token}"
            try:
                resp = client.get(feed_url, timeout=15)
                if resp.status_code != 200:
                    continue

                parsed = parse_feed(resp.text)
                channel_title = parsed.feed.get("title", "").strip()
                source_name = channel_title or f"公众号/{fid}"
                category = self._name_to_category.get(channel_title, "")

                for entry in parsed.entries[:10]:
                    items.append(NewsItem(
                        title=entry.get("title", ""),
                        url=entry.get("link", ""),
                        snippet=entry.get("summary", "")[:300],
                        source=source_name,
                        date=self._parse_date(entry),
                        category=category,
                    ))
                print(f"  [RSS] ✓ {source_name} — {len(parsed.entries)} 条")
            except Exception:
                # 未同步的 feed 会超时，静默跳过
                pass

        return items

    def _parse_date(self, entry) -> str:
        try:
            from datetime import timezone
            p = entry.get("published_parsed") or entry.get("updated_parsed")
            if p:
                return datetime(*p[:6], tzinfo=timezone.utc).strftime("%Y-%m-%d")
        except Exception:
            pass
        return ""


class MonitorChecklist:
    """监控清单：记录每个监测目标的执行状态"""

    def __init__(self):
        self.entries: list[dict] = []

    def record(self, category: str, target: str, status: str, results_count: int = 0, note: str = ""):
        self.entries.append({
            "category": category,
            "target": target,
            "status": status,
            "results_count": results_count,
            "note": note,
        })

    def append_manifest(self):
        """将 MONITOR_MANIFEST 转为检查记录"""
        for section, items in MONITOR_MANIFEST.items():
            for item in items:
                self.record(
                    category=section,
                    target=f"{item['name']} ({item['type']})",
                    status="待确认",
                    note=f"数据源: {', '.join(item['sources'])}",
                )

    def to_text(self) -> str:
        text = "## 附录：监测清单与执行状态\n\n"
        # 按分类分组
        groups = {}
        for e in self.entries:
            groups.setdefault(e["category"], []).append(e)

        for cat, entries in groups.items():
            text += f"### {cat}\n\n"
            text += "| 监测目标 | 状态 | 数据量 | 备注 |\n"
            text += "|---------|------|--------|------|\n"
            for e in entries:
                status_icon = {"✅": "成功", "⚠️": "部分", "❌": "失败", "待确认": "⏳ 待确认"}
                text += f"| {e['target']} | {e['status']} | {e['results_count']} | {e['note']} |\n"
            text += "\n"

        # 统计
        success = sum(1 for e in self.entries if e["status"] == "✅")
        partial = sum(1 for e in self.entries if "⚠" in str(e["status"]))
        total = len(self.entries)
        text += f"\n**监测覆盖率**: {success}/{total} 个目标有数据更新 ({partial} 个部分更新)\n"
        text += "\n*说明：⏳ 待确认 = 该目标在监测范围内但本周搜索结果中未出现。这不代表无信息，可能是搜索未命中。*\n"

        return text


class Collector:
    """协调多源采集"""

    def __init__(self, config: Config):
        self.config = config
        self.deep_fetcher = DeepFetcher()
        self.checklist = MonitorChecklist()
        self.sources = [
            ("Bing新闻", BingNewsSource(config, self.deep_fetcher)),
            ("URL监控", URLMonitor(config)),
            ("RSS订阅", RSSFeedsSource(config)),
        ]

    def collect_all(self) -> list[NewsItem]:
        print(f"\n{'='*60}")
        print(f"  丝网行业情报采集 — {datetime.now().strftime('%Y-%m-%d')}")
        print(f"{'='*60}")

        all_items = []

        with httpx.Client(follow_redirects=True) as client:
            for name, source in self.sources:
                print(f"\n  >>> 数据源: {name}")
                try:
                    items = source.fetch(client)
                    all_items.extend(items)
                    print(f"      → 获得 {len(items)} 条有效信息")
                    self.checklist.record("数据源", name, "✅", len(items))
                except Exception as e:
                    print(f"      ✗ 错误: {e}")
                    self.checklist.record("数据源", name, "❌", note=str(e))

        # 追加完整监控清单
        self.checklist.append_manifest()

        # 标记清单中各目标是否出现在本次结果中（简单匹配）
        all_text = " ".join(it.title + " " + it.snippet for it in all_items)
        for entry in self.checklist.entries:
            if entry["status"] == "待确认":
                keywords = entry["target"].split("(")[0].strip()
                # 取前2-3个中文字符作为匹配关键词
                found = any(k.lower() in all_text.lower()
                          for k in keywords.split() if len(k) > 1)
                if found:
                    entry["status"] = "✅"
                    entry["results_count"] = 1

        # 统计
        print(f"\n  {'='*40}")
        print(f"  采集完成: 共 {len(all_items)} 条")
        cats = {}
        for it in all_items:
            cats[it.category] = cats.get(it.category, 0) + 1
        for c, n in sorted(cats.items()):
            print(f"    {c}: {n} 条")
        print(f"  {'='*40}")

        return all_items

    def format_for_analysis(self, items: list[NewsItem]) -> str:
        """按分类组织，含原文链接和展开内容"""
        grouped = {}
        for item in items:
            grouped.setdefault(item.category, []).append(item)

        ORDER = ["原材料", "丝材料", "交通设施", "建筑装饰", "环境保护", "安全防护", "土工类",
                 "汽车配件", "农林种植", "居家生活", "石油化工", "造纸印刷", "矿山开采",
                 "医疗卫生", "航空航天", "国防科技", "农林渔业", "其他特种",
                 "应用", "设备", "产业集群", "日本产业链", "学术", "综合", "展会", "未分类"]
        sections = []

        for cat in ORDER:
            cat_items = grouped.pop(cat, [])
            if not cat_items:
                continue

            section = f"## {cat}\n"
            for item in cat_items:
                # 原文链接
                url_str = f"\n  原文: {item.url}" if item.url and not item.url.startswith("/") else ""

                # 展开全文
                full = ""
                if item.full_text:
                    full = f"\n  展开全文:\n{item.full_text[:1500]}\n"

                section += (
                    f"- [{item.title}]({item.url})  [{item.source}]"
                    f"{'  ' + item.date if item.date else ''}"
                    f"{url_str}\n"
                    f"  {item.snippet[:200]}{full}\n"
                )
            sections.append(section)

        # 剩余
        for cat, cat_items in grouped.items():
            section = f"## {cat}\n"
            for item in cat_items:
                url_str = f"\n  原文: {item.url}" if item.url and not item.url.startswith("/") else ""
                section += f"- [{item.title}]({item.url})  [{item.source}]{url_str}\n  {item.snippet[:200]}\n"
            sections.append(section)

        return "\n\n".join(sections) if sections else "（本周未采集到相关信息）"

    def generate_keyword_scan(self, items: list[NewsItem], max_per_keyword: int = 5) -> str:
        """生成关键词扫描新闻列举（周报第10部分）

        对每类产品关键词，扫描采集结果中的标题/摘要/来源，
        列出匹配的新闻条目及原文链接。
        与 LLM 行业分析不同，此为纯文本匹配的新闻列举。
        """
        # 建立可搜索的文本索引
        url_dedup = {}
        for item in items:
            key = item.url or item.title
            if key and key not in url_dedup:
                url_dedup[key] = item

        sections = []

        for cat_name, keywords in KEYWORD_SCAN_GROUPS:
            cat_matches = []
            seen_for_cat = set()

            for kw in keywords:
                # 拆分关键词：允许多词任一项匹配（如 "铜网 编织" 匹配含 "铜网" 或 "编织" 的条目）
                kw_parts = [p.strip().lower() for p in kw.split() if p.strip()]
                matches = []

                for item in url_dedup.values():
                    item_key = item.url or item.title
                    if item_key and item_key in seen_for_cat:
                        continue
                    search_text = (item.title + " " + item.snippet + " " + item.source).lower()
                    # 要求至少一个分词匹配
                    if any(p in search_text for p in kw_parts):
                        matches.append(item)
                        if item_key:
                            seen_for_cat.add(item_key)

                # 去重 + 截取上限
                matches = matches[:max_per_keyword]

                if matches:
                    kw_lines = []
                    for m in matches:
                        url_str = f" 原文: {m.url}" if m.url and not m.url.startswith("/") else ""
                        date_str = f" [{m.date}]" if m.date else ""
                        kw_lines.append(
                            f"  - [{m.title}]({m.url}){date_str} — {m.snippet[:120]}"
                        )
                    cat_matches.append(f"  **{kw}**：\n" + "\n".join(kw_lines))
                else:
                    cat_matches.append(f"  **{kw}**：本周暂无相关新闻")

            section = f"### {cat_name}\n" + "\n\n".join(cat_matches) + "\n"
            sections.append(section)

        header = (
            "## 11. 关键词扫描 — 新闻列举\n\n"
            "> 以下为按产品关键词从本周采集信息中匹配的新闻条目，"
            "属于机器匹配的新闻列举，区别于以上 LLM 行业分析。\n\n"
        )

        return header + "\n".join(sections)


if __name__ == "__main__":
    from config import load_config
    cfg = load_config()
    c = Collector(cfg)
    items = c.collect_all()
    print("\n\n" + c.format_for_analysis(items))
