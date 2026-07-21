"""
vision_tools 工具层入口
提供CLI接口供Agent调用
"""
import sys
import json
from pathlib import Path

# 确保vision_tools在路径中
sys.path.insert(0, str(Path(__file__).parent.parent))
from vision_tools.data_processor import DataProcessor
from vision_tools.chart_selector import ChartSelector
from vision_tools.render_engine import RenderEngine
from vision_tools.exporter import Exporter


def run(action: str, params: dict = None):
    """
    工具层入口函数。

    参数:
        action: 操作类型
                load       - 加载所有Sheet的数据
                read_all   - 返回所有Sheet的原始结构信息
                analyze    - 分析所有Sheet（加载→清洗→维度识别→聚合）
                select_charts - 图表选型
                render     - 渲染Web看板
                export_offline - 导出离线报告
        params: 参数字典
    """
    if params is None:
        params = {}

    if action == "load":
        processor = DataProcessor()
        result = processor.load_excel(params.get("file_paths", []))
        return {"status": "ok", "data": list(result.keys())}

    elif action == "read_all":
        """返回所有Sheet的完整结构信息（不修改原始数据）"""
        processor = DataProcessor()
        raw_info = processor.read_all_sheets_raw(params.get("file_paths", []))
        return {"status": "ok", "data": raw_info}

    elif action == "analyze":
        """
        分析所有Sheet：对每个Sheet逐一执行加载→清洗→维度识别→聚合。
        返回结果按 {文件名_Sheet名} 分组，每个Sheet独立分析。
        """
        processor = DataProcessor()
        dfs = processor.load_excel(params.get("file_paths", []))

        # 可选的填充策略（由调用者传入，不传则只去重不填充）
        fill_strategy = params.get("fill_strategy")

        if not dfs:
            return {"status": "ok", "data": {}}

        all_results = {}
        for sheet_key, df in dfs.items():
            sheet_result = {}

            # 清洗：只去重（除非调用者指定了填充策略）
            cleaned = processor.clean_data(df, fill_strategy=fill_strategy)

            # 维度识别
            dims = processor.identify_dimensions(cleaned)

            # 聚合计算
            agg = processor.aggregate_metrics(cleaned, dims)

            # 汇总信息
            sheet_result["rows"] = len(cleaned)
            sheet_result["columns"] = list(cleaned.columns)
            sheet_result["dimensions"] = dims
            sheet_result["aggregated"] = agg

            # 前5行样本数据（转为可序列化字典）
            sheet_result["sample"] = cleaned.head(5).to_dict(orient="records")

            all_results[sheet_key] = sheet_result

        return {"status": "ok", "data": all_results}

    elif action == "select_charts":
        selector = ChartSelector()
        charts = selector.analyze_data_features(params.get("agg_data", {}))
        return {"status": "ok", "charts": [{"type": c.chart_type, "title": c.title, "dimension": c.dimension} for c in charts]}

    elif action == "render":
        engine = RenderEngine()
        html = engine.render_web_dashboard(params.get("layout", {}))
        exporter = Exporter()
        path = exporter.save_html(html, params.get("filename", "report.html"))
        return {"status": "ok", "path": path}

    elif action == "export_offline":
        engine = RenderEngine()
        html = engine.render_offline_html(params.get("layout", {}))
        exporter = Exporter()
        path = exporter.save_html(html, params.get("filename", "offline_report.html"))
        return {"status": "ok", "path": path}

    return {"status": "error", "message": f"Unknown action: {action}"}


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "help"
    params = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    result = run(action, params)
    print(json.dumps(result, ensure_ascii=False, indent=2))
