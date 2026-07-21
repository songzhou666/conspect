"""
vision_tools 导出模块
处理文件保存、PDF/PNG导出
"""
from pathlib import Path
from typing import Optional


class Exporter:
    """文件导出器"""

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = Path(output_dir) if output_dir else Path.cwd() / "output"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_html(self, content: str, filename: str = "report.html") -> str:
        """保存HTML文件。"""
        filepath = self.output_dir / filename
        filepath.write_text(content, encoding="utf-8")
        return str(filepath)

    def save_pdf(self, content: bytes, filename: str = "report.pdf") -> str:
        """保存PDF文件。"""
        filepath = self.output_dir / filename
        filepath.write_bytes(content)
        return str(filepath)

    def save_png(self, content: bytes, filename: str = "report.png") -> str:
        """保存PNG文件。"""
        filepath = self.output_dir / filename
        filepath.write_bytes(content)
        return str(filepath)
