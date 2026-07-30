"""
vision_tools 多格式导出模块
支持 Markdown/HTML/PDF/Word 导出 + 中文命名复制

核心设计原则：
  - 支持多种输出格式
  - 自动生成中文命名副本
  - 中文命名映射表可配置
"""
from pathlib import Path
from typing import Optional, Union, Dict


class Exporter:
    """
    多格式文件导出器
    
    支持功能：
    - 看板导出 (HTML/PDF/PNG)
    - 报告导出 (Markdown/HTML/PDF/Word)
    - 关联索引保存
    - 中文命名复制
    
    使用示例:
        exporter = Exporter(output_dir="./output")
        # 保存看板
        exporter.save_html("<html>...</html>", "dashboard.html")
        # 保存报告
        exporter.save_report_markdown("# Report", "report.md")
        # 保存并复制中文命名
        exporter.save_with_chinese_name("<html>...</html>", "dashboard.html")
    """
    
    # 中文命名映射表（可配置）
    CHINESE_NAME_MAP = {
        "dashboard.html": "数据看板.html",
        "dashboard.pdf": "数据看板.pdf",
        "dashboard.png": "数据看板.png",
        "report.md": "分析报告.md",
        "report.html": "分析报告.html",
        "report.pdf": "分析报告.pdf",
        "report.docx": "分析报告.docx",
    }
    
    def __init__(self, output_dir: Optional[str] = None):
        """
        初始化导出器
        
        参数:
            output_dir: 输出目录路径，默认为当前目录下的 output 文件夹
        """
        self.output_dir = Path(output_dir) if output_dir else Path.cwd() / "output"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir = self.output_dir / "reports"
        self.report_dir.mkdir(exist_ok=True)
    
    # ===== 看板导出 (已有) =====
    
    def save_html(self, content: str, filename: str = "dashboard.html") -> str:
        """
        保存看板 HTML
        
        参数:
            content: HTML 内容
            filename: 文件名
            
        返回:
            文件路径
        """
        filepath = self.output_dir / filename
        filepath.write_text(content, encoding="utf-8")
        return str(filepath)
    
    def save_pdf(self, content: bytes, filename: str = "dashboard.pdf") -> str:
        """
        保存看板 PDF
        
        参数:
            content: PDF 内容
            filename: 文件名
            
        返回:
            文件路径
        """
        filepath = self.output_dir / filename
        filepath.write_bytes(content)
        return str(filepath)
    
    def save_png(self, content: bytes, filename: str = "dashboard.png") -> str:
        """
        保存看板 PNG
        
        参数:
            content: PNG 内容
            filename: 文件名
            
        返回:
            文件路径
        """
        filepath = self.output_dir / filename
        filepath.write_bytes(content)
        return str(filepath)
    
    # ===== 报告导出 (新增) =====
    
    def save_report_markdown(self, content: str, filename: str = "report.md") -> str:
        """
        保存报告为 Markdown 格式
        
        适用场景:
        - 技术团队内部传阅
        - 版本管理系统
        - 需要二次编辑
        
        参数:
            content: Markdown 内容
            filename: 文件名
            
        返回:
            文件路径
        """
        filepath = self.report_dir / filename
        filepath.write_text(content, encoding="utf-8")
        return str(filepath)
    
    def save_report_html(self, content: str, filename: str = "report.html") -> str:
        """
        保存报告为 HTML 格式
        
        特点:
        - 独立文件，可离线阅读
        - 支持目录导航
        - 支持打印优化
        
        参数:
            content: HTML 内容
            filename: 文件名
            
        返回:
            文件路径
        """
        filepath = self.report_dir / filename
        filepath.write_text(content, encoding="utf-8")
        return str(filepath)
    
    def save_report_pdf(self, content: bytes, filename: str = "report.pdf") -> str:
        """
        保存报告为 PDF 格式
        
        适用场景:
        - 正式汇报
        - 打印归档
        - 邮件发送
        
        参数:
            content: PDF 内容
            filename: 文件名
            
        返回:
            文件路径
        """
        filepath = self.report_dir / filename
        filepath.write_bytes(content)
        return str(filepath)
    
    def save_report_word(self, content: bytes, filename: str = "report.docx") -> str:
        """
        保存报告为 Word 格式
        
        适用场景:
        - 需要二次编辑
        - 领导批注
        - 模板套用
        
        参数:
            content: Word 内容
            filename: 文件名
            
        返回:
            文件路径
        """
        filepath = self.report_dir / filename
        filepath.write_bytes(content)
        return str(filepath)
    
    # ===== 关联索引 (新增) =====
    
    def save_index(self, index: Dict, filename: str = "_cs-index.json") -> str:
        """
        保存看板与报告的关联索引
        
        索引结构:
        {
            "dashboard": "reports/dashboard.html",
            "reports": {
                "markdown": "reports/report.md",
                "html": "reports/report.html",
                "pdf": "reports/report.pdf",
                "word": "reports/report.docx"
            },
            "sections": {
                "executive_summary": {"dashboard": "kpi-section", "report": "section-0"},
                "trend_analysis": {"dashboard": "chart-1", "report": "section-3.1"},
                ...
            }
        }
        
        参数:
            index: 索引字典
            filename: 文件名
            
        返回:
            文件路径
        """
        import json
        filepath = self.output_dir / filename
        filepath.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(filepath)
    
    # ===== 中文命名复制 (新增) =====
    
    def save_with_chinese_name(self, content: Union[str, bytes], filename: str, is_binary: bool = False) -> Dict[str, str]:
        """
        保存文件并复制中文命名版本
        
        参数:
            content: 文件内容
            filename: 原始文件名
            is_binary: 是否为二进制文件
            
        返回:
            {"original": "原始路径", "chinese": "中文路径"}
        """
        # 保存原始文件
        if is_binary:
            original_path = self._save_binary(content, filename)
        else:
            original_path = self._save_text(content, filename)
        
        # 复制中文命名版本
        chinese_name = self.CHINESE_NAME_MAP.get(filename, filename)
        if chinese_name != filename:
            if is_binary:
                chinese_path = self._save_binary(content, chinese_name)
            else:
                chinese_path = self._save_text(content, chinese_name)
        else:
            chinese_path = original_path
        
        return {"original": original_path, "chinese": chinese_path}
    
    def _save_text(self, content: str, filename: str) -> str:
        """
        保存文本文件
        
        参数:
            content: 文本内容
            filename: 文件名
            
        返回:
            文件路径
        """
        # 判断保存到哪个目录
        if filename.startswith("report."):
            filepath = self.report_dir / filename
        else:
            filepath = self.output_dir / filename
        filepath.write_text(content, encoding="utf-8")
        return str(filepath)
    
    def _save_binary(self, content: bytes, filename: str) -> str:
        """
        保存二进制文件
        
        参数:
            content: 二进制内容
            filename: 文件名
            
        返回:
            文件路径
        """
        # 判断保存到哪个目录
        if filename.startswith("report."):
            filepath = self.report_dir / filename
        else:
            filepath = self.output_dir / filename
        filepath.write_bytes(content)
        return str(filepath)
    
    # ===== 批量导出 (新增) =====
    
    def save_all_reports(self, reports: Dict[str, Union[str, bytes]], is_binary: bool = False) -> Dict[str, Dict[str, str]]:
        """
        批量保存所有报告格式
        
        参数:
            reports: 报告内容字典，格式为 {filename: content}
            is_binary: 是否为二进制内容
            
        返回:
            保存结果字典，格式为 {filename: {"original": path, "chinese": path}}
        """
        results = {}
        for filename, content in reports.items():
            results[filename] = self.save_with_chinese_name(content, filename, is_binary)
        return results
