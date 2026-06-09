"""前端主题系统：CSS 变量 + 字体 + Material Symbols 注入 + icon() 助手。

只在 app.py 顶部 st.set_page_config() 之后调用 inject_theme() 一次。
图标通过 icon(name, size, color) 助手生成 HTML 字符串，传给
st.markdown(..., unsafe_allow_html=True) 渲染。
"""
from __future__ import annotations

import streamlit as st

# Data-Dense Dashboard 颜色令牌（与 HTML 导出 CSS 同源）
COLOR_PRIMARY = "#1E40AF"
COLOR_PRIMARY_HOVER = "#1E3A8A"
COLOR_SECONDARY = "#3B82F6"
COLOR_ACCENT = "#D97706"
COLOR_BG = "#F8FAFC"
COLOR_SURFACE = "#FFFFFF"
COLOR_TEXT = "#0F172A"
COLOR_TEXT_SECONDARY = "#475569"
COLOR_MUTED = "#E9EEF6"
COLOR_BORDER = "#DBEAFE"
COLOR_DANGER = "#DC2626"
COLOR_SUCCESS = "#16A34A"
COLOR_WARNING = "#D97706"

_THEME_CSS = """
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=Fira+Code&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined" rel="stylesheet">
<style>
:root {
  --color-primary: #1E40AF;
  --color-primary-hover: #1E3A8A;
  --color-secondary: #3B82F6;
  --color-accent: #D97706;
  --color-bg: #F8FAFC;
  --color-surface: #FFFFFF;
  --color-text: #0F172A;
  --color-text-secondary: #475569;
  --color-muted: #E9EEF6;
  --color-border: #DBEAFE;
  --color-danger: #DC2626;
  --color-success: #16A34A;
  --color-warning: #D97706;
  --radius: 8px;
  --shadow-card: 0 1px 3px rgba(15, 23, 42, 0.08), 0 1px 2px rgba(15, 23, 42, 0.04);
  --transition: all 150ms cubic-bezier(0.4, 0, 0.2, 1);
}

html, body, [class*="css"] {
  font-family: 'Plus Jakarta Sans', -apple-system, 'Segoe UI', system-ui, sans-serif;
  color: var(--color-text);
}

/* 主背景色 */
.stApp { background-color: var(--color-bg); }

/* 数字字体 */
.kpi-num, .num { font-family: 'Fira Code', 'Cascadia Code', Consolas, monospace; }

/* KPI 卡片 */
.kpi-card {
  background: var(--color-surface);
  padding: 16px;
  border-radius: var(--radius);
  box-shadow: var(--shadow-card);
  border-left: 3px solid var(--color-primary);
}
.kpi-card-label { font-size: 12px; color: var(--color-text-secondary); margin-bottom: 4px; }
.kpi-card-main { font-size: 28px; font-weight: 600; color: var(--color-primary); }
.kpi-card-sub { font-size: 12px; color: var(--color-text-secondary); margin-top: 4px; }

/* Section 卡片 */
.section-card {
  background: var(--color-surface);
  margin: 16px 0;
  padding: 20px;
  border-left: 4px solid var(--color-primary);
  border-radius: var(--radius);
  box-shadow: var(--shadow-card);
}

/* Action 卡片 */
.action-card {
  background: var(--color-surface);
  padding: 16px;
  border-radius: var(--radius);
  border-left: 4px solid var(--color-accent);
  box-shadow: var(--shadow-card);
  margin-bottom: 12px;
}
.action-card.priority-critical { border-left-color: var(--color-danger); }
.action-card.priority-important { border-left-color: var(--color-warning); }
.action-card.priority-consider { border-left-color: var(--color-primary); }

/* 导出按钮 */
.btn-export {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: var(--color-primary);
  color: white !important;
  border-radius: var(--radius);
  text-decoration: none;
  font-size: 14px;
  margin-right: 8px;
  transition: var(--transition);
}
.btn-export:hover {
  background: var(--color-primary-hover);
  color: white !important;
  text-decoration: none;
}

/* Material Symbols 默认配置 */
.material-symbols-outlined {
  font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
  vertical-align: middle;
}

/* Streamlit primary button 主色 */
.stButton > button[kind="primary"] {
  background-color: var(--color-primary);
  border-color: var(--color-primary);
}
.stButton > button[kind="primary"]:hover {
  background-color: var(--color-primary-hover);
  border-color: var(--color-primary-hover);
}
</style>
"""


def inject_theme() -> None:
    """注入主题 CSS + 字体 + Material Symbols。仅 app.py 顶部调用一次。"""
    st.markdown(_THEME_CSS, unsafe_allow_html=True)


def icon(name: str, size: int = 20, color: str | None = None) -> str:
    """渲染 Material Symbol 字体图标，返回 HTML 字符串。

    用法：st.markdown(f"{icon('analytics')} 报告标题", unsafe_allow_html=True)
    图标列表：https://fonts.google.com/icons
    """
    style = f"font-size:{size}px"
    if color:
        style += f";color:{color}"
    return f'<span class="material-symbols-outlined" style="{style}">{name}</span>'
