"""
ReportRenderer 测试用例
测试报告渲染功能

接口契约（v3.2 校正）：
    render_markdown(report_design) -> str
    render_html(report_design) -> str
    render_pdf(report_design) -> bytes
    render_word(report_design) -> bytes

渲染方法**只返回内容、不写盘**；写盘由 Exporter（save_report 动作）负责。
历史说明：v3.1 及以前的测试按 `render_xxx(report_design, output_path)` 两参调用
并断言文件被创建，与实现签名不符，必然 TypeError。v3.2 依真实签名重写。
"""
import unittest
import sys
import tempfile
import shutil
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from conspect_tools.report_renderer import ReportRenderer


SAMPLE_DESIGN = {
    "title": "销售数据分析报告",
    "sections": [
        {"type": "summary", "content": "销售总额 100 万"},
        {"type": "chart", "chart_id": "C1"},
    ],
}


class TestReportRenderer(unittest.TestCase):
    """测试 ReportRenderer 主类"""

    def setUp(self):
        self.renderer = ReportRenderer()
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write(self, content, name):
        path = Path(self.temp_dir) / name
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
        return path

    def test_render_markdown_returns_str(self):
        content = self.renderer.render_markdown(SAMPLE_DESIGN)
        self.assertIsInstance(content, str)
        self.assertIn("销售数据分析报告", content)

    def test_render_markdown_content_can_be_persisted(self):
        content = self.renderer.render_markdown(SAMPLE_DESIGN)
        path = self._write(content, "report.md")
        self.assertTrue(path.exists())
        self.assertIn("销售数据分析报告", path.read_text(encoding="utf-8"))

    def test_render_html_returns_html_document(self):
        content = self.renderer.render_html(SAMPLE_DESIGN)
        self.assertIsInstance(content, str)
        self.assertIn("<html", content.lower())
        self.assertIn("销售数据分析报告", content)

    def test_render_pdf_returns_bytes(self):
        content = self.renderer.render_pdf(SAMPLE_DESIGN)
        self.assertIsInstance(content, bytes)
        self.assertGreater(len(content), 0)

    def test_render_word_returns_bytes(self):
        content = self.renderer.render_word(SAMPLE_DESIGN)
        self.assertIsInstance(content, bytes)
        self.assertGreater(len(content), 0)

    def test_empty_report_renders_without_error(self):
        content = self.renderer.render_markdown({"title": "", "sections": []})
        self.assertIsInstance(content, str)

    def test_theme_is_configurable(self):
        renderer = ReportRenderer(theme_name="A49")
        self.assertIsNotNone(renderer.theme)
        self.assertIsInstance(renderer.render_markdown(SAMPLE_DESIGN), str)


if __name__ == "__main__":
    unittest.main()
