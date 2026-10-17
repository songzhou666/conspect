# -*- coding: utf-8 -*-
"""
板块驱动装配测试（v4.1）

校验目标（对应 P1 缺口修复）：
  1. blocks 传字符串 id 或板块 dict，都能驱动装配
  2. 板块顺序即页序，不重排
  3. 图表按板块声明的类型匹配，且**同一图表不被两个板块重复消费**
  4. 文案类板块缺内容时记入 `_gaps`，不静默编造
  5. 未绑定到板块的图表进入「补充图表」区，数据不静默消失
  6. 不传 blocks 时仍走旧的按主题分组路径（向后兼容）
  7. 装配结果可直接渲染成 HTML
"""

import unittest

from conspect_tools.ai_agent import AIAgent
from conspect_tools.render_engine import RenderEngine
from conspect_tools import block_library


def _analysis():
    return {
        "title": "2026 上半年销售分析",
        "data_source": "企业销售明细数据表.xlsx",
        "kpis": {"total_sales": 1234567.0, "orders": 72, "customers": 30},
        "charts": [
            {"type": "line", "title": "月度销售趋势",
             "data": {"categories": ["1月", "2月", "3月"], "values": [10, 20, 30]},
             "description": "逐月上行"},
            {"type": "pie", "title": "区域构成",
             "data": {"categories": ["华东", "华北"], "values": [60, 40]},
             "description": "华东过半"},
            {"type": "bar", "title": "产品销售排名",
             "data": {"categories": ["A", "B"], "values": [5, 3]},
             "description": "A 领先"},
        ],
        "narrative": {
            "subtitle": "上半年营收 123 万",
            "summary": ["营收 123 万", "华东过半", "3 月为峰值"],
            "findings": ["华东贡献 60%", "电子产品毛利最高", "3 月环比增 22%"],
            "risks": ["华北增速放缓"],
            "opportunities": ["西南新客放量"],
            "actions": [{"text": "加大西南投入", "priority": "高"}],
            "closing": "下半年聚焦西南",
        },
    }


INSIGHTS = [
    {"level": "核心", "description": "华东为第一增长极"},
    {"level": "风险", "description": "华北增速下滑"},
]


class TestAssembleByBlocks(unittest.TestCase):

    def setUp(self):
        self.agent = AIAgent()

    def test_accepts_block_id_strings(self):
        """传板块 id 字符串即可装配。"""
        blocks = ["B01", "B02", "B04", "B15", "B22"]
        layout = self.agent.build_dashboard_layout(_analysis(), INSIGHTS, {}, blocks)
        self.assertEqual(layout["_mode"], "blocks")
        self.assertEqual(layout["_blocks"], blocks)
        # 这 5 个板块都不消费图表，故 3 个图表进入「补充图表」区（数据不丢）
        own = [s for s in layout["sections"] if s.get("_block") != "_orphan"]
        self.assertEqual(len(own), 5)

    def test_accepts_block_dicts(self):
        """传 select_content 返回的板块 dict 同样可装配。"""
        blocks = [block_library.get("B01"), block_library.get("B04")]
        layout = self.agent.build_dashboard_layout(_analysis(), INSIGHTS, {}, blocks)
        self.assertEqual(layout["_blocks"], ["B01", "B04"])

    def test_order_preserved(self):
        """板块顺序即页序，不因内部规则重排。"""
        blocks = ["B15", "B01", "B04", "B02"]
        layout = self.agent.build_dashboard_layout(_analysis(), INSIGHTS, {}, blocks)
        self.assertEqual(layout["_blocks"], blocks)

    def test_chart_matched_by_declared_type(self):
        """图表按板块声明的引擎类型匹配，而非标题关键词。"""
        layout = self.agent.build_dashboard_layout(
            _analysis(), INSIGHTS, {}, ["B07", "B08", "B09"])
        types = []
        for sec in layout["sections"]:
            for it in sec.get("items", []):
                if it.get("type") == "chart":
                    types.append(it["chart_type"])
        self.assertEqual(types, ["line", "pie", "bar"])

    def test_chart_not_consumed_twice(self):
        """同一图表不得被两个板块重复使用。"""
        # B07 与 B14 都接受 line
        layout = self.agent.build_dashboard_layout(
            _analysis(), INSIGHTS, {}, ["B07", "B14"])
        line_count = 0
        for sec in layout["sections"]:
            for it in sec.get("items", []):
                if it.get("type") == "chart" and it["chart_type"] == "line":
                    line_count += 1
        self.assertEqual(line_count, 1, "折线图被重复消费")

    def test_missing_chart_recorded_as_gap(self):
        """无匹配图表时记入缺口，不静默省略。"""
        a = _analysis()
        a["charts"] = []
        layout = self.agent.build_dashboard_layout(a, INSIGHTS, {}, ["B07"])
        self.assertEqual(len(layout["sections"]), 0)
        self.assertTrue(any(g["block"] == "B07" for g in layout["_gaps"]))

    def test_missing_narrative_recorded(self):
        """文案缺失时记录缺口而非编造内容。"""
        a = _analysis()
        a.pop("narrative")
        layout = self.agent.build_dashboard_layout(a, [], {}, ["B01"])
        self.assertTrue(any(g["block"] == "B01" for g in layout["_gaps"]))

    def test_unknown_block_id(self):
        """不存在的板块编号记缺口，不抛异常。"""
        layout = self.agent.build_dashboard_layout(_analysis(), INSIGHTS, {}, ["B99"])
        own = [s for s in layout["sections"] if s.get("_block") != "_orphan"]
        self.assertEqual(own, [])
        self.assertTrue(any(g["block"] == "B99" for g in layout["_gaps"]))

    def test_orphan_charts_kept(self):
        """未被任何板块消费的图表进入补充区，不丢数据。"""
        layout = self.agent.build_dashboard_layout(_analysis(), INSIGHTS, {}, ["B01"])
        orphan = [s for s in layout["sections"] if s.get("_block") == "_orphan"]
        self.assertEqual(len(orphan), 1)
        self.assertEqual(len(orphan[0]["items"]), 3)

    def test_explicit_chart_binding(self):
        """图表显式声明 block 字段时优先按声明归属。"""
        a = _analysis()
        a["charts"][0]["block"] = "B09"   # 折线图显式指定给对比排名
        layout = self.agent.build_dashboard_layout(a, INSIGHTS, {}, ["B07", "B09"])
        b09 = [s for s in layout["sections"] if s.get("_block") == "B09"][0]
        self.assertEqual(b09["items"][0]["chart_type"], "line")

    def test_fallback_without_blocks(self):
        """不传 blocks 时走旧的按主题分组路径。"""
        layout = self.agent.build_dashboard_layout(_analysis(), INSIGHTS, {})
        self.assertNotEqual(layout.get("_mode"), "blocks")
        self.assertTrue(len(layout["sections"]) > 0)

    def test_renders_to_html(self):
        """装配结果可直接渲染，各板块在 HTML 中真实出现。"""
        blocks = ["B01", "B02", "B04", "B07", "B15", "B16", "B22"]
        layout = self.agent.build_dashboard_layout(
            _analysis(), INSIGHTS, {"color_scheme": "A12"}, blocks)
        # 装配层：每个板块都有对应 section
        self.assertEqual(layout["_blocks"], blocks)
        html = RenderEngine(theme_name="A12").render_web_dashboard(layout)
        self.assertIn("<html", html.lower())
        # 渲染层：抽查各板块的实际落点（封面的标题是报表名，不是「封面页」）
        self.assertIn("2026 上半年销售分析", html)   # B01
        self.assertIn("执行摘要", html)              # B02
        self.assertIn("kpi-card", html)              # B04
        self.assertIn("趋势分析", html)              # B07
        self.assertIn("核心发现", html)              # B15
        self.assertIn("风险与机会", html)             # B16
        self.assertIn("结尾与下一步", html)           # B22
        self.assertIn("prose-cover", html)
        self.assertIn("@keyframes", html)
        self.assertNotIn("@@keyframes", html)

    def test_risk_opportunity_panels(self):
        """B16 必须产出双栏（风险 × 机会）。"""
        layout = self.agent.build_dashboard_layout(_analysis(), INSIGHTS, {}, ["B16"])
        sec = layout["sections"][0]
        self.assertEqual(len(sec["panels"]), 2)
        self.assertEqual(sec["panels"][0]["title"], "风险")
        self.assertEqual(sec["panels"][1]["title"], "机会")

    def test_no_risk_writes_explicit_note(self):
        """无风险输入时，按板块库要求明写「未识别到显著风险」。"""
        a = _analysis()
        a["narrative"].pop("risks")
        layout = self.agent.build_dashboard_layout(a, [], {}, ["B16"])
        self.assertIn("未识别到显著风险", layout["sections"][0]["panels"][0]["items"][0])


class TestChartCapacityAndLoss(unittest.TestCase):
    """
    图表容量与「不丢数据」。

    两条容易出错的边界：
      1. 排名板块（B09）能容纳多张图，容量不足会把图挤成孤儿
      2. 绑定给某板块但超出其容量的图，若只用「已消费」集合判断会被静默丢弃
    """

    def setUp(self):
        self.agent = AIAgent()

    @staticmethod
    def _many_bars(n):
        return [{"type": "bar", "title": f"维度{i}排名", "block": "B09",
                 "data": {"categories": ["A", "B"], "values": [i + 1, i + 2]}}
                for i in range(n)]

    def test_ranking_block_holds_multiple_charts(self):
        a = _analysis()
        a["charts"] = self._many_bars(4)
        layout = self.agent.build_dashboard_layout(a, INSIGHTS, {}, ["B09"])
        sec = [s for s in layout["sections"] if s.get("_block") == "B09"][0]
        self.assertEqual(len(sec["items"]), 4, "B09 应容纳 4 张排名图")
        self.assertEqual(layout["_gaps"], [])

    def test_over_capacity_charts_not_silently_dropped(self):
        """超出容量的图必须进「补充图表」并记缺口，不能凭空消失。"""
        a = _analysis()
        a["charts"] = self._many_bars(7)          # B09 容量 5
        layout = self.agent.build_dashboard_layout(a, INSIGHTS, {}, ["B09"])
        own = [s for s in layout["sections"] if s.get("_block") == "B09"][0]
        orphan = [s for s in layout["sections"] if s.get("_block") == "_orphan"]
        rendered = len(own["items"]) + (len(orphan[0]["items"]) if orphan else 0)
        self.assertEqual(rendered, 7, "7 张图要么渲染要么进补充区，一张都不能少")
        self.assertTrue(any(g["block"] == "_orphan" for g in layout["_gaps"]))
        self.assertTrue(any("超出板块 B09" in g["reason"] for g in layout["_gaps"]))

    def test_no_duplicate_chart_across_blocks(self):
        """同一张图不能被两个板块同时使用。"""
        a = _analysis()
        a["charts"] = [{"type": "line", "title": "趋势",
                        "data": {"categories": ["a", "b"], "values": [1, 2]}}]
        layout = self.agent.build_dashboard_layout(a, INSIGHTS, {}, ["B07", "B14"])
        total = sum(len([i for i in s.get("items", []) if i.get("type") == "chart"])
                    for s in layout["sections"])
        self.assertEqual(total, 1)


class TestUnservableBlocks(unittest.TestCase):
    """选型阶段必须预演图表绑定，把「没图可画」的板块提前裁掉。"""

    def test_block_dropped_when_no_matching_chart(self):
        agent = AIAgent()
        blocks = [AIAgent._annotate_block(block_library.get("B12"))]   # 需要 scatter
        kept, dropped = AIAgent._drop_unservable(
            blocks, [{"type": "bar", "title": "x", "block": "B09"}])
        self.assertEqual(kept, [])
        self.assertEqual(len(dropped), 1)
        self.assertIn("无可用图表", dropped[0]["reason"])

    def test_block_kept_when_chart_bound(self):
        blocks = [AIAgent._annotate_block(block_library.get("B09"))]
        kept, dropped = AIAgent._drop_unservable(
            blocks, [{"type": "bar", "title": "x", "block": "B09"}])
        self.assertEqual(len(kept), 1)
        self.assertEqual(dropped, [])

    def test_bound_chart_not_borrowed_by_other_block(self):
        """B09 的图不能借给 B11，即使类型匹配。"""
        blocks = [AIAgent._annotate_block(block_library.get("B11"))]
        kept, dropped = AIAgent._drop_unservable(
            blocks, [{"type": "bar", "title": "x", "block": "B09"}])
        self.assertEqual(kept, [])
        self.assertEqual(len(dropped), 1)

    def test_prose_blocks_need_no_chart(self):
        blocks = [AIAgent._annotate_block(block_library.get(b))
                  for b in ("B01", "B02", "B15", "B18", "B22")]
        kept, dropped = AIAgent._drop_unservable(blocks, [])
        self.assertEqual(len(kept), 5)
        self.assertEqual(dropped, [])

    def test_unbound_chart_can_serve_block(self):
        """没写 block 的图（Agent 手写 charts）仍可按类型匹配。"""
        blocks = [AIAgent._annotate_block(block_library.get("B09"))]
        kept, dropped = AIAgent._drop_unservable(
            blocks, [{"type": "bar", "title": "未绑定"}])
        self.assertEqual(len(kept), 1)
        self.assertEqual(dropped, [])

    def test_capacity_per_block(self):
        self.assertEqual(block_library.capacity("B09"), 5)
        self.assertEqual(block_library.capacity("B07"), 2)
        self.assertEqual(block_library.capacity("B99"), 2)


class TestGapSeverity(unittest.TestCase):
    """
    缺口必须分级。

    不分级时，「无图可画」和「文案待补」混在一个列表里，
    QA-5 无法判断哪些真阻塞渲染、哪些只是内容没写。
    「已按板块库要求明写未识别到风险」属于合规降级，更不该算缺陷。
    """

    def test_gaps_carry_severity(self):
        agent = AIAgent()
        layout = agent.build_dashboard_layout(_analysis(), [], {}, ["B01", "B15"])
        self.assertTrue(layout["_gaps"])
        for g in layout["_gaps"]:
            self.assertIn(g.get("severity"), ("blocking", "content", "info"),
                          f"缺口缺 severity：{g}")

    def test_blocking_for_missing_chart(self):
        """无图可画是链路断裂，必须 blocking。"""
        agent = AIAgent()
        a = _analysis()
        a["charts"] = []
        layout = agent.build_dashboard_layout(a, [], {}, ["B07"])
        b07 = [g for g in layout["_gaps"] if g["block"] == "B07"]
        self.assertEqual(b07[0]["severity"], "blocking")

    def test_info_for_compliant_fallback(self):
        """B16 无风险输入时明写「未识别到显著风险」是板块库要求，属 info。"""
        agent = AIAgent()
        a = _analysis()
        a["narrative"].pop("risks")
        a["narrative"].pop("opportunities")
        layout = agent.build_dashboard_layout(a, [], {}, ["B16"])
        g = [x for x in layout["_gaps"] if x["block"] == "B16"]
        self.assertTrue(g, f"应记录 B16 降级说明，实际 {layout['_gaps']}")
        self.assertEqual(g[0]["severity"], "info")

    def test_content_for_missing_narrative(self):
        """文案缺失是 content，不该阻塞渲染。"""
        agent = AIAgent()
        a = _analysis()
        a["narrative"].pop("closing")          # 制造文案缺失
        layout = agent.build_dashboard_layout(a, [], {}, ["B22"])
        g = [x for x in layout["_gaps"] if x["block"] == "B22"]
        self.assertTrue(g, f"应记录 B22 缺口，实际 {layout['_gaps']}")
        self.assertEqual(g[0]["severity"], "content")

    def test_no_blocking_when_content_complete(self):
        """文案齐备时不应出现 blocking 缺口。"""
        agent = AIAgent()
        layout = agent.build_dashboard_layout(_analysis(), INSIGHTS, {},
                                              ["B01", "B02", "B04", "B07",
                                               "B15", "B16", "B22"])
        blocking = [g for g in layout["_gaps"] if g.get("severity") == "blocking"]
        self.assertEqual(blocking, [], f"不该有 blocking 缺口：{blocking}")


if __name__ == "__main__":
    unittest.main()
