"""
AIAgent 测试用例
测试 AI Agent 的图表选型、洞察生成、质量审核等功能
"""
import unittest
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from conspect_tools.ai_agent import AIAgent, ChartDecision, InsightDecision, RecommendationDecision, ReviewDecision


class TestChartDecision(unittest.TestCase):
    """测试 ChartDecision 数据类"""
    
    def test_chart_decision_creation(self):
        """测试创建 ChartDecision 对象"""
        decision = ChartDecision(
            chart_type="line",
            reason="时间序列数据适合折线图",
            config={"x_axis": "date", "y_axis": "value"}
        )
        self.assertEqual(decision.chart_type, "line")
        self.assertIn("时间序列", decision.reason)
    
    def test_chart_decision_to_dict(self):
        """测试 ChartDecision 转字典"""
        decision = ChartDecision(
            chart_type="bar",
            reason="分类对比适合柱状图",
            config={"x_axis": "category", "y_axis": "value"}
        )
        result = decision.to_dict()
        self.assertEqual(result["chart_type"], "bar")
        self.assertIn("reason", result)


class TestInsightDecision(unittest.TestCase):
    """测试 InsightDecision 数据类"""
    
    def test_insight_decision_creation(self):
        """测试创建 InsightDecision 对象"""
        decision = InsightDecision(
            insights=[
                {"title": "销售增长", "description": "销售额环比增长15%"}
            ],
            recommendations=[
                {"title": "加大投入", "priority": "high"}
            ]
        )
        self.assertEqual(len(decision.insights), 1)
        self.assertEqual(len(decision.recommendations), 1)
    
    def test_insight_decision_to_dict(self):
        """测试 InsightDecision 转字典"""
        decision = InsightDecision(
            insights=[{"title": "测试"}],
            recommendations=[{"title": "建议"}]
        )
        result = decision.to_dict()
        self.assertIn("insights", result)
        self.assertIn("recommendations", result)


class TestRecommendationDecision(unittest.TestCase):
    """测试 RecommendationDecision 数据类"""
    
    def test_recommendation_decision_creation(self):
        """测试创建 RecommendationDecision 对象"""
        decision = RecommendationDecision(
            recommendations=[
                {"title": "优化产品", "priority": "high", "action": "调整产品线"}
            ]
        )
        self.assertEqual(len(decision.recommendations), 1)
    
    def test_recommendation_decision_to_dict(self):
        """测试 RecommendationDecision 转字典"""
        decision = RecommendationDecision(
            recommendations=[{"title": "测试"}]
        )
        result = decision.to_dict()
        self.assertIn("recommendations", result)


class TestReviewDecision(unittest.TestCase):
    """测试 ReviewDecision 数据类"""
    
    def test_review_decision_creation(self):
        """测试创建 ReviewDecision 对象"""
        decision = ReviewDecision(
            passed=True,
            score=85.0,
=[],
            summary="审核通过"
        )
        self.assertTrue(decision.passed)
        self.assertEqual(decision.score, 85.0)
    
    def test_review_decision_to_dict(self):
        """测试 ReviewDecision 转字典"""
        decision = ReviewDecision(
            passed=False,
            score=60.0,
            issues=[{"title": "数据不一致"}],
            summary="审核不通过"
        )
        result = decision.to_dict()
        self.assertIn("passed", result)
        self.assertIn("issues", result)


class TestAIAgent(unittest.TestCase):
    """测试 AIAgent 主类"""
    
    def setUp(self):
        """测试前准备"""
        self.agent = AIAgent()
    
    def test_decide_chart(self):
        """测试图表选型决策"""
        features = {
            "has_time_dimension": True,
            "has_numeric_dimension": True,
            "time_points": 12
        }
        decision = self.agent.decide_chart(features, "销售数据分析")
        self.assertIsNotNone(decision)
        self.assertIn("chart_type", decision.to_dict())
    
    def test_generate_insights(self):
        """测试洞察生成"""
        statistics = {
            "total": 1000000,
            "average": 50000,
            "trend": {"direction": "上升", "strength": 0.15}
        }
        decision = self.agent.generate_insights(statistics, "销售数据分析")
        self.assertIsNotNone(decision)
        self.assertIn("insights", decision.to_dict())
    
    def test_review_design(self):
        """测试设计审核"""
        analysis = {"dimensions": ["date", "product"], "metrics": ["sales"]}
        design = {"charts": [{"id": "C1", "type": "line"}]}
        decision = self.agent.review_design(analysis, design)
        self.assertIsNotNone(decision)
        self.assertIn("passed", decision.to_dict())
    
    def test_review_implement(self):
        """测试实现审核"""
        design = {"charts": [{"id": "C1", "type": "line", "colors": ["#2B5F8A"]}]}
        implement = {"charts": [{"id": "C1", "type": "line", "colors": ["#2B5F8A"]}]}
        decision = self.agent.review_implement(design, implement)
        self.assertIsNotNone(decision)
        self.assertIn("passed", decision.to_dict())


if __name__ == "__main__":
    unittest.main()
