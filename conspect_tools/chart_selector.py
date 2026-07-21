"""
vision_tools 图表自动选型模块
根据数据特征自动选择最优图表类型
"""
from typing import List, Dict


class ChartConfig:
    """图表配置"""
    def __init__(self, chart_type: str, title: str, data_ref: str, dimension: str):
        self.chart_type = chart_type
        self.title = title
        self.data_ref = data_ref
        self.dimension = dimension


class ChartSelector:
    """图表自动选型器"""

    # 数据特征→图表类型映射规则
    RULES = [
        {"feature": "time_series", "chart": "line", "label": "趋势图"},
        {"feature": "category_compare", "chart": "bar", "label": "对比图"},
        {"feature": "composition", "chart": "pie", "label": "占比图"},
        {"feature": "ranking", "chart": "bar_horizontal", "label": "排名图"},
        {"feature": "correlation", "chart": "scatter", "label": "关联图"},
        {"feature": "kpi", "chart": "kpi_card", "label": "KPI卡片"},
        {"feature": "detail", "chart": "table", "label": "明细表"},
    ]

    def analyze_data_features(self, agg_data: Dict) -> List[ChartConfig]:
        """分析聚合数据的特征并推荐图表。"""
        charts = []

        # 如果有时间维度，推荐折线图
        if agg_data.get("by_dimension"):
            for dim, values in agg_data["by_dimension"].items():
                if "时间" in dim or "月" in dim or "年" in dim:
                    config = ChartConfig(
                        chart_type="line",
                        title=f"{dim}趋势分析",
                        data_ref=dim,
                        dimension=dim
                    )
                    charts.append(config)

        # 如果有分类维度且数据量适中，推荐柱状图
        if agg_data.get("by_dimension"):
            for dim, values in agg_data["by_dimension"].items():
                if dim not in [c.dimension for c in charts]:
                    config = ChartConfig(
                        chart_type="bar",
                        title=f"{dim}对比分析",
                        data_ref=dim,
                        dimension=dim
                    )
                    charts.append(config)

        # 总览KPI卡片
        if agg_data.get("total"):
            for metric, stats in agg_data["total"].items():
                charts.append(ChartConfig(
                    chart_type="kpi_card",
                    title=metric,
                    data_ref=metric,
                    dimension="overview"
                ))

        return charts

    def select_chart_type(self, features: Dict) -> str:
        """根据特征字典选择图表类型。"""
        feature_type = features.get("type", "category_compare")
        for rule in self.RULES:
            if rule["feature"] == feature_type:
                return rule["chart"]
        return "bar"  # 默认柱状图
