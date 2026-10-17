# -*- coding: utf-8 -*-
"""
conspect 数据契约层（Schema Contract，v5.0）

作用：把「每列是什么角色」这个判断**固化一次**，之后全链路只读契约。

为什么需要契约：
  判断散落会漂移。同一个「这列是不是指标」，早期在 identify_dimensions 按 dtype 判、
  在 chart_advisor 按关键词黑名单再拦一次、在 ai_agent 又过滤一次——三处不一致时，
  下游拿到的结论互相矛盾，且每遇到新行业都要三处一起改。

  有了契约，判定只发生一次（探测 + AI），结果落盘成 `_cs-schema.json`，
  计算层（聚合、图表、统计）全部按契约执行。改判定只改契约，不动代码。

角色定义（role）：

| role | 含义 | 可做什么 |
|------|------|---------|
| `time` | 时间轴 | 趋势、时间序列聚合 |
| `dimension` | 分组维度 | 分类聚合、排名、构成 |
| `measure` | 度量 | 求和/均值等聚合（受 additivity 约束） |
| `identifier` | 标识/明细ID | **只能计数**，不得求和、不得当分类维度出图 |
| `text` | 自由文本 | 不参与数值分析（可做人读展示） |
| `ignore` | 全空/常量 | 完全不参与 |
| `unknown` | 未能判定 | 不参与分析，但必须在报表中明示 |

可加总性（additivity，仅对 measure 有意义）：

| 值 | 含义 | 例 |
|----|------|-----|
| `additive` | 求和有意义 | 销售数量、销售额、订单数 |
| `average` | 求和无意义 | 单价、毛利率、折扣率、单位成本 |
| `none` | 非度量 | 其他角色一律为 none |
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import schema_probe

CONTRACT_VERSION = "5.0"
DEFAULT_FILENAME = "_cs-schema.json"

ROLES = schema_probe.ROLES
#: 契约里允许的最终取值。「hint」是探测层的「未定」标记，不写进契约；
#: 探测给 hint 时，契约落为 average 并标记 additivity_confirmed=false。
ADDITIVITIES = ("additive", "average", "none")

#: role → 下游「时间/分类/数值」三分类的映射（兼容既有计算链路）
ROLE_TO_DIM_KIND = {
    "time": "时间",
    "dimension": "分类",
    "measure": "数值",
}


# ============================================================================
# 从探测结果生成契约
# ============================================================================

def build(probe: Dict[str, Any],
          overrides: Optional[Dict[str, Dict[str, Any]]] = None,
          source: Optional[Dict[str, Any]] = None,
          decided_by: str = "heuristic") -> Dict[str, Any]:
    """
    由探测结果生成契约。

    参数:
        probe: schema_probe.judge_frame() 的返回
        overrides: AI 或人工的终判，形如
                   {"客户名称": {"role": "dimension", "additivity": "none",
                                "reason": "客户名称用于分组，不算标识"}}
                   只需给 role / additivity / reason，其余字段从探测结果继承
        source: 数据源信息（文件、Sheet、行列数）
        decided_by: "heuristic"（纯统计）/ "ai"（AI 终判）/ "mixed"（部分人工）

    返回:
        契约 dict，可直接写盘
    """
    overrides = overrides or {}
    columns: Dict[str, Dict[str, Any]] = {}

    for c in probe["columns"]:
        name = c["column"]
        role = c["role"]
        add = c["additivity"]
        conf = c["confidence"]
        reason = c["reason"]
        decided = "heuristic"
        # additivity 是否已确认：探测给 hint 表示"统计判不出来"，
        # 此时落为 average（安全侧）并明确标记未确认，让报表口径能如实声明。
        add_confirmed = add in ADDITIVITIES

        ov = overrides.get(name)
        if ov:
            new_role = ov.get("role", role)
            if new_role not in ROLES:
                raise ValueError(f"{name}: 非法 role 「{new_role}」，"
                                 f"可选 {ROLES}")
            if new_role != role:
                reason = ov.get("reason") or f"终判覆盖：{role} → {new_role}"
            role = new_role
            ov_add = ov.get("additivity")
            if ov_add:
                if ov_add not in ADDITIVITIES:
                    raise ValueError(f"{name}: 非法 additivity 「{ov_add}」，"
                                     f"可选 {ADDITIVITIES}")
                add = ov_add
                add_confirmed = True
            elif role == "measure":
                add = schema_probe.suggest_additivity(c, role)
                add_confirmed = add in ADDITIVITIES
            else:
                add = "none"
                add_confirmed = True
            conf = ov.get("confidence", "high")
            decided = "override"

        if role != "measure":
            add = "none"
            add_confirmed = True
        elif add not in ADDITIVITIES:
            # 探测给的是 hint：按均值处理（安全侧：宁可少算总额，
            # 也不要把"单价"加起来得出荒谬的天文数字）
            add = "average"
            add_confirmed = False

        columns[name] = {
            "role": role,
            "additivity": add,
            "additivity_confirmed": add_confirmed,
            "confidence": conf,
            "evidence": c["evidence"],
            "reason": reason,
            "decided_by": decided,
            # 保留关键统计事实，便于事后复核判定是否合理
            "profile": {
                "dtype": c["dtype"],
                "n": c["n"],
                "null_rate": c["null_rate"],
                "unique": c["unique"],
                "unique_ratio": c["unique_ratio"],
                "samples": c["samples"],
            },
        }
        if "date_rate" in c:
            columns[name]["profile"]["date_rate"] = c["date_rate"]
        if "avg_len" in c:
            columns[name]["profile"]["avg_len"] = c["avg_len"]

    unresolved = [k for k, v in columns.items() if v["role"] == "unknown"]
    if unresolved and decided_by == "ai":
        decided_by = "mixed" if len(unresolved) < len(columns) else "ai"

    return {
        "contract_version": CONTRACT_VERSION,
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "source": source or {},
        "decided_by": decided_by,
        "probe_summary": probe["summary"],
        "unresolved": unresolved,
        "duplicate_columns": probe.get("duplicate_columns", []),
        "columns": columns,
        # 便捷视图：下游直接取用
        "views": {
            "time": [k for k, v in columns.items() if v["role"] == "time"],
            "dimension": [k for k, v in columns.items() if v["role"] == "dimension"],
            "measure": [k for k, v in columns.items() if v["role"] == "measure"],
            "additive": [k for k, v in columns.items() if v["additivity"] == "additive"],
            "average": [k for k, v in columns.items() if v["additivity"] == "average"],
            "identifier": [k for k, v in columns.items() if v["role"] == "identifier"],
            "text": [k for k, v in columns.items() if v["role"] == "text"],
            "ignore": [k for k, v in columns.items() if v["role"] == "ignore"],
            "unknown": unresolved,
            # 可加总性未确认的度量：报表口径必须声明「按均值处理」
            "unconfirmed_additivity": [k for k, v in columns.items()
                                       if v["role"] == "measure"
                                       and not v.get("additivity_confirmed", True)],
        },
    }


# ============================================================================
# 读写与校验
# ============================================================================

def save(contract: Dict[str, Any], path: str) -> str:
    """把契约写到文件（UTF-8、带缩进便于人工审阅）。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(p)


def load(path: str) -> Dict[str, Any]:
    """读取契约并与实际列做一致性校验。"""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"契约文件不存在：{path}")
    data = json.loads(p.read_text(encoding="utf-8"))
    ver = data.get("contract_version")
    if not ver:
        raise ValueError(f"{path} 不是有效的 conspect 契约（缺 contract_version）")
    return data


def validate(contract: Dict[str, Any], columns: List[str]) -> Dict[str, Any]:
    """
    校验契约与真实数据是否匹配。

    返回 {ok, missing_in_contract, missing_in_data, unknown_role, warnings}
      missing_in_contract: 数据里有、契约没登记 → 这些列会被当 unknown 处理
      missing_in_data:     契约登记了、数据里没有 → 多半是换了一版数据
    """
    ccols = set(contract.get("columns", {}))
    dcols = set(map(str, columns))
    bad_role = [k for k, v in contract.get("columns", {}).items()
                if v.get("role") not in ROLES]
    warnings = []
    if contract.get("unresolved"):
        warnings.append(f"契约中有 {len(contract['unresolved'])} 列未判定角色："
                        f"{contract['unresolved']}，这些列不会参与分析")
    if contract.get("decided_by") == "heuristic":
        warnings.append("契约由统计启发式生成，未经 AI 复核；"
                        "大基数分类列（如名称类）可能被判错")
    return {
        "ok": not (dcols - ccols) and not (ccols - dcols) and not bad_role,
        "missing_in_contract": sorted(dcols - ccols),
        "missing_in_data": sorted(ccols - dcols),
        "unknown_role": bad_role,
        "warnings": warnings,
    }


# ============================================================================
# 下游消费接口
# ============================================================================

def to_dimensions(contract: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    把契约翻译成既有的「时间/分类/数值」三分类。

    保持向后兼容：计算链路一直按这三类取值，换成契约后语义更准
    （identifier 不再混进分类、text 不参与、unknown 明确排除）。
    """
    out: Dict[str, List[str]] = {"时间": [], "分类": [], "数值": []}
    for name, meta in contract.get("columns", {}).items():
        kind = ROLE_TO_DIM_KIND.get(meta.get("role"))
        if kind:
            out[kind].append(name)
    return out


def measure_agg(contract: Dict[str, Any], column: str) -> str:
    """
    该度量列应使用哪种聚合：sum / mean。

    additivity=average → mean；additive → sum；
    未标明的度量按 mean 处理（保守：宁可少算总额，也不要输出荒谬的巨额合计）。
    """
    meta = contract.get("columns", {}).get(column, {})
    if meta.get("role") != "measure":
        return "count"
    return "mean" if meta.get("additivity") == "average" else "sum"


def summary_lines(contract: Dict[str, Any]) -> List[str]:
    """生成人读摘要，供报告与日志使用。"""
    v = contract.get("views", {})
    s = contract.get("probe_summary", {})
    lines = [
        f"数据契约 {contract.get('contract_version')}｜判定来源 {contract.get('decided_by')}",
        f"共 {s.get('total', 0)} 列：时间 {len(v.get('time', []))}、"
        f"维度 {len(v.get('dimension', []))}、度量 {len(v.get('measure', []))}"
        f"（可加总 {len(v.get('additive', []))} / 均值 {len(v.get('average', []))}）、"
        f"标识 {len(v.get('identifier', []))}、文本 {len(v.get('text', []))}、"
        f"忽略 {len(v.get('ignore', []))}、未定 {len(v.get('unknown', []))}",
    ]
    if v.get("additive"):
        lines.append("可加总度量：" + "、".join(v["additive"]))
    if v.get("average"):
        lines.append("仅可取均值的度量：" + "、".join(v["average"]))
    if v.get("identifier"):
        lines.append("标识列（只计数，不出图）：" + "、".join(v["identifier"]))
    if v.get("unknown"):
        lines.append("未判定列（不参与分析）：" + "、".join(v["unknown"]))
    if v.get("unconfirmed_additivity"):
        lines.append("可加总性未确认的度量（已按均值处理，报表需声明）："
                     + "、".join(v["unconfirmed_additivity"]))
    if contract.get("duplicate_columns"):
        pairs = "；".join(f"{a} = {b}" for a, b in contract["duplicate_columns"])
        lines.append("内容重复列：" + pairs)
    return lines
