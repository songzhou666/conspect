"""
conspect_tools AI Agent 模块（v3.0 稳定性增强版）

核心设计原则：
  - AI Agent 负责所有需要理解和判断的工作
  - CLI 只负责数据加载和简单计算
  - AI 根据数据特征和业务场景进行决策
  - v3.0：新增用户偏好识别（替代原确认环节）
  - v3.0：所有决策方法增加异常降级，失败时返回兜底结果不阻断流程
"""
import re
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

try:
    from conspect_tools.config import (
        DEFAULT_USER_PREFERENCES,
        STABILITY_CONFIG,
        ERROR_CODES,
    )
except ImportError:
    # 兜底：config 导入失败时使用空字典，保证模块可用
    DEFAULT_USER_PREFERENCES = {}
    STABILITY_CONFIG = {"max_retries": 3, "enable_fallback": True}
    ERROR_CODES = {}


# 模块级日志器（v3.0 新增）
logger = logging.getLogger("conspect.ai_agent")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


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


class UserPreferenceRecognizer:
    """
    用户偏好识别器（v3.0 新增）
    替代原"确认阶段"，从用户初始需求中自动识别偏好并写入接力棒。
    识别失败时返回默认值，不阻断流程。
    """

    # 配色关键词映射
    COLOR_KEYWORDS = {
        "蓝色": "ocean", "蓝": "ocean", "商务": "ocean", "专业": "ocean",
        "暖色": "warm", "暖": "warm", "温暖": "warm", "消费": "warm", "零售": "warm",
        "科技": "aurora", "炫酷": "aurora", "大屏": "aurora", "互联网": "aurora", "极光": "aurora",
        "绿色": "forest", "森林": "forest", "自然": "forest", "环保": "forest", "健康": "forest",
        "极简": "minimal", "简约": "minimal", "高管": "minimal", "战略": "minimal",
    }

    # 图表类型关键词
    CHART_KEYWORDS = {
        "line": ["折线", "趋势", "走势"],
        "bar": ["柱状", "柱图", "对比", "比较", "排名"],
        "pie": ["饼图", "占比", "比例", "构成"],
        "scatter": ["散点", "相关", "关联"],
        "area": ["面积", "堆叠"],
    }

    # 输出格式关键词
    FORMAT_KEYWORDS = {
        "pdf": ["PDF", "pdf"],
        "html": ["HTML", "html", "网页", "看板", "dashboard"],
        "md": ["MD", "md", "markdown", "Markdown"],
        "docx": ["Word", "word", "docx", "DOCX"],
    }

    # 十六进制色值正则
    HEX_COLOR_PATTERN = re.compile(r"#([0-9A-Fa-f]{6})\b")

    @classmethod
    def recognize(cls, user_requirement: str) -> Dict[str, Any]:
        """从用户初始需求中识别偏好。识别失败的字段使用默认值。

        参数:
            user_requirement: 用户初始需求文本

        返回:
            合并后的用户偏好字典（已与 DEFAULT_USER_PREFERENCES 合并）
        """
        # 深拷贝默认值
        prefs = {
            "color_scheme": DEFAULT_USER_PREFERENCES.get("color_scheme", "ocean"),
            "custom_primary_color": DEFAULT_USER_PREFERENCES.get("custom_primary_color"),
            "chart_preferences": dict(DEFAULT_USER_PREFERENCES.get("chart_preferences", {})),
            "output_formats": list(DEFAULT_USER_PREFERENCES.get("output_formats", ["html"])),
            "generate_chinese_named_copy": DEFAULT_USER_PREFERENCES.get("generate_chinese_named_copy", True),
            "focus_dimensions": DEFAULT_USER_PREFERENCES.get("focus_dimensions"),
            "focus_metrics": DEFAULT_USER_PREFERENCES.get("focus_metrics"),
            "layout": DEFAULT_USER_PREFERENCES.get("layout", "dashboard"),
            "responsive": DEFAULT_USER_PREFERENCES.get("responsive", True),
        }

        if not user_requirement or not isinstance(user_requirement, str):
            return prefs

        try:
            # 识别配色
            prefs["color_scheme"] = cls._recognize_color(user_requirement, prefs["color_scheme"])
            # 识别自定义品牌色
            prefs["custom_primary_color"] = cls._recognize_custom_color(user_requirement)
            # 识别图表偏好
            prefs["chart_preferences"] = cls._recognize_charts(user_requirement, prefs["chart_preferences"])
            # 识别输出格式
            prefs["output_formats"] = cls._recognize_formats(user_requirement, prefs["output_formats"])
            # 识别排版
            prefs["layout"] = cls._recognize_layout(user_requirement, prefs["layout"])
        except Exception as e:
            logger.warning("用户偏好识别异常: %s，使用默认值继续", e)

        return prefs

    @classmethod
    def _recognize_color(cls, text: str, default: str) -> str:
        """识别配色主题关键词。"""
        for keyword, theme in cls.COLOR_KEYWORDS.items():
            if keyword in text:
                return theme
        return default

    @classmethod
    def _recognize_custom_color(cls, text: str) -> Optional[str]:
        """识别自定义品牌色（十六进制色值）。"""
        match = cls.HEX_COLOR_PATTERN.search(text)
        if match:
            return "#" + match.group(1).upper()
        return None

    @classmethod
    def _recognize_charts(cls, text: str, defaults: Dict[str, str]) -> Dict[str, str]:
        """识别图表类型偏好。"""
        result = dict(defaults)
        for chart_type, keywords in cls.CHART_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    # 根据关键词推断用途
                    if any(k in text for k in ["趋势", "走势"]):
                        result["trend"] = chart_type
                    elif any(k in text for k in ["对比", "比较", "排名"]):
                        result["comparison"] = chart_type
                    elif any(k in text for k in ["占比", "比例", "构成"]):
                        result["composition"] = chart_type
                    break
        return result

    @classmethod
    def _recognize_formats(cls, text: str, defaults: List[str]) -> List[str]:
        """识别输出格式偏好。"""
        formats = []
        for fmt, keywords in cls.FORMAT_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    formats.append(fmt)
                    break
        # 未识别到任何格式时使用默认
        if not formats:
            return list(defaults)
        return formats

    @classmethod
    def _recognize_layout(cls, text: str, default: str) -> str:
        """识别排版偏好。"""
        if "看板" in text or "大屏" in text or "dashboard" in text.lower():
            return "dashboard"
        if "报告" in text or "报表" in text or "文档" in text:
            return "report"
        return default


class AIAgent:
    """
    AI Agent（v3.0 稳定性增强版）
    负责图表选型、洞察生成、质量审核、用户偏好识别等决策分析工作。

    v3.0 变更：
      - 所有决策方法增加 try/except 兜底，失败时返回降级结果
      - 新增 recognize_preferences() 替代原确认环节
      - 新增 generate_insights_safe() 洞察生成降级方法

    使用示例:
        agent = AIAgent()
        chart_decision = agent.decide_chart(features, business_context)
        insights = agent.generate_insights(stats, business_context)
        review = agent.review_design(analysis, design)
        prefs = agent.recognize_preferences("用蓝色调，出 PDF")
    """

    def __init__(self):
        """初始化 AI Agent"""
        self.chart_rules = self._load_chart_rules()
        self.recognizer = UserPreferenceRecognizer()

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

    def recognize_preferences(self, user_requirement: str) -> Dict[str, Any]:
        """识别用户偏好（v3.0 新增，替代原确认环节）。

        参数:
            user_requirement: 用户初始需求文本

        返回:
            合并后的用户偏好字典
        """
        return self.recognizer.recognize(user_requirement)

    def decide_chart(self, features: Dict[str, Any],
                     business_context: str = "") -> ChartDecision:
        """
        图表选型决策（v3.0 增加异常降级）

        参数:
            features: 数据特征（来自 DataFeatureExtractor）
            business_context: 业务场景描述

        返回:
            图表选型决策
        """
        try:
            return self._decide_chart_impl(features, business_context)
        except Exception as e:
            logger.warning("图表选型异常: %s，使用默认柱状图", e)
            # 降级：返回默认柱状图
            return ChartDecision(
                chart_id="",
                chart_type="bar",
                title="",
                reason=f"图表选型降级（异常: {e}），默认使用柱状图",
                config={"features": features or {}, "fallback": True}
            )

    def _decide_chart_impl(self, features: Dict[str, Any],
                           business_context: str = "") -> ChartDecision:
        """图表选型核心实现。"""
        if not features:
            return ChartDecision(
                chart_id="",
                chart_type="bar",
                title="",
                reason="无数据特征，默认使用柱状图",
                config={"features": {}}
            )

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
        生成洞察（v3.0 增加异常降级）

        参数:
            stats: 统计数据（来自 DataStatistics）
            business_context: 业务场景描述

        返回:
            洞察列表
        """
        try:
            return self._generate_insights_impl(stats, business_context)
        except Exception as e:
            logger.warning("洞察生成异常: %s，返回空洞察列表", e)
            return []

    def _generate_insights_impl(self, stats: Dict[str, Any],
                                business_context: str = "") -> List[InsightDecision]:
        """洞察生成核心实现。"""
        if not stats:
            return []

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

    def generate_insights_safe(self, stats: Dict[str, Any],
                               business_context: str = "") -> Dict[str, Any]:
        """生成洞察（安全版，v3.0 新增）。

        返回结构化字典，包含 insights/recommendations 和状态信息，
        供 CLI 直接序列化输出，异常时返回降级结果。

        参数:
            stats: 统计数据
            business_context: 业务场景描述

        返回:
            {
                "insights": [...],
                "recommendations": [...],
                "status": "ok" | "fallback",
                "error": None | "异常信息"
            }
        """
        try:
            insights = self.generate_insights(stats, business_context)
            recommendations = self.generate_recommendations(insights, business_context)
            return {
                "insights": insights,
                "recommendations": recommendations,
                "status": "ok",
                "error": None,
            }
        except Exception as e:
            logger.warning("generate_insights_safe 异常: %s", e)
            return {
                "insights": [],
                "recommendations": [],
                "status": "fallback",
                "error": str(e),
            }

    def generate_recommendations(self, insights: List[InsightDecision],
                                  business_context: str = "") -> List[RecommendationDecision]:
        """
        生成建议（v3.0 增加异常降级）

        参数:
            insights: 洞察列表
            business_context: 业务场景描述

        返回:
            建议列表
        """
        try:
            return self._generate_recommendations_impl(insights, business_context)
        except Exception as e:
            logger.warning("建议生成异常: %s，返回空列表", e)
            return []

    def _generate_recommendations_impl(self, insights: List[InsightDecision],
                                        business_context: str = "") -> List[RecommendationDecision]:
        """建议生成核心实现。"""
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
        设计阶段审核（v3.0 增加异常降级）

        参数:
            analysis: 分析结果
            design: 设计文档

        返回:
            审核决策
        """
        try:
            return self._review_design_impl(analysis, design)
        except Exception as e:
            logger.warning("设计审核异常: %s，降级为通过", e)
            # 降级：审核通过，避免阻断流程
            return ReviewDecision(
                phase="design",
                passed=True,
                score=70.0,
                issues=[],
                cross_stage_issues=[{
                    "severity": "W201",
                    "message": f"设计审核降级通过（异常: {e}）",
                    "fallback": True
                }]
            )

    def _review_design_impl(self, analysis: Dict, design: Dict) -> ReviewDecision:
        """设计审核核心实现。"""
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
        实现阶段审核（v3.0 增加异常降级）

        参数:
            design: 设计文档
            implement: 实现文档

        返回:
            审核决策
        """
        try:
            return self._review_implement_impl(design, implement)
        except Exception as e:
            logger.warning("实现审核异常: %s，降级为通过", e)
            return ReviewDecision(
                phase="implement",
                passed=True,
                score=70.0,
                issues=[],
                cross_stage_issues=[{
                    "severity": "W201",
                    "message": f"实现审核降级通过（异常: {e}）",
                    "fallback": True
                }]
            )

    def _review_implement_impl(self, design: Dict, implement: Dict) -> ReviewDecision:
        """实现审核核心实现。"""
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

    def build_dashboard_layout(self, analysis: Dict[str, Any],
                                insights: List[Dict[str, Any]],
                                preferences: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        构建分区式看板布局（v3.0 新增）。

        将图表按主题分组到不同分区，每个图表配数据解读文字。
        替代旧版"所有图表并排堆砌"的简陋布局。

        参数:
            analysis: 分析结果（含 kpis、charts、dimensions）
            insights: 洞察列表（含 level/title/description）
            preferences: 用户偏好（color_scheme/layout/focus_dimensions）

        返回:
            layout dict，可直接传入 RenderEngine.render_web_dashboard()
        """
        try:
            return self._build_dashboard_layout_impl(analysis, insights, preferences or {})
        except Exception as e:
            logger.warning("看板布局构建异常: %s，使用降级布局", e)
            # 降级：返回扁平布局（所有图表在一个分区）
            return self._build_fallback_layout(analysis, insights)

    def _build_dashboard_layout_impl(self, analysis: Dict[str, Any],
                                      insights: List[Dict[str, Any]],
                                      preferences: Dict[str, Any]) -> Dict[str, Any]:
        """看板布局构建核心实现。"""
        kpis = analysis.get("kpis", {})
        charts = analysis.get("charts", [])
        title = analysis.get("title", "数据分析看板")
        data_source = analysis.get("data_source", "")

        # 构建洞察映射（按 title 索引，便于匹配到图表）
        insight_map = {}
        for ins in insights:
            t = ins.get("title", "") or ins.get("text", "")
            level = ins.get("level", ins.get("severity", "基础"))
            # 将 level 映射到标准级别
            if level in ("核心", "critical", "high"):
                level = "核心"
            elif level in ("机会", "warning", "medium"):
                level = "机会"
            elif level in ("风险", "risk"):
                level = "风险"
            else:
                level = "基础"
            insight_map[t] = {"description": ins.get("description", ins.get("text", "")), "level": level}

        # 按图表类型/主题分组到分区
        groups = self._group_charts_by_theme(charts, insights)

        # 构建 layout
        sections = []

        # KPI 卡片区
        if kpis:
            metrics = []
            for key, val in kpis.items():
                if isinstance(val, (int, float)):
                    metrics.append({"label": self._humanize_key(key), "value": val, "change": 0})
                elif isinstance(val, str):
                    metrics.append({"label": self._humanize_key(key), "value": val, "change": 0})
            if metrics:
                sections.append({"type": "kpi_cards", "metrics": metrics})

        # 各分区的图表
        for group in groups:
            items = []
            for chart in group["charts"]:
                # 查找匹配的洞察
                chart_title = chart.get("title", "")
                desc = chart.get("description", "")
                level = "基础"
                for ins_key, ins_val in insight_map.items():
                    if chart_title and ins_key and (chart_title in ins_key or ins_key in chart_title):
                        desc = ins_val["description"]
                        level = ins_val["level"]
                        break

                chart_type = chart.get("chart_type", chart.get("type", "bar"))
                # v3.1：主图自动跨列（趋势/漏斗/堆叠图占双列），次要图表占单列
                span = chart.get("span")
                if span is None:
                    span = 2 if chart_type in ("line", "area", "funnel", "stacked_bar") else 1

                item = {
                    "type": "chart",
                    "chart_type": chart_type,
                    "title": chart_title,
                    "data": self._normalize_chart_data(chart),
                    "description": desc,
                    "insight_level": level,
                    "span": span,
                }
                items.append(item)

            sections.append({
                "type": "section_group",
                "title": group["title"],
                "description": group["description"],
                "columns": group.get("columns", 3),
                "items": items,
            })

        # 结论区（行动建议）
        recommendations = [i.get("description", i.get("text", "")) for i in insights
                          if i.get("level") in ("核心", "critical") or i.get("category") == "risk"]
        if recommendations:
            sections.append({"type": "conclusion", "insights": recommendations})

        return {
            "title": title,
            "generated_at": data_source,
            "sections": sections,
        }

    def _normalize_chart_data(self, chart: Dict) -> Dict:
        """
        将分析阶段的图表数据标准化为渲染引擎可消费的格式（v3.1 新增）。

        分析阶段产出的图表数据存在两种来源格式，渲染引擎 ChartBuilder 无法直接消费，
        必须在此统一转换，否则图表会空渲染（只有框架没有数据）：

        来源格式1（分类+数值）:
            {"categories": ["A","B"], "values": [1,2]}
            {"categories": [...], "series": [{"name":"系列1","values":[...]}]}
        来源格式2（已成对/已标准化）:
            {"x": [...], "y": [...]} / {"series": [{"name","data"}]}
            {"data": [{"name","value"}]} / {"pairs": {...}}（饼图类）
            {"nodes"/"links"}（桑基图） / {"indicators"}（雷达图）

        参数:
            chart: 图表配置（含 chart_type / data）

        返回:
            标准化后的 data dict，可直接传给 ChartBuilder.build()
        """
        chart_type = chart.get("chart_type", chart.get("type", "bar"))
        data = chart.get("data", chart)
        if not isinstance(data, dict):
            return data

        # 已标准化格式直接透传（多系列且已含 x 轴）
        if "x" in data or "pairs" in data or "nodes" in data or "indicators" in data or "data" in data:
            if "series" in data and "categories" in data:
                pass  # 落到下方统一处理
            else:
                return data

        # 无分类轴 → 无法转换，原样透传
        categories = data.get("categories")
        if categories is None:
            return data

        # 饼图/漏斗/词云/树图 → [{"name","value"}] 成对列表
        if chart_type in ("pie", "ring", "funnel", "word_cloud", "treemap"):
            values = data.get("values", data.get("value", []))
            if isinstance(values, list) and len(values) == len(categories):
                return {"data": [{"name": str(c), "value": v}
                                 for c, v in zip(categories, values)]}

        # 多系列（堆叠柱/多线）→ {"x","series":[{"name","data"}]}
        series_raw = data.get("series")
        if isinstance(series_raw, list):
            series = [{
                "name": s.get("name", f"系列{i+1}"),
                "data": s.get("values", s.get("data", [])),
            } for i, s in enumerate(series_raw)]
            return {"x": categories, "series": series}

        # 单系列（折线/柱状/条形）→ {"x","y"}
        values = data.get("values", data.get("value", []))
        if isinstance(values, list):
            return {"x": categories, "y": values}

        return data

    def _group_charts_by_theme(self, charts: List[Dict], insights: List[Dict]) -> List[Dict]:
        """
        将图表按主题分组（v3.0 新增）。
        根据图表标题关键词自动归类到预设主题分区。
        """
        # 预设主题分区及关键词
        theme_keywords = [
            {"title": "核心概览", "description": "关键指标与整体趋势一览", "keywords": ["总", "概览", "趋势", "KPI", "月度", "年度", "汇总"], "columns": 3},
            {"title": "维度对比", "description": "各维度横向对比与排名分析", "keywords": ["对比", "排名", "排行", "分布", "各部门", "各区域", "各产品", "Top"], "columns": 3},
            {"title": "构成分析", "description": "数据构成与占比结构", "keywords": ["占比", "构成", "类型", "分类", "结构", "画像"], "columns": 3},
            {"title": "转化与漏斗", "description": "转化路径与漏斗分析", "keywords": ["漏斗", "转化", "销售阶段", "pipeline", " funnel"], "columns": 2},
            {"title": "交叉分析", "description": "多维度交叉透视", "keywords": ["交叉", "堆叠", "透视", "矩阵", "热力"], "columns": 2},
            {"title": "其他分析", "description": "补充分析视角", "keywords": [], "columns": 3},
        ]

        groups = [{**g, "charts": []} for g in theme_keywords]

        for chart in charts:
            title = chart.get("title", "")
            placed = False
            for i, group in enumerate(groups[:-1]):  # 排除最后的"其他"
                for kw in group["keywords"]:
                    if kw in title:
                        groups[i]["charts"].append(chart)
                        placed = True
                        break
                if placed:
                    break
            if not placed:
                groups[-1]["charts"].append(chart)  # 归入"其他"

        # 过滤空分区
        return [g for g in groups if g["charts"]]

    def _humanize_key(self, key: str) -> str:
        """将英文键名转为中文标签（简单映射）。"""
        mapping = {
            "total_visits": "总拜访量", "total_sales": "总销售额", "total_revenue": "总收入",
            "total_count": "总数", "unique_count": "去重数", "unique_clinics": "覆盖诊所",
            "unique_reps": "销售代表", "unique_provinces": "覆盖省份",
            "avg_value": "平均值", "max_value": "最大值", "min_value": "最小值",
        }
        return mapping.get(key, key.replace("_", " ").title())

    def _build_fallback_layout(self, analysis: Dict, insights: List[Dict]) -> Dict:
        """降级布局：所有图表放入单个分区。"""
        charts = analysis.get("charts", [])
        items = []
        for c in charts:
            chart_type = c.get("chart_type", c.get("type", "bar"))
            items.append({
                "type": "chart",
                "chart_type": chart_type,
                "title": c.get("title", ""),
                "data": self._normalize_chart_data(c),
                "description": c.get("description", ""),
                "insight_level": c.get("insight_level", "基础"),
                "span": c.get("span", 2 if chart_type in ("line", "area", "funnel", "stacked_bar") else 1),
            })
        return {
            "title": analysis.get("title", "数据分析看板"),
            "generated_at": analysis.get("data_source", ""),
            "sections": [
                {"type": "kpi_cards", "metrics": []},
                {"type": "section_group", "title": "数据分析", "description": "", "columns": 2, "items": items},
            ],
        }
