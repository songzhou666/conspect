"""
DataStatistics 测试用例
测试数据统计功能
"""
import unittest
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from conspect_tools.data_statistics import DataStatistics


class TestDataStatistics(unittest.TestCase):
    """测试 DataStatistics 主类"""
    
    def setUp(self):
        """测试前准备"""
        self.statistics = DataStatistics()
    
    def test_calc_basic_stats(self):
        """测试基础统计计算"""
        values = [100, 200, 300, 400, 500]
        stats = self.statistics.calc_basic_stats(values)
        self.assertEqual(stats["total"], 1500)
        self.assertEqual(stats["average"], 300)
        self.assertEqual(stats["count"], 5)
        self.assertEqual(stats["min"], 100)
        self.assertEqual(stats["max"], 500)
    
    def test_calc_concentration(self):
        """测试集中度计算"""
        values = [500, 200, 100, 50, 30]
        concentration = self.statistics.calc_concentration(values)
        self.assertIn("cr4", concentration)
        self.assertIn("hhi", concentration)
        self.assertGreater(concentration["cr4"], 0)
    
    def test_calc_trend(self):
        """测试趋势计算"""
        time_series = [100, 120, 150, 180, 200]
        trend = self.statistics.calc_trend(time_series)
        self.assertIn("direction", trend)
        self.assertIn("strength", trend)
        self.assertEqual(trend["direction"], "上升")
    
    def test_calc_distribution(self):
        """测试分布计算"""
        values = [100, 200, 300, 400, 500]
        distribution = self.statistics.calc_distribution(values)
        self.assertIn("skewness", distribution)
        self.assertIn("kurtosis", distribution)
    
    def test_detect_anomalies(self):
        """测试异常检测"""
        values = [100, 105, 98, 102, 500, 95, 103]
        anomalies = self.statistics.detect_anomalies(values)
        self.assertIsInstance(anomalies, list)
        # 500 应该是异常值
        if anomalies:
            self.assertTrue(any(a["value"] == 500 for a in anomalies))
    
    def test_empty_values(self):
        """测试空值处理"""
        stats = self.statistics.calc_basic_stats([])
        self.assertEqual(stats["total"], 0)
        self.assertEqual(stats["count"], 0)


if __name__ == "__main__":
    unittest.main()
