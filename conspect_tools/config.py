"""
conspect Skill 配置管理模块
"""
import os
from pathlib import Path

# 项目根路径
PROJECT_ROOT = Path(os.getcwd())

# 产物路径
HARNESS_DIR = PROJECT_ROOT / ".agent" / "harness"

# 数据配置
DATA_CONFIG = {
    "max_file_size_mb": 100,
    "supported_extensions": [".xlsx", ".xls", ".csv"],
    "max_sheets": 50,
    "max_rows": 500000,
}

# 渲染配置
RENDER_CONFIG = {
    "theme": "business_light",
    "echarts_cdn": "https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js",
    "output_formats": ["html", "pdf", "png"],
}

# 报告配置
REPORT_CONFIG = {
    "output_formats": ["md", "html", "pdf", "docx"],
    "default_format": "md",
    "template_dir": "templates/reports",
}

# 中文命名映射
CHINESE_NAME_MAP = {
    "dashboard.html": "数据看板.html",
    "dashboard.pdf": "数据看板.pdf",
    "dashboard.png": "数据看板.png",
    "report.md": "分析报告.md",
    "report.html": "分析报告.html",
    "report.pdf": "分析报告.pdf",
    "report.docx": "分析报告.docx",
}

# AI Agent 配置
AI_AGENT_CONFIG = {
    "enable_chart_decision": True,
    "enable_insight_generation": True,
    "enable_quality_review": True,
    "review_timeout_seconds": 300,
}


def get_harness_path(filename: str) -> Path:
    """获取产物文件的完整路径。"""
    return HARNESS_DIR / filename


class Config:
    """配置管理类，提供字典式配置访问。"""

    PROJECT_ROOT = PROJECT_ROOT
    HARNESS_DIR = HARNESS_DIR
    DATA_CONFIG = DATA_CONFIG
    RENDER_CONFIG = RENDER_CONFIG
    REPORT_CONFIG = REPORT_CONFIG
    CHINESE_NAME_MAP = CHINESE_NAME_MAP
    AI_AGENT_CONFIG = AI_AGENT_CONFIG

    @classmethod
    def get(cls, key: str, default=None):
        """获取配置项（兼容字典式访问）。"""
        return getattr(cls, key, default)
