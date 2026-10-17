"""
ReviewDataLoader 测试用例
测试审核数据加载功能

接口契约（v3.2 校正）：
    load_review_context(params) -> Dict            # params 键：raw_data_file/analysis_file/design_file/implement_file
    load_chart_data(chart_id, implement_data) -> Optional[Dict]   # 第二参是「已解析的字典」，不是文件路径
    compare_data(data1, data2, tolerance=0.001) -> Dict
    extract_chart_list(data) -> List[Dict]
    extract_color_scheme(data) -> Dict[str, str]   # 单参，读取 data["color_scheme"]
    extract_layout(data) -> Dict[str, Any]

历史说明：v3.1 及以前本文件按 `load_chart_data(id, path)` 与
`extract_color_scheme(data, chart_id)` 调用，与实现签名不符。v3.2 依真实签名重写。
"""
import unittest
import sys
import json
import tempfile
import shutil
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from conspect_tools.review_data_loader import ReviewDataLoader


class TestReviewDataLoader(unittest.TestCase):
    """测试 ReviewDataLoader 主类"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        # project_root 指向临时目录，使相对路径解析落在隔离环境内
        self.loader = ReviewDataLoader(project_root=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_temp_file(self, filename, data):
        filepath = Path(self.temp_dir) / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        return filename

    def test_load_review_context(self):
        raw_data_file = self._create_temp_file("raw_data.json", {"data": [1, 2, 3]})
        analysis_file = self._create_temp_file("analysis.json", {"dimensions": ["date"]})

        context = self.loader.load_review_context({
            "raw_data_file": raw_data_file,
            "analysis_file": analysis_file,
        })

        self.assertIn("raw_data", context)
        self.assertIn("analysis", context)
        self.assertEqual(context["raw_data"], {"data": [1, 2, 3]})
        self.assertEqual(context["analysis"], {"dimensions": ["date"]})

    def test_load_review_context_missing_keys_does_not_raise(self):
        """缺失/空路径必须静默返回空字典，而不是抛 PermissionError。"""
        context = self.loader.load_review_context({})
        self.assertEqual(context, {"raw_data": {}, "analysis": {}, "design": {}, "implement": {}})

    def test_load_chart_data_accepts_parsed_dict(self):
        implement_data = {"charts": [{"id": "C1", "data": [100, 200, 300]}]}
        chart_data = self.loader.load_chart_data("C1", implement_data)

        self.assertIsNotNone(chart_data)
        self.assertEqual(chart_data["chart_id"], "C1")
        self.assertEqual(chart_data["data"], [100, 200, 300])

    def test_load_chart_data_unknown_id_returns_none(self):
        implement_data = {"charts": [{"id": "C1", "data": []}]}
        self.assertIsNone(self.loader.load_chart_data("NOPE", implement_data))

    def test_compare_data_consistent(self):
        result = self.loader.compare_data({"sales": 1000000, "count": 100},
                                          {"sales": 1000000, "count": 100})
        self.assertTrue(result["is_consistent"])
        self.assertEqual(len(result["differences"]), 0)

    def test_compare_data_inconsistent(self):
        result = self.loader.compare_data({"sales": 1000000, "count": 100},
                                          {"sales": 900000, "count": 100})
        self.assertFalse(result["is_consistent"])
        self.assertGreater(len(result["differences"]), 0)

    def test_extract_chart_list(self):
        design = {"charts": [{"id": "C1", "type": "line"}, {"id": "C2", "type": "bar"}]}
        chart_list = self.loader.extract_chart_list(design)
        self.assertEqual(len(chart_list), 2)
        self.assertEqual(chart_list[0]["id"], "C1")

    def test_extract_color_scheme_reads_color_scheme_key(self):
        design = {
            "charts": [{"id": "C1", "colors": ["#2B5F8A", "#4A90D9"]}],
            "color_scheme": {"primary": "#2B5F8A", "secondary": "#4A9BD9"},
        }
        colors = self.loader.extract_color_scheme(design)
        self.assertIsInstance(colors, dict)
        self.assertEqual(colors["primary"], "#2B5F8A")

    def test_extract_color_scheme_absent_returns_empty_dict(self):
        self.assertEqual(self.loader.extract_color_scheme({}), {})


if __name__ == "__main__":
    unittest.main()
