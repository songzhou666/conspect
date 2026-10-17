# -*- coding: utf-8 -*-
"""
conspect 图表建议器（v4.1）

职责：把「分析数据」阶段算出来的原始表，翻译成**可直接渲染的图表候选**。

为什么需要独立成模块：
  `analyze` 原本只产 rows / dimensions / statistics / data_quality，**不产 charts**，
  导致「汇报内容选型」与「生成报表」两个阶段拿到的 charts 恒为空——报表最终只有文字板块。
  图表候选必须由代码基于数据算出，而不是指望 Agent 凭记忆手搓。

三条硬规则（都由真实业务数据踩出来）：
  1. **可加总性判别**：单价 / 折扣率 / 毛利率这类不能求和，只能取均值；
     否则会得到「平均单价 5.5 万」这种荒谬指标。
  2. **健康度过滤**：缺失率 >30% 的指标不参与聚合（否则 sum 严重低估）；
     唯一值接近行数的列是 ID，不参与分类图（否则饼图出 72 个扇区）。
  3. **时间必须自算**：`aggregated.by_dimension` 不含时间维度，
     趋势图必须在这里按时间分组重算，并在跨度大时按月聚合。
"""

import re
import warnings
from typing import Any, Dict, List, Optional

import pandas as pd

#: 可加总的指标关键词（求和有意义）
ADDITIVE_HINTS = ("数量", "金额", "销售额", "收入", "营收", "利润", "毛利",
                  "成本", "费用", "件数", "次数", "人数", "吨", "台", "套",
                  "qty", "quantity", "amount", "revenue", "sales", "profit", "cost")

#: 只能取均值的指标关键词（求和无意义）。"单位" 类必须是均值——
#: 「单位成本」含「成本」但它是单价概念，求和会得出荒谬的巨额成本。
AVERAGE_HINTS = ("单价", "价格", "均价", "率", "比", "折扣", "均", "分值", "单位",
                 "price", "rate", "ratio", "avg", "mean", "percent", "unit")

#: 缺失率上限：超过则聚合不可信，不纳入图表
MAX_NULL_RATE = 0.30

#: 只有「价格/比率/额度」类字段、没有可加总度量的表，行数达到此值时
#: 视为记录型事实表（如拜访流水、工单、日志），可用「记录数」作为分析指标
COUNT_MIN_ROWS = 100

#: 小样本文档的最小行数。低于此值连简报都不值当，直接判为不可分析。
MIN_TABLE_ROWS = 3

#: 分类维度允许的唯一值区间。
#: 上限放到 50 是给「排名」用的——省/市这种 20–50 类做 TopN 横条完全成立；
#: 构成图另有更严的 PIE_MAX（6），不会因为这里放宽而画出几十个扇区。
MIN_CATEGORIES, MAX_CATEGORIES = 2, 50

#: 不具备「指标」语义的数值列（即便 dtype 是数字也不该做聚合/画图）
NON_METRIC_HINTS = ("电话", "手机", "联系方式", "邮箱", "地址", "经纬度", "坐标",
                    "编号", "id", "序号", "行号", "邮编", "卡号", "身份证",
                    "代码", "code", "phone", "mobile", "email", "url",
                    "照片", "图片", "链接", "lng", "lat")

#: 时间跨度过大时不做趋势（多半是「上市日期」「合作起始日」这类属性日期，
#: 按它聚合得出的是「每个月上市产品的平均成本」这种伪趋势）
MAX_TIME_SPAN_DAYS = 3 * 366

#: 分类维度可作为「构成图」的上限（饼图可读性）
PIE_MAX = 6

#: 图表标题用的指标友好名
METRIC_ALIAS = {
    "销售额": "销售额", "销售数量": "销量", "毛利": "毛利", "毛利率": "毛利率",
    "单价": "均价", "折扣率": "平均折扣", "单位成本": "单位成本",
}


#: 图表生成过程中的告警（不静默吞异常，供 analyze 汇总上报）
_WARNINGS: List[str] = []


def take_warnings() -> List[str]:
    """取出并清空累计告警。"""
    global _WARNINGS
    out, _WARNINGS = _WARNINGS, []
    return out


def _agg_for(col: str) -> str:
    """判定指标聚合方式，返回 pandas 认识的名字（sum / mean）。"""
    name = str(col).lower()
    # 先判不可加总（"单价"含"价"但不可加；"单位成本"含"成本"但应取均值）
    if any(h in name for h in AVERAGE_HINTS):
        return "mean"
    if any(h in name for h in ADDITIVE_HINTS):
        return "sum"
    return "mean"          # 无法判定时保守取均值，避免荒谬的巨额合计


def _metric_label(col: str, agg: str) -> str:
    """指标展示名。已是「均价/人均/比率」类的不要再加「平均」前缀。"""
    base = METRIC_ALIAS.get(col, col)
    if agg != "mean":
        return base
    if any(t in base for t in ("平均", "人均", "均")) or base.endswith(("率", "比")):
        return base
    return f"平均{base}"


def _usable_metrics(df: pd.DataFrame, dims: Dict[str, List[str]],
                    contract: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    筛出可用于图表的度量列。

    **有契约时以契约为准**：角色（measure/identifier/text）、可加总性全部来自契约，
    不再看关键词。这样「客单价」「GMV」「到店人次」这类新行业术语不会因为不在
    白名单里就被判错，而且判定结果可审计（契约里带 reason）。
    无契约时才用关键词兜底，并标记 `provenance=heuristic`。

    两类通用过滤始终保留（与业务无关，纯数据质量）：
      缺失率 >30% 的列不参与聚合；全空/常量/全零列排除。
    """
    out = []
    use_contract = bool(contract and contract.get("columns"))
    # provenance 必须在循环外初始化：无度量列时循环不执行，
    # 若在循环内赋值，退化到「记录数」那一步会引用未定义变量。
    provenance = "contract" if use_contract else "heuristic"

    # 有契约时，度量列直接取 views.measure，不再从 dims["数值"] 里捞
    candidates = (contract["views"].get("measure", []) if use_contract
                  else dims.get("数值", []))

    for col in candidates:
        if col not in df.columns:
            continue
        if not use_contract:
            # 兜底路径：关键词排除「长得像数字的标识列」
            if any(h in str(col).lower() for h in NON_METRIC_HINTS):
                continue
        s = df[col]
        null_rate = float(s.isna().mean())
        if null_rate > MAX_NULL_RATE:
            continue
        valid = s.dropna()
        if valid.empty or valid.nunique() <= 1:
            continue
        if float(valid.abs().sum()) == 0:
            continue

        if use_contract:
            meta = contract["columns"].get(col, {})
            add = meta.get("additivity", "unknown")
            # 契约未标可加总性时取均值：宁可少算总额，也不输出荒谬合计
            agg = "mean" if add != "additive" else "sum"
            provenance = "contract"
        else:
            agg = _agg_for(col)
            provenance = "heuristic"

        # 排序优先级：契约给出的是否为「主度量」信号优先，其次按业务常识
        prio = 0
        if any(h in col for h in ("销售额", "金额", "收入", "营收")):
            prio = 0
        elif any(h in col for h in ("毛利", "利润")):
            prio = 1
        elif any(h in col for h in ("数量", "件数", "次数")):
            prio = 2
        else:
            prio = 3
        # 可加总度量比均值型度量更适合做主图
        if agg == "mean":
            prio += 1

        out.append({"col": col, "agg": agg, "null_rate": null_rate,
                    "prio": prio, "label": _metric_label(col, agg),
                    "provenance": provenance})
    out.sort(key=lambda x: (x["prio"], x["col"]))
    using_count = False
    if not out and len(df) >= COUNT_MIN_ROWS:
        # 记录型表：无金额/数量类度量（如拜访流水、工单、日志），
        # 分析对象本身就是「记录数」。此时若不退化为计数，
        # 整张表会一张图都产不出，报表只剩文字板块。
        out = [{"col": "__count__", "agg": "count", "null_rate": 0.0,
                "prio": 0, "label": "记录数",
                "provenance": provenance if use_contract else "heuristic"}]
        using_count = True
    return out, using_count


def _usable_categories(df: pd.DataFrame, dims: Dict[str, List[str]],
                       contract: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    筛出可用于分类图的维度，并按「出图价值」排序。

    **有契约时只取 role=dimension 的列**：identifier（明细ID/电话/地址）与 text
    （自由文本）在契约层面就已被排除，不再依赖基数与关键词的事后拦截。

    排序依据三个真实影响可读性的因素：
      1. **覆盖率**：缺失 40% 的维度（如只有部分诊所填了「IT设备」）做排名会误导
      2. **类别数**：2 类做排名信息量太低；3–10 类最适合柱状/排名
      3. **业务相关性**：区域/类别/渠道这类维度优先于「填写人」这类操作字段
    """
    n = len(df)
    out = []
    prio_hints = ("区域", "类别", "渠道", "行业", "类型", "等级", "城市", "省", "市",
                  "销售", "客户", "产品", "漏斗", "阶段", "标签", "潜力", "优先级")
    use_contract = bool(contract and contract.get("columns"))
    candidates = (contract["views"].get("dimension", []) if use_contract
                  else dims.get("分类", []))

    seen_sig = {}
    for col in candidates:
        if col not in df.columns:
            continue
        s = df[col].dropna()
        if s.empty:
            continue
        u = int(s.nunique())
        if u < MIN_CATEGORIES or u > MAX_CATEGORIES:
            continue
        # 唯一值几乎等于行数 → 明细 ID，不适合分类图。
        # 契约已判为 dimension 的列仍要过这一关：契约可能判了「客户名称」为维度，
        # 但 940 类做排名图等于把明细表格画成柱状图。
        if u >= max(3, int(n * 0.9)):
            continue
        # 内容重复列只保留第一个出现者
        sig = (u, hash(tuple(sorted(map(str, s.unique()))[:200])))
        if sig in seen_sig:
            continue
        seen_sig[sig] = col

        coverage = len(s) / n
        prio = 0 if any(h in col for h in prio_hints) else 1
        if 3 <= u <= 10:
            ideal = 0
        elif u == 2:
            ideal = 1
        elif u <= 30:
            ideal = 2
        else:
            ideal = 3
        out.append({"col": col, "unique": u, "prio": prio,
                    "coverage": round(coverage, 4), "ideal": ideal,
                    "funnel": any(h in col for h in ("漏斗", "阶段", "转化", "funnel"))})

    # 漏斗/阶段维度排最前：它承载「逐级转化」这条主线，
    # 若按类别数排序会被一堆 3 类标签维度挤掉，漏斗图永远画不出来。
    out.sort(key=lambda c: (0 if c["funnel"] else 1,
                            c["prio"],
                            0 if c["coverage"] >= 0.95 else 1,
                            c["ideal"],
                            -c["coverage"],
                            c["unique"]))
    return out


#: 中文日期写法：「2025年06月27日 15:27」「2026年7月6日」
_CJK_DATE_RE = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?"
                          r"(?:\s*(\d{1,2})\s*[:：]\s*(\d{1,2})(?:\s*[:：]\s*(\d{1,2}))?)?")

#: 常见日期时间格式，按精确优先排序
_DT_FORMATS = (
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
    "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y/%m/%d",
    "%Y-%m-%dT%H:%M:%S", "%Y.%m.%d",
)


def _grab_cjk(x: Any) -> Any:
    """从字符串里用正则抠出中/英式日期。"""
    m = _CJK_DATE_RE.search(str(x))
    if not m:
        return pd.NaT
    y, mo, d, hh, mm, ss = m.groups()
    try:
        return pd.Timestamp(int(y), int(mo), int(d),
                            int(hh or 0), int(mm or 0), int(ss or 0))
    except Exception:
        return pd.NaT


def _to_datetime(series: pd.Series) -> pd.Series:
    """
    尽力把一列解析成 datetime。

    中文业务表格里日期常写成「2025年06月27日 15:27」，`pd.to_datetime` 直接解析
    会 **100% 失败**（实测 0/2500），于是趋势图静默消失——这类失败不报错、只表现为
    「报表里没有趋势」。所以必须先做中文格式归一，再逐个格式精确尝试。

    注意：「日」要用 regex 去掉。写成 `str.replace(r"\\s*日", "", regex=False)`
    会把 `\\s*日` 当成字面量匹配，`日` 根本没被删掉，归一结果变成
    `2025-06-27日 15:27`，后续解析依然全空——这是本次实测踩到的坑。
    """
    s = series.astype(str).str.strip()
    # 中文年月日 → 标准分隔符
    if s.str.contains("年", na=False).any():
        s = (s.str.replace(r"\s*年\s*", "-", regex=True)
               .str.replace(r"\s*月\s*", "-", regex=True)
               .str.replace(r"\s*日", "", regex=True)
               .str.strip())

    best, best_n = None, -1
    for fmt in _DT_FORMATS:
        dt = pd.to_datetime(s, format=fmt, errors="coerce")
        n = int(dt.notna().sum())
        if n > best_n:
            best, best_n = dt, n
        if n == len(s):          # 全部命中，无需再试
            return dt

    # 同一列常混着不同精度（有的到秒、有的到分）。先用命中最多的一种格式解析，
    # 再拿其余格式逐轮补齐剩下的空位——只选「最佳单一格式」会漏掉一部分。
    if best is not None and 0 < best_n < len(s):
        for fmt in _DT_FORMATS:
            miss = best.isna()
            if not miss.any():
                break
            alt = pd.to_datetime(s[miss], format=fmt, errors="coerce")
            if alt.notna().any():
                best.loc[miss] = alt
    if best is not None and int(best.notna().sum()) > 0:
        return best

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        best = pd.to_datetime(s, errors="coerce")
    if int(best.notna().sum()) == 0:
        best = s.map(_grab_cjk)
    return best


def _time_series(df: pd.DataFrame, time_col: str, metric: Dict) -> Optional[Dict]:
    """
    按时间聚合。跨度 >90 天或点数 >12 时按月聚合，否则保留原始时间点。

    返回 {"categories": [...], "values": [...], "granularity": "月"/"日"}
    """
    ts = _to_datetime(df[time_col])
    mask = ts.notna()
    if not mask.any():
        return None
    col = metric["col"]
    ts = ts[mask]
    if metric["agg"] == "count":
        values = pd.Series(1, index=ts.index)
    else:
        values = df.loc[mask, col]
        if values.dropna().empty:
            return None

    span_days = (ts.max() - ts.min()).days
    # 跨度过大 → 多是「上市日期/合作起始日」这类属性日期，按它聚合是伪趋势
    if span_days > MAX_TIME_SPAN_DAYS:
        return None
    if span_days > 90:
        key = ts.dt.to_period("M").astype(str)
        gran = "月"
    else:
        key = ts.dt.strftime("%Y-%m-%d")
        gran = "日"

    agg = "sum" if metric["agg"] == "count" else metric["agg"]
    grouped = values.groupby(key).agg(agg).sort_index()
    # 去掉 NaN 与空组
    grouped = grouped.dropna()
    if len(grouped) < 2:
        return None
    return {
        "categories": [str(i) for i in grouped.index.tolist()],
        "values": [round(float(v), 2) for v in grouped.tolist()],
        "granularity": gran,
    }


def _category_series(df: pd.DataFrame, cat_col: str, metric: Dict,
                     top_n: int = 10) -> Optional[Dict]:
    """按分类聚合，取 TopN。返回 {categories, values, total}"""
    col = metric["col"]
    if metric["agg"] == "count":
        sub = df[[cat_col]].dropna()
        if sub.empty:
            return None
        grouped = sub.groupby(cat_col).size().sort_values(ascending=False)
        total = float(grouped.sum())
    else:
        sub = df[[cat_col, col]].dropna()
        if sub.empty:
            return None
        grouped = sub.groupby(cat_col)[col].agg(metric["agg"]).sort_values(ascending=False)
        if grouped.empty:
            return None
        total = float(grouped.sum()) if metric["agg"] == "sum" else float(grouped.mean())
    top = grouped.head(top_n)
    return {
        "categories": [str(i) for i in top.index.tolist()],
        "values": [round(float(v), 2) for v in top.tolist()],
        "total": round(total, 2),
        "truncated": len(grouped) > top_n,
        "n_all": len(grouped),
    }


def recommend(df: pd.DataFrame, dims: Dict[str, List[str]],
              quality: Dict[str, Any] = None,
              max_charts: int = 10,
              contract: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    基于清洗后的表生成图表候选。

    参数:
        df: 清洗后的 DataFrame（analyze 内部已加载）
        dims: identify_dimensions 的结果（无契约时的兜底来源）
        quality: data_quality（可选，用于写入图表备注）
        max_charts: 最多产出多少个候选
        contract: 数据契约（schema_contract.build 产出）。传入后
                  度量列、维度列、可加总性全部以契约为准，关键词不再参与判定。

    返回:
        图表列表，每项含 chart_type / title / data / description /
        block（建议归属的板块编号）/ 以及可选的 note（降级或口径说明）
    """
    charts: List[Dict[str, Any]] = []
    metrics, using_count = _usable_metrics(df, dims, contract)
    cats = _usable_categories(df, dims, contract)
    if not metrics:
        return charts

    primary = metrics[0]
    time_cols = [c for c in dims.get("时间", []) if c in df.columns]
    # 只有存在「可加总指标」或「记录数」的表才配得上趋势图与构成图。
    # 维表（产品信息表、客户信息表）只有价格/额度这类均值型字段，
    # 按时间聚合得出的是「每个月上市产品的平均成本」——那是伪趋势，不是业务走势。
    has_additive = any(m["agg"] in ("sum", "count") for m in metrics)

    # ---- 1. 趋势（时间维度）→ B07 ----
    if time_cols and has_additive:
        ts = _time_series(df, time_cols[0], primary)
        if ts:
            label = f"{primary['label']}趋势（按{ts['granularity']}）"
            charts.append({
                "chart_type": "line" if len(ts["categories"]) <= 50 else "area",
                "title": label,
                "block": "B07",
                "data": {"categories": ts["categories"], "values": ts["values"]},
                "description": f"{ts['categories'][0]} 至 {ts['categories'][-1]}，"
                               f"共 {len(ts['categories'])} 个{ts['granularity']}节点。",
                "note": f"时间维度：{time_cols[0]}；按{ts['granularity']}聚合",
            })

    # ---- 2. 分类排名 → B09 ----
    # 取 4 个维度：访客流水这类表的分析价值就在多维拆解，只取 2 个太单薄
    used_dims = set()
    for cat in cats[:4]:
        ser = _category_series(df, cat["col"], primary, top_n=10)
        if not ser:
            continue
        used_dims.add(cat["col"])
        # 漏斗/阶段类维度用漏斗图——柱状图看不出逐级转化
        funnel_like = cat.get("funnel", False)
        if funnel_like and ser["n_all"] <= 8:
            ctype = "funnel"
            title = f"{primary['label']}分布（按{cat['col']}）"
            desc = (f"{cat['col']}共 {ser['n_all']} 级，"
                    f"最高一级 {ser['categories'][0]}（{ser['values'][0]:,.0f}）。")
        else:
            ctype = "bar" if ser["n_all"] <= 12 else "horizontal_bar"
            title = f"{primary['label']}按{cat['col']}排名"
            desc = (f"共 {ser['n_all']} 个{cat['col']}，"
                    f"首位为 {ser['categories'][0]}（{ser['values'][0]:,.2f}）。")
        charts.append({
            "chart_type": ctype,
            "title": title,
            "block": "B09",
            "data": {"categories": ser["categories"], "values": ser["values"]},
            "description": desc,
            "note": (f"仅展示 Top{len(ser['categories'])}" if ser["truncated"] else None),
        })

    # ---- 3. 构成 → B08（可加总指标或记录数才有占比意义，均值谈占比无意义）----
    # 跳过已被排名图用掉的维度，否则会出现「漏斗图 + 同一维度环形图」的重复内容
    pie_cat = next((c for c in cats
                    if MIN_CATEGORIES <= c["unique"] <= PIE_MAX
                    and c["coverage"] >= 0.8
                    and c["col"] not in used_dims), None)
    if pie_cat and primary["agg"] in ("sum", "count"):
        ser = _category_series(df, pie_cat["col"], primary, top_n=pie_cat["unique"])
        if ser and ser["total"] > 0:
            shares = [round(100 * v / ser["total"], 1) for v in ser["values"]]
            charts.append({
                "chart_type": "pie" if pie_cat["unique"] <= 5 else "ring",
                "title": f"{primary['label']}构成（按{pie_cat['col']}）",
                "block": "B08",
                "data": {"categories": ser["categories"], "values": ser["values"]},
                "description": f"{ser['categories'][0]} 占比 {shares[0]}%，"
                               f"Top2 合计 {round(shares[0] + (shares[1] if len(shares) > 1 else 0), 1)}%。",
                "note": None,
            })

    # ---- 4. 第二个指标的趋势/对比 → B09 备选 ----
    if len(metrics) > 1:
        second = metrics[1]
        if time_cols and has_additive:
            ts2 = _time_series(df, time_cols[0], second)
            if ts2:
                charts.append({
                    "chart_type": "line",
                    "title": f"{second['label']}趋势（按{ts2['granularity']}）",
                    "block": "B07",
                    "data": {"categories": ts2["categories"], "values": ts2["values"]},
                    "description": f"{second['label']}共 {len(ts2['categories'])} 个节点。",
                    "note": f"第二个指标：{second['col']}",
                })
        elif cats:
            ser2 = _category_series(df, cats[0]["col"], second, top_n=10)
            if ser2:
                charts.append({
                    "chart_type": "bar",
                    "title": f"{second['label']}按{cats[0]['col']}对比",
                    "block": "B09",
                    "data": {"categories": ser2["categories"], "values": ser2["values"]},
                    "description": f"共 {ser2['n_all']} 个{cats[0]['col']}。",
                    "note": None,
                })

    # ---- 5. 关联散点 → B12（≥2 个真数值指标时才有意义）----
    # 计数型指标没有数值列，不能配对
    numeric = [m for m in metrics if m["col"] in df.columns]
    if len(numeric) >= 2:
        xm, ym = numeric[0], numeric[1]
        pair = df[[xm["col"], ym["col"]]].dropna()
        if len(pair) >= 5:
            if len(pair) > 80:                      # 控制点数，避免图糊成一片
                pair = pair.sample(80, random_state=42)
            charts.append({
                "chart_type": "scatter",
                "title": f"{xm['label']} 与 {ym['label']} 的关系",
                "block": "B12",
                "data": {"data": [[round(float(a), 2), round(float(b), 2)]
                                  for a, b in zip(pair[xm["col"]], pair[ym["col"]])],
                         "x_name": xm["label"], "y_name": ym["label"]},
                "description": f"{len(pair)} 个有效数据点。"
                               f"相关不等于因果，仅作分布关系参考。",
                "note": "引擎无相关性系数计算，仅呈现散点分布",
            })

    # ---- 6. 分布 → B11（数值列离散度足够时；计数型指标无分布可言）----
    dist_metric = next((m for m in numeric if df[m["col"]].nunique() >= 20), None)
    if dist_metric:
        vals = df[dist_metric["col"]].dropna()
        try:
            # retbins=True 必须带：否则 pd.cut 只返回分类序列，
            # 解包出来的两个元素不是 (counts, bins)，后续取区间左/右界必然失败。
            counts, bin_edges = pd.cut(
                vals, bins=min(10, max(4, int(vals.nunique() ** 0.5))), retbins=True)
            hist = counts.value_counts().sort_index()
            labels = [f"{iv.left:.0f}~{iv.right:.0f}" for iv in hist.index]
            charts.append({
                "chart_type": "bar",
                "title": f"{dist_metric['label']}分布",
                "block": "B11",
                "data": {"categories": labels,
                         "values": [int(v) for v in hist.tolist()]},
                "description": f"{len(vals)} 条有效记录，"
                               f"中位数 {vals.median():,.2f}。",
                "note": "引擎无直方图，以柱状图呈现分桶频数",
            })
        except Exception as e:                     # 不再静默：记录原因，便于排查
            _WARNINGS.append(
                f"{dist_metric['col']} 分布图生成失败: {type(e).__name__}: {e}")

    return charts[:max_charts]


def classify_table(df: pd.DataFrame, dims: Dict[str, List[str]],
                   contract: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    判定一张表是「事实表」还是「维表」。

    这个判定决定报表主线的取材范围：主报表的分析板块应来自事实表，
    维表只作补充（否则会出现「按职位排名平均工龄」这类与业务无关的图）。

    三类判定：
      1. 有可加总度量（金额/数量）且行数 ≥10 → 金额型事实表
      2. 无度量但行数 ≥ COUNT_MIN_ROWS        → 记录型事实表（拜访流水、工单、日志），
         分析对象就是「记录数」
      3. 其余（只有价格/比率/额度类字段、行数少）→ 维表
    """
    metrics, _ = _usable_metrics(df, dims, contract)
    additive = [m["col"] for m in metrics if m["agg"] == "sum"]
    n = len(df)
    if additive and n >= 10:
        return {"role": "fact", "row_count": n, "additive_metrics": additive,
                "measure": "amount",
                "reason": f"含可加总度量 {additive}，共 {n} 行记录"}
    if n >= COUNT_MIN_ROWS:
        return {"role": "fact", "row_count": n, "additive_metrics": [],
                "measure": "count",
                "reason": f"无金额类度量，但 {n} 行记录构成流水，以「记录数」为分析指标"}
    if additive and n >= MIN_TABLE_ROWS:
        # 小样本但有可加总度量：仍可做简报，只是不能做统计推断
        return {"role": "fact", "row_count": n, "additive_metrics": additive,
                "measure": "amount", "small_sample": True,
                "reason": f"仅 {n} 行，含可加总度量 {additive}；"
                          f"可做描述性简报，不适合统计推断"}
    # 小样本 + 只有均值型度量 → 是「清单/维表」，不是流水。
    # （产品信息表 12 行、价格表这类：有价格但无发生额，不能当事实表）
    return {"role": "dimension", "row_count": n, "additive_metrics": [],
            "measure": "none",
            "reason": (f"行数 {n} 过少（< {MIN_TABLE_ROWS}），不足以分析"
                       if n < MIN_TABLE_ROWS
                       else f"仅 {n} 行且无可加总度量，视为清单/维表")}


def data_issues(df: pd.DataFrame, dims: Dict[str, List[str]],
                quality: Dict[str, Any] = None,
                contract: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    产出数据质量议题清单（供 B19 数据质量说明板块与选型判定使用）。

    每条含 type / column / detail / suggestion，都是**可执行**的提示，
    不是笼统的「数据有缺失」。

    传入契约时额外报三类**语义级**议题（这些靠统计发现不了）：
      - 未判定列：契约里 role=unknown，不会参与分析，必须让读者知道
      - 标识列当维度用：契约判为 identifier 却在 dims 里出现（配置不一致）
      - 重复列：内容完全相同的列，容易在报表里被算两遍
    """
    issues: List[Dict[str, Any]] = []
    n = len(df)
    for col in df.columns:
        s = df[col]
        null_rate = float(s.isna().mean())
        if null_rate >= 0.999:
            issues.append({"type": "全空列", "column": col,
                           "detail": f"{n}/{n} 行全为空",
                           "suggestion": "该列无法参与任何计算，建议从报表口径中移除或在源头补录"})
        elif null_rate > MAX_NULL_RATE:
            issues.append({"type": "高缺失列", "column": col,
                           "detail": f"缺失 {int(s.isna().sum())}/{n} 行（{null_rate:.1%}）",
                           "suggestion": "直接求合计会严重低估，需补全或改用可推导口径（如数量×单价）"})

    # 疑似明细 ID
    for col in dims.get("分类", []):
        if col in df.columns:
            u = int(df[col].dropna().nunique())
            if u >= max(3, int(n * 0.9)):
                issues.append({"type": "疑似明细ID", "column": col,
                               "detail": f"{u} 个唯一值 / {n} 行",
                               "suggestion": "不宜作为分类维度出图（会产生大量扇区/长尾），仅用于计数"})

    # 常数列
    for col in df.columns:
        if df[col].dropna().nunique() == 1:
            issues.append({"type": "常数列", "column": col,
                           "detail": "全部取值相同",
                           "suggestion": "无分析价值，不应出现在图表中"})

    # ---- 契约带来的语义级议题 ----
    if contract and contract.get("columns"):
        for col in contract.get("unresolved", []):
            issues.append({"type": "角色未判定", "column": col,
                           "detail": "数据契约中该列 role=unknown",
                           "suggestion": "该列未参与任何分析。"
                                         "若它重要，需在契约里显式指定角色后重跑"})
        for pair in contract.get("duplicate_columns", []):
            if len(pair) == 2:
                issues.append({"type": "内容重复列", "column": f"{pair[0]} / {pair[1]}",
                               "detail": "两列取值完全相同",
                               "suggestion": f"只保留 {pair[0]}，避免同一信息被算两遍"})
        ident = set(contract.get("views", {}).get("identifier", []))
        misused = [c for c in dims.get("分类", []) if c in ident]
        if misused:
            issues.append({"type": "标识列被当维度", "column": "、".join(misused),
                           "detail": "契约判为 identifier，却出现在分类维度中",
                           "suggestion": "检查契约与 dims 是否一致，标识列只应参与计数"})
    return issues
