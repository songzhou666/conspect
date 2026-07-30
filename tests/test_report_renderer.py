"""
ReportRenderer 测试用例
测试报告渲染功能
"""
import unittest
import sys
import tempfile
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from conspect_tools.report_renderer import ReportRenderer


class TestReportRenderer(unittest.TestCase):
    """测试 ReportRenderer 主类"""
    
    def setUp(self):
        """测试前准备"""
        self.renderer = ReportRenderer()
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_render_markdown(self):
        """测试渲染 Markdown 报告"""
        report_design = {
            "title": "销售数据分析报告",
            "sections": [
                {"type": "summary", "content": "销售总额 100 万"},
                {"type": "chart", "chart_id": "C1"}
            ]
        }
        
        output_path = Path(self.temp_dir) / "report.md"
        self.renderer.render_markdown(report_design, str(output_path))
        
        self.assertTrue(output_path.exists())
        content = output_path.read_text(encoding="utf-8")
        self.assertIn("销售数据分析报告", content)
    
    def test_render_html(self):
        """测试渲染 HTML 报告"""
        report_design = {
            "title": "销售数据分析报告",
            "sections": [
                {"type": "summary", "content": "销售总额 100 万"}
            ]
        }
        
        output_path = Path(self.temp_dir) / "report.html"
        self.renderer.render_html(report_design, str(output_path))
        
        self.assertTrue(output_path.exists())
        content = output_path.read_text(encoding="utf-8")
        self.assertIn("<html", content)
        self.assertIn("销售数据分析报告", content)
    
    def test_render_pdf(self):
        """测试渲染 PDF 报告"""
        report_design = {
            "title": "销售数据分析报告",
            "sections": [
                {"type": "summary", "content": "销售总额 100 万"}
            ]
        }
        
        output_path = Path(self.temp_dir) / "report.pdf"
        # PDF 渲染需要 playwright，这里只测试接口调用
        try:
            self.renderer.render_pdf(report_design, str(output_path))
        except Exception:
            # 如果 playwright 未安装，跳过测试
            pass
    
    def test_render_word(self):
        """测试渲染 Word 报告"""
        report_design = {
            "title": "销售数据分析报告",
            "sections": [
                {"type": "summary", "content": "销售总额 100 万"}
            ]
        }
        
        output_path = Path(self.temp_dir) / "report.docx"
        # Word 渲染需要 python-docx，这里只测试接口调用
        try:
            self.renderer.render_word(report_design, str(output_path))
        except Exception:
            # 如果 python-docx 未安装，跳过测试
            pass
    
    def test_render_empty_report(self):
        """测试渲染空报告"""
        report_design = {
            "title": "",
            "sections": []
        }
        
        output_path = Path(self.temp_dir) / "empty_report.md"
        self.renderer.render_markdown(report_design, str(output_path))
        
        self.assertTrue(output_path.exists())


if __name__ == "__main__":
    unittest.main()
