# -*- coding: utf-8 -*-
"""
风格选型的「人话层」。

问题所在：选型卡原先只给 `A1（推荐）` 这样的资产编号 + 一串十六进制色值。
客户看不懂编号是什么风格、什么色系、适合什么场合——这是**呈现层的缺失**，
不是资产不够：`style-system.json` 里本来就有 label / mood / school / keywords /
report_use.types / taboos，只是没被翻译成客户能决断的语言。

本模块做两件事：
  1. describe()  —— 把技术字段翻成中文判断依据（色系 / 明暗 / 饱和度 / 气质 / 场景 / 不适合）
  2. build_preview_html() —— 生成 3 个候选并排的可视对比页，让客户直接「看见」

设计约束：色系判定由色值**计算**得出，不查表。因为风格资产会增删，
写死 38 条中文描述必然腐坏；而从 HSL 推导「深底 + 青蓝霓虹」是恒成立的。
"""
import colorsys
import re
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------- 颜色 → 中文

def _hex_to_rgb(h: str):
    h = (h or "").strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return None
    try:
        return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    except ValueError:
        return None


def _hsl(h: str):
    """返回 (色相 0-360, 饱和度 0-1, 明度 0-1)；无法解析时 None。"""
    rgb = _hex_to_rgb(h)
    if not rgb:
        return None
    hh, ll, ss = colorsys.rgb_to_hls(*rgb)
    return hh * 360.0, ss, ll


#: 色相区间 → 中文色名。区间边界按人眼可辨的差异划，不是等分。
_HUE_NAMES = [
    (12, "红"), (38, "橙"), (62, "黄"), (95, "黄绿"), (150, "绿"),
    (185, "青"), (215, "天蓝"), (255, "蓝"), (285, "蓝紫"),
    (320, "紫"), (345, "洋红"), (360, "红"),
]


def _hue_name(hue: float) -> str:
    for bound, name in _HUE_NAMES:
        if hue <= bound:
            return name
    return "红"


def _sat_word(s: float) -> str:
    if s < 0.12:
        return "无彩色"
    if s < 0.40:
        return "低饱和"
    if s < 0.68:
        return "中饱和"
    return "高饱和"


def _bg_word(light: float) -> str:
    if light >= 0.97:
        return "纯白底"
    if light >= 0.90:
        return "浅底"
    if light >= 0.72:
        return "米/浅灰底"
    if light >= 0.45:
        return "中灰底"
    if light >= 0.12:
        return "深底"
    return "近黑底"


def _series_mode(series: List[str]) -> str:
    """
    数据系列用色的组织方式。这一条对客户最有用：
    「六色霓虹」和「单色深浅」是完全不同的观感，但在色值列表里看不出区别。
    """
    hues, grays = [], 0
    for c in series[:8]:
        v = _hsl(c)
        if not v:
            continue
        h, s, _ = v
        if s < 0.15:
            grays += 1
        else:
            hues.append(h)
    if not hues:
        return "灰阶系列"
    if grays >= len(series) - 1:
        return "灰阶系列"
    # 色相环形距离：跨 0 度时按短弧算
    def circ(a, b):
        d = abs(a - b) % 360
        return min(d, 360 - d)
    spread = max((circ(hues[0], h) for h in hues), default=0)
    if spread <= 25:
        return "同色系深浅"
    if len(hues) <= 3:
        return "少量撞色"
    return "多彩并列"


def _first_int(s: Any, default: int = 0) -> int:
    """从「5, 6, 8px」或「12–32px」这类资产值里取第一个整数。"""
    m = re.search(r"\d+", str(s or ""))
    return int(m.group()) if m else default


def _radius(style: Dict[str, Any]) -> int:
    """
    圆角像素。这是**同色系风格之间最主要的观感差异**之一：
    直角（0–2px）显硬朗克制，大圆角（8px+）显柔和现代。
    资产里 `shapes.圆角` 可能是 None（未声明），按直角处理。
    """
    shapes = style.get("shapes") or {}
    v = shapes.get("圆角")
    if v is None:
        return 0
    return min(_first_int(v, 0), 20)


def _bg_paint(tokens: Dict[str, Any]) -> str:
    """
    页面底色该画什么。

    **只有 linear-gradient 才能当页面背景**。资产里有一批 `conic-gradient`
    （如 `conic-gradient(#0A84FF 0 67%, #1A1A1A 67% 100%)`），语义是
    **环形进度条/仪表**，从原稿的组件样式里采集来的。把它铺满整页会画出一个
    占满屏幕的饼图——不是"风格预览"，是事故。所以这里按语法判类型，不按字段名信。
    """
    g = (tokens or {}).get("bg_gradient") or ""
    if g.strip().lower().startswith("linear-gradient"):
        return g
    return (tokens or {}).get("bg") or "#FFFFFF"


def _has_bg_gradient(tokens: Dict[str, Any]) -> bool:
    """是否存在**可用于背景**的渐变（同样是 linear 才算）。"""
    return ((tokens or {}).get("bg_gradient") or "").strip().lower().startswith("linear-gradient")


def _title_px(style: Dict[str, Any]) -> int:
    """标题字号（取 size_range 里「标题 xx px」的数字，没有则退到区间上界）。"""
    ty = style.get("typography") or {}
    rng = str(ty.get("size_range") or "")
    m = re.search(r"标题\s*(\d+)", rng)
    if m:
        return int(m.group(1))
    nums = [int(x) for x in re.findall(r"\d+", rng)]
    return max(nums) if nums else 32


def _title_weight(style: Dict[str, Any]) -> int:
    ty = style.get("typography") or {}
    ws = [_first_int(w, 400) for w in (ty.get("weights") or [])]
    return max(ws) if ws else 700


def _weight_word(w: int) -> str:
    if w >= 800:
        return "超粗"
    if w >= 700:
        return "粗"
    if w >= 500:
        return "中等"
    return "常规"


def describe_form(style: Dict[str, Any]) -> str:
    """
    形状与字体的一句话。配色相同、场景相同的两个风格，差别就在这一层：
    「直角 · 标题 56px 特粗」与「圆角 10px · 标题 32px 中等」是完全不同的观感。
    """
    r = _radius(style)
    if r <= 2:
        corner = "直角"
    elif r <= 8:
        corner = f"小圆角 {r}px"
    elif r <= 16:
        corner = f"圆角 {r}px"
    else:
        corner = "大圆角（胶囊感）"
    return f"{corner} · 标题 {_title_px(style)}px {_weight_word(_title_weight(style))}"


def describe_style(style: Dict[str, Any], series: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    把一份风格资产翻成客户能决断的语言。

    返回：
        palette      色系一句话（如「深底 + 青蓝霓虹，多彩并列」）
        bg_word      底色性质
        accent_name  强调色中文名
        sat_word     饱和度
        series_mode  数据系列用色组织方式
        mood         气质（取自资产，已是人话）
        school       设计流派一句话
        scenes       适合场景（中文列表）
        avoid        不建议用于（taboos 摘要，最多 2 条）
        swatches     色板（含中文角色名，供终端/网页展示）
    """
    tokens = style.get("tokens") or {}
    bg = tokens.get("bg", "#FFFFFF")
    ac = tokens.get("ac", "#000000")
    ink = tokens.get("ink", "#000000")
    series = series if series is not None else style.get("series") or []

    bg_v = _hsl(bg) or (0, 0, 1)
    ac_v = _hsl(ac) or (0, 0, 0)
    ink_v = _hsl(ink) or (0, 0, 0)

    bg_word = _bg_word(bg_v[2])
    # 强调色若是无彩色（黑/灰），说「无彩色」比编一个色名准确
    accent_name = _hue_name(ac_v[0]) if ac_v[1] >= 0.12 else "黑/灰"
    sat_word = _sat_word(ac_v[1])
    smode = _series_mode(series)

    dark = bg_v[2] < 0.45
    # 色系一句话：先说底，再说强调色，最后说系列组织方式
    if bg_v[1] < 0.10:
        base = f"{bg_word} + {accent_name}强调"
    else:
        base = f"{bg_word}（带{_hue_name(bg_v[0])}调） + {accent_name}强调"
    palette = f"{base}，{smode}"

    use = style.get("report_use") or {}
    taboos = [t for t in (style.get("taboos") or []) if t]

    return {
        "palette": palette,
        "bg_word": bg_word,
        "accent_name": accent_name,
        "sat_word": sat_word,
        "series_mode": smode,
        "form": describe_form(style),
        "radius": _radius(style),
        "title_px": _title_px(style),
        "title_weight": _title_weight(style),
        "mood": style.get("mood", ""),
        "school": (style.get("school") or "").split("：")[-1] or style.get("school", ""),
        "scenes": (use.get("types") or [])[:4],
        "avoid": taboos[:2],
        "density": use.get("density", ""),
        "media": use.get("media", ""),
        "is_dark": dark,
        "swatches": [
            {"role": "底色", "hex": bg},
            {"role": "文字", "hex": ink},
            {"role": "强调", "hex": ac},
            {"role": "卡片", "hex": tokens.get("card", bg)},
            {"role": "分隔", "hex": tokens.get("line", bg)},
        ] + [{"role": f"图表{i + 1}", "hex": c} for i, c in enumerate(series[:6])],
    }


def diff_note(base: Dict[str, Any], other: Dict[str, Any],
              base_d: Optional[Dict[str, Any]] = None,
              other_d: Optional[Dict[str, Any]] = None) -> str:
    """
    候选相对推荐款的差异，一句话。

    必要性：`report_use`（场景/密度/载体）是**族级**属性，同一族内几款候选的
    这些字段完全一致。若只描述各自属性，客户会看到 4 段几乎相同的文字，仍然选不出来。
    所以必须显式说出「它和推荐款差在哪」——底色明暗、强调色、系列用色。

    无实质差异时返回空串，不编造。
    """
    bd = base_d or describe_style(base, base.get("series"))
    od = other_d or describe_style(other, other.get("series"))
    bits = []

    b_bg = (_hsl((base.get("tokens") or {}).get("bg", "")) or (0, 0, 1))[2]
    o_bg = (_hsl((other.get("tokens") or {}).get("bg", "")) or (0, 0, 1))[2]
    if abs(b_bg - o_bg) >= 0.03:
        bits.append("底色更亮" if o_bg > b_bg else "底色更暗")

    if bd["accent_name"] != od["accent_name"]:
        bits.append(f"强调色由{bd['accent_name']}换成{od['accent_name']}")
    elif abs((_hsl((base.get("tokens") or {}).get("ac", "")) or (0, 0, 1))[1]
             - (_hsl((other.get("tokens") or {}).get("ac", "")) or (0, 0, 1))[1]) >= 0.2:
        bits.append("强调色更浓" if (_hsl((other.get("tokens") or {}).get("ac", "")) or (0, 0, 1))[1]
                    > (_hsl((base.get("tokens") or {}).get("ac", "")) or (0, 0, 1))[1]
                    else "强调色更淡")

    if bd["series_mode"] != od["series_mode"]:
        bits.append(f"数据系列改为{od['series_mode']}")

    # 形状与字体：同色系风格的真正差别在这里。不比对这一层，
    # 四个白底蓝调的候选会给出「差异为空」的错误结论。
    if abs(bd.get("radius", 0) - od.get("radius", 0)) >= 3:
        bits.append("更圆润" if od["radius"] > bd["radius"] else "更硬朗")
    if abs(bd.get("title_px", 0) - od.get("title_px", 0)) >= 6:
        bits.append("标题更大" if od["title_px"] > bd["title_px"] else "标题更小")
    if abs(bd.get("title_weight", 0) - od.get("title_weight", 0)) >= 100:
        bits.append("字更粗" if od["title_weight"] > bd["title_weight"] else "字更细")

    if od["density"] and bd["density"] and od["density"] != bd["density"]:
        bits.append(f"更适合{od['density']}密度")

    # 渐变底是明显的观感差异，单列一条
    if _has_bg_gradient(other.get("tokens")) and \
            not _has_bg_gradient(base.get("tokens")):
        bits.append("底色带渐变")

    # 色系几乎一样时，差异其实在「设计手法」（排版、圆角、装饰）。
    # 这时不能说"无差异"——它确实长得不一样，只是不在配色上。
    # 如实指出差异维度，并引导用户看预览页对比。
    if not bits:
        mb, mo = (base.get("mood") or "").strip(), (other.get("mood") or "").strip()
        if mo and mo != mb:
            return f"配色接近，差别在手法：{mo}"
        return "配色与手法都接近，可按编号顺序或预览观感定"
    return "、".join(bits)


def card_text(style: Dict[str, Any], d: Dict[str, Any],
              diff: str = "") -> str:
    """
    终端可读的选型卡（纯文本）。中文名打头，编号退到括号里——
    客户判断「瑞士极简」时不需要先记住 A1 是什么。
    """
    lines = [
        f"{style.get('label', '')}（{style.get('en', '')}）· 编号 {style.get('code', '')}",
        f"  色系：{d['palette']}",
        f"  形状：{d['form']}",
        f"  气质：{d['mood']}",
    ]
    if d["scenes"]:
        lines.append("  适合：" + "、".join(d["scenes"]))
    lines.append(f"  载体：{d['media'] or '—'} · 数据密度 {d['density'] or '—'}")
    if diff:
        lines.append(f"  与推荐款差异：{diff}")
    if d["avoid"]:
        lines.append("  注意：" + d["avoid"][0])
    return "\n".join(lines)


# ---------------------------------------------------------------- 可视对比页

def _describe_of(card: Dict[str, Any]) -> Dict[str, Any]:
    """
    取一份描述。

    优先用卡片自带的 `describe`——`select_style` 已经基于**原始风格资产**
    算过一次（含圆角/字号/字重）。预览若自己重算，而卡片里没有
    `shapes` / `typography` 字段，就会全部退化成「直角 + 默认字重」，
    四列长得一模一样。宁可复用上游结果，也不要在两处各算一套。
    """
    d = card.get("describe")
    if isinstance(d, dict) and d.get("palette"):
        return d
    return describe_style(card, card.get("series"))


def build_preview_html(candidates: List[Dict[str, Any]],
                       profile: Optional[Dict[str, Any]] = None,
                       title: str = "报表风格候选") -> str:
    """
    生成候选风格并排对比页。

    每一列不是配色表，而是**用该风格真实色值画出的一小段报表**：
    封面条、KPI 卡、柱状图。客户看一眼就知道「这是不是我想要的样子」。

    刻意不引入 ECharts：预览只需要传达观感，手绘柱条即可，
    换来整页 < 40KB、断网可开、可邮件发送。
    """
    prof = profile or {}
    cond = " · ".join([x for x in [prof.get("tone", ""), prof.get("report_type", ""),
                                   prof.get("media", "")] if x]) or "未指定偏好"

    cols = []
    base = candidates[0] if candidates else None
    base_d = _describe_of(base) if base else None
    for idx, c in enumerate(candidates, 1):
        toks = c.get("tokens") or {}
        series = c.get("series") or []
        d = _describe_of(c)
        # 族内候选的场景/密度完全一致，必须显式给出与推荐款的差异，否则客户无从抉择
        diff = c.get("diff_from_recommend") or (
            diff_note(base, c, base_d, d) if idx > 1 else "")
        bg = toks.get("bg", "#FFFFFF")
        ink = toks.get("ink", "#111111")
        ac = toks.get("ac", "#333333")
        card = toks.get("card", bg)
        line = toks.get("line", "#DDDDDD")
        mu = toks.get("mu", ink)

        stage_bg = _bg_paint(toks)
        # 预览必须体现风格的形状与字体，否则同色系的四个候选会长得一模一样。
        # 圆角按资产值等比缩小、字重/标题字号直接映射到预览比例。
        rad = d["radius"]
        tw = d["title_weight"]
        tpx = max(14, min(21, round(d["title_px"] * 0.36)))
        bars = "".join(
            f'<i style="height:{h}%;background:{series[i % len(series)] if series else ac}'
            f';border-radius:{max(0, rad - 2)}px {max(0, rad - 2)}px 0 0"></i>'
            for i, h in enumerate([46, 68, 54, 82, 62]))

        sw = "".join(
            f'<span class="sw"><b style="background:{s["hex"]}"></b>'
            f'<em>{s["role"]}</em><code>{s["hex"]}</code></span>'
            for s in d["swatches"]
        )

        scenes = "".join(f'<span class="chip">{t}</span>' for t in d["scenes"]) or "—"
        avoid = "".join(f'<li>{t}</li>' for t in d["avoid"]) or "<li>无特别限制</li>"

        reason = "".join(f'<li>{r}</li>' for r in (c.get("reasons") or [])[:3])

        cols.append(f"""
    <section class="col{" pick" if idx == 1 else ""}">
      <div class="badge">{idx}</div>
      <header>
        <h2>{c.get('label', '')}</h2>
        <div class="sub">{c.get('en', '')} · 编号 {c.get('code', '')}
          {f"· {c.get('family_label', '')}" if c.get('family_label') else ""}</div>
      </header>
      <p class="mood">{d['mood']}</p>
      {f'<p class="diff">与「{base.get("label", "")}」的区别：{diff}</p>' if diff else ''}

      <div class="stage" style="background:{stage_bg};color:{ink};border-radius:{rad}px">
        <div class="bar" style="background:{ac};border-radius:{max(0, rad - 1)}px"></div>
        <div class="t" style="font-weight:{tw};font-size:{tpx}px">年度经营分析</div>
        <div class="s" style="color:{mu}">2025 全年 · 示例数据</div>
        <div class="kpis">
          <div class="k" style="background:{card};border-color:{line};border-radius:{rad}px">
            <div class="kv" style="color:{ac}">1,284</div>
            <div class="kl" style="color:{mu}">订单数</div>
          </div>
          <div class="k" style="background:{card};border-color:{line};border-radius:{rad}px">
            <div class="kv" style="color:{ac}">28.8万</div>
            <div class="kl" style="color:{mu}">成交额</div>
          </div>
        </div>
        <div class="chart" style="border-color:{line};background:{card};border-radius:{rad}px">
          <div class="bars">{bars}</div>
          <div class="axis" style="border-color:{line}"></div>
        </div>
      </div>

      <dl>
        <dt>色系</dt><dd>{d['palette']}</dd>
        <dt>形状</dt><dd>{d['form']}</dd>
        <dt>适合</dt><dd class="chips">{scenes}</dd>
        <dt>载体</dt><dd>{d['media'] or '—'} · 数据密度 {d['density'] or '—'}</dd>
        <dt>不建议</dt><dd><ul class="avoid">{avoid}</ul></dd>
        {f'<dt>入选理由</dt><dd><ul class="avoid">{reason}</ul></dd>' if reason else ''}
      </dl>

      <div class="sw-row">{sw}</div>
    </section>""")

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
  *{{box-sizing:border-box}}
  body{{margin:0;padding:32px 28px 48px;background:#F1F3F5;color:#1B1F23;
       font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif}}
  .head{{max-width:1400px;margin:0 auto 26px}}
  .head h1{{font-size:22px;margin:0 0 6px;font-weight:650}}
  .head p{{margin:0;color:#5B6570;font-size:13.5px;line-height:1.7}}
  .head .hint{{margin-top:10px;padding:9px 13px;background:#FFF;border-left:3px solid #2F6FEB;
              border-radius:0 6px 6px 0;font-size:13px;color:#39424C}}
  .grid{{max-width:1400px;margin:0 auto;display:grid;gap:20px;
        grid-template-columns:repeat(auto-fit,minmax(330px,1fr))}}
  .col{{position:relative;background:#FFF;border:1px solid #DEE2E6;border-radius:12px;
       padding:18px 18px 14px;display:flex;flex-direction:column;gap:12px}}
  .col.pick{{border-color:#2F6FEB;box-shadow:0 2px 14px rgba(47,111,235,.16)}}
  .badge{{position:absolute;top:-11px;left:16px;width:24px;height:24px;border-radius:50%;
         background:#5B6570;color:#FFF;font-size:13px;font-weight:600;
         display:flex;align-items:center;justify-content:center}}
  .col.pick .badge{{background:#2F6FEB}}
  .col header h2{{margin:0;font-size:17px;font-weight:650}}
  .col header .sub{{color:#6B7684;font-size:12px;margin-top:3px}}
  .mood{{margin:0;font-size:13px;color:#3C4650;line-height:1.6;
        padding-left:9px;border-left:2px solid #D6DBE0}}
  .diff{{margin:0;font-size:12px;color:#2F6FEB;line-height:1.55;
        background:#F2F6FE;border-radius:5px;padding:6px 9px}}
  .stage{{border-radius:8px;padding:14px 13px 11px;overflow:hidden}}
  .stage .bar{{height:3px;width:34px;border-radius:2px;margin-bottom:11px}}
  .stage .t{{font-size:15.5px;font-weight:650;letter-spacing:.01em}}
  .stage .s{{font-size:10.5px;margin-top:2px}}
  .kpis{{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-top:11px}}
  .k{{border:1px solid;border-radius:5px;padding:7px 8px}}
  .kv{{font-size:15px;font-weight:650;line-height:1.15}}
  .kl{{font-size:9.5px;margin-top:2px}}
  .chart{{margin-top:8px;border:1px solid;border-radius:5px;padding:8px 9px 0}}
  .bars{{display:flex;align-items:flex-end;gap:5px;height:42px}}
  .bars i{{flex:1;border-radius:2px 2px 0 0;display:block}}
  .axis{{border-top:1px solid;margin-top:0}}
  dl{{margin:0;font-size:12.5px;line-height:1.65;display:grid;
     grid-template-columns:58px 1fr;gap:4px 10px}}
  dt{{color:#6B7684}}
  dd{{margin:0;color:#242B33}}
  dd.chips{{display:flex;flex-wrap:wrap;gap:4px}}
  .chip{{background:#EEF1F4;border-radius:4px;padding:1px 7px;font-size:11.5px}}
  ul.avoid{{margin:0;padding-left:15px;color:#4A545E}}
  ul.avoid li{{margin:1px 0}}
  .sw-row{{display:flex;flex-wrap:wrap;gap:6px;padding-top:10px;border-top:1px dashed #E3E7EB}}
  .sw{{display:flex;flex-direction:column;align-items:center;gap:2px;width:52px}}
  .sw b{{width:100%;height:20px;border-radius:4px;border:1px solid rgba(0,0,0,.10)}}
  .sw em{{font-size:10px;color:#6B7684;font-style:normal}}
  .sw code{{font-size:9px;color:#9AA3AC;font-family:Consolas,monospace}}
</style>
</head>
<body>
  <div class="head">
    <h1>{title}</h1>
    <p>共 {len(candidates)} 个候选。每一列都用该风格的<strong>真实色值</strong>画了一小段报表，
       看观感即可，不必记编号。</p>
    <div class="hint">你的偏好：{cond}　·　回复「1 / 2 / 3」选定，或说明想改的方向（如「要更亮」「别太花」）。</div>
  </div>
  <div class="grid">{"".join(cols)}
  </div>
</body>
</html>"""
