"""
vision_tools AI Agent 模块
负责图表选型、洞察生成、质量审核等决策分析工作

核心设计原则：
  - AI Agent 负责所有需要理解和判断的工作
  - CLI 只负责数据加载和简单计算
  - AI 根据数据特征和业务场景进行决策
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ChartDecision:
    """图表选型决策"""
    chart_id: str
    chart_type: str
    title: str
    reason: str
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InsightDecision:
    """洞察生成决策"""
    category: str  # finding/risk/opportunity
    title: str
    description: str
    evidence: str
    severity: str = "info"  # info/warning/critical
    related_metrics: List[str] = field(default_factory=list)


@dataclass
class RecommendationDecision:
    """建议生成决策"""
    title: str
    description: str
    priority: str  # high/medium/low
    expected_impact: str
    related_findings: List[str] = field(default_factory=list)


@dataclass
class ReviewDecision:
    """审核决策"""
    phase: str
    passed: bool
    score: float
    issues: List[Dict[str, Any]] = field(default_factory=list)
    cross_stage_issues: List[Dict[str, Any]] = field(default_factory=list)


class AIAgent:
    """
    AI Agent
    负责图表选型、洞察生成、质量审核等决策分析工作
    
    使用示例:
        agent = AIAgent()
        chart_decision = agent.decide_chart(features, business_context)
        insights = agent.generate_insights(stats, business_context)
        review = agent.review_design(analysis, design)
    """
    
    def __init__(self):
        """初始化 AI Agent"""
        self.chart_rules = self._load_chart_rules()
    
    def _load_chart_rules(self) -> Dict:
        """加载图表选型规则（可作为参考，AI可以灵活调整）"""
        return {
            "time_series": {
                "primary": "line",
                "alternatives": ["area"],
                "reason": "折线图适合展示时间趋势"
            },
            "category_compare": {
                "primary": "bar",
                "alternatives": ["horizontal_bar"],
                "reason": "柱状图适合分类对比"
            },
            "composition": {
                "primary": "pie",
                "alternatives": ["ring", "treemap"],
                "reason": "饼图适合展示占比"
            },
            "distribution": {
                "primary": "histogram",
                "alternatives": ["box"],
                "reason": "直方图适合展示分布"
            },
            "correlation": {
                "primary": "scatter",
                "alternatives": ["heatmap"],
                "reason": "散点图适合展示相关性"
            }
        }
    
    def decide_chart(self, features: Dict[str, Any], 
                     business_context: str = "") -> ChartDecision:
        """
        图表选型决策
        
        参数:
            features: 数据特征（来自 DataFeatureExtractor）
            business_context: 业务场景描述
            
        返回:
            图表选型决策
        """
        # 根据数据特征选择图表类型
        if features.get("has_time_dimension") and features.get("has_numeric_dimension"):
            # 时间序列数据
            time_points = features.get("time_points", 0)
            if time_points > 50:
                chart_type = "area"
                reason = f"时间序列数据点较多（{time_points}个），使用面积图更清晰"
            else:
                chart_type = "line"
                reason = f"时间序列数据，使用折线图展示趋势"
        
        elif features.get("has_category_dimension") and features.get("has_numeric_dimension"):
            # 分类数据
            category_count = features.get("category_count", 0)
            if category_count > 10:
                chart_type = "horizontal_bar"
                reason = f"分类数量较多（{category_count}个），使用横向条形图更清晰"
            elif category_count > 5:
                chart_type = "bar"
                reason = f"分类数量适中（{category_count}个），使用柱状图"
            else:
                chart_type = "pie"
                reason = f"分类数量较少（{category_count}个），使用饼图展示占比"
        
        elif features.get("has_numeric_dimension"):
            # 纯数值数据
            chart_type = "histogram"
            reason = "数值数据，使用直方图展示分布"
        
        else:
            chart_type = "bar"
            reason = "默认使用柱状图"
        
        return ChartDecision(
            chart_id="",
            chart_type=chart_type,
            title="",
            reason=reason,
            config={"features": features}
        )
    
    def generate_insights(self, stats: Dict[str, Any], 
                          business_context: str = "") -> List[InsightDecision]:
        """
        生成洞察
        
        参数:
            stats: 统计数据（来自 DataStatistics）
            business_context: 业务场景描述
            
        返回:
            洞察列表
        """
        insights = []
        
        # 集中度风险洞察
        concentration = stats.get("concentration", {})
        if concentration:
            cr4 = concentration.get("cr4", 0)
            if cr4 > 0.6:
                insights.append(InsightDecision(
                    category="risk",
                    title="集中度风险提示",
                    description=f"Top 4 实体占比 {cr4*100:.1f}%，存在较高的集中度风险",
                    evidence=f"CR4 = {cr4:.4f}",
                    severity="warning",
                    related_metrics=["CR4"]
                ))
            elif cr4 > 0.3:
                insights.append(InsightDecision(
                    category="finding",
                    title="集中度分析",
                    description=f"Top 4 实体占比 {cr4*100:.1f}%，集中度适中",
                    evidence=f"CR4 = {cr4:.4f}",
                    severity="info",
                    related_metrics=["CR4"]
                ))
        
        # 趋势洞察
        trend = stats.get("trend", {})
        if trend:
            direction = trend.get("direction", "持平")
            strength = trend.get("strength", 0)
            
            if direction != "持平" and abs(strength) > 0.05:
                insights.append(InsightDecision(
                    category="finding",
                    title="趋势分析",
                    description=f"当前呈{direction}趋势，趋势强度 {strength*100:.1f}%",
                    evidence=f"趋势强度 = {strength:.4f}",
                    severity="info" if direction == "上升" else "warning",
                    related_metrics=["趋势强度"]
                ))
        
        # 分布洞察
        distribution = stats.get("distribution", {})
        if distribution:
            skewness = distribution.get("skewness", 0)
            if abs(skewness) > 1:
                direction = "右偏" if skewness > 0 else "左偏"
                insights.append(InsightDecision(
                    category="finding",
                    title="分布形态分析",
                    description=f"数据呈{direction}分布（偏度 {skewness:.2f}），少数极端值影响较大",
                    evidence=f"偏度 = {skewness:.4f}",
                    severity="info",
                    related_metrics=["偏度"]
                ))
        
        # 异常洞察
        anomalies = stats.get("anomalies", [])
        if anomalies:
            for anomaly in anomalies[:3]:
                insights.append(InsightDecision(
                    category="risk",
                    title="异常检测",
                    description=f"检测到异常点：{anomaly.get('description', '异常')}",
                    evidence=f"偏差 {anomaly.get('deviation', 0):.2f} 个标准差",
                    severity="warning",
                    related_metrics=[]
                ))
        
        return insights
    
    def generate_recommendations(self, insights: List[InsightDecision], 
                                  business_context: str = "") -> List[RecommendationDecision]:
        """
        生成建议
        
        参数:
            insights: 洞察列表
            business_context: 业务场景描述
            
        返回:
            建议列表
        """
        recommendations = []
        
        for insight in insights:
            if insight.category == "risk" and "集中度" in insight.title:
                recommendations.append(RecommendationDecision(
                    title="分散风险",
                    description="建议拓展业务渠道，降低对头部实体/产品的依赖，分散集中度风险",
                    priority="high",
                    expected_impact="降低集中度风险，提升业务稳定性",
                    related_findings=[insight.title]
                ))
            
            elif insight.category == "risk" and "异常" in insight.title:
                recommendations.append(RecommendationDecision(
                    title="排查异常",
                    description="建议深入排查异常数据点，确认是否为数据错误或特殊事件导致",
                    priority="high",
                    expected_impact="确保数据准确性，排除异常影响",
                    related_findings=[insight.title]
                ))
            
            elif insight.category == "finding" and "上升" in insight.description:
                recommendations.append(RecommendationDecision(
                    title="加大投入",
                    description="当前增长趋势明显，建议加大资源投入，抓住增长机会",
                    priority="medium",
                    expected_impact="提升业务增长",
                    related_findings=[insight.title]
                ))
            
            elif insight.category == "finding" and "下降" in insight.description:
                recommendations.append(RecommendationDecision(
                    title="分析原因",
                    description="当前下降趋势明显，建议深入分析原因，制定应对策略",
                    priority="medium",
                    expected_impact="止住下降趋势",
                    related_findings=[insight.title]
                ))
        
        # 按优先级排序
        priority_order = {"high": 0, "medium": 1, "low": 2}
        recommendations.sort(key=lambda x: priority_order.get(x.priority, 3))
        
        return recommendations
    
    def review_design(self, analysis: Dict, design: Dict) -> ReviewDecision:
        """
        设计阶段审核
        
        参数:
            analysis: 分析结果
            design: 设计文档
            
        返回:
            审核决策
        """
        issues = []
        cross_stage_issues = []
        
        # 1. 图表匹配检查
        recommended_charts = analysis.get("recommended_charts", [])
        designed_charts = design.get("charts", [])
        designed_ids = [c.get("id") for c in designed_charts]
        
        for rec_chart in recommended_charts:
            if rec_chart.get("id") not in designed_ids:
                cross_stage_issues.append({
                    "severity": "P0",
                    "message": f"图表 {rec_chart.get('id')} 未在设计中实现",
                    "fix": f"请补充图表 {rec_chart.get('id')} 的设计",
                    "cross_stage": True,
                    "reference": "analysis.recommended_charts"
                })
        
        # 2. 数据一致检查
        analysis_data = analysis.get("aggregated", {})
        for chart in designed_charts:
            dimension = chart.get("dimension")
            metric = chart.get("metric")
            
            analysis_value = analysis_data.get(dimension, {}).get(metric, {}).get("sum")
            design_value = chart.get("data", {}).get("sum")
            
            if analysis_value is not None and design_value is not None:
                if abs(analysis_value - design_value) / max(abs(analysis_value), 1) > 0.001:
                    cross_stage_issues.append({
                        "severity": "P0",
                        "message": f"图表 {chart.get('id')} 数据与分析结果不一致",
                        "detail": f"分析值：{analysis_value}，设计值：{design_value}",
                        "fix": f"请修正图表 {chart.get('id')} 的数据",
                        "cross_stage": True,
                        "reference": "analysis.aggregated"
                    })
        
        # 计算分数
        score = self._calculate_score(issues, cross_stage_issues)
        passed = score >= 70 and all(i["severity"] != "P0" for i in issues + cross_stage_issues)
        
        return ReviewDecision(
            phase="design",
            passed=passed,
            score=score,
            issues=issues,
            cross_stage_issues=cross_stage_issues
        )
    
    def review_implement(self, design: Dict, implement: Dict) -> ReviewDecision:
        """
        实现阶段审核
        
        参数:
            design: 设计文档
            implement: 实现文档
            
        返回:
            审核决策
        """
        issues = []
        cross_stage_issues = []
        
        # 1. 配色一致检查
        design_colors = design.get("color_scheme", {})
        implement_colors = implement.get("color_scheme", {})
        
        for key, design_color in design_colors.items():
            implement_color = implement_colors.get(key)
            if implement_color and design_color != implement_color:
                cross_stage_issues.append({
                    "severity": "P0",
                    "message": f"配色 {key} 不一致",
                    "detail": f"设计值：{design_color}，实现值：{implement_color}",
                    "fix": f"请将 {key} 的颜色修正为 {design_color}",
                    "cross_stage": True,
                    "reference": "design.color_scheme"
                })
        
        # 2. 图表正确检查
        design_charts = design.get("charts", [])
        implement_charts = implement.get("charts", [])
        implement_ids = [c.get("id") for c in implement_charts]
        
        for design_chart in design_charts:
            chart_id = design_chart.get("id")
            if chart_id not in implement_ids:
                cross_stage_issues.append({
                    "severity": "P0",
                    "message": f"图表 {chart_id} 未实现",
                    "fix": f"请实现图表 {chart_id}",
                    "cross_stage": True,
                    "reference": "design.charts"
                })
        
        # 计算分数
        score = self._calculate_score(issues, cross_stage_issues)
        passed = score >= 70 and all(i["severity"] != "P0" for i in issues + cross_stage_issues)
        
        return ReviewDecision(
            phase="implement",
            passed=passed,
            score=score,
            issues=issues,
            cross_stage_issues=cross_stage_issues
        )
    
    def _calculate_score(self, issues: List[Dict], cross_stage_issues: List[Dict]) -> float:
        """计算审核分数"""
        score = 100
        
        for issue in issues:
            if issue["severity"] == "P0":
                score -= 15
            elif issue["severity"] == "P1":
                score -= 5
        
        for issue in cross_stage_issues:
            if issue["severity"] == "P0":
                score -= 20
            elif issue["severity"] == "P1":
                score -= 10
        
        return max(score, 0)
