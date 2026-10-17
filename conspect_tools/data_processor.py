"""
vision_tools 数据处理模块
提供Excel解析、数据清洗、维度识别、指标计算等功能

核心设计原则：
  - 不硬编码任何业务数据
  - 不假设列名或数据类型
  - 所有方法都可通过参数自定义行为
"""
import pandas as pd
import openpyxl
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple, Union

# ---------------------------------------------------------------------------
# 支持的数据源格式（唯一事实源，修改时必须同步 config.py 与 SKILL.md）
#
# 事实说明（2026-10-16 实测）：
#   - openpyxl 只能读取 OOXML（.xlsx / .xlsm），无法读取旧版 .xls（BIFF 格式）。
#   - .csv 由 pandas 直接读取，自动探测 UTF-8 / GBK 编码。
#   - .json 未实现，不在支持范围内。
# ---------------------------------------------------------------------------
EXCEL_EXTENSIONS = {".xlsx", ".xlsm"}
CSV_EXTENSIONS = {".csv"}
SUPPORTED_EXTENSIONS = EXCEL_EXTENSIONS | CSV_EXTENSIONS
LEGACY_EXCEL_EXTENSIONS = {".xls"}


class UnsupportedFormatError(ValueError):
    """数据源格式不受支持时抛出，替代底层晦涩的 BadZipFile 报错。"""


class DataProcessor:
    """Excel数据处理核心类"""

    def __init__(self):
        self.dataframes: Dict[str, pd.DataFrame] = {}
        self.merged_df: Optional[pd.DataFrame] = None

    def load_excel(self, file_paths: List[str]) -> Dict[str, pd.DataFrame]:
        """
        加载多个数据源文件，读取其中全部数据。

        按后缀分派：
          - .xlsx / .xlsm → openpyxl 引擎，遍历所有 Sheet
          - .csv          → pandas 直接读取（自动探测 utf-8 / gbk 编码）
          - .xls          → 抛出 UnsupportedFormatError（openpyxl 不支持 BIFF，请另存为 .xlsx）
          - 其他          → 抛出 UnsupportedFormatError

        不做任何清洗或转换——仅读取原始数据。

        参数:
            file_paths: 数据源文件路径列表
        返回:
            {文件名_Sheet名: DataFrame} 字典（CSV 的 key 为文件名）
        """
        result = {}
        for fp in file_paths:
            path = Path(fp)
            if not path.exists():
                continue

            suffix = path.suffix.lower()

            if suffix in EXCEL_EXTENSIONS:
                # 显式使用 openpyxl 引擎读取所有Sheet
                excel_file = pd.ExcelFile(path, engine="openpyxl")
                for sheet_name in excel_file.sheet_names:
                    key = f"{path.stem}_{sheet_name}"
                    # parse 不改变原始列名和行顺序，保留各列原始类型
                    df = excel_file.parse(sheet_name)
                    result[key] = df
                    self.dataframes[key] = df

            elif suffix in CSV_EXTENSIONS:
                key = path.stem
                df = self._read_csv(path)
                result[key] = df
                self.dataframes[key] = df

            elif suffix in LEGACY_EXCEL_EXTENSIONS:
                raise UnsupportedFormatError(
                    f"不支持旧版 Excel 格式 .xls：{path.name}。"
                    "openpyxl 无法读取 BIFF 格式，请用 Excel/WPS 另存为 .xlsx 后重试。"
                )

            else:
                raise UnsupportedFormatError(
                    f"不支持的文件格式「{suffix or '(无后缀)'}」：{path.name}。"
                    f"当前支持：{', '.join(sorted(SUPPORTED_EXTENSIONS))}。"
                )

        return result

    @staticmethod
    def _read_csv(path: Path) -> pd.DataFrame:
        """读取 CSV，依次尝试 utf-8-sig / gbk / utf-8 编码。"""
        last_error: Optional[Exception] = None
        for encoding in ("utf-8-sig", "gbk", "utf-8"):
            try:
                return pd.read_csv(path, encoding=encoding)
            except UnicodeDecodeError as exc:
                last_error = exc
        raise UnsupportedFormatError(
            f"无法解码 CSV 文件 {path.name}（已尝试 utf-8-sig / gbk / utf-8）：{last_error}"
        )

    def read_all_sheets_raw(self, file_paths: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        返回每个Sheet的原始结构信息，不修改原始数据。

        使用 openpyxl 直接读取工作簿元数据，避免 pandas 类型推断影响。
        每条记录包含：
          - sheet_name: Sheet名称
          - rows: 总行数（不含表头）
          - columns: 总列数
          - column_names: 列名列表
          - column_dtypes: {列名: openpyxl单元格类型描述}
          - sample_data: 前3行数据（原始值列表）

        参数:
            file_paths: Excel文件路径列表
        返回:
            {文件名_Sheet名: 结构信息字典} 字典
        """
        result = {}
        for fp in file_paths:
            path = Path(fp)
            if not path.exists():
                continue

            suffix = path.suffix.lower()

            if suffix in CSV_EXTENSIONS:
                df = self._read_csv(path)
                key = path.stem
                column_dtypes = {}
                for col in df.columns:
                    types = {type(v).__name__ for v in df[col].dropna().tolist()}
                    column_dtypes[str(col)] = sorted(types) if types else ["NoneType"]
                sample_data = []
                for row in df.head(3).to_dict(orient="records"):
                    sample_data.append({
                        str(k): (str(v) if isinstance(v, pd.Timestamp) else (None if pd.isna(v) else v))
                        for k, v in row.items()
                    })
                result[key] = {
                    "sheet_name": key,
                    "rows": int(df.shape[0]),
                    "columns": int(df.shape[1]),
                    "column_names": [str(c) for c in df.columns],
                    "column_dtypes": column_dtypes,
                    "sample_data": sample_data,
                }
                continue

            if suffix in LEGACY_EXCEL_EXTENSIONS:
                raise UnsupportedFormatError(
                    f"不支持旧版 Excel 格式 .xls：{path.name}。"
                    "openpyxl 无法读取 BIFF 格式，请用 Excel/WPS 另存为 .xlsx 后重试。"
                )

            if suffix not in EXCEL_EXTENSIONS:
                raise UnsupportedFormatError(
                    f"不支持的文件格式「{suffix or '(无后缀)'}」：{path.name}。"
                    f"当前支持：{', '.join(sorted(SUPPORTED_EXTENSIONS))}。"
                )

            wb = openpyxl.load_workbook(path, data_only=True)
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                key = f"{path.stem}_{sheet_name}"

                # 将工作表数据转为列表（每行一个列表）
                rows_data = list(ws.iter_rows(values_only=True))
                if not rows_data:
                    result[key] = {
                        "sheet_name": sheet_name,
                        "rows": 0,
                        "columns": 0,
                        "column_names": [],
                        "column_dtypes": {},
                        "sample_data": []
                    }
                    continue

                # 第一行为表头
                headers = [str(cell) if cell is not None else f"Unnamed:{i}" for i, cell in enumerate(rows_data[0])]
                num_cols = len(headers)

                # 按列收集数据类型（从数据行推断）
                column_dtypes = {}
                for col_idx in range(num_cols):
                    col_name = headers[col_idx]
                    col_types = set()
                    for row in rows_data[1:]:
                        if col_idx < len(row) and row[col_idx] is not None:
                            col_types.add(type(row[col_idx]).__name__)
                    column_dtypes[col_name] = sorted(col_types) if col_types else ["NoneType"]

                # 前3行样本（从第2行开始，每行转为 {列名: 值} 格式）
                data_rows = rows_data[1:4]  # 最多取3行
                sample_data = []
                for row in data_rows:
                    row_dict = {}
                    for col_idx, header in enumerate(headers):
                        val = row[col_idx] if col_idx < len(row) else None
                        # 处理无法JSON序列化的类型
                        if isinstance(val, (pd.Timestamp,)):
                            val = str(val)
                        row_dict[header] = val
                    sample_data.append(row_dict)

                result[key] = {
                    "sheet_name": sheet_name,
                    "rows": max(0, len(rows_data) - 1),  # 去掉表头
                    "columns": num_cols,
                    "column_names": headers,
                    "column_dtypes": column_dtypes,
                    "sample_data": sample_data
                }
            wb.close()
        return result

    def clean_data(
        self,
        df: pd.DataFrame,
        fill_strategy: Optional[Dict[str, Any]] = None,
        return_info: bool = False
    ) -> Union[pd.DataFrame, Tuple[pd.DataFrame, Dict[str, Any]]]:
        """
        数据清洗：去重 + 可选的自定义空值填充。

        默认行为：只做去重，不做任何空值填充。
        调用者通过 fill_strategy 自行决定填充策略。

        参数:
            df: 输入DataFrame
            fill_strategy: 可选的自定义填充策略字典。
                           键为 dtype 名称（如 'int64', 'float64', 'object'）
                           或具体列名；值为要填充的值。
                           例如: {"int64": 0, "object": "未知"}
                           为 None 时只去重不填充。
            return_info: 为 True 时返回 (清洗后df, 对比信息字典)

        返回:
            return_info=False: 仅返回清洗后的 DataFrame
            return_info=True: 返回 (清洗后df, 对比信息)
                              对比信息包含:
                              - before_rows: 清洗前行数
                              - after_rows: 清洗后行数
                              - duplicates_removed: 去重行数
                              - filled_cells: 填充的单元格数（按列统计）
        """
        before_rows = len(df)
        before_columns = len(df.columns)
        df_clean = df.copy()

        # 记录空值填充情况
        filled_cells = {}

        # 如果指定了填充策略，则按策略填充
        if fill_strategy is not None:
            for key, value in fill_strategy.items():
                # 按 dtype 填充
                dtype_cols = [c for c in df_clean.columns if df_clean[c].dtype.name == key]
                if dtype_cols:
                    for col in dtype_cols:
                        na_count = int(df_clean[col].isna().sum())
                        if na_count > 0:
                            df_clean[col] = df_clean[col].fillna(value)
                            filled_cells[col] = na_count
                # 按列名精确匹配（覆盖 dtype 策略）
                if key in df_clean.columns:
                    na_count = int(df_clean[key].isna().sum())
                    if na_count > 0:
                        df_clean[key] = df_clean[key].fillna(value)
                        filled_cells[key] = na_count

        # 去重
        df_clean = df_clean.drop_duplicates()
        after_rows = len(df_clean)

        if not return_info:
            return df_clean

        info = {
            "before_rows": before_rows,
            "after_rows": after_rows,
            "duplicates_removed": before_rows - after_rows,
            "filled_cells": filled_cells if filled_cells else None,
            "total_filled": sum(filled_cells.values()) if filled_cells else 0
        }
        return df_clean, info

    def identify_dimensions(self, df: pd.DataFrame,
                            contract: Optional[Dict] = None) -> Dict[str, List[str]]:
        """
        识别数据维度，返回 {"时间": [...], "分类": [...], "数值": [...]}。

        **优先走契约**（v5.0）：传入 `contract` 时直接按其 role 映射，
        计算链路不再自行猜测；未传入时才退化到统计启发式。

        为什么要有两条路径：
          契约（探测 + AI/人工终判）能正确处理「电话号码不是指标」「客户名称是维度
          而不是明细ID」这类统计上无法区分的情况，且判定结果可审计。
          但契约需要先跑一次 probe，纯自动场景下仍要能跑通，所以保留启发式兜底。

        启发式路径的能力边界（已在 schema_probe 里诚实标注）：
          关键词表只能覆盖常见术语，新行业的新词（客单价、GMV、到店人次）会漏，
          所以它只是兜底，不是主路径；输出带 `_provenance` 标记便于追责。

        参数:
            df: 数据表
            contract: schema_contract.build() 产出的契约（可选）
        返回:
            {"时间": [...], "分类": [...], "数值": [...]}
            （走契约时额外带 "_provenance" 键，标明来源）
        """
        if contract:
            from conspect_tools import schema_contract
            dims = schema_contract.to_dimensions(contract)
            dims["_provenance"] = {
                # 区分「用户提供的契约」与「未提供时现场探测生成的契约」：
                # 两者都按契约执行，但可信度不同，报表口径需要据此声明。
                "source": ("auto_contract" if contract.get("_auto_generated")
                           else "contract"),
                "decided_by": contract.get("decided_by", "unknown"),
                "excluded": {
                    "identifier": contract.get("views", {}).get("identifier", []),
                    "text": contract.get("views", {}).get("text", []),
                    "ignore": contract.get("views", {}).get("ignore", []),
                    "unknown": contract.get("views", {}).get("unknown", []),
                },
            }
            return dims

        dimensions = {"时间": [], "分类": [], "数值": []}
        dimensions["_provenance"] = {"source": "heuristic"}

        # 行业通用的时间关键词
        date_keywords = [
            "日期", "时间", "年", "月", "日", "时", "季度", "周", "星期",
            "date", "time", "year", "month", "day", "week", "quarter",
            "年度", "月份", "日期时间", "datetime", "timestamp",
            "period", "期间", "开始", "结束", "start", "end", "创建时间",
            "更新时间", "modified", "created", "审批日期", "单据日期"
        ]
        # 行业通用的分类关键词
        category_keywords = [
            "部门", "产品", "区域", "类型", "类别", "渠道", "城市", "品牌",
            "名称", "分类", "状态", "级别", "性别", "色系", "款式", "系列",
            "供应商", "客户", "门店", "仓库", "业务", "行业", "标签",
            "dept", "product", "region", "city", "category", "status",
            "level", "brand", "name", "supplier", "customer", "store",
            "warehouse", "segment", "group", "industry", "business", "tag",
            "省份", "地址", "地区", "单位", "规格", "型号", "备注", "说明",
            "province", "address", "area", "unit", "spec", "model", "remark",
            "负责人", "经理", "owner", "manager", "员工", "employee"
        ]

        for col in df.columns:
            col_lower = str(col).lower()
            col_dtype = df[col].dtype

            # 步骤1: datetime 类型 → 时间
            if pd.api.types.is_datetime64_any_dtype(col_dtype):
                dimensions["时间"].append(col)
                continue

            # 步骤2: 数值类型 → 数值
            if pd.api.types.is_numeric_dtype(col_dtype):
                dimensions["数值"].append(col)
                continue

            # 步骤3: object（文本）类型 → 先用关键词辅助判断
            if pd.api.types.is_object_dtype(col_dtype):
                # 检查是否为"时间"相关（年月日等关键词可能出现在文本列中）
                if any(kw in col_lower for kw in date_keywords):
                    dimensions["时间"].append(col)
                    continue
                # 检查是否为"分类"相关
                if any(kw in col_lower for kw in category_keywords):
                    dimensions["分类"].append(col)
                    continue
                # 无匹配关键词的 object 列，默认归为分类
                dimensions["分类"].append(col)
                continue

            # 步骤4: 其他类型（bool, timedelta 等）归为分类
            dimensions["分类"].append(col)

        return dimensions

    def aggregate_metrics(
        self,
        df: pd.DataFrame,
        dims: Dict[str, List[str]]
    ) -> Dict[str, Any]:
        """
        按维度聚合计算指标。

        参数:
            df: 数据源
            dims: 维度字典（来自 identify_dimensions 的输出）

        返回:
            聚合结果字典，包含：
            - total: 各数值列的统计（sum/avg/max/min/count）
            - by_dimension: 按各分类维度分组聚合的结果
            - insights: 自动生成的数据结论列表
        """
        result: Dict[str, Any] = {
            "total": {},
            "by_dimension": {},
            "insights": []
        }

        # 计算数值列的合计和均值
        for col in dims.get("数值", []):
            if col in df.columns:
                series = df[col]
                result["total"][col] = {
                    "sum": float(series.sum()) if not series.isna().all() else 0.0,
                    "avg": float(series.mean()) if not series.isna().all() else 0.0,
                    "max": float(series.max()) if not series.isna().all() else 0.0,
                    "min": float(series.min()) if not series.isna().all() else 0.0,
                    "count": int(series.count())
                }

        # 按分类维度分组聚合
        numeric_cols = dims.get("数值", [])
        for dim in dims.get("分类", []):
            if dim in df.columns and numeric_cols:
                # 只对确实存在于 df 中的数值列分组
                valid_metrics = [c for c in numeric_cols if c in df.columns]
                if valid_metrics:
                    grouped = df.groupby(dim)[valid_metrics].sum()
                    result["by_dimension"][dim] = grouped.to_dict()

        # 自动生成数据结论
        if dims.get("数值"):
            top_metric = dims["数值"][0]
            if top_metric in result["total"]:
                total_val = result["total"][top_metric]["sum"]
                count_val = result["total"][top_metric]["count"]
                result["insights"].append(f"{top_metric}总计: {total_val:,.2f}")
                result["insights"].append(f"{top_metric}有效记录数: {count_val}")

        return result

    def assess_quality(self, file_paths: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        评估各 Sheet 的数据质量分（0–100）。

        为什么需要这一层：`read_datamap` 要给出「质量分」，但底层此前没有对应方法，
        导致质量分恒为 None——选型阶段因此拿不到「数据是否可信」的信号。

        评分方式：
          每列完整度 = 1 − 缺失率；数值列权重 1.5（缺失直接影响合计口径），
          其余列权重 1.0；加权平均后折算为百分制。

        参数:
            file_paths: 数据文件路径列表
        返回:
            {sheet_key: {"score": float, "row_count": int, "column_count": int,
                         "worst_columns": [...]}}
        """
        result: Dict[str, Dict[str, Any]] = {}
        dfs = self.load_excel(file_paths)
        for key, df in dfs.items():
            if df.empty or df.shape[1] == 0:
                result[key] = {"score": 0.0, "row_count": 0, "column_count": 0,
                               "worst_columns": []}
                continue
            total_w = 0.0
            acc = 0.0
            worst = []
            for col in df.columns:
                null_rate = float(df[col].isna().mean())
                is_num = pd.api.types.is_numeric_dtype(df[col])
                w = 1.5 if is_num else 1.0
                acc += (1 - null_rate) * w
                total_w += w
                if null_rate > 0:
                    worst.append({"column": str(col),
                                  "null_rate": round(null_rate, 4)})
            score = round(100 * acc / total_w, 1) if total_w else 0.0
            worst.sort(key=lambda x: -x["null_rate"])
            result[key] = {
                "score": score,
                "row_count": int(len(df)),
                "column_count": int(df.shape[1]),
                "worst_columns": worst[:5],
            }
        return result

    def calculate_comparison(self, current: float, previous: float) -> Dict[str, float]:
        """
        计算同比/环比增长率。

        参数:
            current: 当前期数值
            previous: 基期数值

        返回:
            {"yoy": 同比增长率(%), "qoq": 环比增长率(%)}
        """
        yoy = ((current - previous) / previous * 100) if previous != 0 else 0.0
        qoq = ((current - previous) / previous * 100) if previous != 0 else 0.0
        return {"yoy": round(yoy, 2), "qoq": round(qoq, 2)}
