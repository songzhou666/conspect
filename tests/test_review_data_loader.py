"""
ReviewDataLoader 测试用例
测试审核数据加载功能
"""
import unittest
import sys
import json
import tempfile
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from conspect_tools.review_data_loader import ReviewDataLoader


class TestReviewDataLoader(unittest.TestCase):
    """测试 ReviewDataLoader 主类"""
    
    def setUp(self):
        """测试前准备"""
        self.loader = ReviewDataLoader()
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_temp_file(self, filename, data):
        """创建临时文件"""
        filepath = Path(self.temp_dir) / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        return str(filepath)
    
    def test_load_review_context(self):
        """测试加载审核上下文"""
        raw_data_file = self._create_temp_file("raw_data.json", {"data": [1, 2, 3]})
        analysis_file = self._create_temp_file("analysis.json", {"dimensions": ["date"]})
        
        context = self.loader.load_review_context({
            "raw_data_file": raw_data_file,
            "analysis_file": analysis_file
        })
        
        self.assertIn("raw_data", context)
        self.assertIn("analysis", context)
    
    def test_load_chart_data(self):
        """测试加载图表数据"""
        implement_file = self._create_temp_file("implement.json", {
            "charts": [{"id": "C1", "data": [100, 200, 300]}]
        })
        
        chart_data = self.loader.load_chart_data("C1", implement_file)
        self.assertIsNotNone(chart_data)
        self.assertEqual(chart_data["chart_id"], "C1")
    
    def test_compare_data_consistent(self):
        """测试数据一致性比较（一致）"""
        data1 = {"sales": 1000000, "count": 100}
        data2 = {"sales": 1000000, "count": 100}
        
        result = self.loader.compare_data(data1, data2)
        self.assertTrue(result["is_consistent"])
        self.assertEqual(len(result["differences"]), 0)
    
    def test_compare_data_inconsistent(self):
        """测试数据一致性比较（不一致）"""
        data1 = {"sales": 1000000, "count": 100}
        data2 = {"sales": 900000, "count": 100}
        
        result = self.loader.compare_data(data1, data2)
        self.assertFalse(result["is_consistent"])
        self.assertGreater(len(result["differences"]), 0)
    
    def test_extract_chart_list(self):
        """测试提取图表列表"""
        design = {
            "charts": [
                {"id": "C1", "type": "line"},
                {"id": "C2", "type": "bar"}
            ]
        }
        
        chart_list = self.loader.extract_chart_list(design)
        self.assertEqual(len(chart_list), 2)
        self.assertEqual(chart_list[0]["id"], "C1")
    
    def test_extract_color_scheme(self):
        """测试提取配色方案"""
        design = {
            "charts": [
                {"id": "C1", "colors": ["#2B5F8A", "#4A90D9"]}
            ]
        }
        
        colors = self.loader.extract_color_scheme(design, "C1")
        self.assertEqual(len(colors), 2)
        self.assertEqual(colors[0], "#2B5F8A")


if __name__ == "__main__":
    unittest.main()
