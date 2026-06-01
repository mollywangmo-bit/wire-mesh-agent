"""
丝网行业研究 Agent - HTML 报告生成器

将 markdown 周报渲染为带可视化的独立 HTML 页面。
设计灵感来自 Vercel Geist Design System。

输出：单文件静态 HTML（Chart.js CDN，无需其他依赖）
"""
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

RELEVANCE_TAGS = {
    "🔗": "direct",
    "⚡": "indirect",
    "📡": "signal",
}
TAG_LABELS = {"direct": "直接相关", "indirect": "间接影响", "signal": "趋势信号"}
TAG_COLORS = {
    "direct": "#0070F3",
    "indirect": "#46A758",
    "signal": "#FFB224",
}


# ── Geist-inspired Design Tokens ──────────────────────────────────────────

CSS_VARIABLES = """
:root {
  /* Background */
  --bg-100: #ffffff;
  --bg-200: #fafafa;
  --bg-300: #f0f0f0;

  /* Text */
  --text-100: #0a0a0a;
  --text-200: #555555;
  --text-300: #888888;

  /* Borders */
  --border: #e5e5e5;
  --border-hover: #d4d4d4;

  /* Accent */
  --accent: #0070F3;
  --accent-hover: #0060DF;
  --accent-light: #EBF5FF;

  /* Semantic */
  --success: #46A758;
  --warning: #FFB224;
  --error: #E5484D;

  /* Typography */
  --font-sans: 'Geist', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --font-mono: 'Geist Mono', 'SF Mono', SFMono-Regular, ui-monospace, monospace;

  /* Spacing */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 24px;
  --space-6: 32px;
  --space-7: 40px;
  --space-8: 48px;

  /* Radius */
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
  --radius-xl: 12px;

  /* Shadows */
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.04);
  --shadow-md: 0 4px 12px rgba(0,0,0,0.06);
  --shadow-lg: 0 8px 24px rgba(0,0,0,0.08);

  /* Sidebar */
  --sidebar-width: 260px;

  /* Transitions */
  --transition: 150ms ease;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg-100: #0a0a0a;
    --bg-200: #171717;
    --bg-300: #1f1f1f;

    --text-100: #ededed;
    --text-200: #a0a0a0;
    --text-300: #737373;

    --border: #2a2a2a;
    --border-hover: #404040;

    --accent-light: #001F3F;

    --shadow-sm: 0 1px 2px rgba(0,0,0,0.2);
    --shadow-md: 0 4px 12px rgba(0,0,0,0.3);
    --shadow-lg: 0 8px 24px rgba(0,0,0,0.4);
  }
}
"""


# ── Markdown Parsing ─────────────────────────────────────────────────────

def _parse_markdown_links(text: str) -> str:
    """[text](url) → <a href="url">text</a>"""
    def _replacer(m):
        link_text, url = m.group(1), m.group(2)
        # For externally visible links, show domain
        display = link_text
        return f'<a href="{url}" target="_blank" rel="noopener">{display}</a>'
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', _replacer, text)


def _parse_inline(text: str) -> str:
    """Handle bold, links, and escape HTML"""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # Links
    text = _parse_markdown_links(text)
    return text


def _section_id(title: str) -> str:
    """Generate an anchor id from section title"""
    slug = re.sub(r'[^\w一-鿿]+', '-', title).strip('-').lower()
    return slug[:60]


def _parse_report(report_text: str) -> dict:
    """Parse markdown report into structured data for HTML rendering.

    Returns:
        dict with: title, date, sections (list of {id, title, level, html, lines_count, word_count})
    """
    lines = report_text.split("\n")
    title = "丝网行业周报"
    date_str = datetime.now().strftime("%Y-%m-%d")
    sections = []
    current_section = None
    current_lines = []

    # Track relevance tags
    relevance_counts: dict[str, int] = {"direct": 0, "indirect": 0, "signal": 0}

    for line in lines:
        stripped = line.strip()

        # Main title
        if stripped.startswith("# ") and not stripped.startswith("## "):
            title_text = stripped[2:]
            date_match = re.search(r'[｜|]\s*(\d{4}-\d{2}-\d{2})', title_text)
            if date_match:
                date_str = date_match.group(1)
                title = title_text.replace(date_match.group(0), "").strip(" ｜|").strip()
            else:
                title = title_text
            continue

        # ## section header (create new section; ### stays as sub-heading within)
        if stripped.startswith("## ") and not stripped.startswith("### "):
            # Save previous section
            if current_section:
                current_section["body_html"] = _render_section_body(current_lines, relevance_counts)
                current_section["lines_count"] = len([l for l in current_lines if l.strip()])
                current_section["word_count"] = sum(len(l.strip()) for l in current_lines if l.strip())
                sections.append(current_section)

            current_section = {
                "id": _section_id(stripped[3:]),
                "title": stripped[3:],
                "level": 2,
                "html": "",
                "lines_count": 0,
                "word_count": 0,
            }
            current_lines = []
            continue

        if current_section is not None:
            current_lines.append(line)

    # Last section
    if current_section and current_lines:
        current_section["body_html"] = _render_section_body(current_lines, relevance_counts)
        current_section["lines_count"] = len([l for l in current_lines if l.strip()])
        current_section["word_count"] = sum(len(l.strip()) for l in current_lines if l.strip())
        sections.append(current_section)

    return {
        "title": title,
        "date": date_str,
        "sections": sections,
        "relevance_counts": relevance_counts,
    }


def _render_section_body(lines: list[str], relevance_counts: dict[str, int]) -> str:
    """Render section body lines to HTML"""
    html_parts = []
    in_list = False
    list_tag = "ul"

    for line in lines:
        stripped = line.strip()

        if not stripped:
            if in_list:
                html_parts.append(f"</{list_tag}>")
                in_list = False
            else:
                html_parts.append('<div class="spacer"></div>')
            continue

        # Horizontal rule
        if stripped.startswith("---"):
            if in_list:
                html_parts.append(f"</{list_tag}>")
                in_list = False
            html_parts.append('<hr class="divider">')
            continue

        # Count relevance tags
        for emoji, key in RELEVANCE_TAGS.items():
            if emoji in stripped:
                relevance_counts[key] += stripped.count(emoji)

        # Table
        if stripped.startswith("|") and stripped.endswith("|"):
            if in_list:
                html_parts.append(f"</{list_tag}>")
                in_list = False
            if re.match(r"^\|[-:| ]+\|$", stripped):
                continue  # skip table separator
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            html_parts.append(
                '<div class="table-row">'
                + "".join(f'<span class="table-cell">{_parse_inline(c)}</span>' for c in cells)
                + "</div>"
            )
            continue

        # Unordered list
        if stripped.startswith("- "):
            item_text = _parse_inline(stripped[2:])
            # Emoji + relevance badge
            item_html = _wrap_relevance_tag(item_text)
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
                list_tag = "ul"
            html_parts.append(f"<li>{item_html}</li>")
            continue

        # Ordered list
        if re.match(r"^\d+\.\s", stripped):
            item_text = _parse_inline(re.sub(r"^\d+\.\s", "", stripped))
            item_html = _wrap_relevance_tag(item_text)
            if not in_list:
                html_parts.append("<ol>")
                in_list = True
                list_tag = "ol"
            html_parts.append(f"<li>{item_html}</li>")
            continue

        # Close list if we were in one
        if in_list:
            html_parts.append(f"</{list_tag}>")
            in_list = False

        # Blockquote
        if stripped.startswith("> "):
            quote_text = _parse_inline(stripped[2:])
            html_parts.append(f'<blockquote>{quote_text}</blockquote>')
            continue

        # Regular paragraph
        if stripped.startswith("#### "):
            html_parts.append(f'<h4>{_parse_inline(stripped[5:])}</h4>')
        elif stripped.startswith("### "):
            html_parts.append(f'<h3>{_parse_inline(stripped[4:])}</h3>')
        else:
            p_text = _parse_inline(stripped)
            p_text = _wrap_relevance_tag(p_text)
            html_parts.append(f"<p>{p_text}</p>")

    if in_list:
        html_parts.append(f"</{list_tag}>")

    return "\n".join(html_parts)


def _wrap_relevance_tag(text: str) -> str:
    """Replace emoji relevance tags with styled badges"""
    for emoji, key in RELEVANCE_TAGS.items():
        if emoji in text:
            color = TAG_COLORS[key]
            label = TAG_LABELS[key]
            badge = (
                f'<span class="relevance-badge" '
                f'style="--badge-color: {color}">'
                f'{emoji} {label}'
                f'</span>'
            )
            text = text.replace(emoji, "", 1)
            # Remove the label text if it follows
            text = re.sub(rf'\s*{re.escape(label)}\s*', ' ', text, count=1)
            text = badge + " " + text.strip()
            return text
    return text


# ── HTML Template ────────────────────────────────────────────────────────

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}｜{date}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js">
</script>
<style>
/* ── Reset & Base ── */
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
html {{ font-size: 16px; scroll-behavior: smooth; }}
body {{
  font-family: var(--font-sans);
  background: var(--bg-100);
  color: var(--text-100);
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
  transition: background var(--transition), color var(--transition);
}}
{css_variables}

/* ── Layout ── */
.wrapper {{
  display: flex;
  min-height: 100vh;
}}

/* Sidebar */
.sidebar {{
  position: fixed;
  top: 0;
  left: 0;
  width: var(--sidebar-width);
  height: 100vh;
  border-right: 1px solid var(--border);
  background: var(--bg-200);
  overflow-y: auto;
  padding: var(--space-6) var(--space-5);
  z-index: 10;
  transition: background var(--transition), border-color var(--transition);
}}
.sidebar-header {{
  margin-bottom: var(--space-6);
  padding-bottom: var(--space-4);
  border-bottom: 1px solid var(--border);
}}
.sidebar-logo {{
  font-size: 14px;
  font-weight: 600;
  color: var(--text-100);
  text-decoration: none;
  display: flex;
  align-items: center;
  gap: var(--space-2);
}}
.sidebar-logo svg {{ width: 20px; height: 20px; }}
.sidebar-date {{
  font-size: 12px;
  color: var(--text-300);
  margin-top: var(--space-1);
}}
.sidebar-nav {{ list-style: none; }}
.sidebar-nav li {{ margin-bottom: 1px; }}
.sidebar-nav a {{
  display: block;
  padding: 6px 12px;
  font-size: 13px;
  color: var(--text-200);
  text-decoration: none;
  border-radius: var(--radius-md);
  transition: all var(--transition);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}}
.sidebar-nav a:hover {{
  background: var(--accent-light);
  color: var(--accent);
}}
.sidebar-nav a.active {{
  background: var(--accent);
  color: white;
}}
.sidebar-nav .section-num {{
  font-weight: 500;
  margin-right: 4px;
  opacity: 0.6;
}}

/* Main Content */
.main {{
  margin-left: var(--sidebar-width);
  flex: 1;
  padding: var(--space-8) var(--space-7);
  max-width: 960px;
}}

/* ── Report Header ── */
.report-header {{
  margin-bottom: var(--space-8);
  padding-bottom: var(--space-6);
  border-bottom: 1px solid var(--border);
}}
.report-title {{
  font-size: 32px;
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: -0.02em;
  margin-bottom: var(--space-2);
}}
.report-meta {{
  font-size: 14px;
  color: var(--text-300);
  display: flex;
  gap: var(--space-4);
  align-items: center;
}}
.report-meta .tag {{
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  background: var(--accent-light);
  color: var(--accent);
}}

/* ── Sections ── */
.section {{
  margin-bottom: var(--space-7);
  scroll-margin-top: var(--space-5);
}}
.section-header {{
  display: flex;
  align-items: baseline;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
  padding-bottom: var(--space-2);
  border-bottom: 2px solid var(--accent);
}}
.section-header h2 {{
  font-size: 20px;
  font-weight: 600;
  letter-spacing: -0.01em;
  line-height: 1.3;
}}
.section-header .section-meta {{
  font-size: 12px;
  color: var(--text-300);
  margin-left: auto;
  white-space: nowrap;
}}
.section-body {{
  font-size: 15px;
  line-height: 1.7;
  color: var(--text-100);
}}
.section-body h3 {{
  font-size: 16px;
  font-weight: 600;
  margin: var(--space-4) 0 var(--space-2);
  color: var(--text-100);
}}
.section-body h4 {{
  font-size: 14px;
  font-weight: 600;
  margin: var(--space-3) 0 var(--space-2);
  color: var(--text-200);
}}
.section-body p {{
  margin-bottom: var(--space-3);
}}
.section-body a {{
  color: var(--accent);
  text-decoration: none;
  border-bottom: 1px solid transparent;
  transition: border-color var(--transition);
}}
.section-body a:hover {{
  border-bottom-color: var(--accent);
}}
.section-body ul, .section-body ol {{
  padding-left: var(--space-5);
  margin-bottom: var(--space-3);
}}
.section-body li {{
  margin-bottom: var(--space-2);
}}
.section-body strong {{
  font-weight: 600;
}}
.section-body .spacer {{ height: var(--space-3); }}
.section-body hr.divider {{
  border: none;
  border-top: 1px solid var(--border);
  margin: var(--space-5) 0;
}}

/* Relevance Badge */
.relevance-badge {{
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 500;
  background: color-mix(in srgb, var(--badge-color) 10%, transparent);
  color: var(--badge-color);
  border: 1px solid color-mix(in srgb, var(--badge-color) 20%, transparent);
  white-space: nowrap;
  margin-right: 4px;
  vertical-align: middle;
}}

/* Blockquote */
.section-body blockquote {{
  margin: var(--space-3) 0;
  padding: var(--space-3) var(--space-4);
  border-left: 3px solid var(--accent);
  background: var(--bg-200);
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
  font-size: 13px;
  color: var(--text-200);
}}

/* Table */
.table-row {{
  display: flex;
  gap: 1px;
  background: var(--border);
  margin-bottom: 1px;
  border-radius: var(--radius-md);
  overflow: hidden;
}}
.table-row:first-child {{
  font-weight: 600;
  background: var(--bg-300);
}}
.table-cell {{
  flex: 1;
  padding: 6px 12px;
  background: var(--bg-100);
  font-size: 13px;
}}

/* ── Charts ── */
.charts-section {{
  margin-top: var(--space-8);
  padding-top: var(--space-6);
  border-top: 1px solid var(--border);
}}
.charts-section h2 {{
  font-size: 20px;
  font-weight: 600;
  margin-bottom: var(--space-5);
  letter-spacing: -0.01em;
}}
.charts-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-5);
}}
.chart-card {{
  background: var(--bg-200);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
}}
.chart-card h3 {{
  font-size: 14px;
  font-weight: 500;
  color: var(--text-200);
  margin-bottom: var(--space-4);
}}
.chart-card canvas {{
  width: 100% !important;
  height: auto !important;
  max-height: 260px;
}}

/* SVG fallback for PDF — hidden in browser, shown in print (WeasyPrint) */
.chart-fallback {{
  display: none;
}}
@media print {{
  .chart-js {{
    display: none !important;
  }}
  .chart-fallback {{
    display: block !important;
  }}
}}

/* ── Footer ── */
.report-footer {{
  margin-top: var(--space-8);
  padding-top: var(--space-5);
  border-top: 1px solid var(--border);
  font-size: 12px;
  color: var(--text-300);
  text-align: center;
}}

/* ── Mobile Toggle ── */
.sidebar-toggle {{
  display: none;
  position: fixed;
  top: 12px;
  left: 12px;
  z-index: 20;
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-100);
  color: var(--text-100);
  font-size: 18px;
  cursor: pointer;
  align-items: center;
  justify-content: center;
}}
.sidebar-overlay {{
  display: none;
}}

@media (max-width: 768px) {{
  .sidebar {{
    transform: translateX(-100%);
    transition: transform 250ms ease;
  }}
  .sidebar.open {{
    transform: translateX(0);
  }}
  .sidebar-overlay {{
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.3);
    z-index: 9;
  }}
  .sidebar-overlay.show {{
    display: block;
  }}
  .main {{
    margin-left: 0;
    padding: var(--space-5) var(--space-4);
  }}
  .sidebar-toggle {{
    display: flex;
  }}
  .charts-grid {{
    grid-template-columns: 1fr;
  }}
  .report-title {{
    font-size: 24px;
  }}
  .section-header h2 {{
    font-size: 17px;
  }}
}}
</style>
</head>
<body>

<button class="sidebar-toggle" id="sidebarToggle" aria-label="Toggle sidebar">☰</button>
<div class="sidebar-overlay" id="sidebarOverlay"></div>

<div class="wrapper">
  <!-- Sidebar -->
  <nav class="sidebar" id="sidebar">
    <div class="sidebar-header">
      <a href="#" class="sidebar-logo">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
        </svg>
        丝网行业周报
      </a>
      <div class="sidebar-date">{date}</div>
    </div>
    <ul class="sidebar-nav" id="toc">
      {toc_items}
    </ul>
  </nav>

  <!-- Main Content -->
  <main class="main">
    <header class="report-header">
      <h1 class="report-title">{title}｜{date}</h1>
      <div class="report-meta">
        <span class="tag">📊 {section_count} 个板块</span>
        <span class="tag">📝 {total_words} 字</span>
      </div>
    </header>

    {sections_html}

    <!-- Charts -->
    <div class="charts-section">
      <h2>📈 报告概览</h2>
      <div class="charts-grid">
        <div class="chart-card">
          <h3>各板块内容量</h3>
          <canvas id="volumeChart" class="chart-js"></canvas>
          {volume_chart_svg}
        </div>
        <div class="chart-card">
          <h3>信息关联度分布</h3>
          <canvas id="relevanceChart" class="chart-js"></canvas>
          {relevance_chart_svg}
        </div>
      </div>
    </div>

    <footer class="report-footer">
      由 丝网行业研究 Agent 自动生成 ｜ {date}
    </footer>
  </main>
</div>

<script>
// ── Sidebar Toggle (Mobile) ──
const sidebar = document.getElementById('sidebar');
const overlay = document.getElementById('sidebarOverlay');
const toggle = document.getElementById('sidebarToggle');
if (toggle) {{
  toggle.addEventListener('click', () => {{
    sidebar.classList.toggle('open');
    overlay.classList.toggle('show');
  }});
}}
if (overlay) {{
  overlay.addEventListener('click', () => {{
    sidebar.classList.remove('open');
    overlay.classList.remove('show');
  }});
}}

// ── Active Section Highlight ──
const observer = new IntersectionObserver((entries) => {{
  entries.forEach(entry => {{
    if (entry.isIntersecting) {{
      document.querySelectorAll('.sidebar-nav a').forEach(a => a.classList.remove('active'));
      const id = entry.target.id;
      const link = document.querySelector(`.sidebar-nav a[href="#${{id}}"]`);
      if (link) link.classList.add('active');
    }}
  }});
}}, {{ rootMargin: '-80px 0px -80% 0px' }});
document.querySelectorAll('.section[id]').forEach(el => observer.observe(el));

// ── Hide SVG fallbacks (they are for print/PDF only) ──
document.querySelectorAll('.chart-fallback').forEach(el => {{ el.style.display = 'none'; }});

// ── Volume Chart ──
const volumeCtx = document.getElementById('volumeChart');
if (volumeCtx) {{
  new Chart(volumeCtx, {{
    type: 'bar',
    data: {{
      labels: {chart_labels},
      datasets: [{{
        label: '字数',
        data: {chart_data},
        backgroundColor: [
          '#0070F3', '#46A758', '#FFB224', '#E5484D',
          '#8B5CF6', '#06B6D4', '#F97316', '#EC4899',
          '#14B8A6', '#6366F1', '#84CC16'
        ],
        borderRadius: 4,
        borderSkipped: false,
      }}]
    }},
    options: {{
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: true,
      plugins: {{
        legend: {{ display: false }},
      }},
      scales: {{
        x: {{
          grid: {{ display: false }},
          ticks: {{ font: {{ size: 11 }} }},
        }},
        y: {{
          grid: {{ display: false }},
          ticks: {{
            font: {{ size: 11 }},
            maxTicksLimit: 15,
          }},
        }}
      }}
    }}
  }});
}}

// ── Relevance Chart ──
const relevanceCtx = document.getElementById('relevanceChart');
if (relevanceCtx) {{
  new Chart(relevanceCtx, {{
    type: 'doughnut',
    data: {{
      labels: ['直接相关', '间接影响', '趋势信号'],
      datasets: [{{
        data: {relevance_chart_data},
        backgroundColor: ['#0070F3', '#46A758', '#FFB224'],
        borderWidth: 0,
      }}]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: true,
      plugins: {{
        legend: {{
          position: 'bottom',
          labels: {{
            padding: 16,
            font: {{ size: 12 }},
            usePointStyle: true,
          }}
        }}
      }},
      cutout: '65%',
    }}
  }});
}}
</script>
</body>
</html>"""


# ── SVG Fallback Charts (for WeasyPrint PDF) ────────────────────────────

_SVG_COLORS = [
    "#0070F3", "#46A758", "#FFB224", "#E5484D",
    "#8B5CF6", "#06B6D4", "#F97316", "#EC4899",
    "#14B8A6", "#6366F1", "#84CC16",
]

_SVG_RELEVANCE_COLORS = {
    "direct": "#0070F3",
    "indirect": "#46A758",
    "signal": "#FFB224",
}
_SVG_RELEVANCE_LABELS = {
    "direct": "直接相关",
    "indirect": "间接影响",
    "signal": "趋势信号",
}


def _generate_volume_svg(sections: list[dict]) -> str:
    """Generate SVG fallback for the volume horizontal bar chart"""
    if not sections:
        return ""

    svg_width = 500
    bar_height = 18
    gap = 8
    label_width = 130
    padding_top = 10
    padding_bottom = 10
    max_bar_width = svg_width - label_width - 60

    max_val = max(s["word_count"] for s in sections) if sections else 1
    total_height = len(sections) * (bar_height + gap) + padding_top + padding_bottom

    lines = [
        f'<svg class="chart-fallback" width="100%" height="{total_height}" '
        f'viewBox="0 0 {svg_width} {total_height}" '
        f'xmlns="http://www.w3.org/2000/svg">'
    ]

    for i, sec in enumerate(sections):
        y = padding_top + i * (bar_height + gap)
        val = max(sec["word_count"], 1)
        bar_w = int(val / max_val * max_bar_width)
        color = _SVG_COLORS[i % len(_SVG_COLORS)]

        # Shorten label
        m = re.match(r"^(\d+)\.\s*(.*)", sec["title"])
        if m:
            label = f'{m.group(1)}. {m.group(2)[:12]}'
        else:
            label = sec["title"][:18]

        lines.append(
            f'  <text x="{label_width - 8}" y="{y + bar_height - 5}" '
            f'text-anchor="end" font-family="sans-serif" font-size="11" '
            f'fill="#555">{_escape_svg_text(label)}</text>'
        )
        lines.append(
            f'  <rect x="{label_width}" y="{y}" width="{bar_w}" '
            f'height="{bar_height}" rx="3" fill="{color}" opacity="0.85"/>'
        )
        lines.append(
            f'  <text x="{label_width + bar_w + 6}" y="{y + bar_height - 5}" '
            f'font-family="sans-serif" font-size="11" '
            f'fill="#888">{val}</text>'
        )

    lines.append("</svg>")
    return "\n".join(lines)


def _generate_relevance_svg(relevance_counts: dict) -> str:
    """Generate SVG fallback for the relevance distribution (stacked bar)"""
    total = sum(relevance_counts.values()) or 1

    svg_width = 400
    bar_height = 28
    bar_y = 10
    margin = 30
    usable_width = svg_width - margin * 2

    lines = [
        f'<svg class="chart-fallback" width="100%" height="90" '
        f'viewBox="0 0 {svg_width} 90" '
        f'xmlns="http://www.w3.org/2000/svg">'
    ]

    # Stacked horizontal bar
    x = margin
    for key in ("direct", "indirect", "signal"):
        val = relevance_counts.get(key, 0)
        width = int(val / total * usable_width) if total > 0 else 0
        if width > 0:
            color = _SVG_RELEVANCE_COLORS[key]
            lines.append(
                f'  <rect x="{x}" y="{bar_y}" width="{width}" '
                f'height="{bar_height}" fill="{color}" rx="2"/>'
            )
            if width > 40:
                label = _SVG_RELEVANCE_LABELS[key]
                lines.append(
                    f'  <text x="{x + width // 2}" y="{bar_y + bar_height // 2 + 4}" '
                    f'text-anchor="middle" font-family="sans-serif" font-size="11" '
                    f'fill="#fff" font-weight="600">{label}</text>'
                )
            x += width

    # Legend
    legend_y = bar_y + bar_height + 18
    x = margin
    for key in ("direct", "indirect", "signal"):
        val = relevance_counts.get(key, 0)
        pct = round(val / total * 100) if total > 0 else 0
        color = _SVG_RELEVANCE_COLORS[key]
        label = _SVG_RELEVANCE_LABELS[key]
        lines.append(
            f'  <rect x="{x}" y="{legend_y - 7}" width="10" height="10" '
            f'fill="{color}" rx="2"/>'
        )
        lines.append(
            f'  <text x="{x + 16}" y="{legend_y + 2}" '
            f'font-family="sans-serif" font-size="10" '
            f'fill="#666">{label} {val} ({pct}%)</text>'
        )
        x += 120

    lines.append("</svg>")
    return "\n".join(lines)


def _escape_svg_text(text: str) -> str:
    """Escape special XML characters for SVG text content"""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ── Public API ───────────────────────────────────────────────────────────

def generate_html_report(report_text: str, output_path: str | Path) -> str:
    """Generate HTML report from markdown report text.

    Args:
        report_text: The full markdown report (from analyzer)
        output_path: Path to write the HTML file

    Returns:
        Path to the generated HTML file
    """
    parsed = _parse_report(report_text)
    sections = parsed["sections"]
    relevance_counts = parsed["relevance_counts"]

    # Build TOC
    toc_items = []
    for sec in sections:
        num = ""
        title_display = sec["title"]
        # Extract section number for display
        m = re.match(r'^(\d+)\.\s*(.*)', sec["title"])
        if m:
            num = m.group(1)
            title_display = m.group(2)
        cls = ' class="active"' if sec == sections[0] else ""
        toc_items.append(
            f'<li><a href="#{sec["id"]}"{cls}>'
            f'<span class="section-num">{num}.</span> {title_display}'
        f"</a></li>"
        )

    # Build sections HTML
    sections_html = []
    for sec in sections:
        meta = f'<span class="section-meta">{sec["word_count"]} 字</span>'
        sections_html.append(
            f'<section class="section" id="{sec["id"]}">'
            f'<div class="section-header"><h2>{sec["title"]}</h2>{meta}</div>'
            f'<div class="section-body">{sec["body_html"]}</div>'
            f"</section>"
        )

    # Chart data
    chart_labels = []
    chart_data = []
    for sec in sections:
        m = re.match(r'^(\d+)\.\s*(.*)', sec["title"])
        if m:
            # Shorten for chart
            label = m.group(2)[:12] + ("…" if len(m.group(2)) > 12 else "")
            chart_labels.append(f'{m.group(1)}. {label}')
        else:
            chart_labels.append(sec["title"][:15])

        # Use word_count as volume
        chart_data.append(max(sec["word_count"], 1))

    relevance_chart = [
        relevance_counts.get("direct", 0),
        relevance_counts.get("indirect", 0),
        relevance_counts.get("signal", 0),
    ]

    total_words = sum(s["word_count"] for s in sections)

    # Generate SVG fallback charts for PDF
    volume_chart_svg = _generate_volume_svg(sections)
    relevance_chart_svg = _generate_relevance_svg(relevance_counts)

    html = HTML_TEMPLATE.format(
        title=parsed["title"],
        date=parsed["date"],
        css_variables=CSS_VARIABLES,
        toc_items="\n".join(toc_items),
        sections_html="\n".join(sections_html),
        section_count=len(sections),
        total_words=total_words,
        chart_labels=str(chart_labels),
        chart_data=str(chart_data),
        relevance_chart_data=str(relevance_chart),
        volume_chart_svg=volume_chart_svg,
        relevance_chart_svg=relevance_chart_svg,
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")

    print(f"  [HTML] ✓ 报告已生成: {output_path}")
    return str(output_path)


if __name__ == "__main__":
    # Test with full-format sample markdown including article links
    test_report = """# 丝网行业周报｜2026-05-19

## 1. 本周一句话判断
本周不锈钢价格震荡上行，[青山集团上调304冷轧出厂价200元/吨](https://example.com/qingshan-price)，🔗 直接相关 丝网生产成本承压。[日本Asada Mesh发布新一代超细丝编织技术](https://example.com/asada-mesh)，⚡ 间接影响 高端丝网竞争格局。

## 2. 丝材料创新
- **[日本精線]开发0.012mm极细不锈钢线材](https://example.com/nihon-seisen-0012mm)** 🔗 直接相关 — 突破超细丝加工极限，可应用于半导体封装和医疗过滤领域
- **[碳纤维复合材料]应用于航空航天结构件](https://example.com/cfrp-aero)** ⚡ 间接影响 — 空客A350复材用量已超50%，拉动复材加工用丝网需求
- **[PTFE/PEEK涂层]耐腐蚀丝网表面处理新工艺](https://example.com/ptfe-coating)** 📡 趋势信号 — 适用于强酸碱环境下的过滤应用

**金属丝网关联分析**：[超细金属丝技术](https://example.com/fine-wire-tech)的突破将推动高端过滤、医疗用丝网的产品升级。碳纤维复合材料虽然不直接替代金属丝网，但其在航空航天领域的发展间接拓展了金属丝网的配套应用场景。[阅读原文](https://example.com/wire-mesh-analysis-01)

## 3. 网的高端应用
### 环保过滤
- [钢铁行业超低排放改造](https://example.com/steel-emission)推动高温滤袋需求 🔗 直接相关 — 2025年全国超低排放改造进入深水区，耐高温金属丝网滤袋采购量同比增长18%
- [废水资源化利用](https://example.com/wastewater)中丝网过滤设备渗透率提升，MBR膜+丝网预处理组合工艺成为主流

### 新能源
- [氢能电解槽用钛纤维毡](https://example.com/hydrogen-titanium-felt)需求增长 ⚡ 间接影响 — 国内电解槽产能规划已超100GW，钛纤维毡作为关键多孔传输层材料受益
- [锂电池极片辊压用钢带](https://example.com/battery-steel-belt)技术升级 🔗 直接相关 — 国产钢带在厚度公差方面已接近日本水平

**金属丝网关联分析**：环保领域是金属丝网的基本盘，[超低排放改造](https://example.com/emission-analysis)直接拉动高温过滤丝网需求。氢能领域虽然目前用量有限，但电解槽用多孔传输层（PTL）是值得关注的高端增量市场。[阅读原文](https://example.com/wire-mesh-analysis-02)

## 4. 织机与工艺装备
- **[Schlatter]新一代精密金属织机](https://example.com/schlatter-new)产能提升 🔗 直接相关 — 新品SX-2000型编织精度达±0.005mm，适用于5微米级过滤网生产
- **[Asagoe]提花织机智能化改造方案](https://example.com/asagoe-smart)发布 ⚡ 间接影响 — 支持AI视觉在线检测，减少织疵率
- **[河北安平]企业引进国产宽幅织机](https://example.com/anping-domestic-loom) 📡 趋势信号 — 国产织机价格仅为进口的1/3，加速中小企业设备升级

**金属丝网关联分析**：[精密织机国产化](https://example.com/loom-domestic)是降低高端丝网生产成本的关键。Schlatter新机型在编织精度上提升显著，将推动高端应用领域的产品升级。

## 5. 区域与产业集群动态
- **[河北安平]丝网产业共享制造基地](https://example.com/anping-shared)投产 🔗 直接相关 — 总投资12亿元，覆盖焊接、编织、表面处理全链条
- **[江苏南通]纺织机械出口](https://example.com/nantong-export)增长18% ⚡ 间接影响

**金属丝网关联分析**：[安平共享制造模式](https://example.com/anping-model)降低了中小企业设备升级门槛，有利于提升整个产业集群的工艺水平。

## 6. 原材料价格与供应链变化
- **[青山集团]304不锈钢冷轧卷板报15200元/吨（+1.3%）](https://example.com/qingshan-304)** 🔗 直接相关 — 连续三周上涨，主要受镍铁原料成本推动
- **[LME镍]收盘19200美元/吨（-0.7%）](https://example.com/lme-nickel) — 印尼镍矿出口政策松动，供应端预期改善
- **[螺纹钢]主力合约报3680元/吨（+0.5%）](https://example.com/rebar-futures) — 基建需求季节性回暖

**金属丝网关联分析**：304不锈钢价格上涨直接推高丝网原材料成本，预计传导至下游需要2-4周。[镍价小幅回落](https://example.com/nickel-analysis)有助于缓解成本压力。

## 7. 值得关注的新闻／公司
1. [青山集团印尼镍冶炼产能扩建获批](https://example.com/qingshan-indonesia) 🔗 直接相关 — 年产5万吨镍金属的HPAL项目预计2026年底投产
2. [日本精線发布2025财年财报](https://example.com/nihon-seisen-earnings)，精密丝材业务增长12%，半导体用线材增长最为显著
3. [河北安平丝网产业2025年一季度出口增长8.5%](https://example.com/anping-export-q1) 🔗 直接相关 — 对东盟出口增长最快，达到15.3%

## 8. 日本产业链
### Asada Mesh
- [新一代精密网织机研发进入测试阶段](https://example.com/asada-new-loom) 🔗 直接相关 — 目标编织精度0.003mm，采用磁悬浮引纬技术
- [半导体用超细丝网订单增长明显](https://example.com/asada-semiconductor) 🔗 直接相关 — 受益于全球半导体设备投资复苏

### 日本精線
- [0.012mm极细不锈钢线材量产](https://example.com/seisen-mass-prod) 🔗 直接相关 — 月产能5吨，主要供应医疗和半导体客户

**金属丝网关联分析**：[日本企业](https://example.com/japan-precision)在精密丝材和织机领域持续领先，国产替代仍需时日，但差距在缩小。

## 9. 全球展会与行业活动
- **[ACHEMA 2025]（法兰克福，7月）](https://example.com/achema-2025)** 📡 趋势信号 — 化工过滤展，丝网除沫器、烧结滤芯等产品参展
- **[中国国际过滤展]（上海，6月）](https://example.com/china-filtration-expo)** 🔗 直接相关 — 安平企业组团参展，重点展示环保过滤丝网解决方案

## 10. 下周关注点
- 青山集团是否进一步上调出厂价
- [安平丝网共享制造项目](https://example.com/anping-shared-project)进展
- LME镍价走势

## 11. 关键词扫描 — 新闻列举

> 以下为按产品关键词从本周采集信息中匹配的新闻条目，属于机器匹配的新闻列举，区别于以上 LLM 行业分析。

### 交通设施
  **[声屏障]：近一月声屏障招标汇总（https://example.com/noise-barrier-bids）**：广东省声屏障招标量环比增长23%，江苏、浙江跟进

  **[护栏网]：本周暂无相关新闻**

### 建筑装饰
  **[金刚网]：2025金刚网防盗纱窗市场分析（https://example.com/jingang-wang-2025）**：不锈钢金刚网在高端住宅渗透率提升至42%

  **[钢筋网]：本周暂无相关新闻**

### 环境保护
  **[过滤器 丝网]：钢铁行业超低排放改造进度（https://example.com/steel-filtration）**：河北钢厂丝网过滤需求增加

### 石油化工
  **[钢格板]：本周暂无相关新闻**
  **[丝网除沫器]：炼化项目丝网除沫器招标（https://example.com/mesh-pad-bid）**：浙石化二期项目招标丝网除沫器1200套

### 安全防护
  **[刀片刺绳]：本周暂无相关新闻**
  **[边坡防护网]：四川山区公路防护工程招标（https://example.com/slope-protection-bid）**：主动防护网需求量大

## 附录：监测清单与执行状态

**监测覆盖率**: 18/45 个目标有数据更新 (5 个部分更新)

| 分类 | 目标数 | 有更新 | 覆盖率 |
|-----|--------|--------|--------|
| 原材料 | 8 | 3 | 37.5% |
| 高端应用 | 6 | 2 | 33.3% |
| 织机设备 | 4 | 1 | 25.0% |
| 产业集群 | 5 | 3 | 60.0% |
| 日本产业链 | 8 | 4 | 50.0% |
| 其他 | 14 | 5 | 35.7% |
"""
    path = generate_html_report(test_report, "/tmp/test_wire_mesh_report.html")
    print(f"Generated: {path}")
