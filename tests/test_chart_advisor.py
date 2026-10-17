# -*- coding: utf-8 -*-
"""
图表建议器测试（v4.1）

校验目标：
  1. 可加总性判别：数量/金额求和，单价/比率/单位成本取均值
  2. 排除「长得像数字的标识列」（电话、编号）
  3. 排除高缺失列与全空列（否则 sum 严重低估）
  4. 排除明细 ID 列做分类图（否则饼图出几十个扇区）
  5. 时间维度自算（aggregated 不含时间），跨度大时按月聚合
  6. 维表不产出趋势图（无可加总指标 → 按时间聚合是伪趋势）
  7. 分布图分桶（retbins 回归）
  8. 事实表 / 维表判定
  9. 数据议题可执行
"""

import unittest

import pandas as pd

from conspect_tools import chart_advisor as ca


def _fact_df():
    """构造一张事实表：72 行、有可加总指标、有日期、有分类、含缺失列。"""
    days = pd.date_range("2026-01-05", periods=6, freq="MS")
    rows = []
    for i, d in enumerate(days):
        for j in range(12):
            rows.append({
                "订单日期": d,
                "订单编号": f"SO{i:02d}{j:03d}",
                "销售区域": ["华东", "华北", "华南"][j % 3],
                "产品类别": ["办公用品", "电子产品", "家居用品", "服装配饰"][j % 4],
                "销售数量": (j + 1) * 3 + i,
                "单价": 100.0 + j * 10 + i,
                "销售额": (j + 1) * 3 * (100.0 + j * 10) if j % 3 == 0 else None,
                "实际成交价": None,
                "联系电话": 13800000000 + j,
            })
    return pd.DataFrame(rows)


def _dim_df():
    """维表：只有价格/额度类字段，没有可加总指标。"""
    return pd.DataFrame({
        "产品编号": [f"P{i:03d}" for i in range(12)],
        "产品名称": [f"产品{i}" for i in range(12)],
        "建议零售价": [99.0 + i * 50 for i in range(12)],
        "单位成本": [50.0 + i * 20 for i in range(12)],
        "上市日期": pd.date_range("2020-01-01", periods=12, freq="QE"),
    })


class TestAdditivity(unittest.TestCase):
    """可加总性判据——求错会得出荒谬指标。"""

    def test_quantity_and_amount_are_additive(self):
        self.assertEqual(ca._agg_for("销售数量"), "sum")
        self.assertEqual(ca._agg_for("销售额"), "sum")
        self.assertEqual(ca._agg_for("毛利"), "sum")

    def test_price_and_rate_are_averaged(self):
        self.assertEqual(ca._agg_for("单价"), "mean")
        self.assertEqual(ca._agg_for("折扣率"), "mean")
        self.assertEqual(ca._agg_for("毛利率"), "mean")

    def test_unit_cost_is_averaged(self):
        """「单位成本」含「成本」但是单价概念，求和会荒谬。"""
        self.assertEqual(ca._agg_for("单位成本"), "mean")

    def test_unknown_defaults_to_mean(self):
        """无法判定时取均值——宁可保守，也不要输出巨额合计。"""
        self.assertEqual(ca._agg_for("某个奇怪字段"), "mean")

    def test_label_no_duplicate_prefix(self):
        """「均价」不得变成「平均均价」，「人均GDP」不得变成「平均人均GDP」。"""
        self.assertEqual(ca._metric_label("单价", "mean"), "均价")
        self.assertEqual(ca._metric_label("人均GDP(元)", "mean"), "人均GDP(元)")
        self.assertEqual(ca._metric_label("销售数量", "sum"), "销量")


class TestMetricFiltering(unittest.TestCase):

    def test_phone_and_id_excluded(self):
        df = _fact_df()
        dims = {"数值": ["销售数量", "联系电话"], "分类": [], "时间": []}
        cols = [m["col"] for m in ca._usable_metrics(df, dims)[0]]
        self.assertIn("销售数量", cols)
        self.assertNotIn("联系电话", cols)

    def test_high_null_column_excluded(self):
        df = _fact_df()
        dims = {"数值": ["销售数量", "销售额"], "分类": [], "时间": []}
        cols = [m["col"] for m in ca._usable_metrics(df, dims)[0]]
        self.assertNotIn("销售额", cols, "缺失 66% 的列不应参与聚合")

    def test_all_null_column_excluded(self):
        df = _fact_df()
        dims = {"数值": ["实际成交价"], "分类": [], "时间": []}
        metrics, using_count = ca._usable_metrics(df, dims)
        # 无有效度量且行数不足 100 → 不硬凑「记录数」
        self.assertEqual(metrics, [])
        self.assertFalse(using_count)

    def test_constant_column_excluded(self):
        df = _fact_df()
        df["固定值"] = 1
        dims = {"数值": ["固定值"], "分类": [], "时间": []}
        metrics, _ = ca._usable_metrics(df, dims)
        self.assertEqual(metrics, [])


class TestCategoryFiltering(unittest.TestCase):

    def test_id_column_excluded(self):
        """唯一值≈行数的列是明细 ID，不能做分类图。"""
        df = _fact_df()
        dims = {"数值": [], "分类": ["订单编号", "销售区域"], "时间": []}
        cols = [c["col"] for c in ca._usable_categories(df, dims)]
        self.assertIn("销售区域", cols)
        self.assertNotIn("订单编号", cols)

    def test_too_many_categories_excluded(self):
        df = _fact_df()
        df["细分类"] = [f"c{i}" for i in range(len(df))]
        dims = {"数值": [], "分类": ["细分类"], "时间": []}
        self.assertEqual(ca._usable_categories(df, dims), [])


class TestRecommend(unittest.TestCase):

    def test_fact_table_produces_charts(self):
        df = _fact_df()
        dims = {"时间": ["订单日期"], "分类": ["销售区域", "产品类别"],
                "数值": ["销售数量", "单价", "销售额", "实际成交价"]}
        charts = ca.recommend(df, dims)
        types = {c["chart_type"] for c in charts}
        self.assertIn("line", types, "事实表应有趋势图")
        self.assertIn("bar", types, "事实表应有排名/分布图")
        self.assertTrue(all(c.get("block") for c in charts), "每张图都应标注归属板块")

    def test_time_granularity_monthly(self):
        df = _fact_df()
        dims = {"时间": ["订单日期"], "分类": ["销售区域"], "数值": ["销售数量"]}
        line = next(c for c in ca.recommend(df, dims) if c["chart_type"] == "line")
        self.assertEqual(len(line["data"]["categories"]), 6)
        self.assertIn("月", line["title"])

    def test_distribution_uses_bins(self):
        """分布图必须真分桶（曾因 pd.cut 缺 retbins 而静默失败）。"""
        df = _fact_df()
        dims = {"时间": [], "分类": ["销售区域"], "数值": ["销售数量"]}
        dist = [c for c in ca.recommend(df, dims) if c["block"] == "B11"]
        self.assertTrue(dist, "应产出分布图")
        cats = dist[0]["data"]["categories"]
        self.assertGreaterEqual(len(cats), 2)
        self.assertIn("~", cats[0], "分桶标签应形如 8~76")

    def test_dimension_table_no_trend(self):
        """维表无可加总指标，不得产出伪趋势。"""
        df = _dim_df()
        dims = {"时间": ["上市日期"], "分类": ["产品名称"], "数值": ["建议零售价", "单位成本"]}
        types = {c["chart_type"] for c in ca.recommend(df, dims)}
        self.assertNotIn("line", types)

    def test_wide_time_span_no_trend(self):
        """时间跨度 >3 年不做趋势（多为属性日期）。"""
        df = _fact_df()
        df["订单日期"] = pd.date_range("2018-01-01", periods=len(df), freq="ME")
        dims = {"时间": ["订单日期"], "分类": ["销售区域"], "数值": ["销售数量"]}
        types = {c["chart_type"] for c in ca.recommend(df, dims)}
        self.assertNotIn("line", types)

    def test_no_metrics_returns_empty(self):
        df = _dim_df()
        dims = {"时间": [], "分类": ["产品名称"], "数值": []}
        self.assertEqual(ca.recommend(df, dims), [])


class TestClassifyTable(unittest.TestCase):

    def test_fact_table(self):
        df = _fact_df()
        dims = {"时间": ["订单日期"], "分类": ["销售区域"], "数值": ["销售数量"]}
        role = ca.classify_table(df, dims)
        self.assertEqual(role["role"], "fact")
        self.assertIn("销售数量", role["additive_metrics"])

    def test_dimension_table(self):
        df = _dim_df()
        dims = {"时间": ["上市日期"], "分类": ["产品名称"], "数值": ["建议零售价", "单位成本"]}
        self.assertEqual(ca.classify_table(df, dims)["role"], "dimension")


class TestDataIssues(unittest.TestCase):

    def test_reports_null_and_empty_columns(self):
        df = _fact_df()
        dims = {"时间": ["订单日期"], "分类": ["销售区域", "订单编号"],
                "数值": ["销售数量", "销售额", "实际成交价"]}
        issues = ca.data_issues(df, dims)
        cols = {(i["type"], i["column"]) for i in issues}
        self.assertIn(("全空列", "实际成交价"), cols)
        self.assertIn(("高缺失列", "销售额"), cols)

    def test_reports_id_column(self):
        df = _fact_df()
        dims = {"时间": [], "分类": ["订单编号"], "数值": []}
        issues = ca.data_issues(df, dims)
        self.assertTrue(any(i["type"] == "疑似明细ID" for i in issues))

    def test_every_issue_has_actionable_suggestion(self):
        df = _fact_df()
        dims = {"时间": [], "分类": ["订单编号"], "数值": ["实际成交价"]}
        for i in ca.data_issues(df, dims):
            self.assertTrue(i.get("suggestion"), f"{i} 缺少可执行建议")


class TestCjkDateTime(unittest.TestCase):
    """
    中文日期解析。

    真实业务表格（企业微信导出）里日期写成「2025年06月27日 15:27」，
    `pd.to_datetime` 直接解析会 100% 失败，趋势图随之静默消失。
    """

    def test_chinese_format(self):
        s = pd.Series(["2025年06月27日 15:27", "2026年07月06日 18:56"])
        dt = ca._to_datetime(s)
        self.assertEqual(int(dt.notna().sum()), 2)
        self.assertEqual(dt.iloc[0].year, 2025)
        self.assertEqual(dt.iloc[0].hour, 15)

    def test_chinese_without_time(self):
        s = pd.Series(["2025年1月5日", "2025年12月31日"])
        dt = ca._to_datetime(s)
        self.assertEqual(int(dt.notna().sum()), 2)

    def test_iso_and_slash_formats(self):
        for vals in (["2026-01-05 08:00:00", "2026-02-01 09:30"],
                     ["2026/01/05", "2026/02/01"]):
            dt = ca._to_datetime(pd.Series(vals))
            self.assertEqual(int(dt.notna().sum()), 2, vals)

    def test_garbage_returns_nat_without_raising(self):
        dt = ca._to_datetime(pd.Series(["不是日期", ""]))
        self.assertEqual(int(dt.notna().sum()), 0)

    def test_mixed_valid_invalid(self):
        dt = ca._to_datetime(pd.Series(["2025年06月27日 15:27", "坏数据"]))
        self.assertEqual(int(dt.notna().sum()), 1)


def _visit_df(n=300):
    """构造一份「记录型」表：无金额度量、有中文日期、有电话与标签维度。"""
    rows = []
    stages = ["加微信", "已报价", "已试用", "已成交"]
    for i in range(n):
        rows.append({
            "填写时间（自动）": f"2025年{1 + i % 12:02d}月{1 + i % 27:02d}日 10:30",
            "诊所名称": f"诊所{i % 40}",
            "省": ["广东省", "江苏省", "浙江省"][i % 3],
            "销售漏斗": stages[i % 4],
            "优先级": ["A重点跟进", "B持续培育"][i % 2],
            "联系方式": 13800000000 + i,
            "拜访图片（必填）": f"photo_{i}.jpeg",
        })
    return pd.DataFrame(rows)


class TestCountMetric(unittest.TestCase):
    """没有金额度量时，必须退化为「记录数」——否则一张图都出不来。"""

    def test_record_table_uses_count(self):
        df = _visit_df()
        dims = {"时间": ["填写时间（自动）"],
                "分类": ["诊所名称", "省", "销售漏斗", "优先级"],
                "数值": ["联系方式"]}
        charts = ca.recommend(df, dims)
        self.assertTrue(charts, "记录型表应产出图表")
        self.assertTrue(all("记录数" in c["title"] for c in charts),
                        [c["title"] for c in charts])

    def test_phone_column_never_used_as_metric(self):
        """电话号码有几百个唯一值，绝不能变成「平均联系方式」。"""
        df = _visit_df()
        dims = {"时间": ["填写时间（自动）"], "分类": ["省"], "数值": ["联系方式"]}
        for c in ca.recommend(df, dims):
            self.assertNotIn("联系方式", c["title"])

    def test_tiny_table_still_returns_nothing(self):
        """行数太少且无度量 → 不硬凑图表。"""
        df = _visit_df(20)
        dims = {"时间": [], "分类": ["省"], "数值": ["联系方式"]}
        self.assertEqual(ca.recommend(df, dims), [])

    def test_record_table_classified_as_fact(self):
        df = _visit_df()
        dims = {"时间": ["填写时间（自动）"], "分类": ["省"], "数值": ["联系方式"]}
        role = ca.classify_table(df, dims)
        self.assertEqual(role["role"], "fact")
        self.assertEqual(role["measure"], "count")

    def test_small_no_metric_table_stays_dimension(self):
        df = _visit_df(20)
        dims = {"时间": [], "分类": ["省"], "数值": ["联系方式"]}
        self.assertEqual(ca.classify_table(df, dims)["role"], "dimension")


class TestFunnelAndDimensions(unittest.TestCase):
    """漏斗优先、重复列去重、覆盖率排序。"""

    def test_funnel_dimension_uses_funnel_chart(self):
        df = _visit_df()
        dims = {"时间": ["填写时间（自动）"],
                "分类": ["诊所名称", "省", "销售漏斗", "优先级"],
                "数值": ["联系方式"]}
        charts = ca.recommend(df, dims)
        funnels = [c for c in charts if c["chart_type"] == "funnel"]
        self.assertEqual(len(funnels), 1)
        self.assertIn("销售漏斗", funnels[0]["title"])

    def test_duplicate_columns_deduped(self):
        df = _fact_df()
        df["销售区域副本"] = df["销售区域"]
        dims = {"时间": [], "分类": ["销售区域", "销售区域副本"], "数值": ["销售数量"]}
        cols = [c["col"] for c in ca._usable_categories(df, dims)]
        self.assertEqual(len(cols), 1, f"内容相同的列应去重：{cols}")

    def test_low_coverage_dimension_ranked_later(self):
        df = _visit_df()
        df.loc[df.index[: len(df) // 2], "优先级"] = None      # 一半缺失
        dims = {"时间": [], "分类": ["优先级", "省"], "数值": []}
        cols = [c["col"] for c in ca._usable_categories(df, dims)]
        self.assertEqual(cols[0], "省", f"覆盖率高的维度应排前：{cols}")


if __name__ == "__main__":
    unittest.main()
