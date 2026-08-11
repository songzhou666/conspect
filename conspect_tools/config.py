"""
conspect Skill 配置管理模块（v3.0 稳定性增强版）

v3.0 升级要点：
  - 新增稳定性配置（重试、超时、降级）
  - 新增用户偏好默认值（替代原确认环节的人工输入）
  - 新增异常处理配置（统一错误码、日志级别）
  - 新增全流程自动推进配置（无阻断点）
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
    "theme": "ocean",
    "echarts_cdn": "https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js",
    "output_formats": ["html", "pdf", "png"],
    "fallback_theme": "ocean",  # 主题加载失败时的兜底主题
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

# ===== v3.0 新增：稳定性配置 =====
STABILITY_CONFIG = {
    # 重试策略（失败自动重试，不阻断流程）
    "max_retries": 3,
    "retry_delay_seconds": 1.0,
    "retry_backoff_factor": 2.0,  # 指数退避因子
    # 超时配置（防卡死）
    "data_load_timeout_seconds": 120,
    "render_timeout_seconds": 180,
    "analysis_timeout_seconds": 300,
    # 降级策略（部分失败时继续流程）
    "enable_fallback": True,
    "fallback_theme": "ocean",
    "fallback_chart_type": "bar",
    "skip_optional_on_error": True,  # 非关键步骤失败时跳过而非阻断
    # 日志与诊断
    "log_level": "INFO",
    "save_diagnostic_log": True,
    "diagnostic_log_path": ".agent/harness/_cs-diagnostic.log",
}

# ===== v3.0 新增：用户偏好默认值（替代原确认环节）=====
DEFAULT_USER_PREFERENCES = {
    # 配色偏好（识别失败时使用）
    "color_scheme": "ocean",  # ocean/warm/aurora/forest/minimal
    "custom_primary_color": None,  # 如 "#1890FF"，未指定则用主题色
    # 图表偏好
    "chart_preferences": {
        "trend": "line",
        "comparison": "bar",
        "composition": "pie",
        "distribution": "histogram",
    },
    # 输出格式偏好
    "output_formats": ["html"],  # html/pdf/md/docx
    "generate_chinese_named_copy": True,
    # 分析焦点（None 表示全维度分析）
    "focus_dimensions": None,
    "focus_metrics": None,
    # 排版偏好
    "layout": "dashboard",  # dashboard/report
    "responsive": True,
}

# ===== v3.0 新增：全流程自动推进配置 =====
AUTO_FLOW_CONFIG = {
    # 状态机自动推进（无用户确认节点）
    "auto_advance": True,
    "skip_user_confirmation": True,  # v3.0 核心变更：跳过确认环节
    "insight_generation_enabled": True,  # 新增洞察生成阶段
    # QA 审核策略（不通过时自动修复，不阻断）
    "qa_auto_fix": True,
    "qa_max_retries": 2,
    "qa_block_on_p0": True,  # 仅 P0 问题阻断，其他自动修复
    # 产物兜底
    "ensure_artifacts": True,  # 缺失产物时自动生成兜底版本
}

# ===== v3.0 新增：异常错误码 =====
ERROR_CODES = {
    "DATA_LOAD_FAILED": "E001",
    "ANALYSIS_FAILED": "E002",
    "INSIGHT_FAILED": "E003",
    "DESIGN_FAILED": "E004",
    "IMPLEMENT_FAILED": "E005",
    "REPORT_FAILED": "E006",
    "VERIFY_FAILED": "E007",
    "QA_BLOCKED": "E101",  # QA 阻断（仅 P0）
    "PARTIAL_FALLBACK": "W201",  # 部分降级警告
}


def get_harness_path(filename: str) -> Path:
    """获取产物文件的完整路径。"""
    return HARNESS_DIR / filename


def ensure_harness_dir() -> Path:
    """确保产物目录存在，不存在则创建。v3.0 新增，避免产物写入失败。"""
    HARNESS_DIR.mkdir(parents=True, exist_ok=True)
    return HARNESS_DIR


def get_stability_config(key: str = None, default=None):
    """获取稳定性配置项。v3.0 新增。

    参数:
        key: 配置键，None 时返回整个配置字典
        default: 默认值
    """
    if key is None:
        return STABILITY_CONFIG
    return STABILITY_CONFIG.get(key, default)


def get_default_preferences(key: str = None, default=None):
    """获取用户偏好默认值。v3.0 新增，替代原确认环节的人工输入。

    参数:
        key: 偏好键，None 时返回整个默认偏好字典
        default: 默认值
    """
    if key is None:
        return DEFAULT_USER_PREFERENCES
    return DEFAULT_USER_PREFERENCES.get(key, default)


class Config:
    """配置管理类，提供字典式配置访问。"""

    PROJECT_ROOT = PROJECT_ROOT
    HARNESS_DIR = HARNESS_DIR
    DATA_CONFIG = DATA_CONFIG
    RENDER_CONFIG = RENDER_CONFIG
    REPORT_CONFIG = REPORT_CONFIG
    CHINESE_NAME_MAP = CHINESE_NAME_MAP
    AI_AGENT_CONFIG = AI_AGENT_CONFIG
    # v3.0 新增
    STABILITY_CONFIG = STABILITY_CONFIG
    DEFAULT_USER_PREFERENCES = DEFAULT_USER_PREFERENCES
    AUTO_FLOW_CONFIG = AUTO_FLOW_CONFIG
    ERROR_CODES = ERROR_CODES

    @classmethod
    def get(cls, key: str, default=None):
        """获取配置项（兼容字典式访问）。"""
        return getattr(cls, key, default)

    @classmethod
    def get_stability(cls, key: str = None, default=None):
        """获取稳定性配置。v3.0 新增。"""
        return get_stability_config(key, default)

    @classmethod
    def get_default_preferences(cls, key: str = None, default=None):
        """获取用户偏好默认值。v3.0 新增。"""
        return get_default_preferences(key, default)
