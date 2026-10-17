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

try:
    from conspect_tools import style_loader
    from conspect_tools import block_library
    from conspect_tools import style_preview
    from conspect_tools.chart_advisor import NON_METRIC_HINTS as _NON_METRIC_HINTS
except ImportError:
    try:
        from . import style_loader
        from . import block_library
        from . import style_preview
        from .chart_advisor import NON_METRIC_HINTS as _NON_METRIC_HINTS
    except ImportError:
        style_loader = None
        block_library = None
        style_preview = None
        _NON_METRIC_HINTS = tuple()


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
    """洞察收尾决策（属分析数据阶段）"""
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

    # 配色关键词映射 —— 把用户的自然语言风格诉求映射到资产库中的风格编号
    # 顺序敏感：更具体的词排在前面（识别逻辑为「首个命中的子串即返回」）
    COLOR_KEYWORDS = {
        # 商务通稿
        "赛博朋克": "A23", "电子墨水": "A37", "极简深色": "A18", "瑞士新章": "A32",
        "自然编辑": "A42", "复古未来": "A11",
        "扁平": "A12", "蓝色": "A12", "蓝": "A12",
        "瑞士": "A1", "网格": "A1",
        "留白": "A29", "极简": "A29", "简约": "A29", "高管": "A29", "战略": "A29",
        "杂志": "A47", "编辑": "A47", "衬线": "A47",
        "无障碍": "A8", "包容": "A17", "商务": "A17", "专业": "A17",
        "米色": "A42",
        # 数据大屏
        "大屏": "A33", "科幻": "A33", "监控": "A33",
        "科技": "A28", "炫酷": "A28", "纵深": "A28", "互联网": "A28",
        "赛博": "A23", "霓虹": "A23", "电竞": "A23",
        "色散": "A48", "重影": "A48", "流彩": "A46", "流光": "A46",
        "深色": "A7", "墨黑": "A7", "夜间": "A7", "黑": "A7",
        "隐藏": "A18",
        # 玻璃光影
        "磨砂": "A3", "毛玻璃": "A3", "玻璃": "A3",
        "极光": "A10", "晕彩": "A10",
        "液态": "A14", "未来感": "A14",
        "智能": "A25", "AI": "A25",
        "产品": "A45", "高端质感": "A45",
        "软塑": "A19", "柔和": "A19",
        # 纸感编辑
        "纸感": "A37", "阅读": "A37", "书": "A37",
        "胶片": "A49", "复古": "A49", "怀旧": "A49",
        "拟物": "A13", "质感": "A13", "浮窗": "A36",
        # 自然柔和
        "绿色": "A24", "森林": "A24", "自然": "A24", "环保": "A24", "ESG": "A24",
        "浮雕": "A2", "同色": "A2", "黏土": "A9", "可爱": "A9",
        "果冻": "A41", "仿生": "A39", "便当": "A21", "苹果风": "A21",
        "暖色": "A42", "温暖": "A9", "暖": "A9",
        # 表达张力
        "粗野": "A4", "先锋": "A4", "宣言": "A4",
        "撞色": "A6", "明快": "A6", "糖果": "A20", "俏皮": "A20",
        "孟菲斯": "A26", "几何": "A26", "像素": "A34", "8bit": "A34",
        "极繁": "A38", "Y2K": "A38", "年轻": "A38",
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
            "color_scheme": DEFAULT_USER_PREFERENCES.get("color_scheme")
                            or (style_loader.default_code() if style_loader else "A12"),
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
        报表选型阶段审核（v4.0）

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
                phase="style",
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
            phase="style",
            passed=passed,
            score=score,
            issues=issues,
            cross_stage_issues=cross_stage_issues
        )

    def review_implement(self, design: Dict, implement: Dict) -> ReviewDecision:
        """
        生成报表阶段审核（v4.0）

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
                phase="render",
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
            phase="render",
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

    # ------------------------------------------------------------------
    # v4.0 新增：汇报内容选型 / 报表选型
    # ------------------------------------------------------------------

    #: 报表形态 → 板块数上限（板块库规则第 4 条）
    FORM_LIMITS = {"投屏": 10, "阅读": 18, "大屏": 10}

    #: 任何报表至少要保留的分析板块数
    MIN_ANALYSIS_BLOCKS = 2

    #: 用户诉求关键词 → 特征开关
    REQUEST_FLAGS = {
        "want_detail": ["明细", "清单", "逐条", "top", "TOP", "排名明细"],
        "want_forecast": ["预测", "预估", "展望", "未来", "趋势外推"],
        "want_trend_glance": ["一眼看趋势", "走势概览", "迷你趋势"],
        "want_appendix": ["附录", "术语", "完整数据", "附表"],
    }

    @classmethod
    def _features_from_analysis(cls, analysis: Dict[str, Any],
                                features: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        优先用显式传入的特征；缺失时从分析结果推导。

        兼容两种 dimensions 形态：
          - `analyze` 的产出：{"时间": [...], "分类": [...], "数值": [...]}
          - 简化形态：[{"name": "日期"}, ...]
        """
        if features:
            return dict(features)
        a = analysis or {}

        # analyze 可能返回多 Sheet 字典，取第一个 Sheet 作为主数据
        if isinstance(a.get("data"), dict) and "dimensions" not in a:
            sheets = [v for v in a["data"].values() if isinstance(v, dict)]
            a = sheets[0] if sheets else a

        dims = a.get("dimensions")
        time_cols, cat_cols, num_cols = [], [], []
        if isinstance(dims, dict):
            time_cols = list(dims.get("时间") or dims.get("time") or [])
            cat_cols = list(dims.get("分类") or dims.get("category") or [])
            num_cols = list(dims.get("数值") or dims.get("numeric") or [])
        elif isinstance(dims, list):
            for d in dims:
                name = d.get("name", "") if isinstance(d, dict) else str(d)
                if not name:
                    continue
                kind = d.get("type", "") if isinstance(d, dict) else ""
                s = f"{kind}{name}"
                if "时间" in s or "time" in s.lower() or "日期" in name:
                    time_cols.append(name)
                elif "数值" in s or "numeric" in s.lower():
                    num_cols.append(name)
                else:
                    cat_cols.append(name)

        quality = a.get("data_quality") or a.get("quality") or {}
        def uniq(col):
            q = quality.get(col)
            return int(q.get("unique_count") or 0) if isinstance(q, dict) else 0

        stats = a.get("statistics") or a.get("stats") or {}
        charts = a.get("charts") or []
        chart_types = {c.get("type") or c.get("chart_type") for c in charts if isinstance(c, dict)}
        advanced = {"pareto", "radar", "lorenz", "box", "heatmap", "forecast", "sankey"}

        # 「长得像数字的标识列」不是指标：电话号码有 2500 个唯一值，
        # 若计入 numeric_count / distinct_max，会让 B11（分布）等板块被误触发，
        # 而实际上一张可画的数值列都没有。
        num_metric_cols = [c for c in num_cols
                           if not any(h in str(c).lower() for h in _NON_METRIC_HINTS)]

        time_points = max([uniq(c) for c in time_cols] + [int(stats.get("time_points") or 0)])
        cat_count = max([uniq(c) for c in cat_cols] + [int(a.get("category_count") or 0)])
        distinct_max = max([uniq(c) for c in num_metric_cols] + [0])
        # 分类维度的「典型规模」：取所有分类维度里最接近构成图可用区间的那个。
        # 只取最大值会把 B08（结构构成）误排除——例如「所在城市」有 15 类，
        # 但「产品类别」只有 4 类，构成图依然成立。
        cat_sizes = sorted(u for u in (uniq(c) for c in cat_cols) if u >= 2)
        cat_min = min(cat_sizes) if cat_sizes else 0
        cat_mid = cat_sizes[len(cat_sizes) // 2] if cat_sizes else 0

        return {
            "has_time": bool(time_cols),
            "time_points": time_points,
            "has_category": bool(cat_cols),
            "category_count": cat_count,
            "category_min": cat_min,
            "category_mid": cat_mid,
            "has_numeric": bool(num_metric_cols),
            "numeric_count": len(num_metric_cols),
            "sample_size": int(a.get("rows") or a.get("row_count") or 0),
            "distinct_max": distinct_max,
            "has_target": bool(a.get("has_target")),
            "has_hierarchy": bool(a.get("has_hierarchy")),
            "has_decomposable": bool(a.get("has_decomposable")) or "pareto" in chart_types,
            "has_advanced": bool(chart_types & advanced),
            "quality_score": float(a.get("quality_score", 100)),
            "has_missing": any(isinstance(q, dict) and (q.get("null_count") or 0) > 0
                               for q in quality.values()) if isinstance(quality, dict) else False,
        }

    @staticmethod
    def _annotate_block(b: Dict[str, Any]) -> Dict[str, Any]:
        """给板块补上引擎可渲染类型、降级说明与**白话用途**（供选型卡与装配共用）。"""
        b = dict(b)
        b["engine_charts"] = block_library.chart_chain(b["id"])
        b["chart_notes"] = block_library.chart_notes(b["id"])
        # 选型卡若只写编号（B08），客户无从判断要不要这一块；
        # purpose 用一句话说清「这一块给读者看什么」。
        b["purpose"] = block_library.purpose(b["id"])
        return b

    @staticmethod
    def _drop_unservable(blocks: List[Dict[str, Any]],
                         charts: List[Dict[str, Any]]) -> (List[Dict[str, Any]],
                                                           List[Dict[str, Any]]):
        """
        预演图表绑定，裁掉「无图可画」的板块。

        绑定规则与装配阶段一致：
          1. 图表自带 `block` 字段 → 只归该板块，其他板块不得借用
          2. 无绑定的图表 → 按板块的图表降级链依次分配，一张只能用一次
          3. `engine_charts` 为空的板块（封面/摘要/表格等）不需要图，直接保留

        返回 (可落地板块, 被裁板块[带 reason])。
        """
        if block_library is None:
            return list(blocks), []

        bound = {str(c.get("block")) for c in charts if str(c.get("block") or "").strip()}
        unbound = [c for c in charts if not str(c.get("block") or "").strip()]

        kept, dropped = [], []
        for b in blocks:
            chain = b.get("engine_charts")
            if not chain:                       # 非图形态板块
                kept.append(b)
                continue
            if b["id"] in bound:                # 已有专属图表
                kept.append(b)
                continue
            hit = next((i for i, c in enumerate(unbound)
                        if (c.get("chart_type") or c.get("type") or "bar") in chain), None)
            if hit is not None:
                unbound.pop(hit)
                kept.append(b)
            else:
                dropped.append({**b,
                                "reason": f"无可用图表（可接受类型 {chain}）"})
        return kept, dropped

    def select_content_plan(self, analysis: Dict[str, Any],
                            insights: Optional[List[Dict]] = None,
                            features: Optional[Dict[str, Any]] = None,
                            report_form: str = "投屏",
                            requirements: str = "") -> Dict[str, Any]:
        """
        汇报内容选型：按板块库的触发条件产出板块组合方案。

        参数:
            analysis: 分析结果（含 kpis/dimensions/charts/statistics）
            insights: 洞察列表（用于判定是否存在可行动项）
            features: 显式数据特征（优先）；缺省时从 analysis 推导
            report_form: 报表形态（投屏 / 阅读 / 大屏），决定板块数上限
            requirements: 用户原始诉求文本，用于识别可选板块诉求

        返回:
            {"blocks": [...], "dropped": [...], "limit": n, "form": ...,
             "features": {...}, "excluded": [...], "notes": [...]}
        """
        try:
            f = self._features_from_analysis(analysis, features)
            for flag, words in self.REQUEST_FLAGS.items():
                if any(w in (requirements or "") for w in words):
                    f[flag] = True
            if insights:
                f["has_actionable"] = bool(f.get("has_actionable", True))
            if f.get("category_count", 0) > 10:
                f["want_detail"] = True

            evaluated = block_library.evaluate(f)
            limit = self.FORM_LIMITS.get(report_form, 8)

            # 先用板块总数判定 B03（目录导航）是否纳入，再做裁剪
            f["block_total"] = len(evaluated["selected"])
            evaluated = block_library.evaluate(f)

            kept, over_limit = block_library.trim(
                evaluated["selected"], limit, self.MIN_ANALYSIS_BLOCKS)
            for d in over_limit:
                d = dict(d)
                d["reason"] = f"超出{report_form}板块上限({limit})，按必需度优先级裁出"

            # 每个板块补上「引擎可渲染类型」与降级说明，让生成阶段不必再猜
            kept = [self._annotate_block(b) for b in kept]

            # 图表可得性校验：触发条件成立的板块，未必真有图可画。
            # 例如「存在数值列且非重复值 ≥20」会被电话号码满足（2500 个唯一值），
            # 但那张表其实一张数值图都出不来。这里按实际 charts 预演一遍绑定，
            # 无图可用的板块提前裁掉并写明原因，而不是留到装配阶段变成空洞的缺口。
            kept, unservable = self._drop_unservable(kept, analysis.get("charts") or [])
            dropped = list(over_limit) + list(unservable)

            notes = []
            if unservable:
                notes.append("以下板块无可用图表，已在选型阶段裁出："
                             + " | ".join(f"{b['id']} {b['name']}（{b['reason']}）"
                                          for b in unservable))
            downgraded = [f"{b['id']} {b['name']}：{'；'.join(b['chart_notes'])}"
                          for b in kept if b.get("chart_notes")]
            if downgraded:
                notes.append("以下板块的图表类型存在引擎降级（如实标注，非缺陷）："
                             + " | ".join(downgraded))
            if over_limit:
                notes.append(f"板块数超上限({limit})，按必需度裁出 {len(over_limit)} 个："
                             + "、".join(x["id"] for x in over_limit))
            if block_library.summary()["count"] != len(evaluated["selected"]) + len(evaluated["excluded"]):
                notes.append("板块库解析异常：选中 + 未选中 ≠ 总数")

            return {
                "status": "ok",
                "form": report_form,
                "limit": limit,
                "blocks": kept,
                "dropped": dropped,
                "excluded": evaluated["excluded"],
                "features": f,
                "notes": notes,
                "section_types": sorted({b["section_type"] for b in kept}),
            }
        except Exception as e:
            logger.warning("汇报内容选型异常: %s", e)
            return {"status": "error", "message": str(e),
                    "blocks": [], "dropped": [], "excluded": [], "notes": ["选型失败，需人工介入"]}

    #: 报表类型关键词（用于与风格的 report_use.types 匹配）
    REPORT_TYPE_ALIASES = {
        "经营分析": ["经营", "业绩", "销售", "运营", "业务"],
        "年度/季度报告": ["年度", "季度", "年报", "季度报告", "总结"],
        "财务汇报": ["财务", "预算", "成本", "利润", "报表"],
        "实时监控大屏": ["监控", "实时", "大屏", "看板"],
        "发布会演示": ["发布", "演示", "路演"],
        "行业研究": ["研究", "洞察", "分析报告", "白皮书", "行业"],
        "深度洞察": ["洞察", "深度", "专题"],
        "健康医疗报告": ["健康", "医疗", "医院", "临床"],
        "ESG 可持续报告": ["esg", "ESG", "可持续", "环保", "碳"],
        "创意提案": ["创意", "提案", "策划", "方案"],
        "品牌宣言": ["品牌", "宣言", "主张"],
        "营销复盘": ["营销", "复盘", "投放", "活动"],
    }

    def select_style_card(self, profile: Optional[Dict[str, Any]] = None,
                          blocks: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        报表选型：L0 按调性硬过滤 → L1 按报表类型/密度/关键词打分 → 输出选型建议卡。

        参数:
            profile: {"tone": 浅色|深色|混合|auto, "report_type": str,
                      "density": 高|中|低, "keywords": [str], "family": 族 id,
                      "media": 投影|打印|大屏|阅读}
            blocks: 内容选型选中的板块 id 列表。传入后按「风格推荐的板块 ∩ 实际选中的板块」
                    计算契合度——报表选型在内容选型之后，理应知道内容是什么。

        置信度说明：`report_use` 是**族级**属性，同族风格的推荐板块/密度/载体天然一致，
        因此同族并列是正常现象。置信度按**族级差距**计算，而不是风格级：
        族内择一由默认偏好与编号顺序决定，这本身不降低对「该用哪个族」的确定程度。
        """
        try:
            p = dict(profile or {})
            tone = p.get("tone", "auto")
            report_type = p.get("report_type", "")
            density = p.get("density", "")
            media = p.get("media", "")
            keywords = [k for k in (p.get("keywords") or []) if k]
            want_family = p.get("family", "")

            styles = style_loader.styles()
            if not styles:
                return {"status": "error", "message": "风格资产为空或不可用",
                        "degraded": style_loader.is_degraded(),
                        "recommend": None, "candidates": [], "reason": []}

            scored = []
            for s in styles:
                if want_family and s["family"] != want_family:
                    continue
                score, reasons = 0, []
                st, use = s.get("tone", ""), s.get("report_use", {})

                if tone in ("浅色", "深色"):
                    if st == tone:
                        score += 3
                        reasons.append(f"调性={tone} 完全命中")
                    elif st == "混合":
                        score += 1
                        reasons.append("调性=混合，浅深均可适配")

                if report_type:
                    aliases = self.REPORT_TYPE_ALIASES.get(report_type, [report_type])
                    hits_t = [a for a in aliases
                              if any(a in t for t in use.get("types", []))]
                    if hits_t:
                        score += 2
                        reasons.append(f"报表类型命中「{report_type}」")

                if density and use.get("density") == density:
                    score += 2
                    reasons.append(f"数据密度={density} 匹配")

                if media and media in (use.get("media") or ""):
                    score += 1
                    reasons.append(f"载体「{media}」适用")

                haystack = " ".join([s.get("mood", ""), s.get("label", ""),
                                     s.get("school", ""), " ".join(s.get("keywords", []))])
                hits = [k for k in keywords if k and k in haystack]
                if hits:
                    score += len(hits)
                    reasons.append("风格关键词命中：" + "、".join(hits))

                # 与已选内容的契合度：风格推荐的板块中有多少真被选中
                if blocks:
                    rec_blocks = set(use.get("blocks") or [])
                    inter = rec_blocks & set(blocks)
                    if inter:
                        add = round(min(2.0, 2.0 * len(inter) / max(1, len(blocks))), 2)
                        score += add
                        reasons.append(f"推荐板块与实际内容重合 {len(inter)}/{len(blocks)}")

                scored.append((round(score, 2), s["code"], s, reasons))

            if not scored:
                return {"status": "error", "message": "无候选风格（过滤器过严）",
                        "degraded": style_loader.is_degraded(),
                        "recommend": None, "candidates": [], "reason": []}

            # 平局处理：得分相同则优先默认风格，其次按编号升序（保证结果稳定可复现）
            default_code = style_loader.default_code()
            scored.sort(key=lambda x: (-x[0], 0 if x[1] == default_code else 1, int(x[1][1:])))
            # 多取几个候选，便于把同族并列项一并展示
            top = scored[:6]
            best = top[0]

            # ---- 置信度按「族级差距」计算 ----
            # report_use 是族级属性，同族风格的推荐板块/密度/载体天然相同，
            # 用风格级 gap 判断会把「族已确定、族内待定」误报成「低置信度」。
            fam_best: Dict[str, float] = {}
            for sc, code, s, _ in scored:
                fid = s["family"]
                if sc > fam_best.get(fid, -1):
                    fam_best[fid] = sc
            ranked = sorted(fam_best.items(), key=lambda kv: -kv[1])
            gap = round(ranked[0][1] - (ranked[1][1] if len(ranked) > 1 else 0), 2)
            confidence = "高" if gap >= 2.5 else ("中" if gap >= 1 else "低")

            best_family = best[2]["family"]
            peers = [x[1] for x in scored
                     if x[2]["family"] == best_family and x[0] == best[0]]

            def card(item):
                score, code, s, reasons = item
                fam = style_loader.get_family(s["family"]) or {}
                series = style_loader.series_for(code)
                out = {
                    "code": code, "label": s["label"], "en": s.get("en", ""),
                    "family": s["family"], "family_label": fam.get("label", ""),
                    "tone": s.get("tone", ""), "mood": s.get("mood", ""),
                    "tokens": s["tokens"], "series": series,
                    "report_use": s.get("report_use", {}),
                    "taboos": s.get("taboos", []), "score": score, "reasons": reasons,
                    "body": s.get("body"),
                }
                # 人话描述：编号与色值对客户没有决断价值，必须给出
                # 色系 / 气质 / 场景 / 不适合 这类可直接判断的信息
                if style_preview:
                    out["describe"] = style_preview.describe_style(s, series)
                return out

            reason = list(best[3])
            reason.append(f"数据密度适配 {best[2].get('report_use', {}).get('density', '—')}"
                          f"，载体 {best[2].get('report_use', {}).get('media', '—')}")
            fam_label = (style_loader.get_family(best_family) or {}).get("label", best_family)
            if len(peers) > 1:
                reason.append(
                    f"族「{fam_label}」已确定（领先次优族 {gap} 分）；"
                    f"族内 {len(peers)} 款同分（{'、'.join(peers)}），"
                    f"按默认偏好择 {best[1]}，可随时换族内其他款")
            else:
                reason.append(f"族「{fam_label}」领先次优族 {gap} 分")

            rec_card = card(best)
            other_cards = [card(x) for x in top[1:]]
            # 同族候选的场景/密度/载体完全一致（report_use 是族级属性），
            # 只给各自属性会让客户看到几段几乎相同的描述，仍然无从抉择。
            # 所以给每个备选补一句「与推荐款差在哪」。
            if style_preview and rec_card.get("describe"):
                for a in other_cards:
                    a["diff_from_recommend"] = style_preview.diff_note(
                        rec_card, a, rec_card.get("describe"), a.get("describe"))

            return {
                "status": "ok",
                "recommend": rec_card,
                "alternatives": other_cards[:3],
                "candidates": [rec_card] + other_cards,
                "confidence": confidence,
                "score_gap": gap,
                "family": best_family,
                "family_label": fam_label,
                "family_ties": peers,
                "reason": reason,
                "filtered_families": [f["id"] for f in style_loader.families()],
                "degraded": style_loader.is_degraded(),
                "asset_count": len(styles),
            }
        except Exception as e:
            logger.warning("报表选型异常: %s", e)
            return {"status": "error", "message": str(e), "recommend": None,
                    "candidates": [], "reason": [], "degraded": style_loader.is_degraded()}

    def build_dashboard_layout(self, analysis: Dict[str, Any],
                                insights: List[Dict[str, Any]],
                                preferences: Dict[str, Any] = None,
                                blocks: Optional[List[Any]] = None) -> Dict[str, Any]:
        """
        构建看板布局。

        两种模式：
          1. **板块驱动**（传 blocks）—— 按板块清单逐个落地 section，板块顺序即页序。
             这是「生成报表」阶段的主路径：内容选型产出 blocks，渲染阶段按 blocks 装配。
          2. **主题分组**（不传 blocks）—— v3.0 的兼容路径，按图表标题关键词分组。
             仅在没有板块清单时兜底，不应作为正常流程使用。

        参数:
            analysis: 分析结果（kpis / charts / tables / narrative 等）
            insights: 洞察列表（含 level/title/description）
            preferences: 用户偏好（color_scheme / layout / focus_dimensions）
            blocks: 板块清单。元素可为板块 id（"B07"）或 select_content 返回的板块 dict。
                    为空时退回主题分组。

        返回:
            layout dict，可直接传入 RenderEngine.render_web_dashboard()
        """
        try:
            if blocks:
                return self._assemble_by_blocks(analysis, insights, preferences or {}, blocks)
            return self._build_dashboard_layout_impl(analysis, insights, preferences or {})
        except Exception as e:
            logger.warning("看板布局构建异常: %s，使用降级布局", e)
            return self._build_fallback_layout(analysis, insights)

    # ---------------------------------------------------------------- 板块驱动装配
    #: 文案类板块（不画图，内容来自 narrative 或 insights 推导）
    _PROSE_BLOCKS = {"B01", "B02", "B03", "B16", "B17", "B18", "B19", "B20", "B21", "B22"}

    @staticmethod
    def _block_id(item: Any) -> str:
        """把板块 id 字符串或板块 dict 统一取成 id。"""
        if isinstance(item, str):
            return item.strip()
        if isinstance(item, dict):
            return str(item.get("id", "")).strip()
        return ""

    @staticmethod
    def _text_list(raw: Any) -> List[Any]:
        """把 str / dict / list 归一成列表（str → 单元素，dict → [dict]）。"""
        if raw is None or raw == "":
            return []
        if isinstance(raw, (str, dict)):
            return [raw]
        return list(raw)

    @staticmethod
    def _item_text(x: Any) -> str:
        if isinstance(x, dict):
            return str(x.get("text") or x.get("description") or x.get("title") or "")
        return str(x)

    def _assemble_by_blocks(self, analysis: Dict[str, Any],
                            insights: List[Dict[str, Any]],
                            preferences: Dict[str, Any],
                            blocks: List[Any]) -> Dict[str, Any]:
        """
        按板块清单装配 layout（v4.1 新增，P1 修复点）。

        规则：
          - 板块顺序即页序，不重排、不增删（选型阶段已定稿）；
          - 图表按「板块声明的图表类型降级链」分配，**一个图表只被消费一次**；
          - 文案类板块的内容优先级：analysis.narrative → insights 推导 → 显式缺口标记；
          - 任何内容缺口都记入 `_gaps`，供 QA-5 核对，**不静默编造**。
        """
        narr = analysis.get("narrative") or {}
        kpis = analysis.get("kpis") or {}
        all_charts = [c for c in (analysis.get("charts") or []) if isinstance(c, dict)]
        tables = [t for t in (analysis.get("tables") or []) if isinstance(t, dict)]

        # 图表显式绑定（生成图表的模块会用 chart["block"]="B09" 声明归属）
        chart_by_block: Dict[str, List[Dict]] = {}
        for c in all_charts:
            bid = str(c.get("block") or "").strip()
            if bid:
                chart_by_block.setdefault(bid, []).append(c)
        # consumed = 不许别的板块借用（绑定的图从开始就归其板块所有）
        consumed = {id(c) for cs in chart_by_block.values() for c in cs}
        # used = 真正渲染了的图。两者必须分开：
        # 若只用 consumed 判孤儿，绑定图里超出板块容量、实际没渲染的会被当成
        # 「已消费」而静默消失——数据丢了却没有缺口记录。
        used: set = set()

        # 洞察分级
        ins_core, ins_risk, ins_opp, ins_action, ins_plain = [], [], [], [], []
        for ins in insights or []:
            if not isinstance(ins, dict):
                ins_plain.append(str(ins))
                continue
            text = self._item_text(ins)
            if not text:
                continue
            lv = str(ins.get("level") or ins.get("severity") or "").lower()
            cat = str(ins.get("category") or "").lower()
            if lv in ("核心", "critical", "high") or cat in ("core", "finding"):
                ins_core.append({"text": text, "badge": "核心"})
            elif lv in ("风险", "risk") or cat == "risk":
                ins_risk.append(text)
            elif lv in ("机会", "opportunity") or cat in ("opportunity", "chance"):
                ins_opp.append(text)
            elif cat in ("action", "recommendation"):
                ins_action.append(text)
            else:
                ins_plain.append(text)

        gaps: List[Dict[str, str]] = []
        sections: List[Dict[str, Any]] = []
        resolved: List[str] = []
        used_kpi_keys: set = set()   # B04 用过的指标，B06 不重复渲染

        def gap(bid, reason, severity="content"):
            """
            记录内容缺口。

            severity 分三级，让 QA-5 能聚焦真正阻塞的问题：
              blocking —— 板块无法落地（无图可画、无数据），必须处置
              content  —— 结构落地但内容缺失/不足（补写文案即可），不阻塞渲染
              info     —— 已按板块库规则优雅降级（如「未识别到显著风险」是合规写法），
                          仅备查，不算缺陷
            """
            gaps.append({"block": bid, "reason": reason, "severity": severity})

        def find_charts(bid: str, limit: Optional[int] = None) -> List[Dict]:
            """
            取该板块要用的图表。

            优先用图表自带的 `block` 绑定：生成阶段已经算好「这张图属于哪个板块」，
            有绑定就只用自己的，不再从公共池里捞——否则靠后的板块（如 B12 关联）
            会被靠前的板块（如 B11 分布）抢先消费掉散点图，凭空产生缺口。
            没有绑定（例如 Agent 手写 charts）时才按图表类型降级链匹配。

            limit 默认 3：排名类板块常有多个维度要拆（区域/品类/渠道），
            只取 2 张会把剩下的图挤掉。
            """
            limit = limit if limit is not None else block_library.capacity(bid)
            bound = chart_by_block.get(bid) or []
            if bound:
                picked = bound[:limit]
                used.update(id(c) for c in picked)
                return picked

            found: List[Dict] = []
            for want in block_library.chart_chain(bid):
                if len(found) >= limit:
                    break
                for c in all_charts:
                    if id(c) in consumed or c in found:
                        continue
                    ct = c.get("chart_type") or c.get("type") or "bar"
                    if ct == want or (want == "line" and ct == "area") or \
                       (want == "bar" and ct in ("horizontal_bar", "stacked_bar")):
                        consumed.add(id(c))
                        used.add(id(c))
                        found.append(c)
                        if len(found) >= limit:
                            break
            return found

        def chart_section(bid: str, bname: str) -> Optional[Dict]:
            cs = find_charts(bid)
            if not cs:
                return None
            items = []
            for c in cs:
                ct = c.get("chart_type") or c.get("type") or "bar"
                span = c.get("span") or (2 if ct in ("line", "area", "funnel",
                                                     "stacked_bar") else 1)
                items.append({
                    "type": "chart",
                    "chart_type": ct,
                    "title": c.get("title", bname),
                    "data": self._normalize_chart_data(c),
                    "description": c.get("description", ""),
                    "insight_level": c.get("insight_level", "基础"),
                    "span": span,
                })
            # 单图占宽（主图跨列）；多图并排——否则两张趋势图会各占满行、纵向堆两屏
            if len(items) > 1:
                for it in items:
                    it["span"] = 1
                cols = min(3, len(items))
            else:
                cols = 2 if items[0]["span"] >= 2 else 3
            return {"type": "section_group", "title": bname,
                    "description": cs[0].get("description", ""),
                    "columns": cols, "items": items}

        # ---- 逐板块装配 ----
        for item in blocks:
            bid = self._block_id(item)
            meta = block_library.get(bid)
            if not meta:
                gap(bid or str(item), "板块库中不存在该编号", "blocking")
                continue
            bname = meta["name"]
            sec: Optional[Dict[str, Any]] = None

            if bid == "B01":
                sec = {
                    "type": "prose", "title": analysis.get("title", "数据报表"),
                    "variant": "cover",
                    "eyebrow": narr.get("scope") or analysis.get("data_source", ""),
                    "body": narr.get("subtitle") or (ins_plain[0] if ins_plain else ""),
                }
                if not sec["body"]:
                    gap(bid, "缺副标题文案（narrative.subtitle）")

            elif bid == "B02":
                items_ = [self._item_text(x) for x in self._text_list(narr.get("summary"))]
                if not items_:
                    items_ = [x["text"] if isinstance(x, dict) else x for x in ins_core[:5]] or ins_plain[:5]
                    if items_:
                        gap(bid, "narrative.summary 未提供，已用洞察列表前 5 条降级")
                if not items_:
                    gap(bid, "无可用结论，执行摘要为空", "content")
                sec = {"type": "prose", "title": bname,
                       "eyebrow": "SUMMARY", "items": items_[:5]}

            elif bid == "B03":
                toc = []
                for i, b in enumerate(blocks):
                    m = block_library.get(self._block_id(b))
                    toc.append(f"{i + 1}. {m['name'] if m else self._block_id(b)}")
                # 分两栏：板块多时单栏竖排会占掉整屏，且信息密度过低
                half = (len(toc) + 1) // 2
                sec = {"type": "prose", "title": bname, "columns": 2, "panels": [
                    {"items": toc[:half]}, {"items": toc[half:]},
                ]}

            elif bid == "B04":
                metrics = []
                src = kpis.items() if isinstance(kpis, dict) else enumerate(self._text_list(kpis))
                for key, val in src:
                    if isinstance(val, (int, float, str)) and val != "":
                        metrics.append({"label": self._humanize_key(str(key)),
                                        "value": val, "change": 0})
                        used_kpi_keys.add(str(key))
                # 指标卡不带迷你趋势（B06 职责），此处只放数值
                if metrics:
                    sec = {"type": "kpi_cards", "metrics": metrics[:8]}
                else:
                    gap(bid, "无可用数值指标，KPI 墙为空", "blocking")

            elif bid == "B05":
                targets = analysis.get("targets") or []
                if targets:
                    sec = {"type": "prose", "title": bname,
                           "items": [t if isinstance(t, str) else
                                     f"{t.get('name', '目标')}：实际 {t.get('actual')} / 目标 "
                                     f"{t.get('target')}（达成 {t.get('rate', '—')}）"
                                     for t in targets]}
                else:
                    sec = chart_section(bid, bname)
                    if not sec:
                        gap(bid, "无目标值亦无仪表盘数据，已省略", "info")

            elif bid == "B06":
                # 迷你趋势卡：引擎无 sparkline，只能用 KPI 数值承载。
                # 但若与 B04 用同一批指标，就会把整组 KPI 卡重复渲染一遍——
                # 所以只取 B04 未覆盖的指标；没有则如实记缺口，让位给 B07 趋势。
                metrics = []
                src = kpis.items() if isinstance(kpis, dict) else []
                for key, val in src:
                    if isinstance(val, (int, float)) and str(key) not in used_kpi_keys:
                        metrics.append({"label": self._humanize_key(str(key)),
                                        "value": val, "change": 0})
                if metrics:
                    sec = {"type": "kpi_cards", "metrics": metrics[:6]}
                else:
                    gap(bid, "引擎无迷你折线组件，且指标已由 B04 覆盖，"
                             "本板块不重复渲染（趋势由 B07 承载）", "info")

            elif bid == "B13":
                cols, rows = [], []
                if tables:
                    t = tables.pop(0)
                    cols = t.get("columns") or []
                    rows = t.get("rows") or []
                else:
                    for c in all_charts:
                        if id(c) not in consumed and (c.get("chart_type") or c.get("type")) == "table":
                            cols = c.get("columns") or (c.get("data") or {}).get("columns") or []
                            rows = c.get("rows") or (c.get("data") or {}).get("rows") or []
                            consumed.add(id(c))
                            break
                if rows:
                    sec = {"type": "table", "title": bname, "columns": cols,
                           "rows": rows[:20], "collapsible": True}
                else:
                    gap(bid, "无表格数据（analysis.tables 为空），明细表已省略")

            elif bid == "B15":
                findings = [self._item_text(x) for x in self._text_list(narr.get("findings"))]
                if not findings:
                    findings = [x["text"] if isinstance(x, dict) else x
                                for x in (ins_core + ins_plain)[:6]]
                    if findings:
                        gap(bid, "narrative.findings 未提供，已用洞察列表降级")
                if len(findings) < 3:
                    gap(bid, f"核心发现仅 {len(findings)} 条，板块库要求 ≥3 条", "content")
                sec = {"type": "conclusion", "title": bname, "insights": findings}

            elif bid == "B16":
                risks = [self._item_text(x) for x in self._text_list(narr.get("risks"))] or ins_risk
                opps = [self._item_text(x) for x in self._text_list(narr.get("opportunities"))] or ins_opp
                if not risks and not opps:
                    risks = ["本期未识别到显著风险"]
                    gap(bid, "无风险/机会输入，已按板块库要求明写「未识别到显著风险」", "info")
                sec = {"type": "prose", "title": bname, "columns": 2, "panels": [
                    {"title": "风险", "items": risks or ["本期未识别到显著风险"]},
                    {"title": "机会", "items": opps or ["本期未识别到显著机会"]},
                ]}

            elif bid == "B17":
                acts = self._text_list(narr.get("actions")) or ins_action
                if acts:
                    items_ = []
                    for a in acts:
                        if isinstance(a, dict):
                            items_.append({"text": self._item_text(a),
                                           "badge": str(a.get("priority") or "中")})
                        else:
                            items_.append(str(a))
                    sec = {"type": "prose", "title": bname, "items": items_}
                else:
                    gap(bid, "未识别出可行动项，行动建议已省略", "info")

            elif bid == "B18":
                defs = self._text_list(narr.get("definitions"))
                if not defs:
                    # 从实际指标反推口径（不编造数值，只说明来源与计算字段）
                    cols = [self._humanize_key(str(k)) for k in (kpis.keys() if isinstance(kpis, dict) else [])]
                    if cols:
                        defs = [f"{c}：由数据源对应字段聚合得出，统计周期同报表范围" for c in cols]
                        gap(bid, "narrative.definitions 未提供，已按指标名生成基础口径说明")
                if defs:
                    sec = {"type": "prose", "title": bname,
                           "items": [self._item_text(x) for x in defs]}
                else:
                    gap(bid, "口径定义缺失（板块库要求不得省略）", "blocking")

            elif bid == "B19":
                q = analysis.get("data_quality") or analysis.get("quality") or {}
                notes = [self._item_text(x) for x in self._text_list(narr.get("quality_notes"))]
                score = narr.get("quality_score", analysis.get("quality_score"))
                if isinstance(q, dict) and q:
                    miss = [f"{k} 缺失 {v.get('null_count')} 条"
                            for k, v in q.items()
                            if isinstance(v, dict) and v.get("null_count")]
                    notes.extend(miss)
                if score is not None:
                    notes.insert(0, f"数据质量评分：{score}")
                sec = {"type": "prose", "title": bname,
                       "items": notes or ["未提供数据质量信息"]}
                if not notes:
                    gap(bid, "无数据质量明细", "content")

            elif bid == "B20":
                methods = [self._item_text(x) for x in self._text_list(narr.get("methods"))]
                if not methods:
                    used = sorted({(c.get("chart_type") or c.get("type") or "")
                                   for c in all_charts} & block_library.ENGINE_CHARTS)
                    label = {"line": "趋势分析", "area": "趋势分析", "bar": "对比分析",
                             "horizontal_bar": "排名分析", "stacked_bar": "结构对比",
                             "pie": "构成分析", "ring": "构成分析", "treemap": "层级构成",
                             "scatter": "相关性分析", "heatmap": "关联热力",
                             "radar": "多维对比", "gauge": "目标达成", "funnel": "转化漏斗",
                             "sankey": "流向分析", "word_cloud": "词频分析"}
                    methods = [f"{label.get(u, u)}：使用 {u} 图呈现" for u in used if u]
                    if methods:
                        gap(bid, "narrative.methods 未提供，已按实际使用图表反推")
                if methods:
                    sec = {"type": "prose", "title": bname, "items": methods}
                else:
                    gap(bid, "无分析方法可列", "content")

            elif bid == "B21":
                apx = [self._item_text(x) for x in self._text_list(narr.get("appendix"))]
                if apx:
                    sec = {"type": "prose", "title": bname, "items": apx}
                else:
                    gap(bid, "无附录内容，已省略", "info")

            elif bid == "B22":
                closing = narr.get("closing") or ""
                if not closing:
                    first = (ins_core[0]["text"] if ins_core else
                             (ins_plain[0] if ins_plain else ""))
                    closing = f"本期核心结论：{first}" if first else "本期报表已完成。"
                    gap(bid, "narrative.closing 未提供，已用首条结论复述")
                sec = {"type": "prose", "title": bname, "variant": "cover",
                       "body": closing,
                       "eyebrow": narr.get("next_review") or ""}

            else:
                # 分析族（B07–B12 / B14）：走图表装配
                sec = chart_section(bid, bname)
                if not sec:
                    chain = block_library.chart_chain(bid)
                    gap(bid, f"无匹配图表（可接受类型 {chain or '无'}，"
                             f"现有图表 {[c.get('chart_type') or c.get('type') for c in all_charts]}）",
                        "blocking")

            if sec:
                sec.setdefault("_block", bid)
                sections.append(sec)
                resolved.append(bid)
            elif bid not in [g["block"] for g in gaps]:
                gap(bid, "装配后无内容", "blocking")

        # 未落到任何板块的图表：不丢弃，附到最后的分区，避免数据静默消失
        # 未渲染的图表：包括「无归属」和「有归属但超出该板块容量」两类。
        # 用 used 判定，不能用 consumed——后者把绑定图预先算作已消费。
        orphan = [c for c in all_charts if id(c) not in used]
        if orphan:
            items = [{
                "type": "chart",
                "chart_type": c.get("chart_type") or c.get("type") or "bar",
                "title": c.get("title", "补充图表"),
                "data": self._normalize_chart_data(c),
                "description": c.get("description", ""),
                "insight_level": c.get("insight_level", "基础"),
                "span": 1,
            } for c in orphan]
            sections.append({"type": "section_group", "title": "补充图表",
                             "description": "板块清单未覆盖、或超出板块容量的图表（供核对）",
                             "columns": 3, "items": items, "_block": "_orphan"})
            for c in orphan:
                bid = str(c.get("block") or "")
                why = (f"超出板块 {bid} 的容量" if bid else "未绑定到任何板块")
                gap("_orphan", f"图表「{c.get('title', '')}」{why}")

        return {
            "title": analysis.get("title", "数据报表"),
            "generated_at": analysis.get("data_source", ""),
            "color_scheme": preferences.get("color_scheme", ""),
            "sections": sections,
            "_blocks": resolved,
            "_gaps": gaps,
            "_mode": "blocks",
        }

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
