"""
vision_tools 数据特征提取模块
只负责提取数据特征，不负责图表选型决策

核心设计原则：
  - CLI只负责数据加载和特征提取
  - AI Agent负责图表选型决策
"""
from typing import List, Dict, Any
import pandas as pd


class DataFeatureExtractor:
    """
    数据特征提取器
    只负责提取数据特征，不负责图表选型决策
    
    使用示例:
        extractor = DataFeatureExtractor()
        features = extractor.extract_features(data)
    """
    
    def extract_features(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        提取数据特征
        
        参数:
            data: 数据字典，包含原始数据、维度、聚合数据
            
        返回:
            {
                "has_time_dimension": bool,
                "has_category_dimension": bool,
                "has_numeric_dimension": bool,
                "time_points": int,
                "category_count": int,
                "numeric_range": {"min": 0, "max": 100},
                "data_distribution": "normal/skewed",
                "has_missing_values": bool,
                "missing_rate": 0.05,
                "concentration": {"cr4": 0.75, "hhi": 2500},
                "trend": {"direction": "上升", "strength": 0.15},
                "distribution": {"skewness": 1.85, "kurtosis": 2.1},
                "anomalies": [{"index": 15, "value": 500000, "deviation": 10.0}]
            }
        """
        features = {}
        
        # 提取维度特征
        dimensions = data.get("dimensions", {})
        features["has_time_dimension"] = len(dimensions.get("时间", [])) > 0
        features["has_category_dimension"] = len(dimensions.get("分类", [])) > 0
        features["has_numeric_dimension"] = len(dimensions.get("数值", [])) > 0
        
        # 提取时间维度特征
        if features["has_time_dimension"]:
            time_features = self._extract_time_features(data)
            features.update(time_features)
        
        # 提取分类维度特征
        if features["has_category_dimension"]:
            category_features = self._extract_category_features(data)
            features.update(category_features)
        
        # 提取数值维度特征
        if features["has_numeric_dimension"]:
            numeric_features = self._extract_numeric_features(data)
            features.update(numeric_features)
        
        # 提取聚合数据特征
        aggregated = data.get("aggregated", {})
        if aggregated:
            aggregated_features = self._extract_aggregated_features(aggregated)
            features.update(aggregated_features)
        
        return features
    
    def _extract_time_features(self, data: Dict) -> Dict:
        """提取时间维度特征"""
        dimensions = data.get("dimensions", {})
        raw_data = data.get("raw_data", {})
        
        time_dim = dimensions.get("时间", [None])[0]
        if not time_dim:
            return {}
        
        time_values = raw_data.get(time_dim, [])
        
        return {
            "time_points": len(time_values),
            "time_range": {
                "start": min(time_values) if time_values else None,
                "end": max(time_values) if time_values else None
            },
            "time_granularity": self._detect_time_granularity(time_values)
        }
    
    def _extract_category_features(self, data: Dict) -> Dict:
        """提取分类维度特征"""
        dimensions = data.get("dimensions", {})
        raw_data = data.get("raw_data", {})
        
        category_dim = dimensions.get("分类", [None])[0]
        if not category_dim:
            return {}
        
        category_values = raw_data.get(category_dim, [])
        unique_values = list(set(category_values))
        
        return {
            "category_count": len(unique_values),
            "categories": unique_values,
            "category_distribution": self._calc_distribution(category_values)
        }
    
    def _extract_numeric_features(self, data: Dict) -> Dict:
        """提取数值维度特征"""
        dimensions = data.get("dimensions", {})
        raw_data = data.get("raw_data", {})
        
        numeric_dim = dimensions.get("数值", [None])[0]
        if not numeric_dim:
            return {}
        
        numeric_values = raw_data.get(numeric_dim, [])
        valid_values = [v for v in numeric_values if v is not None]
        
        if not valid_values:
            return {
                "numeric_range": {"min": 0, "max": 0},
                "has_missing_values": len(numeric_values) > 0,
                "missing_rate": 0
            }
        
        return {
            "numeric_range": {
                "min": min(valid_values),
                "max": max(valid_values)
            },
            "has_missing_values": len(numeric_values) != len(valid_values),
            "missing_rate": 1 - len(valid_values) / max(len(numeric_values), 1)
        }
    
    def _extract_aggregated_features(self, aggregated: Dict) -> Dict:
        """提取聚合数据特征——委派到 DataStatistics 模块进行完整计算"""
        features = {}

        # 提取集中度特征：将嵌套字典展开为 {label: value} 格式
        # by_dimension 结构为 {"dim1": {"col1": {val1: sum1, val2: sum2}}}
        # DataStatistics.calc_concentration 要求 {维度值: 指标值}
        by_dimension = aggregated.get("by_dimension", {})
        if by_dimension:
            # 取第一个维度的第一个指标的聚合数据
            first_dim = next(iter(by_dimension.values()), {})
            first_metric = next(iter(first_dim.values()), {})
            if first_metric and isinstance(first_metric, dict):
                features["concentration"] = self._calc_concentration(first_metric)

        # 提取趋势特征
        # total 结构为 {"col1": {"sum": ..., "avg": ...}}，没有时间序列数据
        # 实际趋势计算需要在 analyze 中按时间维度分组后传入时间序列，
        # 此处仅做标记，由调用方（analyze action 或 AI Agent）补充时间序列数据
        total = aggregated.get("total", {})
        if total:
            # 取第一个数值列的总和值作为"趋势末尾点"参考
            first_metric_key = next(iter(total.keys()), None)
            if first_metric_key:
                first_metric = total[first_metric_key]
                features["trend_reference"] = {
                    "total_sum": first_metric.get("sum", 0),
                    "total_avg": first_metric.get("avg", 0),
                    "note": "完整趋势分析请按时间维度分组后调用 calc_trend"
                }

        return features
    
    def _detect_time_granularity(self, time_values: List) -> str:
        """检测时间粒度"""
        if len(time_values) < 2:
            return "unknown"
        
        # 简化实现
        return "monthly"
    
    def _calc_distribution(self, values: List) -> Dict:
        """计算分布"""
        from collections import Counter
        counter = Counter(values)
        total = len(values)
        
        return {
            item: count / total for item, count in counter.items()
        }
    
    def _calc_concentration(self, by_dimension: Dict) -> Dict:
        """计算集中度——委派到 DataStatistics 模块进行完整计算"""
        from conspect_tools.data_statistics import DataStatistics
        stats = DataStatistics()
        return stats.calc_concentration(by_dimension)
    
    def _calc_trend(self, values: List[float]) -> Dict:
        """计算趋势——委派到 DataStatistics 模块进行完整计算"""
        from conspect_tools.data_statistics import DataStatistics
        stats = DataStatistics()
        return stats.calc_trend(values)
    
    def extract_chart_features(self, chart_data: Dict) -> Dict:
        """
        提取单个图表的数据特征
        
        参数:
            chart_data: 图表数据
            
        返回:
            {
                "data_points": 12,
                "data_range": {"min": 0, "max": 100},
                "has_negative_values": False,
                "has_zero_values": True,
                "data_variance": 15.5
            }
        """
        values = chart_data.get("values", [])
        
        if not values:
            return {
                "data_points": 0,
                "data_range": {"min": 0, "max": 0},
                "has_negative_values": False,
                "has_zero_values": False,
                "data_variance": 0
            }
        
        valid_values = [v for v in values if v is not None]
        
        return {
            "data_points": len(valid_values),
            "data_range": {
                "min": min(valid_values),
                "max": max(valid_values)
            },
            "has_negative_values": any(v < 0 for v in valid_values),
            "has_zero_values": any(v == 0 for v in valid_values),
            "data_variance": self._calc_variance(valid_values)
        }
    
    def _calc_variance(self, values: List) -> float:
        """计算方差"""
        if not values:
            return 0
        
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5
