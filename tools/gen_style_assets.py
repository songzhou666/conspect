#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
conspect v4.0 风格资产生成器

职责：由唯一事实源 assets/style-system.json 生成三级资产：
  L0  assets/catalog/catalog_l0.md   族总览 + 38 风格全景 + 选型规则
  L1  assets/index/{族}.md ×6        族内判别表 + 权重
  L2  assets/body/{编号}_{class}.md ×38   统一 9 节创作载荷

设计原则：资产 md 是**生成物**，不手写。因此与 JSON 不可能漂移。
校验：tools/check_style_assets.py 会比对生成物与源是否一致。

运行：python tools/gen_style_assets.py
"""

import json
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SRC = SKILL_DIR / "assets" / "style-system.json"
ASSETS = SKILL_DIR / "assets"

HEADER = "<!-- 本文件由 tools/gen_style_assets.py 生成，请勿手改；改动请修改 assets/style-system.json -->"


def load():
    if not SRC.exists():
        print(f"[FATAL] 未找到 {SRC}，请先运行 tools/import_sz_styles.py")
        sys.exit(2)
    return json.loads(SRC.read_text(encoding="utf-8"))


def series_for(data, style):
    fam = next(f for f in data["families"] if f["id"] == style["family"])
    series = list(fam["series"])
    series[0] = style["tokens"]["ac"]
    return series


# ---------------------------------------------------------------- L2 正文

def render_body(data, style):
    t = style["tokens"]
    fam = next(f for f in data["families"] if f["id"] == style["family"])
    typo = style["typography"]
    shapes = style["shapes"]
    comp = style["components"]
    use = style["report_use"]
    series = series_for(data, style)

    out = []
    out.append(f"# {style['code']} {style['label']} · {style['en']}")
    out.append("")
    out.append(f"> 编号 `{style['code']}` · 族：**{fam['label']}** · 调性：{style['tone']} "
               f"· 组件类前缀 `.{style['class']}`")
    out.append("")
    out.append(HEADER)
    out.append("")

    out.append("## 设计流派")
    out.append("")
    out.append(style["school"] or "（源资产未提供）")
    out.append("")
    out.append("**关键词**：" + " · ".join(style["keywords"]))
    out.append("")
    out.append(f"**一句话氛围**：{style['mood']}")
    out.append("")

    out.append("## 配色 Token（可直接抄用）")
    out.append("")
    out.append("| 变量 | 值 | 说明 |")
    out.append("| --- | --- | --- |")
    out.append(f"| 背景 `--bg` | `{t['bg']}` | 页面底色 |")
    out.append(f"| 卡片 `--card` | `{t['card']}` | 内容容器底色 |")
    out.append(f"| 文字 `--ink` | `{t['ink']}` | 主文字色 |")
    out.append(f"| 次要文字 `--mu` | `{t['mu']}` | 说明/辅助文字 |")
    out.append(f"| 强调 `--ac` | `{t['ac']}` | 主强调/图表主系列/重点 |")
    out.append(f"| 分割线 `--line` | `{t['line']}` | 边框/分隔线 |")
    out.append("")
    if t.get("bg_gradient"):
        out.append(f"**背景渐变**：`{t['bg_gradient']}`")
        out.append("")
    if style.get("token_note"):
        out.append(f"**取值说明**：{style['token_note']}")
        out.append("")

    out.append("## 字体与排版")
    out.append("")
    out.append(f"- 字体族：`{typo.get('family') or 'system-ui, sans-serif'}`")
    out.append(f"- 字号范围：{typo.get('size_range') or '—'}")
    out.append(f"- 字重：{' / '.join(typo.get('weights') or []) or '—'}")
    out.append("")

    out.append("## 形状与特效")
    out.append("")
    if shapes:
        for k, v in shapes.items():
            out.append(f"- {k}：{v}")
    for item in style.get("shape_extra") or []:
        out.append(f"- {item}")
    if not shapes and not style.get("shape_extra"):
        out.append("- 无特殊形状与特效")
    out.append("")

    out.append("## 组件样式特征（报表化改写）")
    out.append("")
    out.append(f"- **KPI 指标卡**：{comp['kpi']}")
    out.append(f"- **图表**：{comp['chart']}")
    out.append(f"- **表格**：{comp['table']}")
    out.append(f"- **数据解读区**：{comp['insight']}")
    out.append("")

    out.append("## 图表配色序列")
    out.append("")
    out.append(f"本风格取自 **{fam['label']}** 族的图表序列色，首位由本风格强调色覆盖：")
    out.append("")
    out.append("| 序号 | 色值 | 用途 |")
    out.append("| --- | --- | --- |")
    labels = ["主系列 / 强调", "系列 2", "系列 3", "系列 4", "系列 5", "系列 6"]
    for i, c in enumerate(series):
        out.append(f"| {i + 1} | `{c}` | {labels[i]} |")
    out.append("")
    out.append("> 系列色顺序固定，同一报表内不得跳号使用；类别数超过 6 时改用排序 + 汇总，"
               "不得自行扩色。")
    out.append("")

    out.append("## 报表版式建议")
    out.append("")
    out.append(f"- **适用报表类型**：{' · '.join(use['types'])}")
    out.append(f"- **推荐板块组合**：{' · '.join(use['blocks'])}")
    out.append(f"- **数据密度适配**：{use['density']}")
    out.append(f"- **适用载体**：{use['media']}")
    out.append("")

    out.append("## 数据展示禁忌")
    out.append("")
    for x in style["taboos"]:
        out.append(f"- {x}")
    out.append("")

    return "\n".join(out).rstrip() + "\n"


# ---------------------------------------------------------------- L1 族索引

def render_index(data, fam):
    members = [s for s in data["styles"] if s["family"] == fam["id"]]
    out = []
    out.append(f"# 族索引 · {fam['label']}（{fam['en']}）")
    out.append("")
    out.append(f"> 本族 {len(members)} 个风格，调性：{fam['tone']}。定位场景：{fam['scene']}")
    out.append(f"> 选型时通读本索引，用「报表类型 × 数据密度 × 调性」锁定唯一风格。")
    out.append("")
    out.append(HEADER)
    out.append("")
    out.append("| 风格 | 名称 | 调性 | 报表类型 | 密度 | 强调色 | 一句话 | 正文路径 |")
    out.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for s in members:
        types = " / ".join(s["report_use"]["types"][:2])
        out.append(f"| {s['code']} | {s['label']} | {s['tone']} | {types} | "
                   f"{s['report_use']['density']} | `{s['tokens']['ac']}` | {s['mood']} | "
                   f"`{s['body']}` |")
    out.append("")
    out.append(f"**族级图表序列色**：{' '.join('`' + c + '`' for c in fam['series'])}")
    out.append("")
    out.append("## 选型判别")
    out.append("")
    out.append("若报表同时命中本族多风格，按以下权重排序，并在选型卡中列判别语让用户确认：")
    out.append("")
    out.append("1. **调性**（投影/打印 → 浅色；屏幕/沉浸 → 深色）")
    out.append("2. **数据密度**（明细多、指标密 → 选高密度风格；讲观点、重冲击 → 选低密度风格）")
    out.append("3. **报表类型**（对齐上表「报表类型」列）")
    out.append("4. **品牌气质**（克制高级 / 大胆张扬 / 温和亲和 / 前沿硬核）")
    out.append("")
    return "\n".join(out).rstrip() + "\n"


# ---------------------------------------------------------------- L0 总目录

def render_catalog(data):
    fams = data["families"]
    out = []
    out.append("# 报表风格选型总目录（L0）")
    out.append("")
    out.append(f"> conspect 的 {data['total_styles']} 种报表风格资产全景，分 {data['family_count']} 族。")
    out.append("> 选型时先按「调性」硬过滤，再按「族 → 报表类型」锁定候选风格。")
    out.append("")
    out.append(HEADER)
    out.append("")
    out.append(f"## {data['family_count']} 族总览")
    out.append("")
    out.append("| 族 | 风格数 | 调性 | 定位场景 | 索引 |")
    out.append("| --- | --- | --- | --- | --- |")
    for f in fams:
        out.append(f"| {f['label']} {f['en']} | {f['count']} | {f['tone']} | {f['scene']} | "
                   f"`assets/index/{f['id']}.md` |")
    out.append("")
    out.append(f"## {data['total_styles']} 风格全景")
    out.append("")
    out.append("| 编号 | 名称 | 英文 | 族 | 调性 | 密度 | 强调色 | 索引 |")
    out.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    label_of = {f["id"]: f["label"] for f in fams}
    for s in sorted(data["styles"], key=lambda x: int(x["code"][1:])):
        out.append(f"| {s['code']} | {s['label']} | {s['en']} | {label_of[s['family']]} | "
                   f"{s['tone']} | {s['report_use']['density']} | `{s['tokens']['ac']}` | "
                   f"`assets/index/{s['family']}.md` |")
    out.append("")
    out.append("## 选型规则")
    out.append("")
    out.append("1. **调性硬过滤**：投影/打印优先浅色族（商务通稿 / 纸感编辑 / 自然柔和）；"
               "屏幕/沉浸优先深色族（数据大屏），玻璃光影与表达张力为混合调性。")
    out.append("2. **族匹配**：按报表类型与数据密度归入候选族，候选族 ≤3。")
    out.append("3. **唯一风格**：读候选族索引，用四维权重锁定唯一风格；"
               "族内多风格同时命中时不自行合并，回选型卡让用户挑并给出判别语。")
    out.append("4. **必须声明**：进入生成前须在 `_cs-style.md` 写入 "
               "`[资产引用] {编号}→{风格名}`，未声明不得渲染。")
    out.append("")
    out.append("## 已剔除风格")
    out.append("")
    out.append("以下风格不在 conspect 资产范围内（原因见 `assets/style-system.json` 的 `excluded` 字段）：")
    out.append("")
    for code, reason in data["excluded"].items():
        out.append(f"- `{code}`：{reason}")
    out.append("")
    return "\n".join(out).rstrip() + "\n"


def main():
    data = load()
    ASSETS.mkdir(parents=True, exist_ok=True)
    (ASSETS / "catalog").mkdir(exist_ok=True)
    (ASSETS / "index").mkdir(exist_ok=True)
    (ASSETS / "body").mkdir(exist_ok=True)

    written = []
    p = ASSETS / "catalog" / "catalog_l0.md"
    p.write_text(render_catalog(data), encoding="utf-8")
    written.append(p)

    for fam in data["families"]:
        p = ASSETS / "index" / f"{fam['id']}.md"
        p.write_text(render_index(data, fam), encoding="utf-8")
        written.append(p)

    for s in data["styles"]:
        p = ASSETS / "body" / f"{s['code']}_{s['class']}.md"
        p.write_text(render_body(data, s), encoding="utf-8")
        written.append(p)

    total_lines = sum(len(p.read_text(encoding="utf-8").splitlines()) for p in written)
    print(f"[生成] {len(written)} 份资产文件，合计 {total_lines} 行")
    print(f"  L0 catalog_l0.md ×1")
    print(f"  L1 index/*.md ×{len(data['families'])}")
    print(f"  L2 body/*.md ×{len(data['styles'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
