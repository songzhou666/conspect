# -*- coding: utf-8 -*-
"""
数据契约测试（v5.0）

这一层的价值不是"代码能跑"，而是**判定边界被钉死**：
  - 什么情况统计层必须给结论（硬证据）
  - 什么情况必须承认判不出来（hint / unknown）
  - 什么情况契约覆盖必须生效

最后一条最重要：早期实现把「这列是什么角色」判在三个模块里，
本层的测试防的就是那种漂移重新长回来。
"""

import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from conspect_tools import schema_contract as sc
from conspect_tools import schema_probe as sp


def _df(**cols):
    return pd.DataFrame(cols)


class TestProbeHardEvidence(unittest.TestCase):
    """硬证据：只看数据就能定，不看列名。"""

    def test_time_by_parse_rate(self):
        p = sp.probe_column(pd.Series(["2025年06月27日 15:27", "2026年07月06日 18:56"]),
                            "任意列名")
        self.assertGreaterEqual(p["date_rate"], 0.9)
        self.assertEqual(sp.judge_by_stats(p)["role"], "time")

    def test_time_iso(self):
        p = sp.probe_column(pd.Series(pd.date_range("2025-01-01", periods=50)), "x")
        self.assertEqual(sp.judge_by_stats(p)["role"], "time")

    def test_all_null_is_ignore(self):
        p = sp.probe_column(pd.Series([None] * 30), "空列")
        self.assertEqual(sp.judge_by_stats(p)["role"], "ignore")

    def test_constant_is_ignore(self):
        p = sp.probe_column(pd.Series(["是"] * 30), "固定")
        self.assertEqual(sp.judge_by_stats(p)["role"], "ignore")

    def test_phone_is_identifier(self):
        """11 位手机号：全唯一大整数，绝不能当度量。"""
        s = pd.Series([f"1{rng}" for rng in
                       np.random.default_rng(7).integers(10**9, 10**10 - 1, 200)])
        s = s.astype("int64")
        p = sp.probe_column(s, "联系方式")
        j = sp.judge_by_stats(p)
        self.assertEqual(j["role"], "identifier")
        self.assertEqual(j["confidence"], "high")

    def test_address_is_identifier(self):
        s = pd.Series([f"浙江省宁波市江北区某路{i}号综合楼17楼1101室"
                       for i in range(200)])
        p = sp.probe_column(s, "地址")
        j = sp.judge_by_stats(p)
        self.assertEqual(j["role"], "identifier")

    def test_enum_is_dimension(self):
        s = pd.Series(["华东", "华北", "华南", "西南", "西北"] * 100)
        p = sp.probe_column(s, "销售区域")
        j = sp.judge_by_stats(p)
        self.assertEqual(j["role"], "dimension")
        self.assertEqual(j["confidence"], "high")


class TestNumericDefaultsToMeasure(unittest.TestCase):
    """
    数值列的默认角色是度量。

    这是回归测试：早期版本先判「低基数枚举」，导致「就诊人次」（1~3）、
    「课时数」（1~5）、「不良数」（0~30）这类小整数计数列被当成枚举维度。
    dtype 是硬信息，数值列就该优先当度量。
    """

    def test_small_integer_counts(self):
        for name, vals in [("就诊人次", [1, 2, 3] * 200),
                           ("课时数", [1, 2, 3, 4, 5] * 120),
                           ("不良数", list(range(0, 30)) * 20)]:
            p = sp.probe_column(pd.Series(vals), name)
            j = sp.judge_by_stats(p)
            self.assertEqual(j["role"], "measure", f"{name} 应是度量，实际 {j['role']}")

    def test_amount_float(self):
        p = sp.probe_column(pd.Series(np.random.default_rng(1).gamma(2, 180, 300)),
                            "GMV")
        self.assertEqual(sp.judge_by_stats(p)["role"], "measure")

    def test_binary_flag_becomes_dimension(self):
        """只有 0/1 两个值的整数列是布尔标志，作维度更合适。"""
        p = sp.probe_column(pd.Series([0, 1] * 150), "是否退款")
        self.assertEqual(sp.judge_by_stats(p)["role"], "dimension")


class TestAdditivityIsHonest(unittest.TestCase):
    """
    可加总性必须诚实：判不出来就标 hint，不硬猜。

    GMV 与客单价都是正小数、分布右偏，统计特征几乎一样，
    但前者求和有意义、后者求和毫无意义。任何用分布形状区分二者的规则都是猜。
    """

    def test_ratio_is_average(self):
        p = sp.probe_column(pd.Series(np.random.default_rng(2).beta(2, 20, 200)),
                            "退款率")
        self.assertEqual(sp.suggest_additivity(p, "measure"), "average")

    def test_int_count_is_additive(self):
        p = sp.probe_column(pd.Series(np.random.default_rng(3).integers(1, 50, 200)),
                            "数量")
        self.assertEqual(sp.suggest_additivity(p, "measure"), "additive")

    def test_amount_vs_unit_price_both_hint(self):
        """金额与单价统计上无法区分，都必须给 hint —— 承认判不了。"""
        a = sp.probe_column(pd.Series(np.random.default_rng(4).gamma(2, 300, 200)), "GMV")
        b = sp.probe_column(pd.Series(np.random.default_rng(5).gamma(2, 90, 200)), "客单价")
        self.assertEqual(sp.suggest_additivity(a, "measure"), "hint")
        self.assertEqual(sp.suggest_additivity(b, "measure"), "hint")

    def test_non_measure_has_no_additivity(self):
        p = sp.probe_column(pd.Series(["A", "B"] * 100), "类别")
        self.assertEqual(sp.suggest_additivity(p, "dimension"), "none")


class TestUnknownIsVisible(unittest.TestCase):
    """判不出来必须显式 unknown，不能静默塞进分类。"""

    def test_high_cardinality_text_may_be_unknown(self):
        s = pd.Series([f"客户{i}" for i in range(300)])
        p = sp.probe_column(s, "客户名称")
        j = sp.judge_by_stats(p)
        # 300/300 全唯一且短 → 标识或未定，都不能是 dimension
        self.assertIn(j["role"], ("identifier", "unknown"))

    def test_judge_frame_reports_unresolved(self):
        # 900 个不同名称、占比 90%，无法区分「分组维度」与「明细标识」
        s = pd.Series([f"诊所{i}" for i in range(900)] + [None] * 100)
        df = _df(名称=s)
        r = sp.judge_frame(df)
        self.assertTrue(r["unresolved"] or r["columns"][0]["role"] == "identifier")
        self.assertIn("duplicate_columns", r)


class TestContractBuild(unittest.TestCase):

    def _probe(self, df):
        return sp.judge_frame(df)

    def test_build_from_probe(self):
        df = _df(日期=pd.date_range("2025-01-01", periods=120),
                 区域=["华东", "华北"] * 60,
                 金额=np.random.default_rng(6).gamma(2, 100, 120))
        c = sc.build(self._probe(df), source={"rows": 120})
        self.assertEqual(c["contract_version"], sc.CONTRACT_VERSION)
        self.assertEqual(c["views"]["time"], ["日期"])
        self.assertEqual(c["views"]["dimension"], ["区域"])
        self.assertEqual(c["views"]["measure"], ["金额"])
        self.assertTrue(all("role" in v and "reason" in v
                            for v in c["columns"].values()))

    def test_override_changes_role(self):
        df = _df(名称=[f"客户{i}" for i in range(300)])
        base = sc.build(self._probe(df))
        self.assertNotEqual(base["columns"]["名称"]["role"], "dimension")
        fixed = sc.build(self._probe(df),
                         overrides={"名称": {"role": "dimension",
                                            "reason": "客户名称用于分组"}})
        self.assertEqual(fixed["columns"]["名称"]["role"], "dimension")
        self.assertEqual(fixed["columns"]["名称"]["decided_by"], "override")
        self.assertIn("客户名称用于分组", fixed["columns"]["名称"]["reason"])

    def test_override_illegal_role_raises(self):
        df = _df(x=[1, 2] * 60)
        with self.assertRaises(ValueError):
            sc.build(self._probe(df), overrides={"x": {"role": "度量"}})

    def test_override_additivity(self):
        df = _df(GMV=np.random.default_rng(7).gamma(2, 300, 200))
        base = sc.build(self._probe(df))
        # 统计判不出来 → average + 未确认
        self.assertEqual(base["columns"]["GMV"]["additivity"], "average")
        self.assertFalse(base["columns"]["GMV"]["additivity_confirmed"])
        self.assertIn("GMV", base["views"]["unconfirmed_additivity"])

        fixed = sc.build(self._probe(df),
                         overrides={"GMV": {"role": "measure",
                                            "additivity": "additive"}})
        self.assertEqual(fixed["columns"]["GMV"]["additivity"], "additive")
        self.assertTrue(fixed["columns"]["GMV"]["additivity_confirmed"])
        self.assertNotIn("GMV", fixed["views"]["unconfirmed_additivity"])

    def test_hint_falls_back_to_average(self):
        """探测给 hint 时不能落成 sum，否则会把单价加出天文数字。"""
        df = _df(单价=np.random.default_rng(8).gamma(2, 90, 200))
        c = sc.build(self._probe(df))
        self.assertEqual(c["columns"]["单价"]["additivity"], "average")

    def test_duplicate_columns_detected(self):
        a = ["A", "B", "C"] * 50
        df = _df(原列=a, 副本=a)
        c = sc.build(self._probe(df))
        self.assertTrue(any(set(p) == {"原列", "副本"}
                            for p in c["duplicate_columns"]))


class TestContractConsumption(unittest.TestCase):

    def _contract(self):
        df = _df(日期=pd.date_range("2025-01-01", periods=120),
                 区域=["华东", "华北"] * 60,
                 金额=np.random.default_rng(9).gamma(2, 100, 120),
                 单价=np.random.default_rng(10).gamma(2, 40, 120),
                 电话=np.arange(10**9, 10**9 + 120))
        return sc.build(sp.judge_frame(df))

    def test_to_dimensions_excludes_identifier(self):
        d = sc.to_dimensions(self._contract())
        self.assertIn("日期", d["时间"])
        self.assertIn("区域", d["分类"])
        self.assertIn("金额", d["数值"])
        for role in ("identifier", "text", "ignore", "unknown"):
            for col in d["分类"]:
                self.assertNotIn(col, self._contract()["views"].get(role, []))

    def test_measure_agg(self):
        c = self._contract()
        self.assertEqual(sc.measure_agg(c, "单价"), "mean")
        c2 = sc.build(sp.judge_frame(_df(数量=[1, 2, 3] * 60)),
                      overrides={"数量": {"role": "measure",
                                          "additivity": "additive"}})
        self.assertEqual(sc.measure_agg(c2, "数量"), "sum")

    def test_validate_mismatch(self):
        c = self._contract()
        v = sc.validate(c, ["日期", "区域", "金额", "新列"])
        self.assertFalse(v["ok"])
        self.assertIn("新列", v["missing_in_contract"])

    def test_validate_match(self):
        c = self._contract()
        cols = list(c["columns"])
        self.assertTrue(sc.validate(c, cols)["ok"])

    def test_save_and_load(self):
        import tempfile
        c = self._contract()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            p = sc.save(c, str(Path(d) / "_cs-schema.json"))
            back = sc.load(p)
            self.assertEqual(back["contract_version"], sc.CONTRACT_VERSION)
            self.assertEqual(set(back["columns"]), set(c["columns"]))

    def test_summary_lines_mentions_boundaries(self):
        lines = "\n".join(sc.summary_lines(self._contract()))
        self.assertIn("数据契约", lines)
        # 可加总性未确认的列必须出现在摘要里，供报表口径声明
        self.assertIn("可加总性未确认", lines)


class TestContractDrivesAnalyze(unittest.TestCase):
    """端到端：契约必须真的驱动 analyze，而不是被忽略。"""

    def test_analyze_with_contract_excludes_identifier(self):
        import tempfile
        from conspect_tools.run import run

        df = _df(
            日期=pd.date_range("2025-01-01", periods=200),
            区域=["华东", "华北", "华南", "西南"] * 50,
            金额=np.round(np.random.default_rng(11).gamma(2, 200, 200), 2),
            电话=np.arange(10**9, 10**9 + 200),
        )
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            xlsx = Path(d) / "t.xlsx"
            df.to_excel(xlsx, index=False)
            sv = run("save_schema", {
                "file_paths": [str(xlsx)],
                "overrides": {"金额": {"role": "measure", "additivity": "additive"}},
                "output_dir": d, "decided_by": "ai"})
            sf = list(sv["paths"].values())[0]

            an = run("analyze", {"file_paths": [str(xlsx)], "schema_file": sf})
            self.assertEqual(an["status"], "ok")
            r = list(an["data"].values())[0]
            prov = r["dimensions"]["_provenance"]
            self.assertEqual(prov["source"], "contract")
            self.assertEqual(prov["decided_by"], "ai")
            # 电话必须被排除，金额必须在
            self.assertIn("电话", prov["excluded"]["identifier"])
            self.assertNotIn("电话", r["dimensions"]["数值"])
            self.assertIn("金额", r["dimensions"]["数值"])

    def test_analyze_without_contract_marks_heuristic(self):
        import tempfile
        from conspect_tools.run import run

        df = _df(日期=pd.date_range("2025-01-01", periods=150),
                 区域=["A", "B"] * 75,
                 金额=np.round(np.random.default_rng(12).gamma(2, 100, 150), 2))
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            xlsx = Path(d) / "t2.xlsx"
            df.to_excel(xlsx, index=False)
            an = run("analyze", {"file_paths": [str(xlsx)]})
            r = list(an["data"].values())[0]
            prov = r["dimensions"]["_provenance"]
            # 未提供契约时现场生成，provenance 标记为 auto_contract
            self.assertEqual(prov["source"], "auto_contract")
            self.assertEqual(prov["decided_by"], "heuristic")
            self.assertTrue(r["contract"]["note"],
                            "启发式路径必须在 note 里说明判定来源与不确定项")


if __name__ == "__main__":
    unittest.main()
