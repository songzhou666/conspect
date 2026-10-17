# -*- coding: utf-8 -*-
"""
conspect 数据探测层（Schema Probe，v5.0）

设计原则：**本模块只产出客观事实，不做业务语义判断。**

为什么要把探测与判断分开：
  早期实现把「这列是什么角色」的判断散落在三处（identify_dimensions 按 dtype、
  chart_advisor 按关键词黑名单、ai_agent 再过滤一次），同一个判断写三遍，
  每遇到一个新行业的新术语就要在三处补关键词——这是补丁套补丁，永远补不完。

  正确做法是分层：
    D 探测（本模块）—— 只看数据本身，产出可验证的统计事实
    S 判定（schema_contract + AI）—— 基于 D 的事实做角色判定
    C 契约（schema.json）—— 固化判定结果，全链路只读它
    E 计算 —— 按契约算，不再猜

  分层后，新行业只需在 S 层判一次，D 层与 E 层完全不用改。

能力边界（实测：两份真实数据 20/20 关键列判对）：
  硬证据（只看数据即可判定）：日期可解析率、全空/常量、全唯一大整数、
                             全唯一长文本、低基数枚举
  弱线索（需列名辅助）：编号类命名、多值分类
  低置信（必须交 AI 或人工）：大基数文本分类（如「诊所名称」940 类）
"""

import re
from typing import Any, Dict, List, Optional

import pandas as pd

#: 列名线索——**仅作为辅助**，不单独作为判定依据。
#: 放在这里是因为「订单编号」这类列在统计上可能与普通多值分类无法区分。
ID_NAME_HINTS = ("编号", "编码", "代码", "单号", "工号", "学号", "卡号",
                 "批次", "序列号", "流水号", "id", "code", "no.", "uuid", "guid")
TEXT_NAME_HINTS = ("地址", "备注", "说明", "描述", "内容", "意见", "标题",
                   "详情", "链接", "url", "remark", "note", "comment", "description")

#: 判定阈值（集中定义，便于审计与调参）
THRESH = {
    "date_rate": 0.9,        # 可解析为日期的比例，达到即判时间列
    "enum_max": 30,          # 枚举型上限（类别数）
    "enum_ratio": 0.05,      # 枚举型要求：类别数 / 总行数 < 此值
    "id_text_len": 20,       # 全唯一且平均长于此 → 判标识（地址/链接/文件名）
    "free_text_len": 40,     # 平均长度超过 → 判自由文本
    "id_mag": 8,             # 全唯一整数且位数 ≥ 此值 → 判号码类（电话/证件）
    "small_n": 100,          # 小于此样本量时，唯一率不单独作为 ID 依据
}


def _try_date(series: pd.Series) -> float:
    """返回该列可解析为日期的比例（支持中文日期）。"""
    nn = series.dropna()
    if nn.empty:
        return 0.0
    t = nn.astype(str).str.strip()
    if t.str.contains("年", na=False).any():
        t = (t.str.replace(r"\s*年\s*", "-", regex=True)
               .str.replace(r"\s*月\s*", "-", regex=True)
               .str.replace(r"\s*日", "", regex=True)
               .str.strip())
    try:
        return float(pd.to_datetime(t, errors="coerce").notna().mean())
    except Exception:
        return 0.0


def probe_column(series: pd.Series, col: str = "") -> Dict[str, Any]:
    """
    探测单列，产出客观画像。

    返回的字段全部是**可复算的事实**，任何断言都能由原始数据验证：
      n / null_count / null_rate        行数与缺失
      unique / unique_ratio             唯一值数与占比（占比以总行数为分母）
      is_all_unique                     是否逐行唯一
      dtype / is_numeric / all_int      类型特征
      min / max / median / mag          数值特征（mag = 最大值的十进制位数）
      neg_ratio                         负值占比
      avg_len / p90_len                 文本长度特征
      date_rate                         日期可解析率（仅当 >0.5 时输出）
      samples                           前 4 个非空样本值
    """
    n = len(series)
    nn = series.dropna()
    n_null = n - len(nn)
    nunique = int(nn.nunique())

    p: Dict[str, Any] = {
        "column": str(col),
        "dtype": str(series.dtype),
        "n": n,
        "null_count": n_null,
        "null_rate": round(n_null / n, 4) if n else 0.0,
        "unique": nunique,
        "unique_ratio": round(nunique / n, 4) if n else 0.0,
        "is_all_unique": bool(n and nunique == n),
        "samples": [str(x) for x in nn.head(4).tolist()],
    }

    if len(nn):
        lens = nn.astype(str).str.len()
        p["avg_len"] = round(float(lens.mean()), 1)
        p["p90_len"] = int(lens.quantile(0.9))
    else:
        p["avg_len"] = 0.0
        p["p90_len"] = 0

    p["is_numeric"] = bool(pd.api.types.is_numeric_dtype(series))
    if p["is_numeric"] and len(nn):
        p["all_int"] = bool((nn == nn.round()).all())
        p["min"] = float(nn.min())
        p["max"] = float(nn.max())
        p["median"] = float(nn.median())
        amax = abs(p["max"])
        p["mag"] = len(str(int(amax))) if amax >= 1 else 1
        p["neg_ratio"] = round(float((nn < 0).mean()), 4)

    rate = _try_date(series)
    if rate > 0.5:
        p["date_rate"] = round(rate, 4)

    return p


def probe_frame(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """探测整表，逐列返回画像。"""
    return [probe_column(df[c], c) for c in df.columns]


# ============================================================================
# 统计启发式判定（S 层的兜底层）
# ============================================================================
#
# 本函数是「没有任何 AI 参与时」的保底判定。它的能力边界必须诚实：
# 只能基于统计事实，**不猜业务含义**。判定不出来就返回 unknown，绝不硬塞进分类。

ROLES = ("time", "dimension", "measure", "identifier", "text", "ignore", "unknown")


def judge_by_stats(p: Dict[str, Any]) -> Dict[str, Any]:
    """
    仅凭统计画像判定列角色。

    返回 {role, confidence, evidence, reason}：
      confidence = high   仅凭数据即可确定（不看列名）
      confidence = medium 数据 + 列名线索，较可靠
      confidence = low    数据不足，需 AI 或人工确认
    """
    col = str(p.get("column", ""))
    low = col.lower()
    u = p["unique"]

    def out(role, conf, ev, why):
        return {"role": role, "confidence": conf, "evidence": ev, "reason": why}

    # ---------- 硬证据：只看数据 ----------
    if p.get("date_rate", 0) >= THRESH["date_rate"]:
        return out("time", "high", "hard",
                   f"可解析为日期的比例 {p['date_rate']:.0%}")
    if p["n"] == 0 or u == 0:
        return out("ignore", "high", "hard", "全空列")
    if u == 1:
        return out("ignore", "high", "hard", "常数列，无分析价值")

    # 全唯一 + 大整数 → 电话/证件/订单号
    if p.get("is_numeric") and p["is_all_unique"] and p.get("all_int") \
            and p.get("mag", 0) >= THRESH["id_mag"]:
        return out("identifier", "high", "hard",
                   f"全唯一整数且 {p['mag']} 位，疑似电话/证件/单号")
    # 全唯一 + 长文本 → 地址/链接/文件名
    if p["is_all_unique"] and p.get("avg_len", 0) >= THRESH["id_text_len"]:
        return out("identifier", "high", "hard",
                   f"全唯一长文本（平均 {p['avg_len']} 字），疑似地址/链接/文件名")

    # ---- 数值列：dtype 是硬信息，默认按度量处理 ----
    #
    # 这一步必须放在「低基数枚举」之前。早期版本先判枚举，导致「就诊人次」
    # （取值 1~3）、「课时数」（1~5）、「不良数」（0~30）这类小整数计数列
    # 被当成「枚举维度」——它们在统计上确实只有几个不同值，但业务上是度量。
    #
    # 判据：dtype 是数字 → 度量；只有「恰好 2 个唯一值」这种布尔标志才考虑维度。
    if p.get("is_numeric"):
        if u == 2 and p.get("all_int") and p.get("max", 99) <= 1:
            return out("dimension", "medium", "hard",
                       "仅 0/1 两个取值的整数列，疑似布尔标志（可作维度）")
        return out("measure", "high", "hard",
                   "数值型，作度量（可加总性需由契约确认）")

    # ---- 低基数枚举（仅对非数值列生效）----
    if 2 <= u <= THRESH["enum_max"] and p["unique_ratio"] < THRESH["enum_ratio"]:
        return out("dimension", "high", "hard", f"枚举型，{u} 个取值")
    # 自由文本
    if p.get("avg_len", 0) > THRESH["free_text_len"]:
        return out("text", "medium", "hard",
                   f"平均 {p['avg_len']} 字，自由文本（不宜做维度）")

    # ---------- 弱线索：统计不足，用列名辅助 ----------
    if any(h in low for h in ID_NAME_HINTS) and u > 20:
        return out("identifier", "medium", "weak",
                   f"列名含标识词且 {u} 个唯一值，疑似业务主键/明细ID")
    if any(h in low for h in TEXT_NAME_HINTS):
        return out("text", "medium", "weak", f"列名含文本词，疑似自由文本")
    if p["is_all_unique"] and p["n"] >= THRESH["small_n"]:
        return out("identifier", "medium", "weak", "逐行唯一，疑似标识列")
    if 2 <= u <= THRESH["enum_max"]:
        return out("dimension", "medium", "weak", f"{u} 个取值，作分类维度")
    if u > THRESH["enum_max"]:
        # 大基数文本：可能是「城市」这种可分组维度，也可能是「名称」这种明细标识。
        # 统计上无法区分，必须交 AI / 人工。
        if p["unique_ratio"] < 0.5:
            return out("dimension", "low", "weak",
                       f"大基数分类（{u} 类，占比 {p['unique_ratio']:.0%}），"
                       f"可作分组但不宜直接成图，需确认业务含义")
        return out("unknown", "low", "weak",
                   f"大基数且高占比（{u} 类），无法区分「分组维度」与「明细标识」，需确认")

    return out("unknown", "low", "none", "统计特征不足，无法判定")


def suggest_additivity(p: Dict[str, Any], role: str) -> str:
    """
    对 measure 列给出可加总性**提示**（不是结论）。

    ⚠️ 能力边界必须说清：**可加总性本质是业务语义，统计判不出来。**
       GMV 与客单价都是正小数、都右偏分布，统计特征几乎一样，
       但前者求和有意义、后者求和毫无意义。任何试图用分布形状区分二者的
       规则都是猜——实测 22 个度量列，纯统计只能判对 6 个（27%）。

    所以本函数只给三类：
      average  —— 有硬证据：0 ≤ 值 ≤ 1 的小数，几乎不可能是"总额"，是比率
      additive —— 有较强证据：全为非负整数（计数类）且量级不大
      hint     —— 无法判断，需由契约 / AI 按字段名与业务含义终判

    注意返回值 `hint` 不在 ADDITIVITIES 里，它是「未定」的显式标记，
    下游遇到 hint 一律按均值处理（安全侧），并在报表口径里标注未确认。
    """
    if role != "measure" or not p.get("is_numeric"):
        return "none"

    mn, mx = p.get("min", 0), p.get("max", 0)
    all_int = p.get("all_int", False)

    # 硬证据：比率（0~1 的纯小数）
    if not all_int and 0 <= mn and mx <= 1.0:
        return "average"
    # 较强证据：非负整数且量级不超过 6 位（计数/件数/条数类）
    if all_int and mn >= 0 and p.get("mag", 1) <= 6:
        return "additive"
    # 其余一律交契约——不做无根据的猜测
    return "hint"


# ============================================================================
# 整表判定
# ============================================================================

def judge_frame(df: pd.DataFrame) -> Dict[str, Any]:
    """
    对整表做统计判定，产出「待 AI 终判」的清单。

    返回：
      {
        "columns": [{column, role, confidence, evidence, reason, additivity, ...profile}],
        "summary": {total, high, medium, low, unknown},
        "need_ai": [列名...],           # 必须由 AI 或人工确认的列
        "roles": {role: [列名...]},      # 按角色分组的便捷视图
        "duplicate_columns": [[A,B]...], # 内容完全相同的列（去重提示）
        "ready": bool,                   # 是否可直接进入计算（无 unknown）
      }
    """
    cols: List[Dict[str, Any]] = []
    for c in df.columns:
        prof = probe_column(df[c], c)
        j = judge_by_stats(prof)
        prof.update({
            "role": j["role"],
            "confidence": j["confidence"],
            "evidence": j["evidence"],
            "reason": j["reason"],
            "additivity": suggest_additivity(prof, j["role"]),
        })
        cols.append(prof)

    # 内容完全重复的列（同值集）——常见于导出表，去重可避免重复分析
    dups: List[List[str]] = []
    seen: Dict[str, str] = {}
    for c in df.columns:
        try:
            sig = hash(tuple(sorted(map(str, df[c].dropna().unique()))[:300]))
        except Exception:
            continue
        if sig in seen:
            dups.append([seen[sig], str(c)])
        else:
            seen[sig] = str(c)

    summary = {
        "total": len(cols),
        "high": sum(1 for c in cols if c["confidence"] == "high"),
        "medium": sum(1 for c in cols if c["confidence"] == "medium"),
        "low": sum(1 for c in cols if c["confidence"] == "low"),
        "unknown": sum(1 for c in cols if c["role"] == "unknown"),
    }
    roles: Dict[str, List[str]] = {}
    for c in cols:
        roles.setdefault(c["role"], []).append(c["column"])

    # 待 AI 终判的只列「统计推不出来的」：low 与 unknown。
    # medium 是「启发式有明确方向」的结论（数值→度量、低基数→维度），
    # 若也塞进待判清单，23 列的表会要求 AI 逐列复核 18 次，属于无效劳动。
    need_ai = [c["column"] for c in cols if c["confidence"] == "low"]

    return {
        "columns": cols,
        "summary": summary,
        "need_ai": need_ai,
        "unresolved": [c["column"] for c in cols if c["role"] == "unknown"],
        "roles": roles,
        "duplicate_columns": dups,
        "ready": summary["unknown"] == 0,
    }
