"""
vision Skill 配置管理模块
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
    "supported_extensions": [".xlsx", ".xls"],
    "max_sheets": 50,
    "max_rows": 500000,
}

# 渲染配置
RENDER_CONFIG = {
    "theme": "business_light",
    "echarts_cdn": "https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js",
    "output_formats": ["html", "pdf", "png"],
}


def get_harness_path(filename: str) -> Path:
    """获取产物文件的完整路径。"""
    return HARNESS_DIR / filename
