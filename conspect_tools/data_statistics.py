"""
vision_tools 数据统计模块
只负责基础统计计算，不负责洞察生成决策

核心设计原则：
  - CLI只负责基础统计计算
  - AI Agent负责洞察生成决策
"""
from typing import List, Dict, Any, Optional
from collections import Counter


class DataStatistics:
    """
    数据统计器
    只负责基础统计计算，不负责洞察生成决策
    
    使用示例:
        stats = DataStatistics()
        basic_stats = stats.calc_basic_stats(data)
        concentration = stats.calc_concentration(data)
        trend = stats.calc_trend(data)
    """
    
    def calc_basic_stats(self, values: List[float]) -> Dict[str, float]:
        """
        计算基础统计指标
        
        参数:
            values: 数值列表
            
        返回:
            {
                "total": 1000000,
                "average": 50000,
                "median": 45000,
                "std": 15000,
                "min": 10000,
                "max": 200000,
                "count": 20
            }
        """
        valid_values = [v for v in values if v is not None]
        
        if not valid_values:
            return {
                "total": 0,
                "average": 0,
                "median": 0,
                "std": 0,
                "min": 0,
                "max": 0,
                "count": 0
            }
        
        sorted_values = sorted(valid_values)
        count = len(sorted_values)
        total = sum(sorted_values)
        average = total / count
        
        # 中位数
        if count % 2 == 0:
            median = (sorted_values[count // 2 - 1] + sorted_values[count // 2]) / 2
        else:
            median = sorted_values[count // 2]
        
        # 标准差
        variance = sum((x - average) ** 2 for x in valid_values) / count
        std = variance ** 0.5
        
        return {
            "total": total,
            "average": average,
            "median": median,
            "std": std,
            "min": min(valid_values),
            "max": max(valid_values),
            "count": count
        }
    
    def calc_concentration(self, dimension_data: Dict[str, float]) -> Dict[str, float]:
        """
        计算集中度指标
        
        参数:
            dimension_data: 维度数据，格式为 {维度值: 指标值}
            
        返回:
            {
                "cr4": 0.75,
                "cr8": 0.90,
                "hhi": 2500,
                "gini": 0.45,
                "top_20_percent_contribution": 0.80
            }
        """
        if not dimension_data:
            return {"cr4": 0, "cr8": 0, "hhi": 0, "gini": 0, "top_20_percent_contribution": 0}
        
        # 排序
        sorted_items = sorted(dimension_data.items(), key=lambda x: x[1], reverse=True)
        total = sum(v for _, v in sorted_items)
        
        if total == 0:
            return {"cr4": 0, "cr8": 0, "hhi": 0, "gini": 0, "top_20_percent_contribution": 0}
        
        # CR4
        cr4 = sum(v for _, v in sorted_items[:4]) / total
        
        # CR8
        cr8 = sum(v for _, v in sorted_items[:8]) / total
        
        # HHI
        shares = [v / total for _, v in sorted_items]
        hhi = sum((s * 100) ** 2 for s in shares)
        
        # 基尼系数（简化计算）
        gini = self._calc_gini([v for _, v in sorted_items])
        
        # 前20%贡献
        top_20_count = max(1, len(sorted_items) // 5)
        top_20_contribution = sum(v for _, v in sorted_items[:top_20_count]) / total
        
        return {
            "cr4": cr4,
            "cr8": cr8,
            "hhi": hhi,
            "gini": gini,
            "top_20_percent_contribution": top_20_contribution
        }
    
    def _calc_gini(self, values: List[float]) -> float:
        """计算基尼系数（简化）"""
        if not values:
            return 0
        
        sorted_values = sorted(values)
        n = len(sorted_values)
        index = list(range(1, n + 1))
        
        numerator = 2 * sum(i * v for i, v in zip(index, sorted_values))
        denominator = n * sum(sorted_values)
        
        if denominator == 0:
            return 0
        
        return numerator / denominator - (n + 1) / n
    
    def calc_trend(self, time_series: List[float]) -> Dict[str, Any]:
        """
        计算趋势指标
        
        参数:
            time_series: 时间序列数据
            
        返回:
            {
                "direction": "上升",
                "strength": 0.15,
                "growth_rate": 0.12,
                "volatility": 0.05,
                "moving_average_3": [100, 110, 120],
                "forecast_next": 115
            }
        """
        if len(time_series) < 2:
            return {
                "direction": "持平",
                "strength": 0,
                "growth_rate": 0,
                "volatility": 0,
                "moving_average_3": [],
                "forecast_next": 0
            }
        
        # 趋势方向
        first_value = time_series[0]
        last_value = time_series[-1]
        
        if first_value == 0:
            direction = "持平"
            strength = 0
        else:
            strength = (last_value - first_value) / abs(first_value)
            if strength > 0.05:
                direction = "上升"
            elif strength < -0.05:
                direction = "下降"
            else:
                direction = "持平"
        
        # 增长率
        growth_rates = []
        for i in range(1, len(time_series)):
            if time_series[i - 1] != 0:
                rate = (time_series[i] - time_series[i - 1]) / abs(time_series[i - 1])
                growth_rates.append(rate)
        
        growth_rate = sum(growth_rates) / len(growth_rates) if growth_rates else 0
        
        # 波动性
        if len(time_series) > 1:
            mean = sum(time_series) / len(time_series)
            variance = sum((x - mean) ** 2 for x in time_series) / len(time_series)
            volatility = (variance ** 0.5) / abs(mean) if mean != 0 else 0
        else:
            volatility = 0
        
        # 移动平均
        ma3 = self._calc_moving_average(time_series, 3)
        
        # 简单预测（线性外推）
        if len(time_series) >= 2:
            forecast = last_value + (last_value - time_series[-2])
        else:
            forecast = last_value
        
        return {
            "direction": direction,
            "strength": strength,
            "growth_rate": growth_rate,
            "volatility": volatility,
            "moving_average_3": ma3,
            "forecast_next": forecast
        }
    
    def _calc_moving_average(self, values: List[float], window: int) -> List[float]:
        """计算移动平均"""
        if len(values) < window:
            return []
        
        return [
            sum(values[i:i + window]) / window
            for i in range(len(values) - window + 1)
        ]
    
    def calc_distribution(self, values: List[float]) -> Dict[str, float]:
        """
        计算分布指标
        
        参数:
            values: 数值列表
            
        返回:
            {
                "skewness": 1.85,
                "kurtosis": 2.1,
                "is_normal": False,
                "quartiles": {"q1": 30000, "q2": 45000, "q3": 70000}
            }
        """
        valid_values = [v for v in values if v is not None]
        
        if not valid_values:
            return {
                "skewness": 0,
                "kurtosis": 0,
                "is_normal": False,
                "quartiles": {"q1": 0, "q2": 0, "q3": 0}
            }
        
        sorted_values = sorted(valid_values)
        n = len(sorted_values)
        mean = sum(sorted_values) / n
        
        # 标准差
        variance = sum((x - mean) ** 2 for x in sorted_values) / n
        std = variance ** 0.5
        
        # 偏度
        if std == 0:
            skewness = 0
        else:
            skewness = sum((x - mean) ** 3 for x in sorted_values) / (n * std ** 3)
        
        # 峰度
        if std == 0:
            kurtosis = 0
        else:
            kurtosis = sum((x - mean) ** 4 for x in sorted_values) / (n * std ** 4) - 3
        
        # 正态性检验（简化）
        is_normal = abs(skewness) < 1 and abs(kurtosis) < 2
        
        # 四分位数
        q1 = sorted_values[n // 4]
        q2 = sorted_values[n // 2]
        q3 = sorted_values[3 * n // 4]
        
        return {
            "skewness": skewness,
            "kurtosis": kurtosis,
            "is_normal": is_normal,
            "quartiles": {"q1": q1, "q2": q2, "q3": q3}
        }
    
    def detect_anomalies(self, values: List[float], 
                         threshold: float = 2.0) -> List[Dict[str, Any]]:
        """
        检测异常点
        
        参数:
            values: 数值列表
            threshold: 异常检测阈值（标准差倍数）
            
        返回:
            [
                {
                    "index": 15,
                    "value": 500000,
                    "expected": 50000,
                    "deviation": 10.0,
                    "description": "异常增长"
                }
            ]
        """
        valid_values = [v for v in values if v is not None]
        
        if not valid_values:
            return []
        
        mean = sum(valid_values) / len(valid_values)
        variance = sum((x - mean) ** 2 for x in valid_values) / len(valid_values)
        std = variance ** 0.5
        
        if std == 0:
            return []
        
        anomalies = []
        for i, value in enumerate(values):
            if value is None:
                continue
            
            deviation = abs(value - mean) / std
            if deviation > threshold:
                anomalies.append({
                    "index": i,
                    "value": value,
                    "expected": mean,
                    "deviation": deviation,
                    "description": "异常偏高" if value > mean else "异常偏低"
                })
        
        return anomalies
    
    def calc_correlation(self, values1: List[float], 
                         values2: List[float]) -> float:
        """
        计算相关系数
        
        参数:
            values1: 第一组数值
            values2: 第二组数值
            
        返回:
            相关系数（-1 到 1）
        """
        valid_pairs = [(v1, v2) for v1, v2 in zip(values1, values2) 
                      if v1 is not None and v2 is not None]
        
        if not valid_pairs:
            return 0
        
        v1_values = [p[0] for p in valid_pairs]
        v2_values = [p[1] for p in valid_pairs]
        
        mean1 = sum(v1_values) / len(v1_values)
        mean2 = sum(v2_values) / len(v2_values)
        
        covariance = sum((v1 - mean1) * (v2 - mean2) for v1, v2 in valid_pairs) / len(valid_pairs)
        
        variance1 = sum((v1 - mean1) ** 2 for v1 in v1_values) / len(v1_values)
        variance2 = sum((v2 - mean2) ** 2 for v2 in v2_values) / len(v2_values)
        
        std1 = variance1 ** 0.5
        std2 = variance2 ** 0.5
        
        if std1 == 0 or std2 == 0:
            return 0
        
        return covariance / (std1 * std2)
