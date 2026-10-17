"""
conspect 渲染引擎模块
生成 ECharts HTML 报表，支持多种图表类型、多风格资产、丝滑动画交互

风格全部来自资产层（assets/style-system.json），本引擎不持有任何硬编码配色。
视觉规范由「报表选型」阶段命中的风格资产决定，本引擎负责按资产把内容渲染出来。
"""
from typing import Dict, List, Optional, Any
import json
from pathlib import Path

try:
    from conspect_tools import style_loader
except ImportError:  # 允许以包内相对方式导入
    from . import style_loader

#: 本地 ECharts 路径。存在时内联进 HTML，使报表**离线可用**
#: （投屏演示、邮件发送、内网打开的常见场景，靠 CDN 会直接白板）。
ECHARTS_LOCAL = Path(__file__).resolve().parent.parent / "assets" / "vendor" / "echarts.min.js"
ECHARTS_CDN = "https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js"
_echarts_cache: Optional[str] = None


def _lum(hex_color: str) -> float:
    """相对亮度（WCAG 定义）。"""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except (ValueError, IndexError):
        return 0.0

    def f(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _contrast(a: str, b: str) -> float:
    l1, l2 = _lum(a), _lum(b)
    if l1 < l2:
        l1, l2 = l2, l1
    return (l1 + 0.05) / (l2 + 0.05)


def _readable(fg: str, bg: str, min_ratio: float = 4.5) -> str:
    """
    把前景色朝黑（浅背景）或白（深背景）方向逐步调整，直到与背景对比度达标。

    用途：资产的次要文字色是为版式留白设计的，直接拿来画 12px 轴刻度会看不清。
    不修改资产，只在渲染时按背景算一个达标的替代色。
    """
    if not fg.startswith("#") or not bg.startswith("#"):
        return fg
    if _contrast(fg, bg) >= min_ratio:
        return fg
    h = fg.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        rgb = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    except (ValueError, IndexError):
        return fg
    # 浅背景压暗，深背景提亮
    target = 0 if _lum(bg) > 0.5 else 255
    best = fg
    for step in range(1, 21):
        k = step / 20
        mixed = [round(c + (target - c) * k) for c in rgb]
        cand = "#{:02X}{:02X}{:02X}".format(*mixed)
        best = cand
        if _contrast(cand, bg) >= min_ratio:
            return cand
    return best


def echarts_script_tag(inline: bool = True) -> str:
    """
    产出 ECharts 的 script 标签。

    优先内联本地文件（约 1MB，换来离线可用）；本地缺失时退回 CDN。
    结果缓存，避免每次渲染都读 1MB 文件。
    """
    global _echarts_cache
    if inline and ECHARTS_LOCAL.exists():
        if _echarts_cache is None:
            try:
                _echarts_cache = ECHARTS_LOCAL.read_text(encoding="utf-8", errors="replace")
            except Exception:
                _echarts_cache = ""
        if _echarts_cache:
            return f"<script>{_echarts_cache}</script>"
    return f'<script src="{ECHARTS_CDN}"></script>'


class ColorTheme:
    """配色主题系统——风格来自资产层，本类只做翻译与取值。"""

    #: 资产不可用时的兜底风格编号
    FALLBACK = style_loader.DEFAULT_CODE

    @classmethod
    def get(cls, name: str = "") -> dict:
        """
        获取某风格的主题字典；未指定或无效时取默认风格。

        额外补一个 `text_chart`：图表内部（坐标轴刻度、图例）用的文字色。
        资产的 `text_secondary` 是为版式留白设计的浅灰，用作 12px 轴刻度时
        对比度往往不足 4.5:1（浅色族尤甚），在投影上几乎看不见。
        这里按背景自动加深到达标，不改资产本身。
        """
        t = dict(style_loader.theme(name or cls.FALLBACK))
        t["text_chart"] = _readable(t.get("text_secondary", "#666666"),
                                    t.get("bg", "#FFFFFF"), 4.5)
        return t

    @classmethod
    def list_themes(cls) -> List[str]:
        """列出全部可用风格编号。"""
        return style_loader.codes()

    @classmethod
    def list_families(cls) -> List[dict]:
        """列出全部风格族。"""
        return style_loader.families()

    @classmethod
    def describe(cls, name: str) -> dict:
        """风格的完整资产信息（供选型卡展示）。"""
        s = style_loader.get_style(name)
        if not s:
            return {}
        return {
            "code": s["code"], "label": s["label"], "en": s.get("en", ""),
            "family": s["family"], "tone": s.get("tone", ""),
            "mood": s.get("mood", ""), "keywords": s.get("keywords", []),
            "tokens": s["tokens"], "report_use": s.get("report_use", {}),
            "taboos": s.get("taboos", []),
        }

    @classmethod
    def build_series_colors(cls, theme: dict, count: int) -> List[str]:
        """按数据系列数量取图表配色。序列固定，超出部分循环取用并降透明。"""
        all_colors = theme.get("series") or (theme["primary"] + theme["secondary"])
        if count <= len(all_colors):
            return all_colors[:count]
        colors = []
        for i in range(count):
            base = all_colors[i % len(all_colors)]
            alpha = 1.0 - (i // len(all_colors)) * 0.15
            if alpha < 0.4:
                alpha = 0.4
            colors.append(base)
        return colors


class ChartBuilder:
    """图表配置构建器——每种图表类型对应一个构建方法。"""

    @staticmethod
    def get_animation_config() -> dict:
        """
        通用动画配置——让每个图表都有"生命感"。
        柱状图生长、折线图绘制、饼图展开，全部带过渡动画。
        """
        return {
            "animation": True,
            "animationDuration": 800,
            "animationEasing": "cubicOut",
            "animationDelay": None,  # 由具体图表覆盖
        }

    @staticmethod
    def line(data: dict, theme: dict, colors: List[str]) -> dict:
        """折线图（smooth曲线 + 面积渐变填充）。"""
        animation = ChartBuilder.get_animation_config()
        animation["animationDuration"] = 1000
        option = {
            "color": colors,
            "tooltip": {"trigger": "axis", "backgroundColor": "rgba(255,255,255,0.95)", "borderColor": theme["border"], "borderWidth": 1, "textStyle": {"color": theme["text"], "fontSize": 13}},
            "legend": {"data": data.get("series_names", []), "textStyle": {"color": theme["text_chart"], "fontSize": 12}, "bottom": 0},
            "grid": {"left": "3%", "right": "4%", "bottom": "15%", "containLabel": True},
            "xAxis": {"type": "category", "data": data.get("x", []), "axisLine": {"lineStyle": {"color": theme["border"]}}, "axisLabel": {"color": theme["text_chart"]}},
            "yAxis": {"type": "value", "splitLine": {"lineStyle": {"color": theme["border"], "type": "dashed"}}, "axisLabel": {"color": theme["text_chart"]}},
            "dataZoom": [{"type": "inside", "start": 0, "end": 100}, {"type": "slider", "start": 0, "end": 100, "height": 20, "bottom": 30, "borderColor": theme["border"], "textStyle": {"color": theme["text_chart"]}}],
            "series": [],
            **animation,
        }
        series_list = data.get("series", data.get("y", []))
        if isinstance(series_list, list) and len(series_list) > 0 and isinstance(series_list[0], (int, float)):
            series_list = [{"name": data.get("name", "趋势"), "data": series_list}]
        for idx, s in enumerate(series_list):
            color = colors[idx % len(colors)]
            option["series"].append({
                "name": s.get("name", f"系列{idx+1}"),
                "type": "line", "smooth": True,
                "symbol": "circle", "symbolSize": 6,
                "showSymbol": len(s.get("data", [])) <= 24,
                "data": s.get("data", []),
                "lineStyle": {"width": 2.5, "color": color},
                "areaStyle": {"color": {"type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1,
                    "colorStops": [{"offset": 0, "color": color}, {"offset": 1, "color": f"{color}00"}]}},
                "emphasis": {"focus": "series"},
            })
        return option

    @staticmethod
    def bar(data: dict, theme: dict, colors: List[str]) -> dict:
        """柱状图（圆角柱 + 渐变色填充）。"""
        option = {
            "color": colors,
            "tooltip": {"trigger": "axis", "backgroundColor": "rgba(255,255,255,0.95)", "borderColor": theme["border"], "borderWidth": 1, "textStyle": {"color": theme["text"], "fontSize": 13}},
            "legend": {"data": data.get("series_names", []), "textStyle": {"color": theme["text_chart"]}},
            "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
            "xAxis": {"type": "category", "data": data.get("x", []), "axisLabel": {"color": theme["text_chart"]}, "axisLine": {"lineStyle": {"color": theme["border"]}}},
            "yAxis": {"type": "value", "splitLine": {"lineStyle": {"color": theme["border"], "type": "dashed"}}, "axisLabel": {"color": theme["text_chart"]}},
            "series": [],
            **ChartBuilder.get_animation_config(),
        }
        series_list = data.get("series", data.get("y", []))
        if isinstance(series_list, list) and len(series_list) > 0 and isinstance(series_list[0], (int, float)):
            series_list = [{"data": series_list}]
        for idx, s in enumerate(series_list):
            color = colors[idx % len(colors)]
            option["series"].append({
                "name": s.get("name", f"系列{idx+1}"),
                "type": "bar", "data": s.get("data", []),
                "barMaxWidth": 50, "barGap": "30%",
                "itemStyle": {
                    "color": {"type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1,
                        "colorStops": [{"offset": 0, "color": color}, {"offset": 1, "color": f"{color}88"}]},
                    "borderRadius": [4, 4, 0, 0],
                },
                "emphasis": {"focus": "series", "itemStyle": {"shadowBlur": 10, "shadowColor": f"{color}44"}},
            })
        return option

    @staticmethod
    def horizontal_bar(data: dict, theme: dict, colors: List[str]) -> dict:
        """横向条形图（适合排名展示，动画逐条出现）。"""
        opt = ChartBuilder.bar(data, theme, colors)
        opt["xAxis"], opt["yAxis"] = opt["yAxis"], opt["xAxis"]
        for s in opt["series"]:
            s["itemStyle"]["borderRadius"] = [0, 4, 4, 0]
        return opt

    @staticmethod
    def stacked_bar(data: dict, theme: dict, colors: List[str]) -> dict:
        """堆叠柱状图。"""
        opt = ChartBuilder.bar(data, theme, colors)
        for idx, s in enumerate(opt["series"]):
            s["stack"] = "total"
            s["itemStyle"]["borderRadius"] = [0, 0, 0, 0]
        if opt["series"]:
            opt["series"][-1]["itemStyle"]["borderRadius"] = [4, 4, 0, 0]
        return opt

    @staticmethod
    def pie(data: dict, theme: dict, colors: List[str]) -> dict:
        """饼图/环形图（不超过5项用饼图，超过用环形图）。"""
        items = data.get("data", data.get("pairs", {}))
        if isinstance(items, dict):
            items = [{"name": k, "value": v} for k, v in items.items()]
        count = len(items)
        is_ring = count > 5
        option = {
            "color": colors,
            "tooltip": {"trigger": "item", "backgroundColor": "rgba(255,255,255,0.95)", "borderColor": theme["border"], "borderWidth": 1,
                "formatter": "{b}: {c} ({d}%)", "textStyle": {"color": theme["text"]}},
            "legend": {"data": [i["name"] for i in items], "textStyle": {"color": theme["text_chart"]}, "type": "scroll", "bottom": 0},
            "series": [{
                "type": "pie",
                "radius": is_ring and ["35%", "60%"] or "50%",
                "center": ["50%", "45%"],
                "data": items,
                "label": {"show": True, "formatter": "{b}\n{d}%", "color": theme["text"], "fontSize": 12},
                "labelLine": {"lineStyle": {"color": theme["border"]}},
                "emphasis": {"itemStyle": {"shadowBlur": 10, "shadowColor": "rgba(0,0,0,0.15)"}, "label": {"fontSize": 14, "fontWeight": "bold"}},
                "itemStyle": {"borderRadius": 4, "borderColor": theme["card_bg"], "borderWidth": 2},
                "animationType": "scale",
                **ChartBuilder.get_animation_config(),
            }],
        }
        if is_ring:
            # 环形图中心显示总计
            total = sum(i.get("value", 0) for i in items)
            option["series"][0]["graphic"] = {
                "type": "text", "left": "center", "top": "center",
                "style": {"text": f"{total:,}", "textAlign": "center", "fill": theme["text"], "fontSize": 20, "fontWeight": "bold"},
            }
        return option

    @staticmethod
    def funnel(data: dict, theme: dict, colors: List[str]) -> dict:
        """漏斗图（适合展示转化率递减）。"""
        items = data.get("data", [])
        option = {
            "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
            "legend": {"data": [i["name"] for i in items], "textStyle": {"color": theme["text_chart"]}},
            "series": [{
                "type": "funnel", "left": "10%", "top": 40, "bottom": 40,
                "width": "80%", "minSize": "10%", "maxSize": "100%",
                "sort": "descending", "gap": 4,
                "data": items,
                "label": {"show": True, "position": "inside", "formatter": "{b}: {c}", "color": "#fff", "fontWeight": "bold"},
                "labelLine": {"length": 10, "lineStyle": {"width": 1, "type": "solid"}},
                "itemStyle": {"borderColor": theme["card_bg"], "borderWidth": 2},
                "emphasis": {"label": {"fontSize": 16}},
                **ChartBuilder.get_animation_config(),
            }],
            "color": colors,
        }
        return option

    @staticmethod
    def radar(data: dict, theme: dict, colors: List[str]) -> dict:
        """雷达图（适合多维度综合对比）。"""
        indicators = data.get("indicators", [])
        series_data = data.get("data", [])
        option = {
            "color": colors,
            "tooltip": {"trigger": "item", "backgroundColor": "rgba(255,255,255,0.95)", "borderColor": theme["border"]},
            "legend": {"data": [s.get("name", "") for s in series_data], "textStyle": {"color": theme["text_chart"]}, "bottom": 0},
            "radar": {
                "indicator": [{"name": ind.get("name", ""), "max": ind.get("max", 100)} for ind in indicators],
                "radius": "60%",
                "axisName": {"color": theme["text"], "fontSize": 12},
                "splitArea": {"areaStyle": {"color": [f"{theme['primary'][0]}08", f"{theme['primary'][0]}04"]}},
                "axisLine": {"lineStyle": {"color": theme["border"]}},
                "splitLine": {"lineStyle": {"color": theme["border"]}},
            },
            "series": [{
                "type": "radar",
                "data": [{"name": s.get("name", ""), "value": s.get("value", [])} for s in series_data],
                "symbol": "circle", "symbolSize": 6,
                "lineStyle": {"width": 2},
                "areaStyle": {"opacity": 0.1},
                "emphasis": {"lineStyle": {"width": 4}},
                **ChartBuilder.get_animation_config(),
            }],
        }
        return option

    @staticmethod
    def scatter(data: dict, theme: dict, colors: List[str]) -> dict:
        """
        散点图/气泡图。

        symbolSize 用数组 [min,max] 时，ECharts 会拿数据的**第 3 维**做映射；
        若数据只有 [x,y] 两维，就会拿 y 值映射大小——销量从 8 到 350 会让点大小
        差出百倍，图上出现「超大点 + 密集小点」，完全不可读。
        因此只有真给了第 3 维才启用大小映射，否则用固定尺寸。
        """
        series_data = data.get("data", data.get("series", []))
        has_size = (bool(series_data) and isinstance(series_data[0], (list, tuple))
                    and len(series_data[0]) >= 3)
        option = {
            "color": colors,
            "tooltip": {"trigger": "item", "formatter": "{c}", "backgroundColor": "rgba(255,255,255,0.95)", "borderColor": theme["border"]},
            "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
            "xAxis": {"type": "value", "splitLine": {"lineStyle": {"color": theme["border"], "type": "dashed"}}, "axisLabel": {"color": theme["text_chart"]}},
            "yAxis": {"type": "value", "splitLine": {"lineStyle": {"color": theme["border"], "type": "dashed"}}, "axisLabel": {"color": theme["text_chart"]}},
            "series": [{
                "type": "scatter", "data": series_data,
                "symbolSize": [5, 40] if has_size else 9,
                "itemStyle": {"shadowBlur": 10, "shadowColor": "rgba(0,0,0,0.1)",
                              "opacity": 0.75},
                "emphasis": {"itemStyle": {"shadowBlur": 20, "shadowColor": "rgba(0,0,0,0.2)"}},
                **ChartBuilder.get_animation_config(),
            }],
        }
        return option

    @staticmethod
    def heatmap(data: dict, theme: dict, colors: List[str]) -> dict:
        """热力图（适合相关性/密度展示）。"""
        option = {
            "tooltip": {"position": "top", "formatter": "{c}", "backgroundColor": "rgba(255,255,255,0.95)"},
            "grid": {"left": "5%", "right": "5%", "bottom": "10%", "containLabel": True},
            "xAxis": {"type": "category", "data": data.get("x", []), "splitArea": {"show": True}, "axisLabel": {"color": theme["text_chart"]}},
            "yAxis": {"type": "category", "data": data.get("y", []), "splitArea": {"show": True}, "axisLabel": {"color": theme["text_chart"]}},
            "visualMap": {"min": data.get("min", 0), "max": data.get("max", 100), "calculable": True, "orient": "horizontal", "left": "center", "bottom": 0,
                "inRange": {"color": [f"{theme['primary'][0]}33", theme["primary"][0], theme["primary"][-1]]}},
            "series": [{
                "type": "heatmap", "data": data.get("data", []),
                "label": {"show": len(data.get("data", [])) <= 50, "color": theme["text"]},
                "emphasis": {"itemStyle": {"shadowBlur": 10, "shadowColor": "rgba(0,0,0,0.3)"}},
            }],
        }
        return option

    @staticmethod
    def sankey(data: dict, theme: dict, colors: List[str]) -> dict:
        """桑基图（适合流量/转化路径分析）。"""
        option = {
            "tooltip": {"trigger": "item", "triggerOn": "mousemove"},
            "series": [{
                "type": "sankey",
                "layout": "none",
                "emphasis": {"focus": "adjacency"},
                "nodeAlign": "left",
                "nodeWidth": 20, "nodeGap": 12,
                "data": data.get("nodes", []),
                "links": data.get("links", []),
                "lineStyle": {"curveness": 0.5, "opacity": 0.3},
                **ChartBuilder.get_animation_config(),
            }],
            "color": colors,
        }
        return option

    @staticmethod
    def gauge(data: dict, theme: dict, colors: List[str]) -> dict:
        """仪表盘（适合目标达成率展示）。"""
        value = data.get("value", 0)
        name = data.get("name", "")
        max_val = data.get("max", 100)
        option = {
            "series": [{
                "type": "gauge",
                "center": ["50%", "60%"],
                "radius": "80%",
                "startAngle": 220, "endAngle": -40,
                "min": 0, "max": max_val,
                "progress": {"show": True, "width": 12, "itemStyle": {"color": {"type": "linear", "x": 0, "y": 0, "x2": 1, "y2": 0,
                    "colorStops": [{"offset": 0, "color": colors[0]}, {"offset": 1, "color": colors[1]}]}}},
                "pointer": {"show": True, "length": "60%", "width": 4},
                "axisLine": {"lineStyle": {"width": 12, "color": [[1, theme["border"]]]}},
                "axisTick": {"length": 6, "lineStyle": {"color": theme["text_chart"]}},
                "splitLine": {"length": 10, "lineStyle": {"color": theme["text_chart"]}},
                "axisLabel": {"color": theme["text_chart"], "distance": 20},
                "detail": {"valueAnimation": True, "formatter": "{value}%", "color": theme["text"], "fontSize": 28, "fontWeight": "bold", "offsetCenter": [0, "40%"]},
                "data": [{"value": value, "name": name}],
                **ChartBuilder.get_animation_config(),
            }],
        }
        return option

    @staticmethod
    def treemap(data: dict, theme: dict, colors: List[str]) -> dict:
        """树图（适合多层构成展示）。"""
        option = {
            "tooltip": {"formatter": "{b}: {c}", "backgroundColor": "rgba(255,255,255,0.95)"},
            "series": [{
                "type": "treemap",
                "data": data.get("data", []),
                "width": "100%", "height": "100%",
                "roam": True,
                "leafDepth": data.get("depth", 1),
                "drillDownIcon": "▶",
                "label": {"show": True, "formatter": "{b}", "color": "#fff", "fontSize": 12},
                "itemStyle": {"borderColor": theme["card_bg"], "borderWidth": 2},
                "levels": [{"colorSaturation": [0.3, 0.6], "itemStyle": {"borderColor": theme["card_bg"], "borderWidth": 2, "gapWidth": 1}}],
                **ChartBuilder.get_animation_config(),
            }],
            "color": colors,
        }
        return option

    @staticmethod
    def word_cloud(data: dict, theme: dict, colors: List[str]) -> dict:
        """词云（文本数据可视化）。"""
        items = data.get("data", [])
        option = {
            "tooltip": {"formatter": "{b}: {c}"},
            "series": [{
                "type": "wordCloud",
                "gridSize": 10, "sizeRange": [12, 50],
                "rotationRange": [-45, 45], "shape": "circle",
                "width": "100%", "height": "100%",
                "data": items,
            }],
        }
        return option

    @staticmethod
    def build(data: dict, theme: dict, colors: List[str]) -> dict:
        """
        工厂方法——根据 chart_type 自动选择对应的图表构建器。
        支持扩展现有图表类型。
        """
        builders = {
            "line": ChartBuilder.line,
            "area": ChartBuilder.line,
            "bar": ChartBuilder.bar,
            "horizontal_bar": ChartBuilder.horizontal_bar,
            "stacked_bar": ChartBuilder.stacked_bar,
            "pie": ChartBuilder.pie,
            "ring": ChartBuilder.pie,
            "funnel": ChartBuilder.funnel,
            "radar": ChartBuilder.radar,
            "scatter": ChartBuilder.scatter,
            "heatmap": ChartBuilder.heatmap,
            "sankey": ChartBuilder.sankey,
            "gauge": ChartBuilder.gauge,
            "treemap": ChartBuilder.treemap,
            "word_cloud": ChartBuilder.word_cloud,
        }
        chart_type = data.get("chart_type", "bar")
        builder = builders.get(chart_type, builders["bar"])
        return builder(data, theme, colors)


class RenderEngine:
    """
    ECharts 渲染引擎。
    
    特点：
    - 15+ 图表类型支持
    - 5 套预设商务配色 + 自定义主题
    - 丝滑动画过渡
    - 响应式布局
    - Tooltip/图例切换/数据缩放等交互全开
    """

    def __init__(self, theme_name: str = "", inline_assets: bool = True):
        """
        初始化渲染引擎。

        参数:
            theme_name: 风格编号（留空取资产库默认风格）
            inline_assets: 是否把 ECharts 内联进 HTML。默认 True —— 保证报表
                离线可打开（投屏、邮件、内网）。设为 False 则用 CDN 引用，文件更小但需联网。
        """
        self.theme = ColorTheme.get(theme_name)
        self.theme_name = self.theme.get("name") or (theme_name or ColorTheme.FALLBACK)
        self.inline_assets = inline_assets
        # 元素 id 序号：同一份报表里若两个图表的数据完全相同，
        # 纯按数据 hash 生成 id 会撞车（后一个 echarts.init 拿到同一个 DOM）。
        self._el_seq = 0

    def _echarts_tag(self) -> str:
        """ECharts 的 script 标签（内联 or CDN）。"""
        return echarts_script_tag(inline=self.inline_assets)

    def _next_el_id(self, prefix: str, seed: Any = "") -> str:
        """生成报表内唯一的元素 id（数据指纹 + 递增序号）。"""
        self._el_seq += 1
        try:
            digest = abs(hash(json.dumps(seed, sort_keys=True, default=str))) % 10000
        except Exception:
            digest = 0
        return f"{prefix}_{digest}_{self._el_seq}"

    def render_web_dashboard(self, layout: Dict) -> str:
        """
        生成交互式Web看板HTML（v3.0 增强版：支持分区/模块化布局）。

        参数:
            layout: 布局配置，包含 sections 列表
                sections[].type: kpi_cards / chart / conclusion / table / section_group / custom
                sections[].type == "section_group"（分区容器，v3.0 新增）:
                    - title: 分区标题（如"销售概览"）
                    - description: 分区描述（1-2 句话，展示在标题下方）
                    - columns: 该分区网格列数（默认 3，主图可设 2）
                    - items: 子 section 列表（chart/table/conclusion）
                sections[].type == "chart"（v3.0 增强）:
                    - span: 占几列（默认 1，主图可设 2 或 "full"）
                    - description: 该图表的数据解读文字（v3.0 新增，展示在图表下方）
                    - insight_level: 解读级别（"核心"/"机会"/"风险"/"基础"），影响标签颜色
        返回:
            完整 HTML 字符串
        """
        sections_html = ""
        chart_scripts = ""

        for section in layout.get("sections", []):
            section_type = section.get("type", "")
            if section_type == "kpi_cards":
                sections_html += self._render_kpi_cards(section.get("metrics", []))
            elif section_type == "section_group":
                # v3.0 新增：分区容器，渲染标题+描述+子图表网格
                sections_html += self._render_section_group(section, chart_scripts_collector := [])
                for s in chart_scripts_collector:
                    chart_scripts += s
            elif section_type == "chart":
                html, script = self._render_chart(section)
                sections_html += html
                chart_scripts += script
            elif section_type == "conclusion":
                sections_html += self._render_conclusion(
                    section.get("insights", []), section.get("title", "数据洞察"))
            elif section_type == "prose":
                sections_html += self._render_prose(section)
            elif section_type == "table":
                sections_html += self._render_table(section)
            elif section_type == "custom":
                sections_html += section.get("html", "")

        # 统计图表数量用于布局
        chart_count = sum(1 for s in layout.get("sections", []) if s.get("type") == "chart")
        chart_count += sum(
            1 for s in layout.get("sections", [])
            if s.get("type") == "section_group"
            for _ in s.get("items", [])
            if _.get("type") == "chart"
        )

        # 有封面板块（B01）时不渲染顶部 header：
        # 否则第一屏会出现两次标题（header 的 h1 与封面板块 h2 同名），
        # 数据源信息也会重复（header 的 meta 与封面的 eyebrow）。
        has_cover = any(
            s.get("type") == "prose" and s.get("variant") == "cover"
            for s in layout.get("sections", [])
        )
        html = self._build_html_template(
            title=layout.get("title", "数据报表"),
            meta=layout.get("generated_at", ""),
            sections_html=sections_html,
            chart_scripts=chart_scripts,
            chart_count=chart_count,
            has_cover=has_cover,
        )
        return html

    def _render_section_group(self, group: Dict, script_collector: list) -> str:
        """
        渲染分区容器（v3.0 新增）。
        每个分区有标题、描述、列数配置，内部包含多个图表/表格。
        支持"便当盒网格"：子项可指定 span 占多列。
        """
        t = self.theme
        title = group.get("title", "")
        description = group.get("description", "")
        columns = group.get("columns", 3)
        items = group.get("items", [])

        # 限制列数在 1-4 之间
        columns = max(1, min(4, int(columns)))

        # 构建子项 HTML
        items_html = ""
        for item in items:
            item_type = item.get("type", "")
            if item_type == "chart":
                html, script = self._render_chart(item)
                items_html += html
                script_collector.append(script)
            elif item_type == "table":
                items_html += self._render_table(item)
            elif item_type == "conclusion":
                items_html += self._render_conclusion(
                    item.get("insights", []), item.get("title", "数据洞察"))
            elif item_type == "prose":
                items_html += self._render_prose(item)
            elif item_type == "custom":
                items_html += item.get("html", "")

        # 分区标题和描述
        header_html = ""
        if title:
            header_html = f"""
        <div class="section-header">
            <h2 class="section-title">{title}</h2>
            {f'<p class="section-desc">{description}</p>' if description else ''}
        </div>"""

        return f"""
    <section class="section-group" style="--group-cols:{columns}">
        {header_html}
        <div class="section-grid">
            {items_html}
        </div>
    </section>"""

    def _build_html_template(self, title: str, meta: str, sections_html: str,
                              chart_scripts: str, chart_count: int,
                              has_cover: bool = False) -> str:
        """构建完整 HTML 页面（风格 token 来自资产层 + prose 板块 + 密度感知间距）。"""
        t = self.theme
        gap = t.get("gap", 20)
        pad = t.get("pad", 24)
        echarts_tag = self._echarts_tag()

        # has_cover 为真时省略 header —— 封面板块自己就是标题区
        header_html = "" if has_cover else f"""
        <div class="header">
            <h1>{title}</h1>
            <div class="meta">{meta}</div>
            <div class="divider"></div>
        </div>"""

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    {echarts_tag}
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'PingFang SC', 'Microsoft YaHei', -apple-system, sans-serif;
               background: {t['bg']}; color: {t['text']};
               --pad: {pad}px; }}
        .dashboard {{ max-width: 1440px; margin: 0 auto; padding: 32px 32px 64px; }}
        .header {{ text-align: center; padding: 24px 0 32px; }}
        .header h1 {{ font-size: 28px; color: {t['primary'][0]}; letter-spacing: 1px; }}
        .header .meta {{ color: {t['text_secondary']}; font-size: 14px; margin-top: 8px; }}
        .header .divider {{ width: 60px; height: 3px; background: linear-gradient(90deg, {t['gradient'][0]}, {t['gradient'][1]});
                           margin: 16px auto 0; border-radius: 2px; }}
        /* KPI 卡片 */
        .kpi-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                    gap: 16px; margin-bottom: 28px; }}
        .kpi-card {{ background: {t['card_bg']}; border-radius: 14px; padding: 22px 24px;
                     box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 4px 16px rgba(0,0,0,0.04);
                     transition: transform 0.25s ease, box-shadow 0.25s ease;
                     border-top: 3px solid {t['primary'][0]}; }}
        .kpi-card:hover {{ transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.08), 0 8px 24px rgba(0,0,0,0.06); }}
        .kpi-card .label {{ font-size: 13px; color: {t['text_secondary']}; margin-bottom: 6px;
                           text-transform: uppercase; letter-spacing: 0.5px; }}
        .kpi-card .value {{ font-size: 32px; font-weight: 700; color: {t['text']};
                            font-family: 'Inter', 'Helvetica Neue', sans-serif; margin: 6px 0 8px; }}
        .kpi-card .change {{ font-size: 13px; display: flex; align-items: center; gap: 4px; }}
        .kpi-card .change.up {{ color: #32D74B; }}
        .kpi-card .change.down {{ color: #FF453A; }}

        /* v3.0 分区容器（section_group）— 便当盒网格 */
        .section-group {{ margin-bottom: 36px; }}
        .section-header {{ margin-bottom: 16px; padding-left: 4px; }}
        .section-title {{ font-size: 20px; font-weight: 700; color: {t['text']};
                          display: flex; align-items: center; gap: 10px; }}
        .section-title::before {{ content: ""; display: inline-block; width: 4px; height: 22px;
                                   border-radius: 2px; background: linear-gradient(180deg, {t['gradient'][0]}, {t['gradient'][1]}); }}
        .section-desc {{ font-size: 14px; color: {t['text_secondary']}; margin-top: 6px; margin-left: 14px; line-height: 1.6; }}
        .section-grid {{ display: grid; grid-template-columns: repeat(var(--group-cols, 3), 1fr); gap: 18px; }}

        /* 图表卡片 — 支持 span 跨列 */
        .chart-box {{ background: {t['card_bg']}; border-radius: 14px; padding: 18px 20px;
                      box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 4px 16px rgba(0,0,0,0.04);
                      display: flex; flex-direction: column; }}
        .chart-box[data-span="2"] {{ grid-column: span 2; }}
        .chart-box[data-span="3"] {{ grid-column: span 3; }}
        .chart-box[data-span="full"] {{ grid-column: 1 / -1; }}
        .chart-box .chart-title {{ font-size: 15px; font-weight: 600; margin-bottom: 12px;
                                   color: {t['text']}; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
        .chart-container {{ width: 100%; height: 340px; }}
        .chart-box[data-span="2"] .chart-container {{ height: 380px; }}
        .chart-box[data-span="full"] .chart-container {{ height: 420px; }}

        /* v3.0 数据解读区 — 每个图表下方的分析文字 */
        .chart-insight {{ margin-top: 12px; padding: 10px 14px; border-radius: 8px;
                          font-size: 13px; line-height: 1.65; color: {t['text_secondary']};
                          border-left: 3px solid {t['primary'][0]};
                          background: {t['bg']}; }}
        .chart-insight[data-level="核心"] {{ border-left-color: {t['primary'][0]}; background: {t['primary'][0]}0D; }}
        .chart-insight[data-level="机会"] {{ border-left-color: #32D74B; background: #32D74B0D; }}
        .chart-insight[data-level="风险"] {{ border-left-color: #FF453A; background: #FF453A0D; }}
        .chart-insight[data-level="基础"] {{ border-left-color: {t['text_secondary']}; }}
        .insight-tag {{ display: inline-block; padding: 1px 8px; border-radius: 10px;
                        font-size: 11px; font-weight: 600; margin-right: 6px; vertical-align: middle; }}
        .insight-tag[data-level="核心"] {{ background: {t['primary'][0]}; color: #fff; }}
        .insight-tag[data-level="机会"] {{ background: #32D74B; color: #fff; }}
        .insight-tag[data-level="风险"] {{ background: #FF453A; color: #fff; }}
        .insight-tag[data-level="基础"] {{ background: {t['text_secondary']}; color: #fff; }}

        /* 兼容旧版 .chart-grid（非分区模式） */
        .chart-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 18px; margin-bottom: 28px; }}
        @media (max-width: 900px) {{ .chart-grid {{ grid-template-columns: 1fr; }}
                                      .section-grid {{ grid-template-columns: 1fr !important; }}
                                      .chart-box[data-span="2"], .chart-box[data-span="3"], .chart-box[data-span="full"] {{ grid-column: 1; }}
                                      .dashboard {{ padding: 16px; }} }}

        /* 明细表格 */
        .table-wrapper {{ background: {t['card_bg']}; border-radius: 14px; margin-bottom: 20px;
                          box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 4px 16px rgba(0,0,0,0.04); overflow: hidden; }}
        .table-header {{ display: flex; align-items: center; padding: 14px 20px; cursor: pointer; user-select: none; transition: background 0.2s; gap: 12px; }}
        .table-header:hover {{ background: {t['bg']}; }}
        .table-title {{ font-size: 15px; font-weight: 600; color: {t['text']}; flex: 1; }}
        .table-meta {{ font-size: 12px; color: {t['text_secondary']}; }}
        .table-toggle {{ font-size: 13px; color: {t['primary'][0]}; font-weight: 500; }}
        .table-container {{ padding: 0 20px 16px; }}
        .table-scroll {{ overflow-x: auto; max-height: 480px; overflow-y: auto; border: 1px solid {t['border']}; border-radius: 8px; }}
        .detail-table {{ width: 100%; table-layout: fixed !important; border-collapse: collapse; font-size: 13px; }}
        .detail-table thead {{ position: sticky; top: 0; z-index: 2; }}
        .detail-table th {{ background: {t['bg']}; color: {t['text']}; font-weight: 600; padding: 10px 12px; text-align: left; border-bottom: 2px solid {t['border']}; white-space: nowrap; }}
        .detail-table td {{ padding: 8px 12px; border-bottom: 1px solid {t['border']}; color: {t['text']}; word-break: break-word; }}
        .detail-table tbody tr:hover {{ background: {t['primary'][0]}08; }}
        .detail-table tbody tr:nth-child(even) {{ background: {t['bg']}; }}

        /* 结论区 */
        .conclusion {{ background: {t['card_bg']}; border-radius: 14px; padding: 24px;
                       box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 4px 16px rgba(0,0,0,0.04);
                       margin-bottom: 20px; }}
        .conclusion h3 {{ font-size: 16px; font-weight: 600; margin-bottom: 14px; color: {t['text']}; display: flex; align-items: center; gap: 10px; }}
        .conclusion-bar {{ display: inline-block; width: 4px; height: 18px; border-radius: 2px;
                          background: linear-gradient(180deg, {t['gradient'][0]}, {t['gradient'][1]}); }}
        .conclusion ul {{ list-style: none; }}
        .conclusion li {{ padding: 10px 0; border-bottom: 1px solid {t['border']};
                         color: {t['text']}; display: flex; align-items: flex-start; gap: 8px; line-height: 1.6; }}
        .conclusion li:last-child {{ border-bottom: none; }}
        .conclusion li::before {{ content: "—"; color: {t['primary'][0]}; font-size: 14px; flex-shrink: 0; }}

        /* 通用文本板块（prose）——承载封面/摘要/目录/风险机会/口径/方法论/附录/结尾 */
        .prose-block {{ background: {t['card_bg']}; border-radius: 14px; padding: var(--pad, 24px);
                        box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 4px 16px rgba(0,0,0,0.04);
                        margin-bottom: {gap}px; }}
        .prose-block.plain {{ background: transparent; box-shadow: none; padding: 0; }}
        .prose-eyebrow {{ display: inline-block; font-size: 12px; letter-spacing: .08em;
                          color: {t['text_secondary']}; margin-bottom: 8px; }}
        .prose-title {{ font-size: 20px; font-weight: 700; color: {t['text']};
                        display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }}
        .prose-title::before {{ content: ""; display: inline-block; width: 4px; height: 20px;
                                 border-radius: 2px; background: {t['primary'][0]}; }}
        .prose-body {{ font-size: 15px; line-height: 1.75; color: {t['text']}; }}
        .prose-body p {{ margin-bottom: 10px; }}
        .prose-body p:last-child {{ margin-bottom: 0; }}
        .prose-body ol, .prose-body ul {{ padding-left: 22px; }}
        .prose-body li {{ margin-bottom: 8px; }}
        .prose-body .muted {{ color: {t['text_secondary']}; font-size: 13px; }}
        .prose-cols {{ display: grid; grid-template-columns: repeat(var(--prose-cols, 1), 1fr);
                       gap: {gap}px; }}
        .prose-badge {{ display: inline-block; font-size: 12px; padding: 2px 10px; border-radius: 999px;
                        background: {t['bg']}; border: 1px solid {t['border']};
                        color: {t['text_secondary']}; margin-right: 8px; }}
        .prose-cover {{ text-align: center; }}
        .prose-cover .prose-title {{ justify-content: center; font-size: 28px; }}
        .prose-cover .prose-title::before {{ display: none; }}

        @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}
        .kpi-row {{ animation: fadeIn 0.5s ease-out; }}
        .section-group {{ animation: fadeIn 0.6s ease-out; }}
        .chart-box {{ animation: fadeIn 0.6s ease-out; }}
        .conclusion {{ animation: fadeIn 0.7s ease-out; }}
        .prose-block {{ animation: fadeIn 0.7s ease-out; }}
        @media (max-width: 900px) {{ .prose-cols {{ grid-template-columns: 1fr !important; }} }}
    </style>
</head>
<body>
    <div class="dashboard">{header_html}
        {sections_html}
    </div>
    <script>
        document.addEventListener('DOMContentLoaded', function() {{
            setTimeout(function() {{
                {chart_scripts}
            }}, 100);
        }});
        var resizeTimer;
        window.addEventListener('resize', function() {{
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(function() {{
                document.querySelectorAll('.chart-container').forEach(function(el) {{
                    var chart = echarts.getInstanceByDom(el);
                    if (chart) chart.resize();
                }});
            }}, 200);
        }});
    </script>
</body>
</html>"""

    def _render_kpi_cards(self, metrics: List[Dict]) -> str:
        """渲染 KPI 卡片行（带动画渐入效果）。"""
        cards = ""
        for i, m in enumerate(metrics):
            change_val = m.get("change", 0)
            change_class = "up" if change_val >= 0 else "down"
            change_sign = "+" if change_val >= 0 else ""
            value = m.get('value', 0)
            # v3.1：字符串值（如日期/名称）不做千分位格式化，避免 ValueError
            if isinstance(value, (int, float)):
                value_str = f"{value:,}"
            else:
                value_str = str(value)
            cards += f"""
        <div class="kpi-card" style="animation-delay: {i*0.1}s;">
            <div class="label">{m.get('label', '')}</div>
            <div class="value">{value_str}</div>
            <div class="change {change_class}">{change_sign}{change_val*100:.1f}% vs 同期</div>
        </div>"""
        return f'<div class="kpi-row">{cards}</div>'

    def _render_chart(self, section: Dict) -> tuple:
        """
        渲染单个图表，返回 (html, script) 元组（v3.0 增强：span 跨列 + 数据解读区）。
        使用 ChartBuilder 构建 ECharts option，支持 15+ 图表类型。
        """
        chart_id = self._next_el_id("chart", section.get("data", {}))
        chart_type = section.get("chart_type", "bar")
        data = section.get("data", {})
        data["chart_type"] = chart_type

        # 通过 ChartBuilder 工厂构建 option
        colors = ColorTheme.build_series_colors(self.theme, 12)
        option = ChartBuilder.build(data, self.theme, colors)

        # 图表中文名称映射
        chart_labels = {"line": "趋势图", "bar": "对比图", "horizontal_bar": "排名图",
            "stacked_bar": "堆叠图", "pie": "占比图", "ring": "环形图",
            "funnel": "漏斗图", "radar": "雷达图", "scatter": "散点图",
            "heatmap": "热力图", "sankey": "桑基图", "gauge": "仪表盘",
            "treemap": "树图", "word_cloud": "词云"}

        # v3.0 span 跨列支持（便当盒网格）
        span = section.get("span", 1)
        span_attr = f' data-span="{span}"' if span != 1 else ""

        # v3.0 数据解读区（每个图表下方的分析文字）
        description = section.get("description", "")
        insight_level = section.get("insight_level", "基础")
        insight_html = ""
        if description:
            insight_html = f"""
            <div class="chart-insight" data-level="{insight_level}">
                <span class="insight-tag" data-level="{insight_level}">{insight_level}</span>{description}
            </div>"""

        html = f"""
        <div class="chart-box"{span_attr} style="animation-delay: {section.get('_delay', 0.2)}s;">
            <div class="chart-title">
                <span>{chart_labels.get(chart_type, '图表')}</span>
                <span style="font-weight:400;font-size:13px;color:{self.theme['text_secondary']};">{section.get('title', '')}</span>
            </div>
            <div id="{chart_id}" class="chart-container"></div>
            {insight_html}
        </div>"""

        option_json = json.dumps(option, ensure_ascii=False)
        script = f"""
        (function() {{
            var dom = document.getElementById('{chart_id}');
            if (!dom) return;
            var chart = echarts.init(dom, null, {{renderer: 'canvas'}});
            chart.setOption({option_json});
            dom.addEventListener('dblclick', function() {{
                if (document.fullscreenElement) {{
                    document.exitFullscreen();
                }} else {{
                    dom.parentElement.requestFullscreen().catch(function(){{}});
                }}
            }});
            window.addEventListener('resize', function() {{ chart.resize(); }});
        }})();
        """
        return html, script

    def _render_conclusion(self, insights: List[str], title: str = "数据洞察") -> str:
        """渲染数据结论区域（使用主题色装饰，无emoji）。"""
        items = "".join([f"<li>{i}</li>" for i in insights])
        return f"""
        <div class="conclusion">
            <h3><span class="conclusion-bar"></span>{title}</h3>
            <ul>{items}</ul>
        </div>"""

    def _render_prose(self, section: Dict) -> str:
        """
        渲染结构化文本板块（v4.0 新增）。

        承载板块库中 11 个非图表板块：封面页 / 执行摘要 / 目录导航 /
        风险与机会 / 口径定义 / 数据质量 / 分析方法论 / 附录 / 结尾。

        section 格式：
            {
              "type": "prose",
              "title": "执行摘要",
              "eyebrow": "01 / 摘要",            # 可选，标题上方小标签
              "badge": "必需",                    # 可选，标题右侧标记
              "variant": "cover" | "plain",        # 可选，封面居中 / 无卡片底
              "body": "第一段\n\n第二段",          # 可选，按空行分段
              "items": ["条目", {"text": "...", "badge": "高"}],   # 可选，有序列表
              "panels": [{"title": "风险", "items": ["..."]}],     # 可选，多栏并列
              "columns": 2                        # 可选，panels 的栏数，默认 2
            }
        """
        variant = section.get("variant", "")
        classes = ["prose-block"]
        if variant == "plain":
            classes.append("plain")
        elif variant == "cover":
            classes.append("prose-cover")

        title = section.get("title", "")
        eyebrow = section.get("eyebrow", "")
        badge = section.get("badge", "")

        head = ""
        if eyebrow:
            head += f'<span class="prose-eyebrow">{eyebrow}</span>'
        if title:
            badge_html = f'<span class="prose-badge">{badge}</span>' if badge else ""
            head += f'<h2 class="prose-title">{title}{badge_html}</h2>'

        body_html = ""
        raw_body = section.get("body", "")
        if raw_body:
            paras = [p.strip() for p in str(raw_body).split("\n") if p.strip()]
            body_html += "".join(f"<p>{p}</p>" for p in paras)

        items = section.get("items") or []
        if items:
            lis = []
            for it in items:
                if isinstance(it, dict):
                    badge_it = f'<span class="prose-badge">{it["badge"]}</span>' \
                        if it.get("badge") else ""
                    lis.append(f'<li>{badge_it}{it.get("text", "")}</li>')
                else:
                    lis.append(f"<li>{it}</li>")
            body_html += f"<ol>{''.join(lis)}</ol>"

        panels = section.get("panels") or []
        panels_html = ""
        if panels:
            cols = max(1, min(4, int(section.get("columns", len(panels)))))
            cards = []
            for p in panels:
                plis = "".join(
                    f"<li>{x.get('text', '') if isinstance(x, dict) else x}</li>"
                    for x in (p.get("items") or [])
                )
                pt = f'<h3 class="prose-title" style="font-size:16px">{p.get("title", "")}</h3>' \
                    if p.get("title") else ""
                cards.append(f"<div>{pt}<ul>{plis}</ul></div>")
            panels_html = (f'<div class="prose-cols" style="--prose-cols:{cols}">'
                           f'{"".join(cards)}</div>')

        inner = body_html + panels_html
        if not inner:
            inner = '<p class="muted">（本节暂无内容）</p>'

        return (f'\n    <section class="{" ".join(classes)}">'
                f'{head}<div class="prose-body">{inner}</div></section>')

    def _render_table(self, section: dict) -> str:
        """
        渲染明细表格。
        不硬编码列宽——让浏览器根据内容自动分配宽度。
        不截断数据——如果某行列数多于表头，自动扩展表头。

        section 格式:
        {
            "type": "table",
            "title": "xxx",           # 表格标题
            "columns": ["A","B","C"], # 表头列名（可选，缺省则从 rows[0] 推断）
            "rows": [["a1","b1"], ...],  # 数据行
            "collapsible": true,      # 是否可折叠（默认true）
        }
        """
        columns = list(section.get("columns", []))
        rows = list(section.get("rows", []))
        title = section.get("title", "明细数据")
        collapsible = section.get("collapsible", True)
        table_id = self._next_el_id("table", title)

        # 如果没给表头，从第一行数据推断
        if not columns and rows:
            columns = [str(c) for c in rows[0]]
            rows = rows[1:]

        # 统计每列最多需要多少列（不要截断数据）
        max_cols = len(columns)
        for row in rows:
            if len(row) > max_cols:
                max_cols = len(row)
                # 扩展表头（用"列N"补位，不硬编码列名）
                for i in range(len(columns), max_cols):
                    columns.append(f"列{i+1}")

        # 构建表头——不设固定宽度，由内容自适应
        thead = "<tr>" + "".join(f'<th>{col}</th>' for col in columns) + "</tr>"

        # 构建数据行——每行列数不足时用空字符串补位
        tbody = ""
        for row in rows:
            padded = list(row) + [""] * (max_cols - len(row))
            cells = "".join(f"<td>{c}</td>" for c in padded[:max_cols])
            tbody += f"<tr>{cells}</tr>"

        display_style = "display: none;" if collapsible else ""

        return f"""
        <div class="table-wrapper">
            <div class="table-header" onclick="toggleTable('{table_id}')">
                <span class="table-title">{title}</span>
                <span class="table-meta">共 {len(rows)} 条记录 · {max_cols} 列</span>
                <span class="table-toggle" id="{table_id}_toggle">{'▶ 展开' if collapsible else ''}</span>
            </div>
            <div id="{table_id}_container" class="table-container" style="{display_style}">
                <div class="table-scroll">
                    <table class="detail-table" id="{table_id}">
                        <thead>{thead}</thead>
                        <tbody>{tbody}</tbody>
                    </table>
                </div>
            </div>
        </div>
        <script>
        (function() {{
            window.toggleTable = function(id) {{
                var c = document.getElementById(id+'_container');
                var t = document.getElementById(id+'_toggle');
                if (c.style.display === 'none') {{
                    c.style.display = 'block';
                    if (t) t.textContent = '▼ 收起';
                }} else {{
                    c.style.display = 'none';
                    if (t) t.textContent = '▶ 展开';
                }}
            }};
        }})();
        </script>"""

    def render_offline_html(self, layout: Dict) -> str:
        """生成离线HTML（单文件，ECharts通过CDN加载）。"""
        return self.render_web_dashboard(layout)

    def export_pdf(self, html: str) -> bytes:
        """导出PDF（占位实现，实际对接Playwright）。"""
        return html.encode('utf-8')

    def export_png(self, html: str) -> bytes:
        """导出PNG（占位实现，实际对接Playwright截图）。"""
        return html.encode('utf-8')

    def set_theme(self, theme_name: str):
        """动态切换风格。"""
        self.theme = ColorTheme.get(theme_name)
        self.theme_name = self.theme.get("name") or (theme_name or ColorTheme.FALLBACK)
