"""
丝网行业研究 Agent - PDF 报告生成

使用 fpdf2 直接从 Markdown 渲染 PDF（避免 write_html 的嵌套标签限制）
"""
import os
import re
from pathlib import Path

from fpdf import FPDF


def _find_chinese_font() -> str:
    """自动检测系统中可用的中文字体路径

    优先级:
    1. Noto Sans CJK (Linux / Docker 环境)
    2. PingFang (macOS 本地开发)
    3. 遍历系统字体目录兜底
    """
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path

    # 兜底：扫描常见字体目录
    for root in ("/usr/share/fonts", "/usr/local/share/fonts"):
        if os.path.isdir(root):
            for dirpath, _dirnames, filenames in os.walk(root):
                for fn in filenames:
                    if fn.lower().startswith("noto") and (fn.endswith(".ttc") or fn.endswith(".ttf")):
                        return os.path.join(dirpath, fn)
                    if "cjk" in fn.lower() or "chinese" in fn.lower():
                        return os.path.join(dirpath, fn)

    raise FileNotFoundError(
        "未找到中文字体。请安装 fonts-noto-cjk 或类似字体包。"
    )


CHINESE_FONT_PATH = _find_chinese_font()
CHINESE_FONT_IS_COLLECTION = CHINESE_FONT_PATH.endswith(".ttc")


class ReportPDF(FPDF):
    """自定义 PDF 类，支持 Markdown 渲染"""

    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=20)
        self.add_page()
        # 确定字体集合索引（PingFang.ttc 是集合字体，collection_font_number=2 对应 SC）
        coll_idx = 2 if "PingFang" in CHINESE_FONT_PATH else 1
        if CHINESE_FONT_IS_COLLECTION:
            self.add_font("Chinese", "", CHINESE_FONT_PATH, collection_font_number=coll_idx)
            self.add_font("Chinese", "B", CHINESE_FONT_PATH, collection_font_number=coll_idx)
        else:
            self.add_font("Chinese", "", CHINESE_FONT_PATH)
            self.add_font("Chinese", "B", CHINESE_FONT_PATH)
        self.set_font("Chinese", "", 10)

    def _write_line(self, text: str, font_size: int = 10, style: str = "", indent: float = 0):
        """写入一行文本，自动换行"""
        self.set_font("Chinese", style, font_size)
        x = self.get_x() + indent
        self.set_x(x)
        w = self.w - self.r_margin - x
        self.multi_cell(w, font_size * 0.5, text, new_x="LMARGIN", new_y="NEXT")

    def _strip_markdown_links(self, text: str) -> str:
        """[text](url) → text"""
        return re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    def render_markdown(self, md_text: str):
        """渲染 Markdown 文本为 PDF"""
        # 替换 emoji 为文本
        md_text = md_text.replace("✅", "[OK]").replace("❌", "[--]").replace("⏳", "[..]").replace("⚠️", "[!]")
        lines = md_text.split("\n")
        in_table = False

        for line in lines:
            stripped = line.strip()

            # === 空行 ===
            if not stripped:
                self.ln(3)
                in_table = False
                continue

            # === 表格 ===
            if stripped.startswith("|") and stripped.endswith("|"):
                if not in_table:
                    in_table = True
                # 表头分隔行
                if re.match(r"^\|[-:| ]+\|$", stripped):
                    continue
                cells = [c.strip() for c in stripped.split("|")[1:-1]]
                # 表格内容用缩进 + 管道符展示
                text = "    │ " + " │ ".join(cells)
                self._write_line(self._strip_markdown_links(text), 8)
                continue

            in_table = False

            # === 标题 ===
            if stripped.startswith("# "):
                text = self._strip_markdown_links(stripped[2:])
                self._write_line(text, 16, "B")
                self.ln(2)
            elif stripped.startswith("## "):
                text = self._strip_markdown_links(stripped[3:])
                self._write_line(text, 13, "B")
                self.ln(1)
            elif stripped.startswith("### "):
                text = self._strip_markdown_links(stripped[4:])
                self._write_line(text, 11, "B")
                self.ln(1)
            elif stripped.startswith("#### "):
                text = self._strip_markdown_links(stripped[5:])
                self._write_line(text, 10, "B")
                self.ln(1)

            # === 无序列表 ===
            elif stripped.startswith("- "):
                text = "  • " + self._strip_markdown_links(stripped[2:])
                self._write_line(text, 10, "", 5)

            # === 有序列表 ===
            elif re.match(r"^\d+\. ", stripped):
                text = "  " + self._strip_markdown_links(stripped)
                self._write_line(text, 10, "", 5)

            # === 普通段落 ===
            elif stripped.startswith("---"):
                # 水平分割线
                self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
                self.ln(3)
            else:
                text = self._strip_markdown_links(stripped)
                self._write_line(text, 10)

        return self


def generate_pdf(report_text: str, output_path: str | Path) -> str:
    """生成 PDF 报告，返回文件路径"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pdf = ReportPDF()
    pdf.render_markdown(report_text)
    pdf.output(str(output_path))
    return str(output_path)


if __name__ == "__main__":
    test = "# 测试\n\n这是一个PDF测试。\n\n| 列1 | 列2 |\n|-----|-----|\n| A | B |\n\n- 列表项1\n- 列表项2"
    path = generate_pdf(test, "/tmp/wire_mesh_test.pdf")
    print(f"PDF 已生成: {path}")
