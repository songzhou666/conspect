# -*- coding: utf-8 -*-
"""
报表板块库测试（v4.0）

校验目标：
  1. 板块库可解析出 22 个板块、6 个族
  2. 必需度取值合法，且分布与文档一致（必需 7 / 条件 13 / 可选 2）
  3. 每个板块的 section type 都在渲染引擎支持集内
  4. 每个板块都有可执行的触发条件
  5. 触发评估的「选中 + 未选中」恒等于总数
  6. 裁剪规则：核心板块保底、分析板块至少留 2 个
"""

import unittest

from conspect_tools import block_library

EXPECTED_COUNT = 22
EXPECTED_FAMILIES = 6
#: render_engine.render_web_dashboard 支持的类型
SUPPORTED_SECTION_TYPES = {
    "kpi_cards", "section_group", "chart", "conclusion", "table", "custom", "prose",
}


class TestBlockLibraryParsing(unittest.TestCase):

    def test_block_count(self):
        self.assertEqual(len(block_library.all_blocks()), EXPECTED_COUNT)

    def test_family_count(self):
        fams = {b["family_id"] for b in block_library.all_blocks()}
        self.assertEqual(len(fams), EXPECTED_FAMILIES)

    def test_ids_are_unique_and_sequential(self):
        ids = block_library.ids()
        self.assertEqual(len(ids), len(set(ids)), "板块编号重复")
        expected = [f"B{i:02d}" for i in range(1, EXPECTED_COUNT + 1)]
        self.assertEqual(sorted(ids), expected, "板块编号不连续或有缺失")

    def test_requirement_values_valid(self):
        for b in block_library.all_blocks():
            self.assertIn(b["requirement"], ("必需", "条件", "可选"),
                          f"{b['id']} 必需度非法：{b['requirement']}")

    def test_requirement_distribution_matches_doc(self):
        self.assertEqual(len(block_library.by_requirement("必需")), 7)
        self.assertEqual(len(block_library.by_requirement("条件")), 13)
        self.assertEqual(len(block_library.by_requirement("可选")), 2)

    def test_every_block_has_section_type_in_engine(self):
        for b in block_library.all_blocks():
            self.assertIn(b["section_type"], SUPPORTED_SECTION_TYPES,
                          f"{b['id']} 的 section type {b['section_type']} 引擎不支持")

    def test_every_block_has_trigger(self):
        missing = [b["id"] for b in block_library.all_blocks()
                   if b["id"] not in block_library.TRIGGERS]
        self.assertEqual(missing, [], f"以下板块缺触发实现：{missing}")

    def test_every_block_has_trigger_text(self):
        texts = block_library.triggers()
        for b in block_library.all_blocks():
            self.assertIn(b["id"], texts, f"{b['id']} 缺触发条件描述")
            self.assertTrue(texts[b["id"]].strip())

    def test_summary_consistent(self):
        s = block_library.summary()
        self.assertEqual(s["count"], EXPECTED_COUNT)
        self.assertEqual(s["families"], EXPECTED_FAMILIES)
        self.assertEqual(s["required"] + s["conditional"] + s["optional"], EXPECTED_COUNT)


class TestBlockEvaluation(unittest.TestCase):

    RICH = {
        "has_time": True, "time_points": 12,
        "has_category": True, "category_count": 5,
        "has_numeric": True, "numeric_count": 3,
        "sample_size": 500, "distinct_max": 40,
        "has_target": True, "has_decomposable": True, "has_advanced": True,
        "quality_score": 95,
    }

    POOR = {"has_numeric": True, "numeric_count": 1, "sample_size": 5}

    def test_selected_plus_excluded_equals_total(self):
        for feat in (self.RICH, self.POOR, {}):
            r = block_library.evaluate(feat)
            self.assertEqual(len(r["selected"]) + len(r["excluded"]), EXPECTED_COUNT)

    def test_required_blocks_always_selected(self):
        required = {b["id"] for b in block_library.by_requirement("必需")}
        for feat in (self.RICH, self.POOR, {}):
            got = {b["id"] for b in block_library.evaluate(feat)["selected"]}
            self.assertTrue(required.issubset(got),
                            f"必需板块被漏选：{required - got}")

    def test_poor_data_excludes_advanced_analysis(self):
        got = {b["id"] for b in block_library.evaluate(self.POOR)["selected"]}
        for bid in ("B07", "B10", "B12", "B14"):
            self.assertNotIn(bid, got, f"贫数据下不应纳入 {bid}")

    def test_rich_data_includes_analysis_blocks(self):
        got = {b["id"] for b in block_library.evaluate(self.RICH)["selected"]}
        for bid in ("B05", "B07", "B08", "B09", "B10", "B11", "B12"):
            self.assertIn(bid, got, f"富数据下应纳入 {bid}")

    def test_excluded_items_carry_reason(self):
        for item in block_library.evaluate(self.POOR)["excluded"]:
            self.assertTrue(item.get("reason"), f"{item['id']} 未给出未选中原因")


class TestBlockTrim(unittest.TestCase):

    def _all(self):
        # 人为构造「全部板块都命中」的场景
        return block_library.evaluate({
            "has_time": True, "time_points": 12, "has_category": True,
            "category_count": 5, "numeric_count": 3, "sample_size": 500,
            "distinct_max": 40, "has_target": True, "has_decomposable": True,
            "has_advanced": True, "quality_score": 50, "has_missing": True,
            "want_detail": True, "want_forecast": True,
            "want_trend_glance": True, "want_appendix": True,
        })["selected"]

    def test_no_trim_when_under_limit(self):
        blocks = self._all()
        kept, dropped = block_library.trim(blocks, limit=len(blocks))
        self.assertEqual(len(kept), len(blocks))
        self.assertEqual(dropped, [])

    def test_core_blocks_never_trimmed(self):
        blocks = self._all()
        kept, _ = block_library.trim(blocks, limit=8)
        kept_ids = {b["id"] for b in kept}
        self.assertTrue(block_library.CORE.issubset(kept_ids),
                        f"核心板块被裁掉：{block_library.CORE - kept_ids}")

    def test_at_least_two_analysis_blocks_survive(self):
        blocks = self._all()
        kept, _ = block_library.trim(blocks, limit=10, min_analysis=2)
        analysis = [b for b in kept if b["family_id"] == "analysis"]
        self.assertGreaterEqual(len(analysis), 2, "分析板块被裁到不足 2 个")

    def test_trim_result_preserves_library_order(self):
        blocks = self._all()
        kept, _ = block_library.trim(blocks, limit=10)
        order = {b["id"]: i for i, b in enumerate(blocks)}
        positions = [order[b["id"]] for b in kept]
        self.assertEqual(positions, sorted(positions), "裁剪后板块顺序被打乱")

    def test_kept_and_dropped_are_disjoint_and_complete(self):
        blocks = self._all()
        kept, dropped = block_library.trim(blocks, limit=9)
        kept_ids = {b["id"] for b in kept}
        dropped_ids = {b["id"] for b in dropped}
        self.assertEqual(kept_ids & dropped_ids, set())
        self.assertEqual(kept_ids | dropped_ids, {b["id"] for b in blocks})


class TestChartCapabilityMapping(unittest.TestCase):
    """
    板块声明的图表必须能落到引擎真实支持的类型。

    这组测试防的是「板块库声明了引擎画不出的图」——那种缺陷只在渲染时暴露，
    静态看文档完全发现不了。
    """

    def test_every_declared_word_has_alias(self):
        """板块库声明的每个图表词都必须有降级映射。"""
        unmapped = block_library.unmapped_chart_words()
        self.assertEqual(unmapped, [], f"无映射的声明词：{unmapped}")

    def test_chains_only_contain_engine_types(self):
        """所有板块的图表链只能是引擎支持的类型。"""
        for b in block_library.all_blocks():
            for ct in block_library.chart_chain(b["id"]):
                self.assertIn(ct, block_library.ENGINE_CHARTS,
                              f"{b['id']} 的 {ct} 不在引擎支持集内")

    def test_engine_charts_matches_render_engine(self):
        """ENGINE_CHARTS 必须与 ChartBuilder.build 的分派表逐项一致。"""
        import re
        from pathlib import Path
        src = (Path(__file__).resolve().parent.parent
               / "conspect_tools" / "render_engine.py").read_text(encoding="utf-8")
        m = re.search(r"builders = \{(.*?)\n        \}", src, re.S)
        self.assertIsNotNone(m, "未能解析 ChartBuilder.build 的分派表")
        real = set(re.findall(r'"([a-z_]+)":\s*ChartBuilder\.', m.group(1)))
        self.assertEqual(real, block_library.ENGINE_CHARTS)

    def test_downgrade_is_declared(self):
        """引擎画不出的类型必须明确降级，且降级说明如实报出。"""
        # 帕累托 / 瀑布 / 直方图 / 箱线 / 旭日 / K线 引擎都没有
        self.assertEqual(block_library.chart_chain("B10"), ["bar"])
        self.assertIn("帕累托 → bar（降级）", block_library.chart_notes("B10"))
        self.assertIn("旭日 → treemap（降级）", block_library.chart_notes("B08"))
        self.assertTrue(any("K线" in n for n in block_library.chart_notes("B07")))

    def test_non_chart_blocks_not_reported_as_downgrade(self):
        """非图形态（指标卡/表格）不算降级，不该出现在降级说明里。"""
        self.assertEqual(block_library.chart_notes("B04"), [])
        self.assertEqual(block_library.chart_notes("B13"), [])
        self.assertEqual(block_library.chart_notes("B01"), [])

    def test_chart_word_spacing_normalized(self):
        """「K 线」带空格也必须能映射（否则只在渲染时才暴露）。"""
        words = ["K 线", "K线", "折线 + 置信区间", "折线+置信区间"]
        for w in words:
            self.assertNotIn(w, block_library.unmapped_chart_words())

    def test_annotate_block_adds_capability(self):
        """选型结果需带引擎可渲染类型，供生成阶段直接使用。"""
        from conspect_tools.ai_agent import AIAgent
        b = AIAgent._annotate_block(block_library.get("B09"))
        self.assertIn("bar", b["engine_charts"])
        self.assertIn("engine_charts", b)
        self.assertIn("chart_notes", b)


if __name__ == "__main__":
    unittest.main()
