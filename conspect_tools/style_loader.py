# -*- coding: utf-8 -*-
"""
conspect 风格资产加载器（v4.0）

唯一职责：读取 `assets/style-system.json`，把它翻译成渲染引擎可消费的主题字典。
渲染引擎不再持有任何硬编码配色——**风格全部来自资产层**。

对外接口：
    families()          全部族
    styles()            全部风格
    get_style(code)     单个风格（含 tokens / components / report_use / taboos）
    get_family(fid)     单个族
    codes()             全部风格编号
    series_for(code)    该风格的 6 色图表序列（首位 = 强调色）
    theme(code)         渲染引擎用的主题字典（旧字段名保持兼容）
    default_code()      默认风格编号
    block_library()     板块库元信息
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional

SKILL_DIR = Path(__file__).resolve().parent.parent
STYLE_JSON = SKILL_DIR / "assets" / "style-system.json"

DEFAULT_CODE = "A12"

# 资产文件缺失时的兜底主题。仅保证「渲染不崩」，不保证风格正确；
# 一旦启用，调用方必须向用户明示已降级。
_FALLBACK = {
    "version": "fallback",
    "families": [{
        "id": "biz", "label": "商务通稿", "en": "BIZ REPORT", "tone": "浅色",
        "scene": "降级兜底", "series": ["#2B4C8C", "#4A7CF7", "#6FC3A0",
                                       "#F5A623", "#E86868", "#8B6CD6"],
        "styles": [DEFAULT_CODE], "count": 1,
    }],
    "styles": [{
        "code": DEFAULT_CODE, "label": "扁平无影", "en": "FLAT DESIGN",
        "class": "flat", "family": "biz", "tone": "浅色",
        "tokens": {"bg": "#FFFFFF", "card": "#FFFFFF", "ink": "#111111",
                   "mu": "#8A8A8A", "ac": "#3497DB", "line": "#E2E2E2",
                   "bg_gradient": None},
        "typography": {}, "shapes": {}, "shape_extra": [],
        "school": "扁平化设计", "keywords": ["扁平", "纯色", "无阴影"],
        "mood": "干净利落，一目了然",
        "components": {}, "report_use": {"types": [], "blocks": [],
                                         "density": "中", "media": "投影/打印"},
        "taboos": [], "body": None,
    }],
    "block_library": {"path": "assets/common/block_library.md", "count": 22,
                      "families": ["open", "metric", "analysis", "conclusion",
                                   "meta", "close"]},
    "total_styles": 1, "family_count": 1,
}

_DENSITY = {
    "高": {"gap": 16, "pad": 18},
    "中": {"gap": 20, "pad": 24},
    "低": {"gap": 30, "pad": 30},
}

_cache: Optional[Dict] = None
_degraded = False


def _degenerate_gradient(g: Optional[str]) -> bool:
    """
    渐变是否退化为单色（所有色标相同）。

    `linear-gradient(#2C3E50,#2C3E50)` 视觉上就是一块实色，不是渐变。
    资产里出现过这种值（A12 的 bg 是 #FFFFFF，渐变却是深灰蓝实色，自相矛盾），
    生成脚本按「有渐变就写进文档」处理，会把它当成真渐变渲染成深底。
    在加载层统一归一为 None：一处修好，所有消费者（预览/文档/未来的渲染）都受益，
    也不怕资产被重新生成时再带回来。
    """
    if not g or "gradient" not in g:
        return False
    stops = re.findall(r"#[0-9a-fA-F]{3,8}\b", g)
    return len(stops) >= 2 and len({s.lower() for s in stops}) == 1


def _data() -> Dict:
    global _cache, _degraded
    if _cache is not None:
        return _cache
    try:
        _cache = json.loads(STYLE_JSON.read_text(encoding="utf-8"))
        _degraded = False
        for s in _cache.get("styles", []):
            toks = s.get("tokens") or {}
            if _degenerate_gradient(toks.get("bg_gradient")):
                toks["bg_gradient"] = None
    except Exception:
        _cache = _FALLBACK
        _degraded = True
    return _cache


def is_degraded() -> bool:
    """是否因资产文件缺失而降级到内置兜底。"""
    _data()
    return _degraded


def asset_path() -> Path:
    return STYLE_JSON


def families() -> List[dict]:
    return list(_data().get("families", []))


def styles() -> List[dict]:
    return list(_data().get("styles", []))


def codes() -> List[str]:
    return [s["code"] for s in styles()]


def get_style(code: str) -> Optional[dict]:
    for s in styles():
        if s["code"] == code:
            return s
    return None


def get_family(fid: str) -> Optional[dict]:
    for f in families():
        if f["id"] == fid:
            return f
    return None


def resolve(code: Optional[str]) -> dict:
    """取风格；编号无效时回退默认风格，并保持 silent（调用方可用 is_degraded 判断）。"""
    return get_style(code or "") or get_style(DEFAULT_CODE) or _FALLBACK["styles"][0]


def series_for(code: str) -> List[str]:
    """该风格的 6 色图表序列；首位替换为风格强调色。"""
    s = resolve(code)
    fam = get_family(s["family"])
    series = list(fam["series"]) if fam else list(_FALLBACK["families"][0]["series"])
    if series:
        series[0] = s["tokens"]["ac"]
    return series


def default_code() -> str:
    return DEFAULT_CODE if get_style(DEFAULT_CODE) else (codes() or [DEFAULT_CODE])[0]


def block_library() -> dict:
    return dict(_data().get("block_library", {}))


def theme(code: Optional[str] = None) -> Dict:
    """把风格资产翻译成渲染引擎的主题字典。旧字段名（primary/secondary/bg/…）保持兼容。"""
    s = resolve(code)
    t = s["tokens"]
    series = series_for(s["code"])
    density = (s.get("report_use") or {}).get("density", "中")
    spacing = _DENSITY.get(density, _DENSITY["中"])

    primary = [t["ac"]] + [c for c in series[1:3]]
    secondary = list(series[3:6])
    return {
        # 新字段
        "name": s["code"],
        "label": s.get("label", ""),
        "family": s.get("family", ""),
        "tone": s.get("tone", ""),
        "density": density,
        "series": series,
        "ac": t["ac"], "card": t["card"], "ink": t["ink"],
        "mu": t["mu"], "line": t["line"],
        "bg_gradient": t.get("bg_gradient"),
        "gap": spacing["gap"], "pad": spacing["pad"],
        # 兼容字段（渲染引擎模板沿用）
        "primary": primary,
        "secondary": secondary,
        "bg": t["bg"],
        "card_bg": t["card"],
        "text": t["ink"],
        "text_secondary": t["mu"],
        "border": t["line"],
        "gradient": [t["ac"], series[1] if len(series) > 1 else t["ac"]],
    }


def summary() -> Dict:
    d = _data()
    return {
        "total_styles": d.get("total_styles", len(d.get("styles", []))),
        "family_count": d.get("family_count", len(d.get("families", []))),
        "degraded": is_degraded(),
        "asset": str(STYLE_JSON),
    }
