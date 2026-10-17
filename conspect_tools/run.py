"""
conspect_tools 工具层入口（v3.0 稳定性增强版）
提供CLI接口供Agent调用

注意 - PowerShell 正确调用方式：
  [正确] 先 cd 到本文件所在目录，再用相对路径：
     cd {CLI_DIR}
     python run.py <action> '<json_params>'

  [正确] 如果使用绝对路径，用 & 调用符：
     & "python.exe" "{CLI_DIR}/run.py" <action> '<json_params>'

  [错误] 不要两个路径参数都用引号：
     "python.exe" "run.py" ...  # 这会导致 PowerShell ParserError

使用方式:
    python run.py <action> '<params_json>'

示例:
    python run.py load '{"file_paths": ["数据源文件.xlsx"]}'
    python run.py analyze '{"file_paths": ["数据源文件.xlsx"]}'
    python run.py cross_tabulate '{"file_paths": ["数据源文件.xlsx"], "row_dim": "维度A", "col_dim": "维度B"}'
    python run.py quality_assess '{"file_paths": ["数据源文件.xlsx"]}'
    python run.py render_report '{"report_design": {...}}'
    python run.py save_report '{"content": "...", "filename": "report.md"}'
    python run.py recognize_preferences '{"user_requirement": "用蓝色调，出 PDF"}'

v3.0 变更：
  - 新增 recognize_preferences 动作（替代原确认环节）
  - 新增 ai_generate_insights_safe 动作（降级版洞察生成，属分析数据阶段）
  - 所有 action 增加异常降级处理，失败时返回结构化错误而非崩溃
  - 新增诊断日志记录
"""
import sys
import json
import os
import logging
from pathlib import Path
from typing import Dict, Any

# 确保conspect_tools在路径中
sys.path.insert(0, str(Path(__file__).parent.parent))

# v3.0：模块级日志器
logger = logging.getLogger("conspect.run")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

from conspect_tools.data_processor import DataProcessor
from conspect_tools.data_feature_extractor import DataFeatureExtractor
from conspect_tools.data_statistics import DataStatistics
from conspect_tools.ai_agent import AIAgent
from conspect_tools.review_data_loader import ReviewDataLoader
from conspect_tools.render_engine import RenderEngine
from conspect_tools.report_renderer import ReportRenderer
from conspect_tools.exporter import Exporter


def _resolve_content(params: Dict[str, Any], default: Any = "") -> Any:
    """
    解析待保存内容。

    优先级：content_file > content。

    content_file 用于解决「长文本无法作为命令行 JSON 字面量传入」的问题：
    调用方（AI）先用写文件工具把内容落到临时文件，再把该文件路径交给 CLI。
    is_binary 为真时按二进制读取，返回 bytes。

    参数:
        params: 参数字典
        default: 两个来源都缺失时的默认值
    返回:
        文本内容（str）或二进制内容（bytes）
    """
    content_file = params.get("content_file")
    if content_file:
        path = Path(content_file)
        if not path.exists():
            raise FileNotFoundError(
                f"content_file 不存在：{content_file}。请先写入该文件，再调用本动作。"
            )
        raw = path.read_bytes()
        if params.get("is_binary"):
            return raw
        text = raw.decode("utf-8-sig", errors="replace")
        # 归一化换行：Exporter 用 write_text（Windows 会把 \n 翻成 \r\n），
        # 若此处保留源文件的 \r\n 会写成 \r\r\n。统一先归一到 \n。
        return text.replace("\r\n", "\n").replace("\r", "\n")
    return params.get("content", default)


def run(action: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    工具层入口函数。

    参数:
        action: 操作类型
                load              - 加载所有Sheet的数据
                read_all          - 返回所有Sheet的原始结构信息
                analyze           - 全面分析所有Sheet（加载→清洗→维度识别→聚合→统计→质量评分）
                select_charts     - 图表选型（旧，向后兼容）
                cross_tabulate    - 交叉分析（任意两维度交叉聚合）
                quality_assess    - 数据质量评估（按列质量评级）
                compare_data      - 数据比较（两数据集一致性检查）
                render            - 渲染Web看板
                export_offline     - 导出离线报告
                generate_insights - 生成智能洞察（旧，向后兼容）
                render_report    - 渲染报告
                save_report      - 保存报告
                save_with_chinese_name - 保存并复制中文命名
                
                # AI Agent 功能（AI 自主分析决策）
                extract_features     - 提取数据特征
                calc_statistics     - 计算统计数据
                ai_decide_chart     - AI Agent 图表选型决策
                ai_generate_insights - AI Agent 生成洞察
                ai_review_style     - AI Agent 报表选型阶段审核
                ai_review_render    - AI Agent 生成报表阶段审核
                load_review_context - 加载审核上下文
                
                # 审核功能（旧，向后兼容）
                review_design      - 设计阶段审核
                review_render      - 生成报表阶段审核
                verify_end_to_end  - 端到端验证
                final_judgment    - 最终判定
                generate_review_report - 生成审核报告
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
        分析所有 Sheet：加载 → 清洗 → **按数据契约判角色** → 聚合 → 统计 → 图表候选。

        参数:
            file_paths: 数据文件路径列表
            fill_strategy: 可选，按列指定缺失填充方式
            schema_file: 可选，数据契约（_cs-schema.json）。传入后所有角色判定按契约走；
                         不传则现场用统计启发式探测，并明确报出哪些列没判准。
        """
        processor = DataProcessor()
        file_paths = params.get("file_paths", [])
        dfs = processor.load_excel(file_paths)

        # 可选的填充策略（由调用者传入，不传则只去重不填充）
        fill_strategy = params.get("fill_strategy")
        # 可选的数据契约：判定的唯一事实源
        schema_file = params.get("schema_file") or ""
        if schema_file and not Path(schema_file).exists():
            return {"status": "error",
                    "message": f"schema_file 不存在：{schema_file}",
                    "data": {}}

        if not dfs:
            # v3.0：文件不存在或无法加载时返回明确的错误信息，避免静默失败
            missing = [p for p in file_paths if not Path(p).exists()]
            if missing:
                return {"status": "error", "message": f"文件不存在: {missing}", "data": {}}
            return {"status": "error", "message": "数据加载失败，未读取到任何 Sheet", "data": {}}

        # 初始化统计模块
        from conspect_tools.data_statistics import DataStatistics
        stats_calc = DataStatistics()

        all_results = {}
        for sheet_key, df in dfs.items():
            sheet_result = {}

            # 清洗：只去重（除非调用者指定了填充策略）
            cleaned = processor.clean_data(df, fill_strategy=fill_strategy)

            # ---- 数据契约（v5.0）----
            # 有 schema_file 就按契约走；没有则现场探测一遍（纯统计启发式），
            # 并把「哪些列没判准」明确报出来，而不是静默按关键词猜。
            from conspect_tools import schema_contract, schema_probe
            contract = None
            contract_note = ""
            if schema_file:
                try:
                    contract = schema_contract.load(schema_file)
                    v = schema_contract.validate(contract, list(cleaned.columns))
                    if not v["ok"]:
                        contract_note = (
                            f"契约与数据不匹配：新增列 {v['missing_in_contract']}，"
                            f"缺失列 {v['missing_in_data']}。新增列按未判定处理"
                            if v["missing_in_contract"] or v["missing_in_data"]
                            else f"契约存在非法 role：{v['unknown_role']}")
                    # 契约里没登记的列，补探测并标为 unknown（不隐式归入分类）
                    if v["missing_in_contract"]:
                        probe_now = schema_probe.judge_frame(
                            cleaned[v["missing_in_contract"]])
                        for c in probe_now["columns"]:
                            contract["columns"][c["column"]] = {
                                "role": "unknown", "additivity": "none",
                                "confidence": "low", "evidence": "hard",
                                "reason": "契约未登记该列，需在契约中指定角色",
                                "decided_by": "probe",
                                "profile": {"dtype": c["dtype"], "n": c["n"],
                                            "null_rate": c["null_rate"],
                                            "unique": c["unique"],
                                            "unique_ratio": c["unique_ratio"],
                                            "samples": c["samples"]},
                            }
                            contract["unresolved"] = contract.get("unresolved", [])
                            contract["unresolved"].append(c["column"])
                            contract["views"]["unknown"] = contract.get("unresolved", [])
                except Exception as e:
                    contract_note = f"契约加载失败（{type(e).__name__}: {e}），已降级为统计启发式"

            if contract is None:
                probe_res = schema_probe.judge_frame(cleaned)
                contract = schema_contract.build(
                    probe_res,
                    source={"sheet": sheet_key, "rows": len(cleaned),
                            "cols": len(cleaned.columns)},
                    decided_by="heuristic")
                # 标记为「现场生成」：下游据此区分可信度，报表需声明未经人工复核
                contract["_auto_generated"] = True
                contract_note = contract_note or (
                    f"未提供数据契约，已用统计启发式现场判定；"
                    f"{len(probe_res['need_ai'])} 列置信度低需人工确认："
                    f"{probe_res['need_ai']}")

            sheet_result["contract"] = {
                "decided_by": contract.get("decided_by"),
                "summary": schema_contract.summary_lines(contract),
                "views": contract.get("views", {}),
                "unresolved": contract.get("unresolved", []),
                "note": contract_note,
            }

            # 维度识别（优先按契约）
            dims = processor.identify_dimensions(cleaned, contract=contract)

            # 聚合计算
            agg = processor.aggregate_metrics(cleaned, dims)

            # 汇总信息
            sheet_result["rows"] = len(cleaned)
            sheet_result["columns"] = list(cleaned.columns)
            sheet_result["dimensions"] = dims
            sheet_result["aggregated"] = agg

            # 前5行样本数据（转为可序列化字典）
            sheet_result["sample"] = cleaned.head(5).to_dict(orient="records")

            # ---- 统计计算（聚合方式按契约：additive 求和 / average 取均值）----
            sheet_result["statistics"] = {}
            numeric_cols = dims.get("数值", [])
            for num_col in numeric_cols:
                if num_col not in cleaned.columns:
                    continue
                values = cleaned[num_col].dropna().tolist()
                if not values:
                    continue
                # 单价/比率类求和毫无意义，按其可加总性选聚合
                col_agg = schema_contract.measure_agg(contract, num_col)
                group_agg = "mean" if col_agg == "mean" else "sum"

                col_stats = {}
                # 基础统计
                col_stats["basic"] = stats_calc.calc_basic_stats(values)
                # 分布形态
                col_stats["distribution"] = stats_calc.calc_distribution(values)
                # 异常点
                col_stats["anomalies"] = stats_calc.detect_anomalies(values)
                col_stats["aggregation"] = {
                    "chosen": col_agg,
                    "reason": contract["columns"].get(num_col, {}).get("additivity", "unknown"),
                }

                # 集中度（取第一个分类维度）
                cat_dims = dims.get("分类", [])
                for cat_dim in cat_dims:
                    if cat_dim in cleaned.columns:
                        dim_data = cleaned.groupby(cat_dim)[num_col].agg(
                            group_agg).to_dict()
                        col_stats["concentration"] = stats_calc.calc_concentration(dim_data)
                        break

                # 趋势（如果存在时间维度）
                time_dims = dims.get("时间", [])
                for time_dim in time_dims:
                    if time_dim in cleaned.columns:
                        try:
                            time_grouped = cleaned.groupby(time_dim)[num_col].agg(group_agg)
                            time_series = time_grouped.sort_index().tolist()
                            trend = stats_calc.calc_trend(time_series)
                            if "moving_average_3" in trend and len(trend["moving_average_3"]) > 20:
                                ma = trend["moving_average_3"]
                                step = max(1, len(ma) // 20)
                                trend["moving_average_3"] = [ma[i] for i in range(0, len(ma), step)][:20]
                                trend["moving_average_note"] = "已抽样，原始点数{}".format(len(ma))
                            col_stats["trend"] = trend
                        except Exception:
                            pass
                        break

                # 限制异常点输出数量
                if "anomalies" in col_stats and len(col_stats["anomalies"]) > 10:
                    col_stats["anomalies"] = col_stats["anomalies"][:10]
                    col_stats["anomalies_note"] = "仅显示前10条"

                sheet_result["statistics"][num_col] = col_stats

            # ---- 数据质量概览 ----
            sheet_result["data_quality"] = {}
            for col in cleaned.columns:
                total = len(cleaned)
                null_count = int(cleaned[col].isna().sum())
                unique_count = int(cleaned[col].nunique())
                null_rate = null_count / total if total > 0 else 0

                if null_rate < 0.01:
                    quality = "优秀"
                elif null_rate < 0.05:
                    quality = "注意"
                elif null_rate < 0.20:
                    quality = "警告"
                else:
                    quality = "不可用"

                sheet_result["data_quality"][col] = {
                    "null_count": null_count,
                    "null_rate": round(null_rate, 4),
                    "unique_count": unique_count,
                    "dtype": str(cleaned[col].dtype),
                    "quality_rating": quality
                }

            # ---- 图表候选与数据议题（v5.0：全部按契约）----
            from conspect_tools import chart_advisor
            try:
                sheet_result["charts"] = chart_advisor.recommend(
                    cleaned, dims, sheet_result["data_quality"], contract=contract)
                warns = chart_advisor.take_warnings()
                if warns:
                    sheet_result.setdefault("warnings", []).extend(warns)
            except Exception as e:
                sheet_result["charts"] = []
                sheet_result.setdefault("warnings", []).append(
                    f"图表候选生成失败: {type(e).__name__}: {e}")
            try:
                sheet_result["data_issues"] = chart_advisor.data_issues(
                    cleaned, dims, sheet_result["data_quality"], contract=contract)
            except Exception as e:
                sheet_result["data_issues"] = []
                sheet_result.setdefault("warnings", []).append(
                    f"数据议题生成失败: {type(e).__name__}: {e}")
            # 标明事实表/维表：主报表的分析板块只应取事实表的图表
            try:
                sheet_result["table_role"] = chart_advisor.classify_table(
                    cleaned, dims, contract=contract)
            except Exception as e:
                sheet_result["table_role"] = {"role": "unknown", "reason": str(e)}

            all_results[sheet_key] = sheet_result

        return {"status": "ok", "data": all_results}

    elif action == "cross_tabulate":
        """
        交叉分析：对指定两维度进行交叉聚合计算。
        CLI 只负责计算，AI Agent 负责解读交叉分析结果的业务含义。

        参数:
            file_paths: Excel文件路径列表
            row_dim: 行维度列名
            col_dim: 列维度列名
            metric: 指标列名（可选，不传则计数）
            agg_func: 聚合函数（sum/avg/count，默认 sum）

        返回:
            {
                "status": "ok",
                "data": {
                    "row_dim": "行维度列名",
                    "col_dim": "列维度列名",
                    "metric": "指标列名",
                    "agg_func": "聚合函数",
                    "pivot_table": {行值: {列值: 聚合值}},
                    "row_totals": {行值: 合计},
                    "col_totals": {列值: 合计},
                    "grand_total": 总计,
                    "row_field_counts": {行值: 记录数}
                }
            }
        """
        import pandas as pd
        processor = DataProcessor()
        dfs = processor.load_excel(params.get("file_paths", []))
        row_dim = params.get("row_dim", "")
        col_dim = params.get("col_dim", "")
        metric = params.get("metric")
        agg_func = params.get("agg_func", "sum")

        if not dfs or not row_dim or not col_dim:
            return {"status": "error", "message": "缺少必要参数: file_paths, row_dim, col_dim"}

        # 取第一个Sheet数据
        first_key = next(iter(dfs))
        df = dfs[first_key]

        if row_dim not in df.columns or col_dim not in df.columns:
            return {"status": "error",
                    "message": f"维度列不存在: row_dim={row_dim}, col_dim={col_dim}"}

        # 如果指定了指标列，验证存在性
        if metric and metric not in df.columns:
            return {"status": "error", "message": f"指标列不存在: {metric}"}

        # 交叉聚合
        if metric:
            agg_map = {"sum": "sum", "avg": "mean", "count": "count"}
            pandas_agg = agg_map.get(agg_func, "sum")
            pivot = df.pivot_table(
                index=row_dim, columns=col_dim,
                values=metric, aggfunc=pandas_agg,
                fill_value=0
            )
        else:
            # 无指标列，按计数聚合
            pivot = df.pivot_table(
                index=row_dim, columns=col_dim,
                aggfunc="count", fill_value=0
            )

        # 转可序列化格式
        pivot_dict = {}
        for idx_val in pivot.index:
            row_dict = {}
            for col_val in pivot.columns:
                if metric:
                    val = pivot.loc[idx_val, col_val]
                else:
                    # 无指标时取第一个可用数值
                    val = pivot.loc[idx_val, col_val]
                    if isinstance(val, (pd.Series,)):
                        val = val.iloc[0] if len(val) > 0 else 0
                row_dict[str(col_val)] = float(val) if pd.notna(val) else 0
            pivot_dict[str(idx_val)] = row_dict

        # 行合计
        row_totals = {}
        for idx_val in pivot.index:
            if metric:
                row_totals[str(idx_val)] = float(pivot.loc[idx_val].sum())
            else:
                val = pivot.loc[idx_val].sum()
                row_totals[str(idx_val)] = float(val.iloc[0]) if isinstance(val, (pd.Series,)) else float(val)

        # 列合计
        col_totals = {}
        for col_val in pivot.columns:
            if metric:
                col_totals[str(col_val)] = float(pivot[col_val].sum())
            else:
                val = pivot[col_val].sum()
                col_totals[str(col_val)] = float(val.iloc[0]) if isinstance(val, (pd.Series,)) else float(val)

        # 总计
        grand_total = sum(row_totals.values())

        # 行维度记录数
        row_field_counts = df[row_dim].value_counts().to_dict()
        row_field_counts = {str(k): int(v) for k, v in row_field_counts.items()}

        return {
            "status": "ok",
            "data": {
                "row_dim": row_dim,
                "col_dim": col_dim,
                "metric": metric or "(计数)",
                "agg_func": agg_func,
                "pivot_table": pivot_dict,
                "row_totals": row_totals,
                "col_totals": col_totals,
                "grand_total": grand_total,
                "row_field_counts": row_field_counts
            }
        }

    elif action == "quality_assess":
        """
        数据质量评估：对每列计算质量指标并给出评级。
        CLI 只负责评估，AI Agent 负责判断质量问题的业务影响。

        参数:
            file_paths: Excel文件路径列表

        返回:
            {
                "status": "ok",
                "data": {
                    "overall_score": 总体评分,
                    "column_reports": [{每列报告}],
                    "warnings": [警告列表]
                }
            }
        """
        processor = DataProcessor()
        dfs = processor.load_excel(params.get("file_paths", []))
        fill_strategy = params.get("fill_strategy")

        if not dfs:
            return {"status": "ok", "data": {}}

        all_reports = {}
        for sheet_key, df in dfs.items():
            cleaned, clean_info = processor.clean_data(df, fill_strategy=fill_strategy, return_info=True)

            column_reports = []
            total_score = 100
            warnings = []

            for col in cleaned.columns:
                total = len(cleaned)
                null_count = int(cleaned[col].isna().sum())
                null_rate = null_count / total if total > 0 else 0
                unique_count = int(cleaned[col].nunique())
                unique_rate = unique_count / total if total > 0 else 0
                dtype = str(cleaned[col].dtype)

                col_score = 100
                col_warnings = []

                # 空值扣分
                if null_rate > 0.20:
                    col_score -= 40
                    col_warnings.append(f"空值率 {null_rate:.1%}>20%，数据基本不可用")
                elif null_rate > 0.05:
                    col_score -= 15
                    col_warnings.append(f"空值率 {null_rate:.1%}>5%，需关注")
                elif null_rate > 0.01:
                    col_score -= 5

                # 唯一性检查：数值列唯一值太少可能异常
                if "float" in dtype or "int" in dtype:
                    if unique_count <= 1 and total > 1:
                        col_score -= 20
                        col_warnings.append(f"数值列只有 {unique_count} 个唯一值，可能非数值或常量列")

                # 分类列唯一值过多
                if "object" in dtype:
                    if unique_rate > 0.95 and total > 10:
                        col_score -= 10
                        col_warnings.append(f"分类列唯一值占比 {unique_rate:.1%}，近于唯一标识符")

                # 异常值检查（数值列）
                anomalies = []
                if "float" in dtype or "int" in dtype:
                    values = cleaned[col].dropna().tolist()
                    if len(values) > 0:
                        from conspect_tools.data_statistics import DataStatistics
                        stats_calc = DataStatistics()
                        anomalies = stats_calc.detect_anomalies(values, threshold=3.0)
                        if len(anomalies) > 0:
                            col_score -= min(len(anomalies) * 5, 25)
                            col_warnings.append(f"检测到 {len(anomalies)} 个异常值")

                total_score -= (100 - col_score) // 3  # 累加到总体分

                quality_rating = "优秀" if col_score >= 90 else "注意" if col_score >= 70 else "警告" if col_score >= 40 else "不可用"

                column_reports.append({
                    "column": col,
                    "dtype": dtype,
                    "total_count": total,
                    "null_count": null_count,
                    "null_rate": round(null_rate, 4),
                    "unique_count": unique_count,
                    "score": col_score,
                    "quality_rating": quality_rating,
                    "warnings": col_warnings
                })
                warnings.extend(col_warnings)

            all_reports[sheet_key] = {
                "overall_score": max(0, round(total_score / max(len(cleaned.columns), 1), 1)),
                "column_count": len(cleaned.columns),
                "row_count": len(cleaned),
                "duplicates_removed": clean_info.get("duplicates_removed", 0),
                "total_filled": clean_info.get("total_filled", 0),
                "column_reports": column_reports,
                "warnings": warnings[:20]  # 最多显示20条
            }

        return {"status": "ok", "data": all_reports}

    elif action == "compare_data":
        """
        数据比较：比较两组数据的一致性。
        CLI 只负责对比计算，AI Agent 负责判断差异的业务影响。

        参数:
            data1: 第一组数据（键值对字典或数值）
            data2: 第二组数据（键值对字典或数值）
            tolerance: 容差（默认 0.1%）

        返回:
            {
                "status": "ok",
                "data": {
                    "is_consistent": bool,
                    "total_fields": 总字段数,
                    "diff_count": 差异数,
                    "max_diff_percent": 最大差异百分比,
                    "differences": [...]
                }
            }
        """
        from conspect_tools.review_data_loader import ReviewDataLoader

        data1 = params.get("data1", {})
        data2 = params.get("data2", {})
        tolerance = params.get("tolerance", 0.001)

        loader = ReviewDataLoader()
        result = loader.compare_data(data1, data2, tolerance)

        # 增强结果
        diffs = result.get("differences", [])
        max_diff = max([d.get("diff_percent", 0) for d in diffs]) if diffs else 0

        return {
            "status": "ok",
            "data": {
                "is_consistent": result.get("is_consistent", True),
                "total_fields": len(diffs),
                "diff_count": len(diffs),
                "max_diff_percent": max_diff,
                "differences": diffs
            }
        }

    elif action == "select_charts":
        """图表选型（旧，向后兼容 - 建议改用 ai_decide_chart）"""
        try:
            from conspect_tools.chart_selector import ChartSelector
            selector = ChartSelector()
            charts = selector.analyze_data_features(params.get("agg_data", {}))
            return {"status": "ok", "charts": [{"type": c.chart_type, "title": c.title, "dimension": c.dimension} for c in charts]}
        except ImportError:
            return {"status": "ok", "charts": [], "note": "chart_selector 已弃用，请使用 ai_decide_chart"}

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

# ===== 旧版功能（向后兼容，建议改用 AI Agent 新版）=====

    elif action == "generate_insights":
        """
        基于分析结果生成智能洞察（旧，向后兼容 - 建议改用 ai_generate_insights）
        """
        analysis_result = params.get("analysis_result", {})
        try:
            from conspect_tools.insight_generator import InsightGenerator
            generator = InsightGenerator(analysis_result)
            result = generator.generate_all()
            
            def serialize_insight(insight):
                return {
                    "category": insight.category,
                    "title": insight.title,
                    "description": insight.description,
                    "evidence": insight.evidence,
                    "severity": insight.severity,
                    "related_metrics": insight.related_metrics,
                    "markdown": insight.to_markdown()
                }
            
            def serialize_recommendation(rec):
                return {
                    "title": rec.title,
                    "description": rec.description,
                    "priority": rec.priority,
                    "expected_impact": rec.expected_impact,
                    "related_findings": rec.related_findings,
                    "markdown": rec.to_markdown()
                }
            
            serialized_result = {
                "executive_summary": result["executive_summary"],
                "key_findings": [serialize_insight(i) for i in result["key_findings"]],
                "risk_alerts": [serialize_insight(i) for i in result["risk_alerts"]],
                "opportunities": [serialize_insight(i) for i in result["opportunities"]],
                "recommendations": [serialize_recommendation(r) for r in result["recommendations"]],
                "appendix": result["appendix"]
            }
            return {"status": "ok", "data": serialized_result}
        except ImportError:
            return {"status": "ok", "data": {}, "note": "insight_generator 已弃用，请使用 ai_generate_insights"}
    
    elif action == "review_design":
        """
        设计阶段审核（含关联性检查）
        
        参数:
            analysis_file: 分析结果文件路径
            design_file: 设计文档文件路径
            
        返回:
            {
                "status": "ok",
                "result": {
                    "phase": "style",
                    "passed": bool,
                    "score": float,
                    "issues": [...],
                    "cross_stage_issues": [...]
                }
            }
        """
        from conspect_tools.quality_auditor import QualityAuditor
        
        analysis_file = params.get("analysis_file", "")
        design_file = params.get("design_file", "")
        
        auditor = QualityAuditor(project_root=str(Path.cwd()))
        result = auditor.review_design(analysis_file, design_file)
        
        return {"status": "ok", "result": result.to_dict()}
    
    elif action == "review_implement":
        """
        实现阶段审核（含关联性检查）
        
        参数:
            design_file: 设计文档文件路径
            implement_file: 实现文档文件路径
            
        返回:
            {
                "status": "ok",
                "result": {
                    "phase": "render",
                    "passed": bool,
                    "score": float,
                    "issues": [...],
                    "cross_stage_issues": [...]
                }
            }
        """
        from conspect_tools.quality_auditor import QualityAuditor
        
        design_file = params.get("design_file", "")
        implement_file = params.get("implement_file", "")
        
        auditor = QualityAuditor(project_root=str(Path.cwd()))
        result = auditor.review_implement(design_file, implement_file)
        
        return {"status": "ok", "result": result.to_dict()}
    
    elif action == "verify_end_to_end":
        """
        端到端验证（全链路检查）
        
        参数:
            raw_data_file: 原始数据文件路径
            analysis_file: 分析结果文件路径
            design_file: 设计文档文件路径
            implement_file: 实现文档文件路径
            
        返回:
            {
                "status": "ok",
                "result": {
                    "phase": "verify",
                    "passed": bool,
                    "score": float,
                    "issues": [...]
                }
            }
        """
        from conspect_tools.quality_auditor import QualityAuditor
        
        raw_data_file = params.get("raw_data_file", "")
        analysis_file = params.get("analysis_file", "")
        design_file = params.get("design_file", "")
        implement_file = params.get("implement_file", "")
        
        auditor = QualityAuditor(project_root=str(Path.cwd()))
        result = auditor.verify_end_to_end(raw_data_file, analysis_file, design_file, implement_file)
        
        return {"status": "ok", "result": result.to_dict()}
    
    elif action == "final_judgment":
        """
        最终判定（基于所有阶段的审核结果）
        
        返回:
            {
                "status": "ok",
                "result": {
                    "phase": "judge",
                    "passed": bool,
                    "score": float,
                    "issues": [...]
                }
            }
        """
        from conspect_tools.quality_auditor import QualityAuditor
        
        auditor = QualityAuditor(project_root=str(Path.cwd()))
        result = auditor.final_judgment()
        
        return {"status": "ok", "result": result.to_dict()}
    
    elif action == "generate_review_report":
        """
        生成审核报告 Markdown
        
        参数:
            phase: 阶段名称 (content/style/render)
            
        返回:
            {
                "status": "ok",
                "report": "审核报告 Markdown"
            }
        """
        from conspect_tools.quality_auditor import QualityAuditor
        
        phase = params.get("phase", "style")
        
        auditor = QualityAuditor(project_root=str(Path.cwd()))
        
        # 获取对应阶段的审核结果
        result = None
        for r in auditor.review_results:
            if r.phase == phase:
                result = r
                break
        
        if not result:
            return {"status": "error", "message": f"没有找到阶段 {phase} 的审核结果"}
        
        report = auditor.generate_report(result)
        
        return {"status": "ok", "report": report}
    
    # ===== AI Agent 功能 =====
    
    elif action == "extract_features":
        """
        提取数据特征（不负责图表选型决策）
        
        参数:
            data: 数据字典
            
        返回:
            {
                "status": "ok",
                "features": {...}
            }
        """
        from conspect_tools.data_feature_extractor import DataFeatureExtractor
        
        data = params.get("data", {})
        extractor = DataFeatureExtractor()
        features = extractor.extract_features(data)
        
        return {"status": "ok", "features": features}
    
    elif action == "calc_statistics":
        """
        计算统计数据（不负责洞察生成决策）
        
        参数:
            values: 数值列表
            dimension_data: 维度数据
            time_series: 时间序列数据
            
        返回:
            {
                "status": "ok",
                "statistics": {...}
            }
        """
        from conspect_tools.data_statistics import DataStatistics
        
        values = params.get("values", [])
        dimension_data = params.get("dimension_data", {})
        time_series = params.get("time_series", [])
        
        stats = DataStatistics()
        
        result = {}
        if values:
            result["basic"] = stats.calc_basic_stats(values)
        if dimension_data:
            result["concentration"] = stats.calc_concentration(dimension_data)
        if time_series:
            result["trend"] = stats.calc_trend(time_series)
        if values:
            result["distribution"] = stats.calc_distribution(values)
            result["anomalies"] = stats.detect_anomalies(values)
        
        return {"status": "ok", "statistics": result}
    
    elif action == "ai_decide_chart":
        """
        AI Agent 图表选型决策
        
        参数:
            features: 数据特征
            business_context: 业务场景描述
            
        返回:
            {
                "status": "ok",
                "decision": {
                    "chart_type": "line",
                    "reason": "..."
                }
            }
        """
        from conspect_tools.ai_agent import AIAgent
        
        features = params.get("features", {})
        business_context = params.get("business_context", "")
        
        agent = AIAgent()
        decision = agent.decide_chart(features, business_context)
        
        return {
            "status": "ok",
            "decision": {
                "chart_type": decision.chart_type,
                "title": decision.title,
                "reason": decision.reason,
                "config": decision.config
            }
        }
    
    elif action == "ai_generate_insights":
        """
        AI Agent 生成洞察
        
        参数:
            statistics: 统计数据
            business_context: 业务场景描述
            
        返回:
            {
                "status": "ok",
                "insights": [...],
                "recommendations": [...]
            }
        """
        from conspect_tools.ai_agent import AIAgent
        
        statistics = params.get("statistics", {})
        business_context = params.get("business_context", "")
        
        agent = AIAgent()
        insights = agent.generate_insights(statistics, business_context)
        recommendations = agent.generate_recommendations(insights, business_context)
        
        return {
            "status": "ok",
            "insights": [
                {
                    "category": i.category,
                    "title": i.title,
                    "description": i.description,
                    "evidence": i.evidence,
                    "severity": i.severity,
                    "related_metrics": i.related_metrics
                }
                for i in insights
            ],
            "recommendations": [
                {
                    "title": r.title,
                    "description": r.description,
                    "priority": r.priority,
                    "expected_impact": r.expected_impact,
                    "related_findings": r.related_findings
                }
                for r in recommendations
            ]
        }
    
    elif action == "ai_review_design":
        """
        AI Agent 设计阶段审核
        
        参数:
            analysis: 分析结果
            design: 设计文档
            
        返回:
            {
                "status": "ok",
                "review": {
                    "phase": "style",
                    "passed": bool,
                    "score": float,
                    "issues": [...],
                    "cross_stage_issues": [...]
                }
            }
        """
        from conspect_tools.ai_agent import AIAgent
        
        analysis = params.get("analysis", {})
        design = params.get("design", {})
        
        agent = AIAgent()
        review = agent.review_design(analysis, design)
        
        return {
            "status": "ok",
            "review": {
                "phase": review.phase,
                "passed": review.passed,
                "score": review.score,
                "issues": review.issues,
                "cross_stage_issues": review.cross_stage_issues
            }
        }
    
    elif action == "ai_review_implement":
        """
        AI Agent 实现阶段审核
        
        参数:
            design: 设计文档
            implement: 实现文档
            
        返回:
            {
                "status": "ok",
                "review": {
                    "phase": "render",
                    "passed": bool,
                    "score": float,
                    "issues": [...],
                    "cross_stage_issues": [...]
                }
            }
        """
        from conspect_tools.ai_agent import AIAgent
        
        design = params.get("design", {})
        implement = params.get("implement", {})
        
        agent = AIAgent()
        review = agent.review_implement(design, implement)
        
        return {
            "status": "ok",
            "review": {
                "phase": review.phase,
                "passed": review.passed,
                "score": review.score,
                "issues": review.issues,
                "cross_stage_issues": review.cross_stage_issues
            }
        }

    elif action == "load_review_context":
        """
        加载审核所需的所有上下文。
        CLI 只负责加载数据，AI Agent 负责审核决策。

        参数:
            raw_data_file: 原始数据文件路径
            analysis_file: 分析结果文件路径
            design_file: 设计文档文件路径
            implement_file: 实现文档文件路径

        返回:
            {
                "status": "ok",
                "context": {
                    "raw_data": {...},
                    "analysis": {...},
                    "design": {...},
                    "implement": {...}
                }
            }
        """
        from conspect_tools.review_data_loader import ReviewDataLoader

        loader = ReviewDataLoader(project_root=params.get("project_root"))
        context = loader.load_review_context(params)

        return {"status": "ok", "context": context}

    elif action == "render_report":
        """
        渲染报告为指定格式
        
        参数:
            report_design: 报告设计字典
            format: 输出格式 (markdown/html/pdf/word)
            
        返回:
            {
                "status": "ok",
                "content": "报告内容",
                "format": "输出格式"
            }
        """
        report_design = params.get("report_design", {})
        output_format = params.get("format", "markdown")
        
        renderer = ReportRenderer(theme_name=params.get("theme", ""))
        
        if output_format == "markdown":
            content = renderer.render_markdown(report_design)
        elif output_format == "html":
            content = renderer.render_html(report_design)
        elif output_format == "pdf":
            content = renderer.render_pdf(report_design)
            return {"status": "ok", "content": content, "format": "pdf", "is_binary": True}
        elif output_format == "word":
            content = renderer.render_word(report_design)
            return {"status": "ok", "content": content, "format": "word", "is_binary": True}
        else:
            return {"status": "error", "message": f"Unsupported format: {output_format}"}
        
        return {"status": "ok", "content": content, "format": output_format}

    elif action == "save_report":
        """
        保存报告到文件

        参数:
            content: 报告内容（短文本直接内联；长文本请改用 content_file）
            content_file: 内容文件路径（优先于 content，用于长文本/二进制）
            filename: 文件名
            is_binary: 是否为二进制内容

        返回:
            {
                "status": "ok",
                "path": "文件路径"
            }
        """
        content = _resolve_content(params, default="")
        filename = params.get("filename", "report.md")
        is_binary = params.get("is_binary", False)
        
        exporter = Exporter(output_dir=params.get("output_dir"))
        
        if is_binary:
            path = exporter._save_binary(content, filename)
        else:
            path = exporter._save_text(content, filename)
        
        return {"status": "ok", "path": path}

    elif action == "save_with_chinese_name":
        """
        保存文件并复制中文命名版本

        参数:
            content: 文件内容（长文本请改用 content_file）
            content_file: 内容文件路径（优先于 content）
            filename: 原始文件名
            is_binary: 是否为二进制文件

        返回:
            {
                "status": "ok",
                "original": "原始路径",
                "chinese": "中文路径"
            }
        """
        content = _resolve_content(params, default="")
        filename = params.get("filename", "")
        is_binary = params.get("is_binary", False)
        
        exporter = Exporter(output_dir=params.get("output_dir"))
        result = exporter.save_with_chinese_name(content, filename, is_binary)
        
        return {"status": "ok", **result}

    elif action == "save_index":
        """
        保存看板与报告的关联索引

        参数:
            index: 索引字典
            filename: 文件名

        返回:
            {
                "status": "ok",
                "path": "文件路径"
            }
        """
        index = params.get("index", {})
        filename = params.get("filename", "_cs-index.json")

        exporter = Exporter(output_dir=params.get("output_dir"))
        path = exporter.save_index(index, filename)

        return {"status": "ok", "path": path}

    # ===== v3.0 新增：用户偏好识别（替代原确认环节）=====

    elif action == "recognize_preferences":
        """
        识别用户偏好（v3.0 新增，替代原确认环节）

        从用户初始需求文本中自动识别配色、图表、输出格式等偏好，
        识别失败时返回默认值，不阻断流程。

        参数:
            user_requirement: 用户初始需求文本

        返回:
            {
                "status": "ok",
                "preferences": {...},
                "source": "recognized" | "default"
            }
        """
        from conspect_tools.ai_agent import AIAgent

        user_requirement = params.get("user_requirement", "")

        agent = AIAgent()
        preferences = agent.recognize_preferences(user_requirement)

        # 判断是否识别到非默认值
        source = "recognized" if user_requirement else "default"

        return {
            "status": "ok",
            "preferences": preferences,
            "source": source
        }

    elif action == "ai_generate_insights_safe":
        """
        生成洞察（安全版，v3.0 新增）

        异常时返回降级结果（空洞察列表 + 错误信息），不阻断流程。

        参数:
            statistics: 统计数据
            business_context: 业务场景描述

        返回:
            {
                "status": "ok" | "fallback",
                "insights": [...],
                "recommendations": [...],
                "error": null | "异常信息"
            }
        """
        from conspect_tools.ai_agent import AIAgent

        statistics = params.get("statistics", {})
        business_context = params.get("business_context", "")

        agent = AIAgent()
        result = agent.generate_insights_safe(statistics, business_context)

        return {
            "status": result.get("status", "ok"),
            "insights": [
                {
                    "category": i.category,
                    "title": i.title,
                    "description": i.description,
                    "evidence": i.evidence,
                    "severity": i.severity,
                    "related_metrics": i.related_metrics
                }
                for i in result.get("insights", [])
            ],
            "recommendations": [
                {
                    "title": r.title,
                    "description": r.description,
                    "priority": r.priority,
                    "expected_impact": r.expected_impact,
                    "related_findings": r.related_findings
                }
                for r in result.get("recommendations", [])
            ],
            "error": result.get("error")
        }

    elif action == "build_dashboard_layout":
        """
        按板块清单组装看板布局（v4.1 修复：blocks 真正驱动装配）

        参数:
            analysis: 分析结果（kpis / charts / tables / narrative）
            insights: 洞察列表（含 level/title/description）
            preferences: 用户偏好（可选）
            blocks: 板块清单（板块 id 列表，或 select_content 返回的板块 dict 列表）
                    不传则按图表标题关键词分组（v3.0 兼容路径）

        返回:
            layout dict，可直接传入 render_dashboard 的 layout 参数
        """
        from conspect_tools.ai_agent import AIAgent

        analysis = params.get("analysis", {})
        insights = params.get("insights", [])
        preferences = params.get("preferences", {})
        blocks = params.get("blocks")

        agent = AIAgent()
        layout = agent.build_dashboard_layout(analysis, insights, preferences, blocks)

        return {"status": "ok", "layout": layout,
                "mode": layout.get("_mode", "theme"),
                "blocks": layout.get("_blocks", []),
                "gaps": layout.get("_gaps", [])}

    elif action == "render_dashboard":
        """
        渲染分区式看板 HTML（v3.0 新增）

        使用增强版 RenderEngine 生成带分区、数据解读、便当盒网格的看板。
        禁止 AI 自己写 HTML 脚本，必须通过此动作渲染。

        参数:
            layout: 布局配置（由 build_dashboard_layout 生成，或手工构建）
            theme: 风格编号（如 "A12"），全部可选值见 assets/catalog/catalog_l0.md

        返回:
            {"status": "ok", "html": "...完整HTML字符串..."}
        """
        from conspect_tools.render_engine import RenderEngine

        layout = params.get("layout", {})
        theme = params.get("theme", "")
        # theme 未显式指定时，从 preferences/layout 中自动读取，最终回退资产库默认风格
        if not theme:
            theme = (params.get("preferences") or {}).get("color_scheme", "")
        if not theme:
            theme = layout.get("color_scheme", "")

        engine = RenderEngine(theme_name=theme)
        html = engine.render_web_dashboard(layout)

        return {"status": "ok", "html": html,
                "theme": engine.theme_name, "style": engine.theme.get("label", "")}

    # ================= v4.0 新增动作（对应 5 阶段流程）=================

    elif action == "probe_schema":
        """
        数据契约第一步：探测每列画像，并给出「统计层能判到什么程度」。

        **这一步不写盘、不改数据**，只产出证据与待判清单，供 Agent 或人做终判。

        参数:
            file_paths: 数据源路径列表
            sheet: 可选，只探测某个 Sheet（默认全部）

        返回:
            {
              "status": "ok",
              "sheets": {
                "<sheet_key>": {
                  "columns": [{column, role, confidence, evidence, reason,
                               additivity, ...统计画像}],
                  "summary": {total, high, medium, low, unknown},
                  "need_ai": [需终判的列],
                  "unresolved": [role=unknown 的列],
                  "duplicate_columns": [[A,B]],
                  "ready": bool
                }
              },
              "summary": "人读摘要"
            }
        """
        from conspect_tools import schema_probe

        processor = DataProcessor()
        file_paths = params.get("file_paths", [])
        if not file_paths:
            return {"status": "error", "message": "未提供 file_paths", "sheets": {}}
        missing = [p for p in file_paths if not Path(p).exists()]
        if missing:
            return {"status": "error", "message": f"文件不存在: {missing}", "sheets": {}}

        dfs = processor.load_excel(file_paths)
        if not dfs:
            return {"status": "error", "message": "未读取到任何 Sheet", "sheets": {}}

        only = params.get("sheet") or ""
        out = {}
        for key, df in dfs.items():
            if only and only not in key:
                continue
            out[key] = schema_probe.judge_frame(df)

        if not out:
            return {"status": "error",
                    "message": f"未找到匹配 sheet「{only}」的 Sheet", "sheets": {}}

        tot = sum(v["summary"]["total"] for v in out.values())
        need = sum(len(v["need_ai"]) for v in out.values())
        unk = sum(len(v["unresolved"]) for v in out.values())
        return {
            "status": "ok",
            "sheets": out,
            "summary": (f"{len(out)} 个 Sheet / {tot} 列；"
                        f"需终判 {need} 列，其中 {unk} 列统计层无法判定"),
            "next": ("把 need_ai 的列逐条给出 role（time/dimension/measure/"
                     "identifier/text/ignore/unknown），再调 save_schema 固化契约。"
                     "unresolved 列若确实无用可留 unknown，但必须在报表中明示"),
        }

    elif action == "save_schema":
        """
        数据契约第二步：合并探测结果与终判，写出 `_cs-schema.json`。

        参数:
            file_paths: 数据源路径列表
            overrides: 终判字典，形如
                       {"客户名称": {"role": "dimension",
                                    "reason": "客户名称用于分组，不算明细标识"}}
                       只需给 role；additivity 可省略（会自动按统计特征推断）
            sheet: 可选，只处理某个 Sheet
            output_dir: 契约落盘目录（默认 .agent/harness）
            filename: 契约文件名（默认 _cs-schema.json）
            decided_by: ai | human | mixed（默认 ai）

        返回:
            {"status": "ok", "paths": {sheet_key: 契约文件路径}, "summary": [...]}
        """
        from conspect_tools import schema_contract, schema_probe

        processor = DataProcessor()
        file_paths = params.get("file_paths", [])
        overrides = params.get("overrides") or {}
        output_dir = params.get("output_dir") or ".agent/harness"
        filename = params.get("filename") or schema_contract.DEFAULT_FILENAME
        decided_by = params.get("decided_by") or "ai"
        only = params.get("sheet") or ""

        if not file_paths:
            return {"status": "error", "message": "未提供 file_paths", "paths": {}}
        dfs = processor.load_excel(file_paths)
        if not dfs:
            return {"status": "error", "message": "未读取到任何 Sheet", "paths": {}}

        # overrides 允许按 sheet 分组：{"<sheet_key>": {...}} 或全局一份
        per_sheet = overrides if all(isinstance(v, dict) for v in overrides.values()) \
            and any(k in dfs for k in overrides) else None

        paths, lines = {}, []
        for key, df in dfs.items():
            if only and only not in key:
                continue
            ov = (per_sheet or {}).get(key, {}) if per_sheet else overrides
            probe_res = schema_probe.judge_frame(df)
            contract = schema_contract.build(
                probe_res, overrides=ov,
                source={"sheet": key, "rows": len(df), "cols": len(df.columns)},
                decided_by=decided_by)
            # 一个文件多个 Sheet 时，文件名带上 sheet 后缀避免互相覆盖
            fname = filename if len(dfs) == 1 else \
                filename.replace(".json", f"__{key.split('_')[-1]}.json")
            p = schema_contract.save(contract, str(Path(output_dir) / fname))
            paths[key] = p
            lines.extend(schema_contract.summary_lines(contract))

        return {
            "status": "ok",
            "paths": paths,
            "summary": lines,
            "note": ("契约已固化。后续 analyze 传 schema_file 即按此执行；"
                     "未判定的列不会参与分析"),
        }

    elif action == "check_schema":
        """
        校验数据契约与实际数据是否匹配（换了一版数据后必跑）。

        参数:
            file_paths: 数据源路径列表
            schema_file: 契约文件路径
            sheet: 可选，只校验某个 Sheet

        返回:
            {"status": "ok", "results": {sheet_key: validate(...)}, "summary": "..."}
        """
        import json as _json
        from conspect_tools import schema_contract

        processor = DataProcessor()
        file_paths = params.get("file_paths", [])
        schema_file = params.get("schema_file") or ""
        if not schema_file or not Path(schema_file).exists():
            return {"status": "error", "message": f"schema_file 不存在：{schema_file}",
                    "results": {}}
        try:
            contract = schema_contract.load(schema_file)
        except Exception as e:
            return {"status": "error", "message": f"契约读取失败：{e}", "results": {}}

        dfs = processor.load_excel(file_paths)
        only = params.get("sheet") or ""
        results = {}
        for key, df in dfs.items():
            if only and only not in key:
                continue
            results[key] = schema_contract.validate(contract, list(df.columns))

        bad = [k for k, v in results.items() if not v["ok"]]
        return {
            "status": "ok" if not bad else "mismatch",
            "results": results,
            "summary": (f"{len(results)} 个 Sheet，全部匹配" if not bad
                        else f"{len(bad)} 个 Sheet 与契约不匹配：{bad}"),
        }

    elif action == "read_datamap":
        """
        读取数据阶段：汇总数据源清单（文件 / Sheet / 列名与类型 / 样本 / 质量分）。

        参数:
            file_paths: 数据源路径列表
        返回:
            {"status": "ok", "datamap": {...}, "quality": {...}, "summary": "..."}
        """
        processor = DataProcessor()
        file_paths = params.get("file_paths", [])
        if not file_paths:
            return {"status": "error", "message": "未提供 file_paths", "datamap": {}}

        missing = [p for p in file_paths if not Path(p).exists()]
        if missing:
            return {"status": "error", "message": f"文件不存在: {missing}", "datamap": {}}

        raw_info = processor.read_all_sheets_raw(file_paths)

        quality = {}
        try:
            quality = processor.assess_quality(file_paths)
        except Exception as e:
            quality = {"error": f"{type(e).__name__}: {e}"}

        sources, column_count = [], 0
        for sheet_key, info in (raw_info or {}).items():
            if not isinstance(info, dict):
                continue
            names = info.get("column_names") or []
            dtypes = info.get("column_dtypes") or {}
            column_count += len(names)
            sources.append({
                "sheet": info.get("sheet_name") or sheet_key,
                "columns": names,
                "column_count": len(names),
                "column_types": dtypes,
                "row_count": info.get("rows"),
                "sample": (info.get("sample_data") or [])[:3],
            })

        # 顶层质量分取**最差 Sheet**，而不是平均：
        # 一张表数据差，整份报表的可信度就受限于它，平均分会把风险抹平。
        scored = []
        if isinstance(quality, dict) and quality and "error" not in quality:
            for k, v in quality.items():
                if isinstance(v, dict) and isinstance(v.get("score"), (int, float)):
                    scored.append((float(v["score"]), k))
        avg_score = round(sum(s for s, _ in scored) / len(scored), 1) if scored else None
        min_score, min_sheet = (min(scored) if scored else (None, ""))

        files = []
        for p in file_paths:
            fp = Path(p)
            files.append({"path": str(fp), "name": fp.name,
                          "size_kb": round(fp.stat().st_size / 1024, 1)})

        return {
            "status": "ok",
            "datamap": {
                "files": files,
                "file_count": len(files),
                "sources": sources,
                "sheet_count": len(sources),
                "column_count": column_count,
                # 取最差 Sheet 分：报表可信度由最弱环节决定
                "quality_score": min_score,
                "quality_sheet": min_sheet,
                "quality_avg": avg_score,
                "quality_by_sheet": {k: v.get("score") for k, v in (quality or {}).items()
                                     if isinstance(v, dict)},
            },
            "quality": quality,
            "summary": f"{len(files)} 个文件 / {len(sources)} 个 Sheet / {column_count} 列"
                       + (f" / 质量分 {min_score}（最低表：{min_sheet.split('_')[-1]}）"
                          if min_score is not None else ""),
        }

    elif action == "list_styles":
        """
        列出风格资产（6 族 + 38 风格），供 L0 通读与用户挑选。

        返回:
            {"status": "ok", "families": [...], "styles": [...], "catalog": "..." }
        """
        from conspect_tools import style_loader

        fams = [{
            "id": f["id"], "label": f["label"], "en": f.get("en", ""),
            "tone": f["tone"], "scene": f.get("scene", ""),
            "count": f.get("count", len(f.get("styles", []))),
            "series": f.get("series", []),
            "index": f"assets/index/{f['id']}.md",
        } for f in style_loader.families()]

        styles = [{
            "code": s["code"], "label": s["label"], "en": s.get("en", ""),
            "family": s["family"], "tone": s.get("tone", ""),
            "ac": s["tokens"]["ac"], "mood": s.get("mood", ""),
            "density": s.get("report_use", {}).get("density", ""),
            "media": s.get("report_use", {}).get("media", ""),
            "types": s.get("report_use", {}).get("types", []),
            "body": s.get("body"),
        } for s in style_loader.styles()]

        return {"status": "ok", "families": fams, "styles": styles,
                "summary": style_loader.summary(),
                "catalog": "assets/catalog/catalog_l0.md"}

    elif action == "list_blocks":
        """列出报表板块库（22 板块 × 6 族）与触发条件，供内容选型核对。"""
        from conspect_tools import block_library
        return {"status": "ok", "blocks": block_library.all_blocks(),
                "triggers": block_library.triggers(),
                "summary": block_library.summary()}

    elif action == "select_style":
        """
        报表选型阶段：产出风格选型建议卡。

        参数:
            profile: {"tone": 浅色|深色|混合|auto, "report_type": str,
                      "density": 高|中|低, "keywords": [str], "family": 族 id,
                      "media": 投影|打印|大屏|阅读}
            blocks: 内容选型选中的板块 id 列表（可选）。传入后按板块契合度加分。
        返回:
            {"status": "ok", "recommend": {...}, "alternatives": [...],
             "confidence": 高|中|低, "family": 族 id, "family_ties": [...]}
        """
        from conspect_tools.ai_agent import AIAgent
        agent = AIAgent()
        profile = params.get("profile") or {
            k: params[k] for k in ("tone", "report_type", "density",
                                   "keywords", "family", "media")
            if k in params
        }
        return agent.select_style_card(profile, params.get("blocks"))

    elif action == "render_style_preview":
        """
        生成风格候选的**可视对比页**（HTML 文件），供用户挑选。

        为什么需要这个动作：选型卡是文字，客户看到「A1」和一堆十六进制色值
        无法判断观感。此动作把候选按各自真实 token 画成一小段报表并排展示，
        客户看一眼就能选。

        参数:
            candidates: select_style 返回的 candidates 数组（必填，直接用其原样传入）
            profile: 同 select_style 的 profile（可选，仅用于页头说明）
            output_path: 输出 HTML 路径（可选，默认写当前目录 _cs-style-preview.html）
            title: 页面标题（可选）
        返回:
            {"status": "ok", "path": 绝对路径, "candidates": [中文名...], "size": 字节数}
        """
        from conspect_tools import style_preview
        cands = params.get("candidates")
        if not cands:
            return {"status": "error",
                    "message": "缺少 candidates：请先调 select_style，"
                               "把返回的 candidates 原样传入"}
        if not isinstance(cands, list) or not all(isinstance(c, dict) for c in cands):
            return {"status": "error", "message": "candidates 应为对象数组"}

        html = style_preview.build_preview_html(
            cands[:4], params.get("profile"),
            params.get("title") or "报表风格候选")

        out = params.get("output_path") or os.path.join(os.getcwd(), "_cs-style-preview.html")
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write(html)

        return {"status": "ok", "path": os.path.abspath(out),
                "candidates": [c.get("label", "") for c in cands[:4]],
                "size": len(html.encode("utf-8")),
                "hint": "把该文件呈现给用户，并同时给出文字版选型卡"
                        "（文字里用中文名，不要只写编号）"}

    elif action == "select_content":
        """
        汇报内容选型阶段：按板块库触发条件产出板块组合方案。

        参数:
            analysis / insights / features: 分析数据（三者至少提供 analysis）
            report_form: 投屏 | 阅读 | 大屏（决定板块数上限）
            requirements: 用户原始诉求文本
        返回:
            {"status": "ok", "blocks": [...], "dropped": [...], "notes": [...]}
        """
        from conspect_tools.ai_agent import AIAgent
        agent = AIAgent()
        return agent.select_content_plan(
            analysis=params.get("analysis", {}),
            insights=params.get("insights", []),
            features=params.get("features"),
            report_form=params.get("report_form", "投屏"),
            requirements=params.get("requirements", ""),
        )

    return {"status": "error", "message": f"Unknown action: {action}"}


def main():
    """CLI入口点（v3.0 增强异常处理与诊断日志）"""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    action = sys.argv[1]

    # 读取参数（优先级：--params-file > 命令行JSON > 标准输入）
    params = {}

    if len(sys.argv) > 2:
        # 支持 --params-file / -p 从文件读取JSON（推荐，绕过PowerShell引号问题）
        if sys.argv[2] in ("--params-file", "-p") and len(sys.argv) > 3:
            params_file = sys.argv[3]
            try:
                with open(params_file, 'r', encoding='utf-8') as f:
                    params = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                print(json.dumps({"status": "error", "message": f"Params file error: {e}"}, ensure_ascii=False))
                sys.exit(1)
        else:
            # 从命令行参数读取JSON
            try:
                params = json.loads(sys.argv[2])
            except json.JSONDecodeError as e:
                print(json.dumps({"status": "error", "message": f"Invalid JSON params: {e}"}, ensure_ascii=False))
                sys.exit(1)
    else:
        # 尝试从标准输入读取
        try:
            input_data = sys.stdin.read()
            params = json.loads(input_data) if input_data.strip() else {}
        except json.JSONDecodeError:
            params = {}

    try:
        result = run(action, params)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        # v3.0：返回 status=error 时以非零退出码退出，便于 Shell 脚本检测
        if isinstance(result, dict) and result.get("status") == "error":
            sys.exit(1)
    except KeyboardInterrupt:
        # v3.0：用户中断时优雅退出
        logger.warning("用户中断执行: action=%s", action)
        print(json.dumps({"status": "error", "message": "User interrupted"}, ensure_ascii=False))
        sys.exit(130)
    except Exception as e:
        # v3.0：记录诊断日志后返回结构化错误
        logger.exception("CLI 执行异常: action=%s, error=%s", action, e)
        print(json.dumps({
            "status": "error",
            "message": str(e),
            "action": action,
            "error_code": "E500"
        }, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
