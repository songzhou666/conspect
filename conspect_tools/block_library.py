# -*- coding: utf-8 -*-
"""
conspect 报表板块库（v4.0）

数据来源：`assets/common/block_library.md` 的「板块总览」表（板块元信息）
          + 本模块的 `_TRIGGERS`（触发条件的可执行实现）。

为什么触发条件写在代码里：md 里的触发条件是人类可读的散文，选型阶段需要**可执行**判定。
本模块因此承担「散文 → 判定函数」的翻译，并由 tools/check_style_assets.py 校验
两侧的板块编号集合完全一致，防止 md 与代码漂移。
"""

import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

SKILL_DIR = Path(__file__).resolve().parent.parent
LIB_MD = SKILL_DIR / "assets" / "common" / "block_library.md"

ROW_RE = re.compile(
    r"^\|\s*(B\d{2})\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*(.+?)\s*\|\s*$",
    re.M,
)
BACKTICK_RE = re.compile(r"`([^`]+)`")
FAMILY_NAMES = {
    "开场": "open", "指标": "metric", "分析": "analysis",
    "结论": "conclusion", "说明": "meta", "收尾": "close",
}


def _parse() -> List[Dict[str, Any]]:
    blocks: List[Dict[str, Any]] = []
    try:
        text = LIB_MD.read_text(encoding="utf-8")
    except Exception:
        return blocks
    for m in ROW_RE.finditer(text):
        bid, name, family, need, chart, stype_raw = (x.strip() for x in m.groups())
        stypes = BACKTICK_RE.findall(stype_raw) or [stype_raw]
        blocks.append({
            "id": bid, "name": name, "family": family,
            "family_id": FAMILY_NAMES.get(family, family),
            "requirement": need,
            "chart": None if chart in ("—", "-", "") else chart,
            "section_type": stypes[0],
            "section_types": stypes,
        })
    return blocks


_BLOCKS = None


#: 每个板块「给读者看什么」的白话说明。
#:
#: 必要性：板块库里的 `name`（如「结构构成」）仍偏内部术语，
#: 而选型卡若只给编号（B08），客户完全无从判断要不要这一块。
#: 这里用一句话说清「这一块解决什么问题」——是**呈现层**用语，不是资产字段。
BLOCK_PURPOSE = {
    "B01": "开场：报表叫什么、什么范围、谁出品",
    "B02": "一页看完最重要的 3–5 条结论，不展开细节",
    "B03": "长报表的导航，告诉读者后面有什么",
    "B04": "把关键数字摆成一排，让人第一眼看到体量",
    "B05": "目标 vs 实际，用仪表或进度条显示完成度",
    "B06": "每个关键指标旁边挂一条小折线，看走向不看具体值",
    "B07": "时间上怎么变的：涨了还是跌了、有没有拐点",
    "B08": "总量由哪些部分构成，各占多少比例",
    "B09": "谁高谁低：按区域/产品/人员排序对比",
    "B10": "找出真正拉动结果的那几个因素（贡献度拆解）",
    "B11": "数值怎么分布、有没有异常值或长尾",
    "B12": "两个指标之间是否同向变化（相关关系，非因果）",
    "B13": "把明细数据摊开，供核对与下钻",
    "B14": "往后会怎样：基于历史趋势外推并给出区间",
    "B15": "把分析结论提炼成几条可复述的发现",
    "B16": "哪些地方有风险、哪些地方有机会",
    "B17": "接下来做什么，按优先级排",
    "B18": "每个指标怎么算的，避免口径争议",
    "B19": "数据本身的毛病：缺失、异常、口径限制",
    "B20": "用了哪些分析方法，结论的可信度边界在哪",
    "B21": "术语表、数据源清单等备查内容",
    "B22": "收尾：下一步动作与联系方式",
}


def purpose(bid: str) -> str:
    """
    板块的白话用途。

    未登记时退回「名称（家族）」，仍不可读时退回编号本身——
    宁可给出一个可识别但信息不足的字符串，也不返回空值：
    空值会让选型卡出现「B99：」这种半截内容，比缺信息更让人困惑。
    """
    hit = BLOCK_PURPOSE.get(bid)
    if hit:
        return hit
    b = get(bid)
    if b:
        return f"{b['name']}（{b['family']}）"
    return f"库外板块 {bid}"


def all_blocks() -> List[Dict[str, Any]]:
    global _BLOCKS
    if _BLOCKS is None:
        _BLOCKS = _parse()
    # 补上白话用途，让选型卡不必只给编号
    out = []
    for b in _BLOCKS:
        b = dict(b)
        b["purpose"] = BLOCK_PURPOSE.get(b["id"], "")
        out.append(b)
    return out


def get(bid: str) -> Optional[Dict[str, Any]]:
    for b in all_blocks():
        if b["id"] == bid:
            return b
    return None


def by_requirement(level: str) -> List[Dict[str, Any]]:
    return [b for b in all_blocks() if b["requirement"] == level]


def ids() -> List[str]:
    return [b["id"] for b in all_blocks()]


# ============================================================================
# 图表能力映射（板块库的「图表映射」列 → 渲染引擎真实能画的类型）
# ============================================================================
#
# 板块库用业务语言描述图表（如「帕累托 / 瀑布」「旭日 / 树图」），
# 而渲染引擎只认固定的 chart_type 枚举。两者之间必须有一层**显式映射**，
# 否则会出现「板块声明了引擎画不出的图」这种只在渲染时才暴露的缺陷。
#
# 映射规则：每个声明词给出一个**降级链**，按顺序取第一个引擎支持的；空链 = 该板块不画图（由 prose/kpi 承载）。

#: 渲染引擎真实支持的 chart_type（与 render_engine.ChartBuilder.build 的分派表逐项对应）
ENGINE_CHARTS = {
    "line", "area", "bar", "horizontal_bar", "stacked_bar", "pie", "ring",
    "funnel", "radar", "scatter", "heatmap", "sankey", "gauge", "treemap", "word_cloud",
}

#: 板块库声明词 → 引擎类型降级链（首个可用者生效）
DECLARED_CHART_ALIASES: Dict[str, List[str]] = {
    # --- 指标族 ---
    "指标卡": [],
    "仪表盘": ["gauge"],
    "进度条": ["gauge", "bar"],
    "迷你折线": [],                       # 由 kpi_cards 的变化值承载，不单独出图
    # --- 趋势 ---
    "折线": ["line"],
    "折线+置信区间": ["line"],            # 引擎无置信带，降级纯折线
    "面积": ["area", "line"],
    "K线": ["line"],                      # 引擎无 K 线，降级折线
    # --- 构成 ---
    "饼图": ["pie"],
    "环形": ["ring", "pie"],
    "堆叠": ["stacked_bar"],
    "旭日": ["treemap", "pie"],           # 引擎无旭日图，降级树图
    "树图": ["treemap"],
    # --- 对比 ---
    "柱状": ["bar"],
    "横向条形": ["horizontal_bar", "bar"],
    "分组柱": ["bar", "stacked_bar"],
    # --- 归因 ---
    "帕累托": ["bar"],                    # 引擎无帕累托（柱+累计线），降级柱状
    "瀑布": ["bar"],                      # 引擎无瀑布图，降级柱状
    # --- 分布 ---
    "直方图": ["bar"],                    # 引擎无直方图，降级柱状
    "箱线": ["bar", "scatter"],           # 引擎无箱线图，降级柱状
    "散点密度": ["scatter"],
    # --- 关联 ---
    "散点": ["scatter"],
    "热力图": ["heatmap"],
    "雷达": ["radar"],
    # --- 非图形态 ---
    "表格": [],
    "条件格式": [],
}

def _split_chart_words(raw: Optional[str]) -> List[str]:
    """
    把「折线 / 面积 / K线」拆成 ['折线','面积','K线']。

    规范化：去掉声明词内部的空格（「K 线」→「K线」、「折线 + 置信区间」→「折线+置信区间」），
    否则同一类型因写法不同就会漏配——这类问题只在渲染时才暴露，必须在解析层统一。
    """
    if not raw:
        return []
    parts = re.split(r"[/、,，]", raw)
    out = []
    for p in parts:
        w = re.sub(r"\s+", "", p.strip())
        if w and w not in ("—", "-"):
            out.append(w)
    return out


def chart_chain(bid: str) -> List[str]:
    """
    返回某板块按声明顺序可用的引擎 chart_type 列表（已去重、已过滤不支持者）。

    例：B07「折线 / 面积 / K线」→ ['line', 'area']
         B10「帕累托 / 瀑布」   → ['bar']
         B04「指标卡」           → []
    """
    b = get(bid)
    if not b:
        return []
    out: List[str] = []
    for word in _split_chart_words(b.get("chart")):
        for ct in DECLARED_CHART_ALIASES.get(word, []):
            if ct in ENGINE_CHARTS and ct not in out:
                out.append(ct)
    return out


def unmapped_chart_words() -> List[Dict[str, str]]:
    """返回板块库中「没有降级映射」的图表声明词，供校验脚本报错。"""
    bad = []
    for b in all_blocks():
        for word in _split_chart_words(b.get("chart")):
            if word not in DECLARED_CHART_ALIASES:
                bad.append({"block": b["id"], "word": word})
    return bad


#: 本身就是「非图形态」的声明词（由 kpi_cards / table / prose 承载，不算降级）
NON_CHART_WORDS = {"指标卡", "迷你折线", "表格", "条件格式"}

#: 声明词与其首个可用引擎类型同名者（即无降级）
_DIRECT = {"折线", "面积", "饼图", "环形", "树图", "柱状", "横向条形",
           "散点", "热力图", "雷达", "仪表盘", "堆叠", "分组柱"}


def chart_notes(bid: str) -> List[str]:
    """
    返回该板块需要如实标注的图表说明。

    只报两类：
      - 降级（声明的类型引擎画不出，已改用替代类型）
      - 无映射（声明词在映射表里找不到，属缺陷）
    「非图形态」不报——指标卡/表格本就该由 kpi_cards/table 承载，不是降级。
    """
    b = get(bid)
    if not b:
        return []
    notes = []
    for word in _split_chart_words(b.get("chart")):
        if word in NON_CHART_WORDS:
            continue
        chain = DECLARED_CHART_ALIASES.get(word)
        if chain is None:
            notes.append(f"{word} → 无映射（缺陷）")
        elif not chain:
            continue
        elif word not in _DIRECT:
            notes.append(f"{word} → {chain[0]}（降级）")
    return notes


# ============================================================================
# 触发条件（可执行实现，对应 md 中每个板块的「触发条件」）
# ============================================================================

def _f(features: Dict[str, Any]) -> Dict[str, Any]:
    """把 extract_features 的输出与用户诉求归一成扁平特征字典。"""
    f = dict(features or {})
    dims = f.get("dimensions") or {}
    return {
        "has_time": bool(f.get("has_time") or dims.get("time")),
        "time_points": int(f.get("time_points") or 0),
        "has_category": bool(f.get("has_category") or dims.get("category")),
        "category_count": int(f.get("category_count") or 0),
        # 分类维度的最小/典型规模：判断「是否存在适合做构成图的维度」。
        # 缺省时回退到 category_count，保证只传 category_count 的旧调用方行为不变。
        "category_min": int(f.get("category_min") or f.get("category_count") or 0),
        "category_mid": int(f.get("category_mid") or f.get("category_min")
                            or f.get("category_count") or 0),
        "has_numeric": bool(f.get("has_numeric", True)),
        "numeric_count": int(f.get("numeric_count") or 0),
        "sample_size": int(f.get("sample_size") or 0),
        "distinct_max": int(f.get("distinct_max") or 0),
        "has_target": bool(f.get("has_target")),
        "has_hierarchy": bool(f.get("has_hierarchy")),
        "has_decomposable": bool(f.get("has_decomposable")),
        "block_total": int(f.get("block_total") or 0),
        "want_detail": bool(f.get("want_detail")),
        "want_forecast": bool(f.get("want_forecast")),
        "want_trend_glance": bool(f.get("want_trend_glance")),
        "want_appendix": bool(f.get("want_appendix")),
        "has_advanced": bool(f.get("has_advanced")),
        "quality_score": float(f.get("quality_score", 100)),
        "has_missing": bool(f.get("has_missing")),
        "has_actionable": bool(f.get("has_actionable", True)),
    }


TRIGGERS: Dict[str, Callable[[Dict[str, Any]], bool]] = {
    "B01": lambda f: True,
    "B02": lambda f: True,
    "B03": lambda f: f["block_total"] > 6,
    "B04": lambda f: True,
    "B05": lambda f: f["has_target"],
    # B06 需要「迷你折线（无坐标轴）」组件，渲染引擎没有该组件；
    # 硬选进来只会在装配阶段报一个空洞的缺口。故暂不启用，趋势统一由 B07 承载。
    "B06": lambda f: False,
    "B07": lambda f: f["has_time"] and f["time_points"] >= 5,
    # B08 判「是否存在适合做构成图的维度」，用最小类别数而非最大：
    # 一张表里常有「所在城市」15 类这种不适合构成图的维度，
    # 但也有「产品类别」4 类——只取最大值会把构成图整块误排除。
    "B08": lambda f: f["has_category"] and 1 < f["category_min"] <= 10,
    "B09": lambda f: f["has_category"] and f["category_count"] >= 3,
    "B10": lambda f: f["has_decomposable"],
    "B11": lambda f: f["has_numeric"] and f["distinct_max"] >= 20,
    "B12": lambda f: f["numeric_count"] >= 2 and f["sample_size"] >= 30,
    "B13": lambda f: f["want_detail"] or f["category_count"] > 10,
    "B14": lambda f: f["want_forecast"] and f["time_points"] >= 8,
    "B15": lambda f: True,
    "B16": lambda f: True,
    "B17": lambda f: f["has_actionable"],
    "B18": lambda f: True,
    "B19": lambda f: f["quality_score"] < 90 or f["has_missing"],
    "B20": lambda f: f["has_advanced"],
    "B21": lambda f: f["want_appendix"],
    "B22": lambda f: True,
}

_TRIGGER_TEXT = {
    "B01": "无条件",
    "B02": "无条件",
    "B03": "板块总数 > 6",
    "B04": "无条件",
    "B05": "存在目标值/预算值/计划值列",
    "B06": "暂不启用：引擎无迷你折线组件（趋势由 B07 承载）",
    "B07": "存在时间维度且 ≥5 个不同取值",
    "B08": "存在分类维度且该维度类别数在 2–10（取最接近构成图可用的那个维度）",
    "B09": "存在分类维度且类别数 ≥3",
    "B10": "存在可分解的贡献结构",
    "B11": "数值列非重复值 ≥20",
    "B12": "≥2 个数值维度且有效样本 ≥30",
    "B13": "用户要求明细，或类别数 >10",
    "B14": "用户要求预测且时间点 ≥8",
    "B15": "无条件",
    "B16": "无条件",
    "B17": "识别出可行动项",
    "B18": "无条件",
    "B19": "质量分 <90 或存在缺失",
    "B20": "使用了高级分析",
    "B21": "用户要求附录",
    "B22": "无条件",
}


def triggers() -> Dict[str, str]:
    """返回 id → 触发条件的人类可读描述（用于选型卡展示）。"""
    return dict(_TRIGGER_TEXT)


def evaluate(features: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """
    按触发条件评估全部板块。

    返回：
        {"selected": [...], "excluded": [{"id","name","reason"}]}
    """
    f = _f(features)
    selected, excluded = [], []
    for b in all_blocks():
        fn = TRIGGERS.get(b["id"])
        if fn is None:
            excluded.append({**b, "reason": "未实现触发判定"})
            continue
        try:
            ok = bool(fn(f))
        except Exception as e:
            excluded.append({**b, "reason": f"判定异常：{type(e).__name__}"})
            continue
        if ok:
            selected.append({**b, "trigger": _TRIGGER_TEXT.get(b["id"], "")})
        else:
            excluded.append({**b, "reason": _TRIGGER_TEXT.get(b["id"], "")})
    return {"selected": selected, "excluded": excluded}


#: 永不被裁的核心板块（对应板块库 7 个必需板块）
CORE = {"B01", "B02", "B04", "B15", "B16", "B18", "B22"}

#: 裁剪时族的优先顺序：分析最该保留，收尾最先舍弃
FAMILY_ORDER = {"analysis": 0, "metric": 1, "conclusion": 2,
                "open": 3, "meta": 4, "close": 5}

_REQ_RANK = {"必需": 0, "条件": 1, "可选": 2}


#: 板块能容纳几张图表。
#: 排名（B09）天然支持多维拆解（区域/品类/渠道/人员…），一个分区放 4–5 张是常规做法；
#: 趋势（B07）超过 2 张就重复了；其余分析板块 2 张足够。
CAPACITY = {"B09": 5, "B07": 2, "B08": 2, "B10": 2, "B11": 2, "B12": 2, "B14": 2}


def capacity(bid: str) -> int:
    """该板块最多放几张图。"""
    return CAPACITY.get(bid, 2)


def trim(blocks: List[Dict[str, Any]], limit: int,
         min_analysis: int = 2) -> (List[Dict[str, Any]], List[Dict[str, Any]]):
    """
    板块超量时裁剪。

    规则：
      1. 核心板块（CORE）一律保留；
      2. 分析族板块至少保留 min_analysis 个（数据报表不能没有分析）；
      3. 其余按「分析 → 指标 → 结论 → 开场 → 说明 → 收尾」的族序填充；
      4. 族序相同时按必需度排序。
    """
    if limit <= 0 or len(blocks) <= limit:
        return list(blocks), []

    keep = [b for b in blocks if b["id"] in CORE]
    rest = [b for b in blocks if b["id"] not in CORE]

    analysis = [b for b in rest if b["family_id"] == "analysis"]
    others = [b for b in rest if b["family_id"] != "analysis"]

    kept_extra = []
    slots = max(0, limit - len(keep))
    must = min(min_analysis, len(analysis))
    kept_extra.extend(analysis[:must])
    slots -= must

    pool = analysis[must:] + sorted(
        others, key=lambda b: (FAMILY_ORDER.get(b["family_id"], 9),
                               _REQ_RANK.get(b["requirement"], 9))
    )
    kept_extra.extend(pool[:max(0, slots)])

    kept = keep + kept_extra
    kept_ids = [b["id"] for b in kept]
    dropped = [b for b in blocks if b["id"] not in set(kept_ids)]

    order = {b["id"]: i for i, b in enumerate(blocks)}
    kept.sort(key=lambda b: order[b["id"]])
    return kept, dropped


def summary() -> Dict[str, Any]:
    bs = all_blocks()
    return {
        "count": len(bs),
        "families": len({b["family_id"] for b in bs}),
        "required": len([b for b in bs if b["requirement"] == "必需"]),
        "conditional": len([b for b in bs if b["requirement"] == "条件"]),
        "optional": len([b for b in bs if b["requirement"] == "可选"]),
        "source": str(LIB_MD),
    }
