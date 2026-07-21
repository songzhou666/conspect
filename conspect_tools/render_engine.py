"""
vision_tools 渲染引擎模块
生成 ECharts HTML 看板，支持多种图表类型、多配色主题、丝滑动画交互

不限制AI发挥——只要传入正确的 layout 配置，渲染引擎就能输出对应图表。
视觉设计师 Agent 负责把控"好看"，本引擎负责"能用"。
"""
from typing import Dict, List, Optional, Any
import json


class ColorTheme:
    """配色主题系统——所有主题都是精心调试过的商业级配色。"""

    # ===== 5 套预设高级配色 =====
    THEMES = {
        "ocean": {      # 沧海商务：沉稳专业，适合金融/科技/正式汇报
            "primary": ["#2B4C8C", "#4A7CF7", "#6EA8FE"],
            "secondary": ["#6FC3A0", "#F5A623", "#E86868", "#8B6CD6"],
            "bg": "#F7FAFC", "card_bg": "#FFFFFF",
            "text": "#1A202C", "text_secondary": "#718096",
            "border": "#E2E8F0",
            "gradient": ["#2B4C8C", "#4A7CF7"],
        },
        "warm": {       # 朝霞温暖：亲和商务，适合消费/零售/运营
            "primary": ["#D46B4A", "#F09B6A", "#F5B78A"],
            "secondary": ["#5BA3A0", "#C49B6C", "#B45A5A", "#8FA87A"],
            "bg": "#FDF8F3", "card_bg": "#FFFFFF",
            "text": "#2D221C", "text_secondary": "#8B7D72",
            "border": "#EDE0D4",
            "gradient": ["#D46B4A", "#F09B6A"],
        },
        "aurora": {     # 极光科技：炫酷科技，适合互联网/大屏/创新
            "primary": ["#0F172A", "#1E3A5F", "#2563EB"],
            "secondary": ["#38BDF8", "#2DD4BF", "#F472B6", "#A78BFA"],
            "bg": "#0A0F1E", "card_bg": "#1A2332",
            "text": "#E2E8F0", "text_secondary": "#94A3B8",
            "border": "#2D3A4A",
            "gradient": ["#0F172A", "#2563EB"],
        },
        "forest": {     # 森林雅致：清新自然，适合环保/健康/教育
            "primary": ["#2D6A4F", "#40916C", "#52B788"],
            "secondary": ["#95D5B2", "#E9C46A", "#D4A373", "#A3B18A"],
            "bg": "#F0F7F4", "card_bg": "#FFFFFF",
            "text": "#1B3A2D", "text_secondary": "#5A7A6A",
            "border": "#D8E6DF",
            "gradient": ["#2D6A4F", "#52B788"],
        },
        "minimal": {    # 极简商务：极致简约，适合高管汇报/战略会议
            "primary": ["#1A1A2E", "#16213E", "#2D3748"],
            "secondary": ["#E2E8F0", "#A0AEC0", "#CBD5E0", "#718096"],
            "bg": "#FFFFFF", "card_bg": "#F8F9FA",
            "text": "#1A202C", "text_secondary": "#718096",
            "border": "#E2E8F0",
            "gradient": ["#1A1A2E", "#2D3748"],
        },
    }

    @classmethod
    def get(cls, name: str = "ocean") -> dict:
        """获取主题配置。"""
        return cls.THEMES.get(name, cls.THEMES["ocean"])

    @classmethod
    def list_themes(cls) -> List[str]:
        """列出所有可用主题。"""
        return list(cls.THEMES.keys())

    @classmethod
    def build_series_colors(cls, theme: dict, count: int) -> List[str]:
        """根据主题和数据系列数量生成系列色。"""
        all_colors = theme["primary"] + theme["secondary"]
        if count <= len(all_colors):
            return all_colors[:count]
        # 超过预设数量时循环取色并调整透明度
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
            "legend": {"data": data.get("series_names", []), "textStyle": {"color": theme["text_secondary"], "fontSize": 12}, "bottom": 0},
            "grid": {"left": "3%", "right": "4%", "bottom": "15%", "containLabel": True},
            "xAxis": {"type": "category", "data": data.get("x", []), "axisLine": {"lineStyle": {"color": theme["border"]}}, "axisLabel": {"color": theme["text_secondary"]}},
            "yAxis": {"type": "value", "splitLine": {"lineStyle": {"color": theme["border"], "type": "dashed"}}, "axisLabel": {"color": theme["text_secondary"]}},
            "dataZoom": [{"type": "inside", "start": 0, "end": 100}, {"type": "slider", "start": 0, "end": 100, "height": 20, "bottom": 30, "borderColor": theme["border"], "textStyle": {"color": theme["text_secondary"]}}],
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
            "legend": {"data": data.get("series_names", []), "textStyle": {"color": theme["text_secondary"]}},
            "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
            "xAxis": {"type": "category", "data": data.get("x", []), "axisLabel": {"color": theme["text_secondary"]}, "axisLine": {"lineStyle": {"color": theme["border"]}}},
            "yAxis": {"type": "value", "splitLine": {"lineStyle": {"color": theme["border"], "type": "dashed"}}, "axisLabel": {"color": theme["text_secondary"]}},
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
            s["animationDelay"] = lambda idx: idx * 80
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
            "legend": {"data": [i["name"] for i in items], "textStyle": {"color": theme["text_secondary"]}, "type": "scroll", "bottom": 0},
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
            "legend": {"data": [i["name"] for i in items], "textStyle": {"color": theme["text_secondary"]}},
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
            "legend": {"data": [s.get("name", "") for s in series_data], "textStyle": {"color": theme["text_secondary"]}, "bottom": 0},
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
        """散点图/气泡图。"""
        series_data = data.get("data", data.get("series", []))
        option = {
            "color": colors,
            "tooltip": {"trigger": "item", "formatter": "{c}", "backgroundColor": "rgba(255,255,255,0.95)", "borderColor": theme["border"]},
            "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
            "xAxis": {"type": "value", "splitLine": {"lineStyle": {"color": theme["border"], "type": "dashed"}}, "axisLabel": {"color": theme["text_secondary"]}},
            "yAxis": {"type": "value", "splitLine": {"lineStyle": {"color": theme["border"], "type": "dashed"}}, "axisLabel": {"color": theme["text_secondary"]}},
            "series": [{
                "type": "scatter", "data": series_data,
                "symbolSize": lambda v: max(5, min(50, v[2] if len(v) > 2 else 10)),
                "itemStyle": {"shadowBlur": 10, "shadowColor": "rgba(0,0,0,0.1)"},
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
            "xAxis": {"type": "category", "data": data.get("x", []), "splitArea": {"show": True}, "axisLabel": {"color": theme["text_secondary"]}},
            "yAxis": {"type": "category", "data": data.get("y", []), "splitArea": {"show": True}, "axisLabel": {"color": theme["text_secondary"]}},
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
                "axisTick": {"length": 6, "lineStyle": {"color": theme["text_secondary"]}},
                "splitLine": {"length": 10, "lineStyle": {"color": theme["text_secondary"]}},
                "axisLabel": {"color": theme["text_secondary"], "distance": 20},
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
                "textStyle": {"color": lambda p: colors[p.dataIndex % len(colors)]},
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

    def __init__(self, theme_name: str = "ocean"):
        """初始化渲染引擎，指定配色主题。"""
        self.theme_name = theme_name
        self.theme = ColorTheme.get(theme_name)

    def render_web_dashboard(self, layout: Dict) -> str:
        """
        生成交互式Web看板HTML。
        
        参数:
            layout: 布局配置，包含 sections 列表
                sections[].type: kpi_cards / chart / conclusion / custom
                sections[].chart_type: line / bar / pie / funnel / radar / ...
        返回:
            完整 HTML 字符串
        """
        sections_html = ""
        chart_scripts = ""

        for section in layout.get("sections", []):
            section_type = section.get("type", "")
            if section_type == "kpi_cards":
                sections_html += self._render_kpi_cards(section.get("metrics", []))
            elif section_type == "chart":
                html, script = self._render_chart(section)
                sections_html += html
                chart_scripts += script
            elif section_type == "conclusion":
                sections_html += self._render_conclusion(section.get("insights", []))
            elif section_type == "table":
                sections_html += self._render_table(section)
            elif section_type == "custom":
                sections_html += section.get("html", "")

        # 统计图表数量用于布局
        chart_count = sum(1 for s in layout.get("sections", []) if s.get("type") == "chart")

        html = self._build_html_template(
            title=layout.get("title", "数据报表"),
            meta=layout.get("generated_at", ""),
            sections_html=sections_html,
            chart_scripts=chart_scripts,
            chart_count=chart_count,
        )
        return html

    def _build_html_template(self, title: str, meta: str, sections_html: str,
                              chart_scripts: str, chart_count: int) -> str:
        """构建完整 HTML 页面。"""
        t = self.theme
        grid_cols = "1fr 1fr" if chart_count >= 2 else "1fr"

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'PingFang SC', 'Microsoft YaHei', -apple-system, sans-serif;
               background: {t['bg']}; color: {t['text']}; }}
        .dashboard {{ max-width: 1440px; margin: 0 auto; padding: 32px 32px 64px; }}
        .header {{ text-align: center; padding: 24px 0 32px; }}
        .header h1 {{ font-size: 28px; color: {t['primary'][0]}; letter-spacing: 1px; }}
        .header .meta {{ color: {t['text_secondary']}; font-size: 14px; margin-top: 8px; }}
        .header .divider {{ width: 60px; height: 3px; background: linear-gradient(90deg, {t['gradient'][0]}, {t['gradient'][1]});
                           margin: 16px auto 0; border-radius: 2px; }}
        .kpi-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 16px; margin-bottom: 28px; }}
        .kpi-card {{ background: {t['card_bg']}; border-radius: 14px; padding: 22px 24px;
                     box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 4px 16px rgba(0,0,0,0.04);
                     transition: transform 0.25s ease, box-shadow 0.25s ease; }}
        .kpi-card:hover {{ transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.08), 0 8px 24px rgba(0,0,0,0.06); }}
        .kpi-card .label {{ font-size: 13px; color: {t['text_secondary']}; margin-bottom: 6px;
                           text-transform: uppercase; letter-spacing: 0.5px; }}
        .kpi-card .value {{ font-size: 34px; font-weight: 700; color: {t['text']};
                            font-family: 'Inter', 'Helvetica Neue', sans-serif; margin: 6px 0 8px; }}
        .kpi-card .change {{ font-size: 13px; display: flex; align-items: center; gap: 4px; }}
        .kpi-card .change.up {{ color: {t['secondary'][0] if t['secondary'][0].startswith('#6F') else '#6FC3A0'}; }}
        .kpi-card .change.down {{ color: {t['secondary'][2] if len(t['secondary']) > 2 else '#E86868'}; }}
        .chart-grid {{ display: grid; grid-template-columns: {grid_cols}; gap: 20px; margin-bottom: 28px; }}
        @media (max-width: 900px) {{ .chart-grid {{ grid-template-columns: 1fr; }} .dashboard {{ padding: 16px; }} }}
        .chart-box {{ background: {t['card_bg']}; border-radius: 14px; padding: 20px;
                      box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 4px 16px rgba(0,0,0,0.04); }}
        .chart-box .chart-title {{ font-size: 16px; font-weight: 600; margin-bottom: 14px;
                                   color: {t['text']}; display: flex; align-items: center; gap: 8px; }}
        .chart-container {{ width: 100%; height: 380px; }}

        /* 明细表格 — table-layout:fixed 强制列对齐 */
        .table-wrapper {{ background: {t['card_bg']}; border-radius: 14px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 4px 16px rgba(0,0,0,0.04); overflow: hidden; }}
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

        .conclusion {{ background: {t['card_bg']}; border-radius: 14px; padding: 24px;
                       box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 4px 16px rgba(0,0,0,0.04);
                       margin-bottom: 20px; }}
        .conclusion h3 {{ font-size: 16px; font-weight: 600; margin-bottom: 14px; color: {t['text']}; display: flex; align-items: center; gap: 10px; }}
        .conclusion-bar {{ display: inline-block; width: 4px; height: 18px; border-radius: 2px;
                          background: linear-gradient(180deg, {t['gradient'][0]}, {t['gradient'][1]}); }}
        .conclusion ul {{ list-style: none; }}
        .conclusion li {{ padding: 10px 0; border-bottom: 1px solid {t['border']};
                         color: {t['text']}; display: flex; align-items: center; gap: 8px; }}
        .conclusion li:last-child {{ border-bottom: none; }}
        .conclusion li::before {{ content: "✦"; color: {t['primary'][0]}; font-size: 12px; }}
        @@keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}
        .kpi-row {{ animation: fadeIn 0.5s ease-out; }}
        .chart-box {{ animation: fadeIn 0.6s ease-out; }}
        .conclusion {{ animation: fadeIn 0.7s ease-out; }}
    </style>
</head>
<body>
    <div class="dashboard">
        <div class="header">
            <h1>{title}</h1>
            <div class="meta">{meta}</div>
            <div class="divider"></div>
        </div>
        {sections_html}
    </div>
    <script>
        // 页面加载完成后初始化图表
        document.addEventListener('DOMContentLoaded', function() {{
            setTimeout(function() {{
                {chart_scripts}
            }}, 100);
        }});
        // 窗口大小变化时自适应
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
            cards += f"""
        <div class="kpi-card" style="animation-delay: {i*0.1}s;">
            <div class="label">{m.get('label', '')}</div>
            <div class="value">{m.get('value', 0):,}</div>
            <div class="change {change_class}">{change_sign}{change_val*100:.1f}% vs 同期</div>
        </div>"""
        return f'<div class="kpi-row">{cards}</div>'

    def _render_chart(self, section: Dict) -> tuple:
        """
        渲染单个图表，返回 (html, script) 元组。
        使用 ChartBuilder 构建 ECharts option，支持 15+ 图表类型。
        """
        chart_id = f"chart_{abs(hash(json.dumps(section.get('data', {}), sort_keys=True))) % 100000}"
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

        html = f"""
        <div class="chart-box" style="animation-delay: {section.get('_delay', 0.2)}s;">
            <div class="chart-title">
                <span>{chart_labels.get(chart_type, '图表')}</span>
                <span style="font-weight:400;font-size:13px;color:{self.theme['text_secondary']};">{section.get('title', '')}</span>
            </div>
            <div id="{chart_id}" class="chart-container"></div>
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

    def _render_conclusion(self, insights: List[str]) -> str:
        """渲染数据结论区域（使用主题色装饰，无emoji）。"""
        items = "".join([f"<li>{i}</li>" for i in insights])
        return f"""
        <div class="conclusion">
            <h3><span class="conclusion-bar"></span>数据洞察</h3>
            <ul>{items}</ul>
        </div>"""

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
        table_id = f"table_{abs(hash(title)) % 100000}"

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
        """动态切换配色主题。"""
        self.theme_name = theme_name
        self.theme = ColorTheme.get(theme_name)
