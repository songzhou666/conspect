"""
DataFeatureExtractor 测试用例
测试数据特征提取功能
"""
import unittest
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from conspect_tools.data_feature_extractor import DataFeatureExtractor


class TestDataFeatureExtractor(unittest.TestCase):
    """测试 DataFeatureExtractor 主类"""
    
    def setUp(self):
        """测试前准备"""
        self.extractor = DataFeatureExtractor()
    
    def test_extract_features_with_time_series(self):
        """测试提取时间序列数据特征"""
        data = {
            "dimensions": {
                "时间": ["date"],
                "数值": ["sales"]
            },
            "raw_data": {
                "date": ["2026-01", "2026-02", "2026-03"],
                "sales": [100, 200, 300]
            }
        }
        features = self.extractor.extract_features(data)
        self.assertTrue(features["has_time_dimension"])
        self.assertTrue(features["has_numeric_dimension"])
        self.assertEqual(features["time_points"], 3)
    
    def test_extract_features_with_category(self):
        """测试提取分类数据特征"""
        data = {
            "dimensions": {
                "分类": ["product"],
                "数值": ["sales"]
            },
            "raw_data": {
                "product": ["A", "B", "C"],
                "sales": [100, 200, 300]
            }
        }
        features = self.extractor.extract_features(data)
        self.assertTrue(features["has_category_dimension"])
        self.assertTrue(features["has_numeric_dimension"])
        self.assertEqual(features["category_count"], 3)
    
    def test_extract_features_numeric_range(self):
        """测试提取数值范围特征"""
        data = {
            "dimensions": {
                "数值": ["sales"]
            },
            "raw_data": {
                "sales": [100, 200, 300, 400, 500]
            }
        }
        features = self.extractor.extract_features(data)
        self.assertIn("numeric_range", features)
        self.assertEqual(features["numeric_range"]["min"], 100)
        self.assertEqual(features["numeric_range"]["max"], 500)
    
    def test_extract_features_empty_data(self):
        """测试空数据特征提取"""
        data = {
            "dimensions": {},
            "raw_data": {}
        }
        features = self.extractor.extract_features(data)
        self.assertFalse(features["has_time_dimension"])
        self.assertFalse(features["has_category_dimension"])
        self.assertFalse(features["has_numeric_dimension"])


if __name__ == "__main__":
    unittest.main()
