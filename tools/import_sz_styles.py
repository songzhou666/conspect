#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
conspect v4.0 风格资产导入器（一次性工具，可重复运行）

职责：
  1. 解析外部风格资产集合的 49 份风格正文（统一 8 节格式）
  2. 叠加「报表化改造层」——筛选、分族、补报表专属维度（图表序列色 / 版式建议 / 数据禁忌）
  3. 补齐设计 token（bg 从 / ink / ac 推导出 card / mu / line）
  4. 产出 assets/style-system.json —— conspect 的唯一风格事实源

运行：
  python tools/import_sz_styles.py --src <资产目录> [--out <输出路径>]

说明：本脚本只在资产体系需要重建时运行一次；日常使用读取 style-system.json。
      运行结果会被 tools/check_style_assets.py 校验。
"""

import argparse
import json
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_OUT = SKILL_DIR / "assets" / "style-system.json"

# ============================================================================
# 报表化改造层（人工判断，集中在此便于审阅）
# ============================================================================

# ---------- 六族（按报表使用场景分类） ----------
FAMILIES = [
    {
        "id": "biz",
        "label": "商务通稿",
        "en": "BIZ REPORT",
        "tone": "浅色",
        "scene": "正式汇报 · 年度报告 · 经营分析 · 打印分发",
        "series": ["#2B4C8C", "#4A7CF7", "#6FC3A0", "#F5A623", "#E86868", "#8B6CD6"],
    },
    {
        "id": "screen",
        "label": "数据大屏",
        "en": "DATA SCREEN",
        "tone": "深色",
        "scene": "会议室投屏 · 监控大屏 · 沉浸演示 · 展会轮播",
        "series": ["#05D9E8", "#FF2D95", "#7C5CFF", "#46E6A0", "#FFC53D", "#4A9BFF"],
    },
    {
        "id": "glass",
        "label": "玻璃光影",
        "en": "GLASS & LIGHT",
        "tone": "混合",
        "scene": "产品发布 · 品牌质感 · 高端提案 · 汇报封面",
        # 第 6 色由 #A0A8FF 改为 #7EE787：原浅紫与 #8A6DF2 色相差仅 18°、明度差 12，
        # 多系列图无法区分。改用绿加入色相环缺口（距紫 128°）。
        "series": ["#8A6DF2", "#29A1FF", "#6BE3C8", "#FFB26B", "#FF7BA6", "#7EE787"],
    },
    {
        "id": "editorial",
        "label": "纸感编辑",
        "en": "EDITORIAL PAPER",
        "tone": "浅色",
        "scene": "深度研究 · 行业洞察 · 阅读型长报告 · 归档留存",
        # 原 #C9A227（金）与 #B76E2E（棕）色相差 17.5°、明度差仅 2.2，几乎同色。
        # 改为橄榄绿 #7A8450，既补色相缺口，又贴合纸感调性。
        "series": ["#B76E2E", "#8B0000", "#2C3E50", "#7A8450", "#7F8C8D", "#4A6B5A"],
    },
    {
        "id": "organic",
        "label": "自然柔和",
        "en": "ORGANIC SOFT",
        "tone": "浅色",
        "scene": "健康医疗 · 教育科研 · ESG 可持续 · 亲和型内部汇报",
        # 原 #D4A373（土黄）与 #E9C46A（黄）色相差 12.8°、明度差 2.4，几乎同色。
        # 改为柔和玫瑰 #D98CA0，与族内黄/青/蓝/紫均拉开，也更贴合亲和调性。
        "series": ["#2A9D8F", "#6BBF8A", "#E9C46A", "#D98CA0", "#8AB6D6", "#C8A2C8"],
    },
    {
        "id": "bold",
        "label": "表达张力",
        "en": "BOLD EXPRESSION",
        "tone": "混合",
        "scene": "创意提案 · 品牌宣言 · 年轻化团队 · 营销复盘",
        "series": ["#FF2D55", "#2C6BFF", "#FFD23F", "#00C48C", "#FF6B35", "#9B5DE5"],
    },
]

# ---------- 筛选结果：38 风格 → 6 族 ----------
SELECTED = {
    "biz": ["A1", "A12", "A29", "A42", "A47", "A8", "A17"],
    "screen": ["A7", "A18", "A33", "A28", "A23", "A48", "A46"],
    "glass": ["A3", "A10", "A14", "A25", "A45", "A19"],
    "editorial": ["A37", "A49", "A13", "A36", "A11", "A32"],
    "organic": ["A24", "A2", "A9", "A41", "A39", "A21"],
    "bold": ["A4", "A6", "A20", "A26", "A34", "A38"],
}

# ---------- 剔除说明（族分类之外，保留可追溯的排除理由） ----------
EXCLUDED = {
    "A15": "交互型：风格载体是动势流转，静态报表无法承载",
    "A16": "交互型：风格载体是微交互反馈，静态报表无法承载",
    "A30": "交互型：风格载体是流动字态动画，静态报表无法承载",
    "A31": "交互型：风格载体是滚动视差叙事，静态报表无法承载",
    "A43": "交互型：风格载体是光标磁吸跟随，静态报表无法承载",
    "A44": "交互型：风格载体是语音对话界面，静态报表无法承载",
    "A5": "与数据展示冲突：重体积感压制数据层级，读数变慢",
    "A22": "与数据展示冲突：金属眩光干扰读数，且与族内 A46/A48 重叠",
    "A27": "与数据展示冲突：粉紫低对比不利于投影与打印，且与族内 A46 重叠",
    "A35": "族内高度重叠：与 A21 便当拼盒视觉语言重复",
    "A40": "与数据展示冲突：终端字符噪声降低表格可读性",
}

# ---------- 族级组件样式（报表化改写：KPI / 图表 / 表格 / 解读区） ----------
FAMILY_COMPONENTS = {
    "biz": {
        "kpi": "白卡 + 顶部细色条，数值用主色加粗，标签用次级灰，卡片与卡片之间靠留白分隔而非重阴影",
        "chart": "细条栅格，去掉冗余网格线与背景块，仅保留水平基准线；分类标签水平排列",
        "table": "无竖线，仅横线分隔；表头用主色底或加粗；斑马纹极淡（3% 透明度）",
        "insight": "浅灰底 + 左侧主色竖线，字号比正文小一档，语气克制",
    },
    "screen": {
        "kpi": "深色卡 + 霓虹描边 + 数值发光，数值字号明显大于标签，四角可加角标装饰",
        "chart": "暗底亮线，渐变面积填充，网格线用低透明度同色系，强调点做光晕",
        "table": "深底亮字 + 行高亮，表头用强调色描边，避免大面积高饱和填充",
        "insight": "深色底 + 左侧霓虹竖线 + 低透明度同色系底纹，文字用高亮色",
    },
    "glass": {
        "kpi": "半透明毛玻璃卡 + 背景模糊 + 细白描边，数值用强调色，卡片浮在渐变背景上",
        "chart": "平滑曲线 + 半透明渐变填充，数据点带柔光，网格线极淡",
        "table": "毛玻璃容器 + 无边框行，靠行背景微差区分",
        "insight": "半透明底 + 细描边，文字用高亮色，与卡片同质感",
    },
    "editorial": {
        "kpi": "纸色卡 + 细黑描边（或仅下边线），数值用衬线字，标签用小号大写字母距",
        "chart": "低饱和配色 + 明确刻度 + 图注编号，允许细网格，风格接近印刷图表",
        "table": "完整横线分隔 + 衬线数字 + 顶部双线表头，接近书籍表格",
        "insight": "引用块样式：左缩进 + 左侧粗线 + 斜体或衬线，像编辑批注",
    },
    "organic": {
        "kpi": "大圆角卡 + 柔和同色系底 + 无边框，数值与标签都偏大偏松",
        "chart": "圆润曲线 + 柔和填充 + 大圆点，避免尖锐折角",
        "table": "大圆角容器 + 宽松行高 + 无竖线，斑马纹用同色系浅色调",
        "insight": "圆角色块底 + 左侧圆头竖线，语气亲和",
    },
    "bold": {
        "kpi": "高饱和色块卡 + 硬边框 + 极粗数值字，允许非对称尺寸制造张力",
        "chart": "高对比色块 + 粗线粗柱 + 明确描边，避免渐变与阴影",
        "table": "硬边框 + 高饱和表头 + 粗字，行分隔用实线",
        "insight": "高饱和色块底 + 粗边框，文字用对比色，像宣言而非注释",
    },
}

# ---------- 族级报表适配（报表类型 / 推荐板块 / 数据密度 / 载体） ----------
FAMILY_REPORT_USE = {
    "biz": {
        "types": ["经营分析", "年度/季度报告", "财务汇报", "项目复盘"],
        "blocks": ["B01", "B02", "B04", "B07", "B08", "B09", "B13", "B15", "B18", "B22"],
        "density": "高",
        "media": "投影 / 打印",
    },
    "screen": {
        "types": ["实时监控大屏", "发布会演示", "展会轮播", "沉浸式数据故事"],
        "blocks": ["B01", "B04", "B05", "B06", "B07", "B12", "B14", "B15", "B22"],
        "density": "中",
        "media": "大屏投屏",
    },
    "glass": {
        "types": ["产品发布", "品牌提案", "融资路演", "年度品牌报告"],
        "blocks": ["B01", "B02", "B03", "B04", "B07", "B08", "B09", "B15", "B17", "B22"],
        "density": "中",
        "media": "屏幕 / 投影",
    },
    "editorial": {
        "types": ["行业研究", "深度洞察", "年度白皮书", "归档长报告"],
        "blocks": ["B01", "B02", "B03", "B04", "B07", "B08", "B10", "B11", "B13", "B16", "B18", "B19", "B20", "B21", "B22"],
        "density": "高",
        "media": "阅读 / 打印",
    },
    "organic": {
        "types": ["健康医疗报告", "教育科研汇报", "ESG 可持续报告", "内部团队汇报"],
        "blocks": ["B01", "B02", "B04", "B08", "B09", "B12", "B15", "B17", "B22"],
        "density": "中",
        "media": "屏幕 / 打印",
    },
    "bold": {
        "types": ["创意提案", "品牌宣言", "营销复盘", "年轻化产品发布"],
        "blocks": ["B01", "B02", "B04", "B06", "B09", "B10", "B15", "B17", "B22"],
        "density": "低",
        "media": "投影 / 屏幕",
    },
}

# ---------- 族级数据展示禁忌 ----------
FAMILY_TABOOS = {
    "biz": [
        "不使用超过 6 类的分类色，多类别改用排序 + 汇总",
        "不使用渐变与霓虹特效，会破坏克制感",
        "不在一屏内放超过 4 个 KPI 卡",
    ],
    "screen": [
        "不用于打印：暗底大面积输出会严重耗墨且失真",
        "不用低饱和浅色做数据系列，暗底上看不清",
        "不在同一屏内混用超过 3 种霓虹色，会失去主次",
    ],
    "glass": [
        "不在文字下叠加高透明度背景图，对比度会跌破 4.5:1",
        "不用毛玻璃承载密集表格，可读性差",
        "不在浅色投影环境下使用深色玻璃卡",
    ],
    "editorial": [
        "不使用高饱和色系列，会与纸感基调冲突",
        "不用无衬线超大标题，会失去编辑感",
        "不压缩行高：阅读型报告行高不低于 1.6",
    ],
    "organic": [
        "不用尖角与硬边元素",
        "不使用高对比撞色，会破坏柔和基调",
        "不在小尺寸图表中使用大圆点，会互相遮挡",
    ],
    "bold": [
        "不用高饱和色承载长文本，阅读疲劳",
        "不用于正式财务与合规类报告",
        "不在同一屏混用超过 3 个高饱和主色",
    ],
}

# ---------- 风格级附加禁忌（仅对需要注意的风格补充） ----------
STYLE_TABOOS = {
    "A34": ["像素艺术：不用于类别数 ≥ 8 的图表，像素点会糊成一团"],
    "A26": ["孟菲斯彩：不用于多系列折线对比，几何装饰会干扰曲线判读"],
    "A38": ["世代极繁：不用于超过 15 行的明细表，装饰元素会淹没数据"],
    "A4": ["粗野主义：不用于对外正式报告，宣言式排版不适合中性陈述"],
    "A13": ["仿真实物：不用于高清投影，材质拟物在小尺寸下会显得脏"],
    "A41": ["触感果冻：不用于精确数值对比，柔软边框弱化了数值边界"],
    "A39": ["细胞仿生：不用于时间序列趋势，有机形状与线性趋势语义冲突"],
    "A18": ["隐于无形：不用于需要快速定位指标的场合，极简会牺牲可扫读性"],
    "A46": ["流彩网格：不用于彩打以外的输出，网格流光在灰度打印下消失"],
    "A48": ["色散重影：不用于小字号正文，重影会显著降低可读性"],
    "A2": ["同色浮雕：不用于投影环境，低对比立体感在投影下会糊掉"],
    "A36": ["空间浮窗：不用于超过 3 层的层级结构，浮窗叠深会失去层次"],
}

# ---------- 风格级报表适配覆盖 ----------
STYLE_REPORT_OVERRIDES = {
    "A8": {"density": "高", "media": "投影 / 打印 / 无障碍阅读"},
    "A17": {"density": "高", "media": "投影 / 打印 / 无障碍阅读"},
    "A7": {"density": "中", "media": "屏幕 / 夜间投屏"},
    "A33": {"density": "中", "media": "大屏投屏"},
    "A46": {"density": "低", "media": "大屏投屏"},
    "A48": {"density": "低", "media": "大屏投屏"},
    "A23": {"density": "低", "media": "大屏投屏"},
    "A37": {"density": "高", "media": "打印 / 长文阅读"},
    "A13": {"density": "中", "media": "屏幕"},
    "A49": {"density": "中", "media": "打印 / 屏幕"},
    "A21": {"density": "高", "media": "投影 / 屏幕"},
    "A29": {"density": "低", "media": "投影 / 打印"},
    "A34": {"density": "低", "media": "屏幕"},
    "A38": {"density": "低", "media": "屏幕"},
}

FALLBACK_BY_TONE = {"浅色": "#FFFFFF", "深色": "#14141C", "混合": "#F7F7FA"}

# ---------- Token 人工覆盖 ----------
# 源资产中有 3 份用 CSS 变量或纯渐变表达底色，机械解析会取到渐变里的装饰色；
# 另有 1 份的 ink 与 bg 同为浅色（原资产缺陷，白底米字不可读）。
# 覆盖值一律取自该资产**自身色板**，并记录原因，可追溯。
TOKEN_OVERRIDES = {
    "A3": {
        "bg": "#0D1226",
        "ink": "#FFFFFF",
        "_note": "源资产 --bg 为多层 radial-gradient，实际暗底为 linear-gradient 端点 #0D1226，人工指定",
    },
    "A13": {
        "ink": "#3E2723",
        "_note": "源资产 ink=#F5F5DC（米色）与 bg=#FFFFFF 对比度仅 1.11 不可读；改用其色板中的 #3E2723 深棕",
    },
    "A46": {
        "bg": "#0F0F1A",
        "ink": "#FFFFFF",
        "_note": "源资产 --bg/--ink 为 CSS 变量，取该资产色板 #0F0F1A 与 #FFFFFF",
    },
}


def repair_contrast(tokens, code, log):
    """ink/bg 对比度不足 4.5:1 时向黑白两极拉，直到达标。"""
    bg = tokens["bg"]
    ink = tokens["ink"]
    cr = contrast_ratio(ink, bg)
    if cr >= 4.5:
        return tokens, None
    target = "#111111" if not is_dark(bg) else "#F7F7FA"
    for step in range(1, 11):
        candidate = mix(ink, target, step / 10)
        c = contrast_ratio(candidate, bg)
        if c >= 4.5:
            log.append(f"{code}: ink {ink} → {candidate}（对比度 {cr} → {c}）")
            tokens = dict(tokens)
            tokens["ink"] = candidate
            return tokens, candidate
    tokens = dict(tokens)
    tokens["ink"] = target
    log.append(f"{code}: ink {ink} → {target}（对比度 {cr} → {contrast_ratio(target, bg)}，强制）")
    return tokens, target


# ============================================================================
# 颜色工具
# ============================================================================

HEX_RE = re.compile(r"#([0-9A-Fa-f]{3,8})\b")


def normalize_hex(value):
    """#fff / #ffffff / #ffffffff → #rrggbb；非法返回 None。"""
    if not value:
        return None
    m = HEX_RE.search(value)
    if not m:
        return None
    h = m.group(1)
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    elif len(h) == 4:
        h = "".join(c * 2 for c in h[:3])
    elif len(h) >= 6:
        h = h[:6]
    else:
        return None
    return "#" + h.upper()


def to_rgb(hex_color):
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def to_hex(rgb):
    return "#" + "".join(f"{max(0, min(255, int(round(c)))):02X}" for c in rgb)


def mix(a, b, t):
    """t=0 → a，t=1 → b。"""
    ra, rb = to_rgb(a), to_rgb(b)
    return to_hex(tuple(ra[i] * (1 - t) + rb[i] * t for i in range(3)))


def relative_luminance(hex_color):
    r, g, b = (c / 255 for c in to_rgb(hex_color))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast_ratio(fg, bg):
    l1, l2 = relative_luminance(fg), relative_luminance(bg)
    if l1 < l2:
        l1, l2 = l2, l1
    return round((l1 + 0.05) / (l2 + 0.05), 2)


def is_dark(hex_color):
    return relative_luminance(hex_color) < 0.35


# ============================================================================
# 正文解析
# ============================================================================

def _section_body(text, title):
    """取出 '## {title}' 到下一个 '## ' 之间的内容。"""
    m = re.search(r"^##\s+" + re.escape(title) + r"\s*$(.*?)(?=^##\s+|\Z)",
                  text, re.M | re.S)
    return m.group(1).strip() if m else ""


def _bullets(block):
    """把 '- 键：值' 收成 dict；无冒号的行丢进 _extra。值两端反引号一律剥离。"""
    out = {}
    extra = []
    for line in block.splitlines():
        line = line.strip()
        if not line.startswith("- "):
            continue
        item = line[2:].strip()
        item = re.sub(r"^\*\*(.+?)\*\*\s*[：:]\s*", r"\1：", item)
        if "：" in item:
            k, v = item.split("：", 1)
            out[k.strip()] = v.strip().strip("`").strip()
        else:
            extra.append(item.strip("`").strip())
    if extra:
        out["_extra"] = extra
    return out


def _balanced(text):
    """括号成对（渐变串完整）才可用。"""
    return text and text.count("(") == text.count(")")


def parse_body(path):
    text = path.read_text(encoding="utf-8")
    stem = path.stem

    m = re.match(r"^(A\d+)_(.+)$", stem)
    if not m:
        raise ValueError(f"文件名不符合 A{{编号}}_{{class}} 约定：{path.name}")
    code, cls = m.group(1), m.group(2)

    head = text.splitlines()[2] if len(text.splitlines()) > 2 else ""
    fam_src = (re.search(r"族：\*\*(.+?)\*\*", head) or [None, ""])[1]
    tone = (re.search(r"调性：\s*([^\s·]+)", head) or [None, ""])[1]
    tone = "深色" if "深" in tone else ("浅色" if "浅" in tone else tone)

    title_line = text.splitlines()[0].lstrip("# ").strip()
    tm = re.match(r"^(A\d+)\s+(.+?)\s+·\s+(.+)$", title_line)
    label = tm.group(2) if tm else title_line
    en = tm.group(3) if tm else ""

    school_block = _section_body(text, "设计流派")
    school = re.split(r"\n\s*\n", school_block)[0].strip() if school_block else ""
    keywords = []
    km = re.search(r"\*\*关键词\*\*\s*[：:]\s*(.+)", text)
    if km:
        keywords = [k.strip() for k in re.split(r"[·、,，]", km.group(1)) if k.strip()]
    mood = ""
    mm = re.search(r"\*\*一句话氛围\*\*\s*[：:]\s*(.+)", text)
    if mm:
        mood = mm.group(1).strip()

    # ---- 配色 Token ----
    # 表格单元格可能跨多个物理行（渐变串），先把 token 段整体取出再按行首 '|' 重组
    token_block = _section_body(text, "配色 Token（可直接抄用）") or _section_body(text, "配色 Token")
    logical_rows = []
    buf = ""
    for line in token_block.splitlines():
        s = line.rstrip()
        if s.startswith("|"):
            if buf:
                logical_rows.append(buf)
            buf = s
        elif buf and s:
            buf += " " + s.strip()
    if buf:
        logical_rows.append(buf)

    tokens = {"bg": None, "bg_gradient": None, "ink": None, "ac": None}
    for line in logical_rows:
        if "`--" not in line:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        key = re.search(r"`--(\w+)`", cells[0])
        if not key:
            continue
        name, raw = key.group(1), cells[1]
        # 单元格格式：`<颜色>[；渐变：<渐变串>]` 或直接是渐变串
        head, _, tail = raw.partition("；渐变：")
        gradient = tail.strip(" `") or None
        value = normalize_hex(head)
        if value is None:
            # 无显式色值（CSS 变量或纯渐变）→ 取渐变串中最后一个色值作为底色
            hexes = HEX_RE.findall(tail or raw)
            if name == "bg" and hexes:
                value = normalize_hex("#" + hexes[-1])
        if name == "bg":
            tokens["bg"] = value
            # 源资产中部分渐变串本身被截断（括号不闭合），保留会污染生成物 → 丢弃并留痕
            tokens["bg_gradient"] = gradient if _balanced(gradient) else None
            if gradient and not _balanced(gradient):
                tokens["_gradient_truncated"] = gradient
        else:
            tokens[name] = value

    # ---- 色板 ----
    palette = []
    pm = re.search(r"\*\*色板（\d+\s*色）\*\*\s*[：:]\s*(.+)", text)
    if pm:
        seen = set()
        for h in HEX_RE.findall(pm.group(1)):
            v = normalize_hex("#" + h)
            if v and v not in seen:
                seen.add(v)
                palette.append(v)

    # ---- 字体 / 形状 / 组件 / 版式 ----
    typo = _bullets(_section_body(text, "字体与排版"))
    shapes = _bullets(_section_body(text, "形状与特效"))
    comp_src = _section_body(text, "组件样式特征")
    comp_raw = ""
    for line in comp_src.splitlines():
        if line.strip().startswith("- "):
            comp_raw = line.strip()[2:].strip()
            break
    layout_src = _bullets(_section_body(text, "版式建议"))
    orig_scenes = [s.strip() for s in
                   re.split(r"[·、,，]", layout_src.get("适用演示场景", "")) if s.strip()]

    return {
        "code": code,
        "class": cls,
        "label": label,
        "en": en,
        "tone": tone,
        "source_family": fam_src,
        "school": school,
        "keywords": keywords,
        "mood": mood,
        "palette": palette,
        "typography": {
            "family": typo.get("字体族", ""),
            "size_range": typo.get("字号范围", ""),
            "weights": [w.strip() for w in
                        re.split(r"[/、]", typo.get("字重", "")) if w.strip()],
        },
        "shapes": {k: v for k, v in shapes.items() if k != "_extra"},
        "shape_extra": shapes.get("_extra", []),
        "components_source": comp_raw,
        "original_scenes": orig_scenes,
        "original_media": layout_src.get("明暗调性", ""),
        "tokens_raw": tokens,
    }


# ============================================================================
# 组装
# ============================================================================

def build_tokens(raw, code=None):
    """由 bg / ink / ac 推导完整 token 集；支持人工覆盖。"""
    override = TOKEN_OVERRIDES.get(code or "", {})
    bg = override.get("bg") or raw.get("bg")
    ink = override.get("ink") or raw.get("ink")
    ac = override.get("ac") or raw.get("ac")
    bg_gradient = override.get("bg_gradient", raw.get("bg_gradient"))
    token_note = override.get("_note")
    if raw.get("_gradient_truncated"):
        token_note = ((token_note + "；") if token_note else "") + \
            "源资产背景渐变串被截断（括号不闭合），已丢弃该渐变"

    if not bg:
        bg = FALLBACK_BY_TONE.get("浅色", "#FFFFFF")
    dark = is_dark(bg)
    if not ink:
        ink = "#F5F5FA" if dark else "#111111"
    if not ac:
        ac = "#2563EB"
    if dark:
        card = mix(bg, "#FFFFFF", 0.07)
        line = mix(bg, "#FFFFFF", 0.17)
        mu = mix(ink, bg, 0.40)
    else:
        card = "#FFFFFF"
        line = mix(ink, bg, 0.88)
        mu = mix(ink, bg, 0.52)
    return {
        "bg": bg,
        "bg_gradient": bg_gradient,
        "ink": ink,
        "ac": ac,
        "card": card,
        "mu": mu,
        "line": line,
    }, token_note


def parse_args(argv):
    p = argparse.ArgumentParser(description="把外部风格资产导入为 conspect 的 style-system.json")
    p.add_argument("--src", required=True,
                   help="风格资产目录（含 A*.md 正文文件）")
    p.add_argument("--out", default=str(DEFAULT_OUT), help="输出 JSON 路径")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    src = Path(args.src)
    if not src.is_dir():
        print(f"[FATAL] 资产目录不存在：{src}")
        return 2

    files = sorted(src.glob("A*.md"), key=lambda p: int(re.match(r"A(\d+)", p.stem).group(1)))
    if not files:
        print(f"[FATAL] 目录内无 A*.md 正文：{src}")
        return 2

    parsed = {}
    errors = []
    for f in files:
        try:
            item = parse_body(f)
            parsed[item["code"]] = item
        except Exception as e:
            errors.append(f"{f.name}: {type(e).__name__} {e}")

    print(f"[解析] 发现 {len(files)} 份正文，成功 {len(parsed)} 份，失败 {len(errors)} 份")
    for e in errors:
        print("   ! " + e)

    fam_by_id = {f["id"]: f for f in FAMILIES}
    styles = []
    missing = []
    repairs = []
    for fid, codes in SELECTED.items():
        fam = fam_by_id[fid]
        for code in codes:
            item = parsed.get(code)
            if not item:
                missing.append(f"{fid}/{code}")
                continue
            tokens, token_note = build_tokens(item["tokens_raw"], code)
            tokens, repaired_ink = repair_contrast(tokens, code, repairs)
            if token_note and repaired_ink:
                token_note += f"；另因对比度不足将 ink 调整为 {repaired_ink}"
            base_use = FAMILY_REPORT_USE[fid]
            use = {
                "types": list(base_use["types"]),
                "blocks": list(base_use["blocks"]),
                "density": base_use["density"],
                "media": base_use["media"],
            }
            use.update(STYLE_REPORT_OVERRIDES.get(code, {}))
            styles.append({
                "code": code,
                "label": item["label"],
                "en": item["en"],
                "class": item["class"],
                "family": fid,
                "tone": item["tone"],
                "tokens": tokens,
                "token_note": token_note,
                "source_palette": item["palette"],
                "typography": item["typography"],
                "shapes": item["shapes"],
                "shape_extra": item["shape_extra"],
                "school": item["school"],
                "keywords": item["keywords"],
                "mood": item["mood"],
                "components_source": item["components_source"],
                "components": dict(FAMILY_COMPONENTS[fid]),
                "report_use": use,
                "taboos": list(FAMILY_TABOOS[fid]) + list(STYLE_TABOOS.get(code, [])),
                "original_scenes": item["original_scenes"],
                "original_media": item["original_media"],
                "body": f"assets/body/{code}_{item['class']}.md",
            })

    if missing:
        print(f"[FATAL] 以下风格在资产目录中未找到：{missing}")
        return 1

    family_out = []
    for fam in FAMILIES:
        members = [s["code"] for s in styles if s["family"] == fam["id"]]
        family_out.append({**fam, "styles": members, "count": len(members)})

    out = {
        "version": "4.0",
        "generated_by": "tools/import_sz_styles.py",
        "note": "conspect 唯一风格事实源；assets/{catalog,index,body} 下的 md 均由本文件生成",
        "total_styles": len(styles),
        "family_count": len(family_out),
        "excluded": EXCLUDED,
        "families": family_out,
        "styles": styles,
        "block_library": {
            "path": "assets/common/block_library.md",
            "count": 22,
            "families": ["open", "metric", "analysis", "conclusion", "meta", "close"],
        },
    }

    dst = Path(args.out)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    warnings = []
    for s in styles:
        t = s["tokens"]
        cr = contrast_ratio(t["ink"], t["bg"])
        if cr < 4.5:
            warnings.append(f"{s['code']} {s['label']}：ink/bg 对比度 {cr} < 4.5")
    print(f"[产出] {dst}")
    print(f"[统计] {len(styles)} 风格 / {len(family_out)} 族；"
          f"对比度告警 {len(warnings)} 条")
    for w in warnings:
        print("   ? " + w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
