# -*- coding: utf-8 -*-
"""
渲染引擎测试（v4.0）

校验目标：
  1. 38 个风格全部可实例化并渲染出 HTML
  2. 风格 token 真实写入了 CSS（不再有硬编码主题）
  3. prose 板块（封面 / 摘要 / 列表 / 多栏 / 无内容兜底）渲染正确
  4. 入场动画的 keyframes 语法正确（回归 @@keyframes 拼写错误）
  5. section_group 内可嵌 prose
"""

import re
import unittest

from conspect_tools import style_loader
from conspect_tools.render_engine import ColorTheme, RenderEngine


def _layout(style_code, sections=None):
    return {
        "title": "测试报表",
        "generated_at": "2026-10-17",
        "color_scheme": style_code,
        "sections": sections if sections is not None else [
            {"type": "prose", "title": "报表标题", "variant": "cover", "body": "一句话结论"},
            {"type": "kpi_cards", "metrics": [{"label": "营收", "value": 100, "change": 5}]},
        ],
    }


class TestColorTheme(unittest.TestCase):

    def test_lists_all_styles_and_families(self):
        self.assertEqual(len(ColorTheme.list_themes()), 38)
        self.assertEqual(len(ColorTheme.list_families()), 6)

    def test_default_theme_is_valid(self):
        t = ColorTheme.get("")
        self.assertTrue(t["name"])
        self.assertIn("series", t)

    def test_unknown_style_falls_back(self):
        t = ColorTheme.get("NOPE")
        self.assertEqual(t["name"], style_loader.default_code())

    def test_describe_returns_asset_fields(self):
        d = ColorTheme.describe("A23")
        self.assertEqual(d["label"], "赛博朋克")
        for key in ("tokens", "report_use", "taboos", "mood"):
            self.assertIn(key, d)

    def test_describe_unknown_returns_empty(self):
        self.assertEqual(ColorTheme.describe("NOPE"), {})

    def test_series_colors_respect_count(self):
        t = ColorTheme.get("A1")
        self.assertEqual(len(ColorTheme.build_series_colors(t, 3)), 3)
        self.assertEqual(len(ColorTheme.build_series_colors(t, 6)), 6)
        # 超出序列长度应循环而不抛错
        self.assertEqual(len(ColorTheme.build_series_colors(t, 9)), 9)


class TestRenderAllStyles(unittest.TestCase):

    def test_every_style_renders(self):
        failures = []
        for code in ColorTheme.list_themes():
            try:
                html = RenderEngine(theme_name=code).render_web_dashboard(_layout(code))
                if not html or "</html>" not in html:
                    failures.append(f"{code}: 输出不完整")
            except Exception as e:
                failures.append(f"{code}: {type(e).__name__} {e}")
        self.assertEqual(failures, [], "以下风格渲染失败：" + "; ".join(failures))

    def test_style_tokens_applied_to_css(self):
        for code in ("A1", "A23", "A37"):
            s = style_loader.get_style(code)
            html = RenderEngine(theme_name=code).render_web_dashboard(_layout(code))
            self.assertIn(s["tokens"]["bg"], html, f"{code} 的背景色未写入 HTML")
            self.assertIn(s["tokens"]["ac"], html, f"{code} 的强调色未写入 HTML")

    def test_theme_name_resolved_when_empty(self):
        engine = RenderEngine(theme_name="")
        self.assertEqual(engine.theme_name, style_loader.default_code())

    def test_set_theme_switches(self):
        engine = RenderEngine(theme_name="A1")
        engine.set_theme("A7")
        self.assertEqual(engine.theme_name, "A7")


class TestProseBlock(unittest.TestCase):

    def setUp(self):
        self.engine = RenderEngine(theme_name="A12")

    def test_title_and_body(self):
        html = self.engine.render_web_dashboard(_layout("A12", [
            {"type": "prose", "title": "执行摘要", "body": "第一段\n第二段"},
        ]))
        self.assertIn('class="prose-block', html)
        self.assertIn("执行摘要", html)
        self.assertIn("<p>第一段</p>", html)
        self.assertIn("<p>第二段</p>", html)

    def test_items_render_as_ordered_list(self):
        html = self.engine.render_web_dashboard(_layout("A12", [
            {"type": "prose", "title": "核心发现", "items": ["结论一", "结论二"]},
        ]))
        self.assertIn("<ol>", html)
        self.assertIn("<li>结论一</li>", html)

    def test_items_support_badges(self):
        html = self.engine.render_web_dashboard(_layout("A12", [
            {"type": "prose", "title": "行动建议",
             "items": [{"text": "扩产", "badge": "高"}]},
        ]))
        self.assertIn('class="prose-badge">高<', html)
        self.assertIn("扩产", html)

    def test_panels_render_multi_column(self):
        html = self.engine.render_web_dashboard(_layout("A12", [
            {"type": "prose", "title": "风险与机会", "columns": 2,
             "panels": [{"title": "风险", "items": ["风险A"]},
                        {"title": "机会", "items": ["机会B"]}]},
        ]))
        self.assertIn("prose-cols", html)
        self.assertIn("--prose-cols:2", html)
        self.assertIn("风险A", html)
        self.assertIn("机会B", html)

    def test_cover_variant_centered(self):
        html = self.engine.render_web_dashboard(_layout("A12", [
            {"type": "prose", "title": "标题", "variant": "cover"},
        ]))
        self.assertIn("prose-cover", html)

    def test_empty_prose_has_fallback_text(self):
        html = self.engine.render_web_dashboard(_layout("A12", [
            {"type": "prose", "title": "空板块"},
        ]))
        self.assertIn("本节暂无内容", html)

    def test_eyebrow_renders(self):
        html = self.engine.render_web_dashboard(_layout("A12", [
            {"type": "prose", "title": "摘要", "eyebrow": "01 / 摘要"},
        ]))
        self.assertIn("prose-eyebrow", html)
        self.assertIn("01 / 摘要", html)

    def test_prose_inside_section_group(self):
        html = self.engine.render_web_dashboard(_layout("A12", [
            {"type": "section_group", "title": "分析", "columns": 2, "items": [
                {"type": "prose", "title": "口径", "body": "指标口径说明"},
            ]},
        ]))
        self.assertIn("指标口径说明", html)
        self.assertIn("section-grid", html)


class TestHtmlSanity(unittest.TestCase):

    def setUp(self):
        self.html = RenderEngine(theme_name="A12").render_web_dashboard(
            _layout("A12", [
                {"type": "prose", "title": "封面", "variant": "cover", "body": "x"},
                {"type": "kpi_cards", "metrics": [{"label": "A", "value": 1}]},
            ])
        )

    def test_has_no_double_at_keyframes(self):
        """回归：历史上模板误写为 @@keyframes，导致全部入场动画失效。"""
        self.assertNotIn("@@keyframes", self.html)

    def test_has_valid_keyframes(self):
        self.assertIn("@keyframes fadeIn", self.html)

    def test_has_density_padding_variable(self):
        self.assertIn("--pad:", self.html)

    def test_has_no_emoji(self):
        import re
        emoji = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\u2705\u274C\u26A0]")
        hits = emoji.findall(self.html)
        self.assertEqual(hits, [], f"产物中出现 emoji：{set(hits)}")


class TestOfflineAssets(unittest.TestCase):
    """
    ECharts 必须内联，保证报表离线可打开。

    投屏演示、邮件附件、内网打开的常见场景都拿不到 CDN，
    只引用 CDN 的报表在那些环境下就是白板。
    """

    def test_local_echarts_exists(self):
        from conspect_tools.render_engine import ECHARTS_LOCAL
        self.assertTrue(ECHARTS_LOCAL.exists(),
                        f"缺少本地 ECharts：{ECHARTS_LOCAL}")

    def test_html_inlines_echarts(self):
        from conspect_tools.render_engine import ECHARTS_CDN
        html = RenderEngine(theme_name="A12").render_web_dashboard(
            {"title": "离线", "sections": []})
        self.assertNotIn(ECHARTS_CDN, html, "默认应内联，不应引用 CDN")
        self.assertIn("echarts", html.lower())

    def test_can_opt_out_to_cdn(self):
        from conspect_tools.render_engine import ECHARTS_CDN
        html = RenderEngine(theme_name="A12", inline_assets=False).render_web_dashboard(
            {"title": "CDN", "sections": []})
        self.assertIn(ECHARTS_CDN, html)

    def test_chart_text_contrast_meets_wcag(self):
        """图表内文字（轴刻度/图例）对比度须 ≥4.5:1，否则投影看不清。"""
        from conspect_tools.render_engine import _contrast
        for code in style_loader.codes():
            t = ColorTheme.get(code)
            ratio = _contrast(t["text_chart"], t["bg"])
            self.assertGreaterEqual(
                round(ratio, 1), 4.5,
                f"{code} 图表文字对比度 {ratio:.2f} 不足")


class TestElementIdUniqueness(unittest.TestCase):
    """
    元素 id 必须唯一。

    原实现用「数据 hash」当 id：两张数据完全相同的图会生成同一个 id，
    后一个 echarts.init 会拿到前一个的 DOM，导致第二张图不渲染或错乱。
    """

    def _layout(self, n):
        sections = []
        for i in range(n):
            sections.append({
                "type": "chart", "chart_type": "bar", "title": f"图{i}",
                # 数据完全相同——正是会撞 id 的场景
                "data": {"categories": ["A", "B"], "values": [1, 2]},
            })
        return {"title": "id 唯一性", "sections": sections}

    def test_identical_charts_get_distinct_ids(self):
        html = RenderEngine(theme_name="A12").render_web_dashboard(self._layout(3))
        ids = re.findall(r'id="(chart_\d+_\d+)"', html)
        self.assertEqual(len(ids), 3, "应渲染出 3 个图表容器")
        self.assertEqual(len(set(ids)), 3, f"图表 id 重复：{ids}")

    def test_identical_tables_get_distinct_ids(self):
        layout = {"title": "t", "sections": [
            {"type": "table", "title": "同名表", "columns": ["A"], "rows": [["1"]]},
            {"type": "table", "title": "同名表", "columns": ["A"], "rows": [["2"]]},
        ]}
        html = RenderEngine(theme_name="A12").render_web_dashboard(layout)
        ids = re.findall(r'id="(table_\d+_\d+)"', html)
        self.assertEqual(len(set(ids)), len(ids), f"表格 id 重复：{ids}")


if __name__ == "__main__":
    unittest.main()
