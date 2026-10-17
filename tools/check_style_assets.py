#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
conspect 资产校验器（v4.0）

校验四类不变量：
  A. 源结构   —— style-system.json 的风格数/族数/双向引用/token 齐全
  B. 取值合法 —— hex 合法性、ink/bg 对比度 ≥4.5、series 长度 6、密度枚举
  C. 生成物   —— L0/L1/L2 全部存在，且**重新生成后与磁盘一致**（防手改漂移）
  D. 板块库   —— md 的板块编号集合与代码的触发实现完全一致

运行：python tools/check_style_assets.py [--quiet]
退出码：0 全通过；1 有失败项
"""

import colorsys
import importlib.util
import json
import re
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
ASSETS = SKILL / "assets"
SRC = ASSETS / "style-system.json"
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

BODY_SECTIONS = (
    "## 设计流派",
    "## 配色 Token",
    "## 字体与排版",
    "## 形状与特效",
    "## 组件样式特征",
    "## 图表配色序列",
    "## 报表版式建议",
    "## 数据展示禁忌",
)


class Report:
    def __init__(self):
        self.ok = 0
        self.fail = []
        self.warn = []

    def passed(self, n=1):
        self.ok += n

    def failed(self, msg):
        self.fail.append(msg)

    def warned(self, msg):
        self.warn.append(msg)


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _lum(h):
    def f(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(h[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a, b):
    l1, l2 = _lum(a), _lum(b)
    if l1 < l2:
        l1, l2 = l2, l1
    return round((l1 + 0.05) / (l2 + 0.05), 2)


def _hsl(h):
    """hex → (色相 0-360, 饱和度 0-1, 明度 0-100)。"""
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    hh, l, s = colorsys.rgb_to_hls(r, g, b)
    return hh * 360, s, l * 100


#: 序列色可区分判据的阈值
HUE_MIN = 20.0     # 色相差达到此值即视为可区分
LUM_MIN = 22.0     # 色相接近时，要求的最小明度差
GRAY_S = 0.15      # 饱和度低于此值视为无彩色（灰阶）
GRAY_LUM_MIN = 20.0  # 两个灰阶之间的最小明度差


def series_clash(a, b):
    """
    判断两个序列色在图表中是否**无法区分**。

    判据（按视觉可分性设计，不是简单比色相）：
      - 两者都是灰阶 → 只看明度差（灰阶色彩无意义）
      - 一灰一彩     → 饱和度已提供区分度，判为可区分
      - 都是彩色：
          * 色相差 ≥ HUE_MIN → 可区分
          * 色相太近 → 需明度差 ≥ LUM_MIN 才能拉开（同色系深浅法是合法设计手法）

    返回 (是否可区分, 色相差, 明度差)
    """
    ha, sa, la = _hsl(a)
    hb, sb, lb = _hsl(b)
    dh = min(abs(ha - hb), 360 - abs(ha - hb))
    dl = abs(la - lb)

    if sa < GRAY_S and sb < GRAY_S:
        return dl >= GRAY_LUM_MIN, dh, dl
    if sa < GRAY_S or sb < GRAY_S:
        return True, dh, dl
    if dh >= HUE_MIN:
        return True, dh, dl
    return dl >= LUM_MIN, dh, dl


# ---------------------------------------------------------------- A/B 源与取值

def check_source(data, rep):
    styles = data.get("styles") or []
    fams = data.get("families") or []
    if not styles:
        rep.failed("style-system.json 中没有 styles")
        return
    if len(styles) != data.get("total_styles"):
        rep.failed(f"total_styles={data.get('total_styles')} 与 styles 实际数 {len(styles)} 不符")
    else:
        rep.passed()
    if len(fams) != data.get("family_count"):
        rep.failed(f"family_count={data.get('family_count')} 与实际族数 {len(fams)} 不符")
    else:
        rep.passed()

    codes = [s["code"] for s in styles]
    if len(codes) != len(set(codes)):
        dup = {c for c in codes if codes.count(c) > 1}
        rep.failed(f"风格编号重复：{sorted(dup)}")
    else:
        rep.passed()

    fam_ids = {f["id"] for f in fams}
    for s in styles:
        c = s["code"]
        if s.get("family") not in fam_ids:
            rep.failed(f"{c}: 族 {s.get('family')} 不存在")
            continue
        missing = [k for k in ("bg", "card", "ink", "mu", "ac", "line")
                   if not s["tokens"].get(k)]
        if missing:
            rep.failed(f"{c}: 缺 token {missing}")
            continue
        bad = [k for k in ("bg", "card", "ink", "mu", "ac", "line")
               if not HEX_RE.match(s["tokens"][k])]
        if bad:
            rep.failed(f"{c}: 非法 hex {bad}")
            continue
        rep.passed()

        cr = contrast(s["tokens"]["ink"], s["tokens"]["bg"])
        if cr < 4.5:
            rep.failed(f"{c} {s.get('label','')}: ink/bg 对比度 {cr} < 4.5")
        else:
            rep.passed()

        use = s.get("report_use") or {}
        if use.get("density") not in ("高", "中", "低"):
            rep.failed(f"{c}: 密度取值非法 {use.get('density')!r}")
        else:
            rep.passed()
        if not s.get("taboos"):
            rep.failed(f"{c}: 没有数据展示禁忌")
        else:
            rep.passed()

    for fam in fams:
        if len(fam.get("series") or []) != 6:
            rep.failed(f"族 {fam['id']}: series 长度不是 6")
            continue
        bad = [c for c in fam["series"] if not HEX_RE.match(c)]
        if bad:
            rep.failed(f"族 {fam['id']}: 非法 hex {bad}")
            continue
        rep.passed()
        if fam.get("styles") and len(fam["styles"]) != fam.get("count"):
            rep.failed(f"族 {fam['id']}: count 与成员数不符")
        else:
            rep.passed()

        # 序列色两两可区分（多系列图表不出现肉眼难分的两色）
        series = fam["series"]
        clashes = []
        for i in range(len(series)):
            for j in range(i + 1, len(series)):
                good, dh, dl = series_clash(series[i], series[j])
                if not good:
                    clashes.append(f"{series[i]}×{series[j]}"
                                   f"（色相差 {dh:.1f}°，明度差 {dl:.1f}）")
        if clashes:
            rep.failed(f"族 {fam['id']} 序列色存在不可区分组合：" + "；".join(clashes))
        else:
            rep.passed()


# ---------------------------------------------------------------- C 生成物

def check_generated(data, rep):
    gen = _load_module("gen_style_assets", SKILL / "tools" / "gen_style_assets.py")

    catalog = ASSETS / "catalog" / "catalog_l0.md"
    if not catalog.exists():
        rep.failed("缺 L0 总目录 assets/catalog/catalog_l0.md")
    else:
        expect = gen.render_catalog(data)
        if catalog.read_text(encoding="utf-8") != expect:
            rep.failed("L0 总目录与源不一致（请运行 tools/gen_style_assets.py）")
        else:
            rep.passed()

    for fam in data["families"]:
        p = ASSETS / "index" / f"{fam['id']}.md"
        if not p.exists():
            rep.failed(f"缺族索引 index/{fam['id']}.md")
            continue
        if p.read_text(encoding="utf-8") != gen.render_index(data, fam):
            rep.failed(f"族索引 {fam['id']}.md 与源不一致")
        else:
            rep.passed()

    for s in data["styles"]:
        p = SKILL / s["body"]
        if not p.exists():
            rep.failed(f"缺正文 {s['body']}")
            continue
        text = p.read_text(encoding="utf-8")
        if text != gen.render_body(data, s):
            rep.failed(f"{s['code']} 正文与源不一致")
            continue
        rep.passed()
        miss = [sec for sec in BODY_SECTIONS if sec not in text]
        if miss:
            rep.failed(f"{s['code']} 正文缺章节 {miss}")
        else:
            rep.passed()


# ---------------------------------------------------------------- D 板块库

def check_blocks(data, rep):
    md = ASSETS / "common" / "block_library.md"
    if not md.exists():
        rep.failed("缺板块库 assets/common/block_library.md")
        return
    bl = _load_module("_bl", SKILL / "conspect_tools" / "block_library.py")
    blocks = bl.all_blocks()
    if len(blocks) != 22:
        rep.failed(f"板块库解析出 {len(blocks)} 个板块，期望 22")
    else:
        rep.passed()

    md_ids = {b["id"] for b in blocks}
    code_ids = set(bl.TRIGGERS)
    if md_ids != code_ids:
        rep.failed(f"md 板块与代码触发实现不一致：仅在 md {sorted(md_ids - code_ids)}；"
                   f"仅在代码 {sorted(code_ids - md_ids)}")
    else:
        rep.passed()

    text_md = md.read_text(encoding="utf-8")
    for bid in sorted(md_ids):
        if f"#### {bid} " not in text_md:
            rep.warned(f"{bid} 在总览表有、但缺少独立规格小节")

    # 推断的 section type 必须落在引擎支持集内
    supported = {"kpi_cards", "section_group", "chart", "conclusion",
                 "table", "custom", "prose"}
    for b in blocks:
        if b["section_type"] not in supported:
            rep.failed(f"{b['id']} 的 section type {b['section_type']} 引擎不支持")
        else:
            rep.passed()

    # 板块声明的图表必须能落到引擎真实支持的类型（否则只在渲染时才暴露）
    unmapped = bl.unmapped_chart_words()
    if unmapped:
        rep.failed("板块库存在无降级映射的图表声明词："
                   + "；".join(f"{x['block']}:{x['word']}" for x in unmapped))
    else:
        rep.passed()

    for b in blocks:
        chain = bl.chart_chain(b["id"])
        illegal = [c for c in chain if c not in bl.ENGINE_CHARTS]
        if illegal:
            rep.failed(f"{b['id']} 的图表链含引擎不支持类型 {illegal}")
        else:
            rep.passed()

    # 确认映射表里的引擎类型与渲染引擎真实分派表一致（防单边改动）
    engine_src = (SKILL / "conspect_tools" / "render_engine.py").read_text(encoding="utf-8")
    m = re.search(r"builders = \{(.*?)\n        \}", engine_src, re.S)
    if not m:
        rep.failed("无法从 render_engine.py 解析 ChartBuilder.build 的分派表")
    else:
        real = set(re.findall(r'"([a-z_]+)":\s*ChartBuilder\.', m.group(1)))
        if real != bl.ENGINE_CHARTS:
            rep.failed("block_library.ENGINE_CHARTS 与渲染引擎分派表不一致："
                       f"仅代码 {sorted(bl.ENGINE_CHARTS - real)}；"
                       f"仅引擎 {sorted(real - bl.ENGINE_CHARTS)}")
        else:
            rep.passed()

    # 风格推荐的板块必须真实存在
    for s in data["styles"]:
        unknown = [x for x in s["report_use"]["blocks"] if x not in md_ids]
        if unknown:
            rep.failed(f"{s['code']} 推荐了不存在的板块 {unknown}")
        else:
            rep.passed()


def main(argv):
    quiet = "--quiet" in argv
    rep = Report()

    if not SRC.exists():
        print(f"[FATAL] 未找到风格资产源 {SRC}")
        return 1
    data = json.loads(SRC.read_text(encoding="utf-8"))

    check_source(data, rep)
    check_generated(data, rep)
    check_blocks(data, rep)

    total = rep.ok + len(rep.fail)
    print(f"资产校验：通过 {rep.ok} / 共 {total} 项")
    if rep.warn:
        print(f"告警 {len(rep.warn)} 条：")
        for w in rep.warn[:10]:
            print("  ? " + w)
    if rep.fail:
        print(f"失败 {len(rep.fail)} 条：")
        for f in rep.fail[:25]:
            print("  x " + f)
        if len(rep.fail) > 25:
            print(f"  ...另有 {len(rep.fail) - 25} 条")
        return 1
    if not quiet:
        print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
