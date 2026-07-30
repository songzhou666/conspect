"""
vision_tools 审核数据加载模块
只负责加载审核所需的数据，不负责审核决策

核心设计原则：
  - CLI只负责数据加载和简单比较
  - AI Agent负责审核决策
"""
from typing import Dict, List, Any, Optional
from pathlib import Path
import json


class ReviewDataLoader:
    """
    审核数据加载器
    只负责加载审核所需的数据，不负责审核决策
    
    使用示例:
        loader = ReviewDataLoader(project_root)
        context = loader.load_review_context(params)
        comparison = loader.compare_data(data1, data2)
    """
    
    def __init__(self, project_root: Optional[str] = None):
        """
        初始化审核数据加载器
        
        参数:
            project_root: 项目根目录
        """
        self.project_root = Path(project_root) if project_root else Path.cwd()
    
    def load_json(self, filepath: str) -> Dict:
        """加载 JSON 文件"""
        path = self.project_root / filepath
        if not path.exists():
            return {}
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def load_text(self, filepath: str) -> str:
        """加载文本文件"""
        path = self.project_root / filepath
        if not path.exists():
            return ""
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def load_review_context(self, params: Dict) -> Dict[str, Any]:
        """
        加载审核所需的所有上下文
        
        参数:
            params: 参数字典
                - raw_data_file: 原始数据文件路径
                - analysis_file: 分析结果文件路径
                - design_file: 设计文档文件路径
                - implement_file: 实现文档文件路径
            
        返回:
            {
                "raw_data": {...},
                "analysis": {...},
                "design": {...},
                "implement": {...}
            }
        """
        return {
            "raw_data": self.load_json(params.get("raw_data_file", "")),
            "analysis": self.load_json(params.get("analysis_file", "")),
            "design": self.load_json(params.get("design_file", "")),
            "implement": self.load_json(params.get("implement_file", ""))
        }
    
    def load_chart_data(self, chart_id: str, 
                        implement_data: Dict) -> Optional[Dict]:
        """
        加载图表数据
        
        参数:
            chart_id: 图表 ID
            implement_data: 实现数据
            
        返回:
            {
                "chart_id": "C1",
                "data": [100, 200, 300],
                "type": "line",
                "colors": ["#2B5F8A"],
                "layout": {"x": 0, "y": 0, "width": 12, "height": 6}
            }
        """
        charts = implement_data.get("charts", [])
        chart = next((c for c in charts if c.get("id") == chart_id), None)
        
        if not chart:
            return None
        
        return {
            "chart_id": chart_id,
            "data": chart.get("data", []),
            "type": chart.get("type", ""),
            "colors": chart.get("colors", []),
            "layout": chart.get("layout", {})
        }
    
    def compare_data(self, data1: Any, data2: Any, 
                     tolerance: float = 0.001) -> Dict[str, Any]:
        """
        比较两个数据的一致性
        
        参数:
            data1: 第一个数据
            data2: 第二个数据
            tolerance: 容差（默认 0.1%）
            
        返回:
            {
                "is_consistent": False,
                "differences": [
                    {
                        "field": "sales",
                        "value1": 1000000,
                        "value2": 900000,
                        "diff_percent": 10.0
                    }
                ]
            }
        """
        differences = []
        
        if isinstance(data1, dict) and isinstance(data2, dict):
            # 比较字典
            all_keys = set(data1.keys()) | set(data2.keys())
            for key in all_keys:
                value1 = data1.get(key)
                value2 = data2.get(key)
                
                if value1 != value2:
                    diff = self._calc_difference(value1, value2)
                    if diff is not None:
                        differences.append({
                            "field": key,
                            "value1": value1,
                            "value2": value2,
                            "diff_percent": diff
                        })
        elif isinstance(data1, (int, float)) and isinstance(data2, (int, float)):
            # 比较数值
            diff = self._calc_difference(data1, data2)
            if diff is not None and diff > tolerance * 100:
                differences.append({
                    "field": "value",
                    "value1": data1,
                    "value2": data2,
                    "diff_percent": diff
                })
        
        return {
            "is_consistent": len(differences) == 0,
            "differences": differences
        }
    
    def _calc_difference(self, value1: Any, value2: Any) -> Optional[float]:
        """计算差异百分比"""
        if value1 is None or value2 is None:
            return None
        
        if not isinstance(value1, (int, float)) or not isinstance(value2, (int, float)):
            return None
        
        if value1 == 0:
            return None
        
        return abs(value1 - value2) / abs(value1) * 100
    
    def extract_chart_list(self, data: Dict) -> List[Dict]:
        """
        提取图表列表
        
        参数:
            data: 数据字典
            
        返回:
            [
                {
                    "id": "C1",
                    "type": "line",
                    "title": "趋势图",
                    "dimension": "日期",
                    "metric": "销售额"
                }
            ]
        """
        charts = data.get("charts", [])
        
        return [
            {
                "id": chart.get("id", ""),
                "type": chart.get("type", ""),
                "title": chart.get("title", ""),
                "dimension": chart.get("dimension", ""),
                "metric": chart.get("metric", "")
            }
            for chart in charts
        ]
    
    def extract_color_scheme(self, data: Dict) -> Dict[str, str]:
        """
        提取配色方案
        
        参数:
            data: 数据字典
            
        返回:
            {
                "primary": "#2B5F8A",
                "secondary": "#4A9BD9",
                "background": "#F5F7FA"
            }
        """
        return data.get("color_scheme", {})
    
    def extract_layout(self, data: Dict) -> Dict[str, Any]:
        """
        提取布局信息
        
        参数:
            data: 数据字典
            
        返回:
            {
                "grid_system": "24栅格",
                "header_height": 80,
                "kpi_row_height": 120,
                "chart_height": 380
            }
        """
        return data.get("layout", {})
