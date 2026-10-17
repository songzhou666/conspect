"""
AIAgent 测试用例

覆盖范围：
  1. 四个决策数据类的「字段契约」—— 防止文档/调用方与实现漂移
  2. AIAgent.decide_chart 的选型规则（含降级路径）
  3. AIAgent.generate_insights / generate_insights_safe / generate_recommendations
  4. AIAgent.review_design / review_implement（v4.0 阶段为 style / render）
  5. UserPreferenceRecognizer 的偏好识别

历史说明：
  本文件在 v3.1 及以前是照着不存在的 API 写的（调用 `to_dict()`、使用
  `insights=` / `recommendations=` / `summary=` 等实现里没有的字段与参数），
  整个文件无法导入、也不反映真实行为。v3.2 依据 ai_agent.py 的真实签名重写。
"""
import unittest
import sys
from dataclasses import fields
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from conspect_tools.ai_agent import (
    AIAgent,
    ChartDecision,
    InsightDecision,
    RecommendationDecision,
    ReviewDecision,
    UserPreferenceRecognizer,
)


class TestDecisionDataclassContract(unittest.TestCase):
    """字段契约：这些名字是 CLI 与产物模板依赖的对外接口，改动必须在此同步。"""

    def test_chart_decision_fields(self):
        self.assertEqual(
            [f.name for f in fields(ChartDecision)],
            ["chart_id", "chart_type", "title", "reason", "config"],
        )

    def test_insight_decision_fields(self):
        self.assertEqual(
            [f.name for f in fields(InsightDecision)],
            ["category", "title", "description", "evidence", "severity", "related_metrics"],
        )

    def test_recommendation_decision_fields(self):
        self.assertEqual(
            [f.name for f in fields(RecommendationDecision)],
            ["title", "description", "priority", "expected_impact", "related_findings"],
        )

    def test_review_decision_fields(self):
        self.assertEqual(
            [f.name for f in fields(ReviewDecision)],
            ["phase", "passed", "score", "issues", "cross_stage_issues"],
        )

    def test_mutable_defaults_are_not_shared(self):
        """默认工厂：两个实例的可变字段不得共享同一个列表对象。"""
        a = ReviewDecision(phase="design", passed=True, score=90.0)
        b = ReviewDecision(phase="design", passed=True, score=90.0)
        a.issues.append({"title": "x"})
        self.assertEqual(b.issues, [])


class TestDecideChart(unittest.TestCase):
    """图表选型规则。"""

    def setUp(self):
        self.agent = AIAgent()

    def test_empty_features_falls_back_to_bar(self):
        decision = self.agent.decide_chart({})
        self.assertIsInstance(decision, ChartDecision)
        self.assertEqual(decision.chart_type, "bar")

    def test_time_series_small_uses_line(self):
        decision = self.agent.decide_chart({
            "has_time_dimension": True,
            "has_numeric_dimension": True,
            "time_points": 12,
        })
        self.assertEqual(decision.chart_type, "line")

    def test_time_series_large_uses_area(self):
        decision = self.agent.decide_chart({
            "has_time_dimension": True,
            "has_numeric_dimension": True,
            "time_points": 60,
        })
        self.assertEqual(decision.chart_type, "area")

    def test_many_categories_uses_horizontal_bar(self):
        decision = self.agent.decide_chart({
            "has_category_dimension": True,
            "has_numeric_dimension": True,
            "category_count": 20,
        })
        self.assertEqual(decision.chart_type, "horizontal_bar")

    def test_medium_categories_uses_bar(self):
        decision = self.agent.decide_chart({
            "has_category_dimension": True,
            "has_numeric_dimension": True,
            "category_count": 7,
        })
        self.assertEqual(decision.chart_type, "bar")

    def test_few_categories_uses_pie(self):
        decision = self.agent.decide_chart({
            "has_category_dimension": True,
            "has_numeric_dimension": True,
            "category_count": 3,
        })
        self.assertEqual(decision.chart_type, "pie")

    def test_numeric_only_uses_histogram(self):
        decision = self.agent.decide_chart({"has_numeric_dimension": True})
        self.assertEqual(decision.chart_type, "histogram")

    def test_decision_always_carries_reason(self):
        for features in (
            {},
            {"has_time_dimension": True, "has_numeric_dimension": True, "time_points": 5},
            {"has_numeric_dimension": True},
        ):
            self.assertTrue(self.agent.decide_chart(features).reason)


class TestInsightAndRecommendation(unittest.TestCase):
    """洞察与建议生成。"""

    def setUp(self):
        self.agent = AIAgent()

    def test_empty_stats_returns_empty_list(self):
        self.assertEqual(self.agent.generate_insights({}), [])

    def test_high_concentration_produces_risk_insight(self):
        insights = self.agent.generate_insights({"concentration": {"cr4": 0.7}})
        self.assertGreaterEqual(len(insights), 1)
        self.assertIsInstance(insights[0], InsightDecision)
        self.assertEqual(insights[0].category, "risk")

    def test_insight_severity_is_in_known_vocabulary(self):
        insights = self.agent.generate_insights({"concentration": {"cr4": 0.7}})
        for insight in insights:
            self.assertIn(insight.severity, {"info", "warning", "critical"})

    def test_generate_recommendations_accepts_insights(self):
        insights = self.agent.generate_insights({"concentration": {"cr4": 0.7}})
        recs = self.agent.generate_recommendations(insights)
        self.assertIsInstance(recs, list)
        for rec in recs:
            self.assertIsInstance(rec, RecommendationDecision)

    def test_generate_insights_safe_returns_structured_dict(self):
        result = self.agent.generate_insights_safe({})
        self.assertIsInstance(result, dict)
        for key in ("insights", "recommendations", "status", "error"):
            self.assertIn(key, result)


class TestReview(unittest.TestCase):
    """报表选型与生成报表阶段的审核决策。"""

    def setUp(self):
        self.agent = AIAgent()

    def test_review_design_phase(self):
        decision = self.agent.review_design({"dimensions": ["date"]}, {"charts": []})
        self.assertIsInstance(decision, ReviewDecision)
        self.assertEqual(decision.phase, "style")
        self.assertIsInstance(decision.passed, bool)

    def test_review_implement_phase(self):
        decision = self.agent.review_implement({"charts": []}, {"charts": []})
        self.assertIsInstance(decision, ReviewDecision)
        self.assertEqual(decision.phase, "render")
        self.assertIsInstance(decision.passed, bool)

    def test_score_within_range(self):
        for decision in (
            self.agent.review_design({}, {}),
            self.agent.review_implement({}, {}),
        ):
            self.assertGreaterEqual(decision.score, 0.0)
            self.assertLessEqual(decision.score, 100.0)


class TestUserPreferenceRecognizer(unittest.TestCase):
    """偏好识别：识别失败必须回落到默认值，不阻断流程。"""

    def setUp(self):
        self.agent = AIAgent()

    def test_empty_requirement_returns_defaults(self):
        prefs = self.agent.recognize_preferences("")
        for key in (
            "color_scheme",
            "output_formats",
            "layout",
            "generate_chinese_named_copy",
        ):
            self.assertIn(key, prefs)

    def test_recognizes_blue_style(self):
        """「蓝色」应映射到扁平无影 A12（其强调色为蓝）。"""
        prefs = self.agent.recognize_preferences("用蓝色调做一个看板")
        self.assertEqual(prefs["color_scheme"], "A12")

    def test_recognizes_pdf_output_format(self):
        prefs = self.agent.recognize_preferences("帮我出一份 PDF 报告")
        self.assertIn("pdf", prefs["output_formats"])

    def test_recognizes_custom_brand_color(self):
        prefs = self.agent.recognize_preferences("主色调用 #1890FF")
        self.assertEqual(prefs["custom_primary_color"], "#1890FF")

    def test_recognizer_is_directly_usable(self):
        prefs = UserPreferenceRecognizer.recognize("用暖色调")
        self.assertEqual(prefs["color_scheme"], "A42")


if __name__ == "__main__":
    unittest.main()
