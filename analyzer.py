"""
丝网行业研究 Agent - 分析与报告生成模块
"""
from datetime import datetime

import httpx

from config import Config


REPORT_SYSTEM_PROMPT = """你是一个专业的丝网（Wire Mesh / 金属丝网及工业用网）行业分析师。你需要根据收集到的行业信息，生成一份结构化的中文周报。

## 写作原则
- **每条信息尽量附上原文链接**（格式：[标题](原文URL)）
- **对有展开全文的内容，充分利用详细信息撰写有深度的分析**
- **信息不足的部分如实写"本周暂无更新"**，不要编造
- **有具体数据（价格变化、产能数据等）务必引用**
- **中文输出，专业但简明**

## 格式要求

请严格按以下结构输出：

# 丝网行业周报｜{date}

## 1. 本周一句话判断
用一句话概括本周行业核心趋势。

## 2. 丝材料创新
- 更细金属丝、高强度、耐腐蚀
- 新型非金属丝（玻纤、玄武岩、碳纤维、芳纶、PTFE/PEEK/PPS）
- 可编织新材料、复合丝材

## 3. 网的高端应用
- 环保：过滤、废气、废水、催化剂载体
- 航空航天：高温过滤、屏蔽、复合材料增强
- 新能源：电池、氢能、电解槽、燃料电池
- 医疗 / 电子 / 机器人：植入物、柔性传感、电磁屏蔽
- 建筑：幕墙、防护、隔音

## 4. 织机与工艺装备
- 金属织机：Schlatter、Asada/Asagoe、国产替代进展
- 纺织织机：Jacquard、电子提花、3D编织、技术纺织品

## 5. 区域与产业集群动态
- 河北安平：丝网产业升级、共享制造
- 江苏南通：纺织机械、技术纺织
- 江苏常州：碳纤维、复材
- 浙江、广东：过滤、环保、电子应用
- 山东、河南：玻纤、玄武岩纤维、复材

## 6. 原材料价格与供应链变化
- 青山 / 不锈钢（价格、产能、新闻）
- 镍 / 铜 / 螺纹钢（期货、现货、供需）
- 对丝网成本的影响分析

## 7. 值得关注的新闻/公司
- 列出本周最重要的 3-5 条具体新闻，附原文链接

## 8. 日本产业链
- Asada Mesh 精密网与超细金属编织最新动态
- 日本精線 不锈钢线材与精密过滤技术
- 津田駒 织机技术进展与设备更新
- 鋼筘・綜絖・ヘルド 纺织器材供应链
- 日本金網産業 整体动向
- 关联性分析（对国内丝网产业的启示）

## 9. 全球展会与行业活动
- 列出近期或正在举办的行业相关展会（过滤、丝网、复合材料、纺织机械、环保等）
- 展会时间、地点、看点
- 值得关注的参展商和新技术发布

## 10. 下周关注点
- 价格走势、技术突破、政策变化、展会等
"""


class Analyzer:
    def __init__(self, config: Config):
        self.config = config
        self.client = httpx.Client(timeout=120.0)

    def generate_report(self, raw_data: str) -> str:
        if not self.config.llm_api_key:
            return self._fallback_report(raw_data)

        date_str = datetime.now().strftime("%Y-%m-%d")
        system_prompt = REPORT_SYSTEM_PROMPT.format(date=date_str)

        user_prompt = f"""以下是本周采集到的丝网行业相关信息（含原文链接和部分展开全文）。

采集时间：{date_str}

{raw_data}

---

请生成完整的丝网行业周报。注意：
1. 对包含 "展开全文" 的条目，利用详细信息充分展开分析
2. 每条信息标注原文链接
3. 保留最后的"附录：监测清单与执行状态"部分"""

        try:
            resp = self.client.post(
                f"{self.config.llm_base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.config.llm_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.config.llm_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 8192,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return content

        except Exception as e:
            print(f"\n  [LLM API 调用失败] {e}")
            print("  使用降级方案生成基础报告...")
            return self._fallback_report(raw_data, date_str)

    def _fallback_report(self, raw_data: str, date_str: str = "") -> str:
        date_str = date_str or datetime.now().strftime("%Y-%m-%d")
        # 降级时仍然保留原始数据中的附录
        appendix = ""
        if "附录：监测清单" in raw_data:
            appendix = raw_data[raw_data.index("## 附录"):]
            raw_data = raw_data[:raw_data.index("## 附录")]

        return f"""# 丝网行业周报｜{date_str}

## 1. 本周一句话判断
（LLM 分析不可用，以下为原始采集信息的汇总）

## 2. 丝材料创新
*原始数据待 AI 分析*

## 3. 网的高端应用
*原始数据待 AI 分析*

## 4. 织机与工艺装备
*原始数据待 AI 分析*

## 5. 区域与产业集群动态
*原始数据待 AI 分析*

## 6. 原材料价格与供应链变化
*原始数据待 AI 分析*

## 7. 值得关注的新闻/公司
*原始数据待 AI 分析*

## 8. 日本产业链
*原始数据待 AI 分析*

## 9. 全球展会与行业活动
*原始数据待 AI 分析*

## 10. 下周关注点
*原始数据待 AI 分析*

---

## 附：本周原始采集信息

{raw_data}

---

{appendix}
"""


if __name__ == "__main__":
    from config import load_config
    cfg = load_config()
    a = Analyzer(cfg)
    report = a.generate_report("测试数据：青山不锈钢期货价格上涨。")
    print(report)
