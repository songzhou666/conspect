# -*- coding: utf-8 -*-
"""
呈现层测试：客户看到的到底是「A1」还是「瑞士极简」。

背景：选型卡原先只给资产编号 + 十六进制色值，客户无法判断风格是什么样。
这类缺陷不会让任何计算出错，测试也很容易漏掉——所以单独成文件，
把「不许出现裸编号 / 裸色值 / 空差异」写成断言。
"""
import os
import re
import tempfile
import unittest

from conspect_tools import block_library, style_loader
from conspect_tools import style_preview as sp


def _all_styles():
    return style_loader.styles()


class TestColorWords(unittest.TestCase):
    """色值 → 中文，全部由色值计算得出，不许查表。"""

    def test_known_hex_maps_to_chinese_hue(self):
        self.assertEqual(sp._hue_name(*sp._hsl("#E30513")[:1]), "红")

    def test_gray_is_not_given_a_hue(self):
        """#8D8D8D 这类无彩色若被叫成「红」就是错的。"""
        _, s, _ = sp._hsl("#8D8D8D")
        self.assertLess(s, 0.12)

    def test_bg_words_cover_light_and_dark(self):
        self.assertEqual(sp._bg_word(1.0), "纯白底")
        self.assertEqual(sp._bg_word(0.03), "近黑底")

    def test_series_mode_single_hue(self):
        """同一色相的深浅渐变是合法手法，应识别为「同色系深浅」而非「多彩」。"""
        self.assertEqual(sp._series_mode(["#1F4E8C", "#2E6FB8", "#4A8FD4"]), "同色系深浅")

    def test_series_mode_multi_hue(self):
        self.assertEqual(
            sp._series_mode(["#05D9E8", "#FF2D95", "#7C5CFF", "#46E6A0"]), "多彩并列")

    def test_series_mode_all_gray(self):
        self.assertEqual(sp._series_mode(["#333333", "#777777", "#BBBBBB"]), "灰阶系列")


class TestDescribeStyle(unittest.TestCase):
    """describe 必须给出可直接判断的信息。"""

    def test_never_contains_raw_hex_in_palette(self):
        for s in _all_styles():
            d = sp.describe_style(s, s.get("series"))
            self.assertNotIn("#", d["palette"],
                             f"{s['code']} 的色系描述混入了十六进制色值：{d['palette']}")

    def test_has_chinese_hue_or_neutral_word(self):
        words = ("红", "橙", "黄", "绿", "青", "蓝", "紫", "洋红", "黑", "灰")
        for s in _all_styles():
            d = sp.describe_style(s, s.get("series"))
            self.assertTrue(any(w in d["accent_name"] for w in words),
                            f"{s['code']} 强调色无法描述：{d['accent_name']}")

    def test_scenes_and_mood_present(self):
        for s in _all_styles():
            d = sp.describe_style(s, s.get("series"))
            self.assertTrue(d["mood"], f"{s['code']} 缺气质描述")
            self.assertTrue(d["scenes"], f"{s['code']} 缺适用场景")

    def test_swatches_cover_all_roles(self):
        s = _all_styles()[0]
        d = sp.describe_style(s, s.get("series"))
        roles = [x["role"] for x in d["swatches"]]
        for need in ("底色", "文字", "强调", "卡片", "分隔"):
            self.assertIn(need, roles)

    def test_card_text_leads_with_chinese_name(self):
        """中文名必须打头，编号退到后面——客户不必先记住 A1 是什么。"""
        s = _all_styles()[0]
        d = sp.describe_style(s, s.get("series"))
        first = sp.card_text(s, d).splitlines()[0]
        self.assertTrue(first.startswith(s["label"]),
                        f"首行应以中文名开头，实为：{first}")


class TestDiffNote(unittest.TestCase):
    """
    同族候选的 report_use 是族级属性，场景/密度天然一致。
    若差异说明为空，客户面对几段雷同描述仍然选不出来。
    """

    def test_never_returns_empty(self):
        styles = _all_styles()
        d0 = sp.describe_style(styles[0], styles[0].get("series"))
        for other in styles[1:20]:
            note = sp.diff_note(styles[0], other, d0,
                                sp.describe_style(other, other.get("series")))
            self.assertTrue(note, f"{styles[0]['code']} vs {other['code']} 差异说明为空")

    def test_reports_accent_change(self):
        a = {"code": "X1", "label": "甲", "mood": "甲的气质",
             "tokens": {"bg": "#FFFFFF", "ac": "#E30513", "ink": "#111111"},
             "report_use": {"density": "高"}, "series": ["#E30513"]}
        b = {"code": "X2", "label": "乙", "mood": "乙的气质",
             "tokens": {"bg": "#FFFFFF", "ac": "#005ECC", "ink": "#111111"},
             "report_use": {"density": "高"}, "series": ["#005ECC"]}
        note = sp.diff_note(a, b)
        self.assertIn("强调色", note)
        self.assertIn("红", note)
        self.assertIn("天蓝", note)


class TestDegenerateGradient(unittest.TestCase):
    """
    资产里出现过 `linear-gradient(#2C3E50,#2C3E50)`（首尾同色，视觉上是实色），
    而该风格 bg 是 #FFFFFF。若当成真渐变渲染，浅色风格会变深底。
    加载层必须归一为 None。
    """

    def test_detects_degenerate(self):
        self.assertTrue(sp_loader_degenerate("linear-gradient(#2C3E50,#2C3E50)"))
        self.assertTrue(sp_loader_degenerate("linear-gradient(#333, #333)"))

    def test_real_gradient_kept(self):
        self.assertFalse(sp_loader_degenerate("linear-gradient(90deg,#0072FF,#00C6FF)"))

    def test_asset_is_normalized(self):
        for s in _all_styles():
            g = (s.get("tokens") or {}).get("bg_gradient")
            if g:
                stops = re.findall(r"#[0-9a-fA-F]{3,8}\b", g)
                self.assertGreater(len({x.lower() for x in stops}), 1,
                                   f"{s['code']} 仍带退化渐变：{g}")


def sp_loader_degenerate(g):
    return style_loader._degenerate_gradient(g)


class TestBlockPurpose(unittest.TestCase):
    """板块的 purpose 是客户判断「要不要这一块」的唯一依据。"""

    def test_every_block_has_purpose(self):
        missing = [b["id"] for b in block_library.all_blocks() if not b.get("purpose")]
        self.assertEqual(missing, [], f"这些板块缺白话用途：{missing}")

    def test_purpose_is_plain_language(self):
        """用途不能只是把名称重复一遍，也不能出现内部编号。"""
        for b in block_library.all_blocks():
            self.assertGreaterEqual(len(b["purpose"]), 8,
                                    f"{b['id']} 用途过短：{b['purpose']}")
            self.assertNotIn(b["id"], b["purpose"],
                             f"{b['id']} 用途里出现内部编号")

    def test_purpose_lookup_by_id(self):
        self.assertIn("构成", block_library.purpose("B08"))
        self.assertTrue(block_library.purpose("B99"), "未知板块也应返回可读文本")


class TestBackgroundPaint(unittest.TestCase):
    """
    `bg_gradient` 字段里混着两种东西：真背景渐变，以及从组件样式里采到的
    `conic-gradient`（环形进度条/仪表）。后者铺满页面会变成一个占满屏幕的饼图。
    必须按语法判类型，不能按字段名信。
    """

    def test_conic_is_not_used_as_background(self):
        toks = {"bg": "#000000",
                "bg_gradient": "conic-gradient(#0A84FF 0 67%, #1A1A1A 67% 100%)"}
        self.assertEqual(sp._bg_paint(toks), "#000000")
        self.assertFalse(sp._has_bg_gradient(toks))

    def test_linear_is_used_as_background(self):
        toks = {"bg": "#FFFFFF",
                "bg_gradient": "linear-gradient(135deg,#FF2D95,#7C4DFF)"}
        self.assertEqual(sp._bg_paint(toks), toks["bg_gradient"])
        self.assertTrue(sp._has_bg_gradient(toks))

    def test_no_gradient_falls_back_to_bg(self):
        self.assertEqual(sp._bg_paint({"bg": "#FAFAFA", "bg_gradient": None}), "#FAFAFA")

    def test_asset_conic_never_reaches_preview(self):
        """资产里 4 个风格带 conic，预览页不该出现 conic。"""
        conic = [s["code"] for s in _all_styles()
                 if "conic" in ((s.get("tokens") or {}).get("bg_gradient") or "")]
        self.assertTrue(conic, "资产里应至少有一个 conic 渐变（用于验证此规则）")
        from conspect_tools.ai_agent import AIAgent
        r = AIAgent().select_style_card({"tone": "深色", "report_type": "实时监控大屏"})
        html = sp.build_preview_html(r["candidates"], {"tone": "深色"})
        self.assertNotIn("conic", html)


class TestShapeInfo(unittest.TestCase):
    """形状与字体是同色系风格之间的真实差异，必须参与描述与差异判定。"""

    def test_radius_and_weight_parsed(self):
        s = {"shapes": {"圆角": "24, 28, 40px"},
             "typography": {"size_range": "12–64px（标题 64px 级）",
                            "weights": ["500", "700", "800"]}}
        self.assertEqual(sp._radius(s), 20)          # 上限截断，避免所有卡片变胶囊
        self.assertEqual(sp._title_px(s), 64)
        self.assertEqual(sp._title_weight(s), 800)

    def test_missing_shapes_defaults_to_square(self):
        self.assertEqual(sp._radius({}), 0)
        self.assertEqual(sp._title_weight({}), 700)

    def test_form_text_is_readable(self):
        f = sp.describe_form({"shapes": {"圆角": "2px"},
                              "typography": {"size_range": "10–56px（标题 56px 级）",
                                             "weights": ["400", "700"]}})
        self.assertIn("直角", f)
        self.assertIn("56px", f)


class TestStyleCardWiring(unittest.TestCase):
    """select_style 的返回必须带 describe 与 diff，否则 Agent 只能靠编号。"""

    def setUp(self):
        from conspect_tools.ai_agent import AIAgent
        self.agent = AIAgent()

    def test_cards_carry_describe(self):
        r = self.agent.select_style_card({"tone": "浅色", "report_type": "经营分析"})
        self.assertEqual(r["status"], "ok")
        self.assertIn("describe", r["recommend"])
        self.assertIn("palette", r["recommend"]["describe"])
        for a in r["alternatives"]:
            self.assertIn("describe", a)

    def test_alternatives_carry_diff(self):
        r = self.agent.select_style_card({"tone": "深色", "report_type": "实时监控大屏"})
        for a in r["alternatives"]:
            self.assertTrue(a.get("diff_from_recommend"),
                            f"{a['code']} 缺与推荐款的差异说明")


class TestPreviewHtml(unittest.TestCase):
    """对比页是可交付物，必须自包含、列数与候选数一致。"""

    def _make(self, profile, n=3):
        from conspect_tools.ai_agent import AIAgent
        r = AIAgent().select_style_card(profile)
        cands = [r["recommend"]] + r["alternatives"][:n - 1]
        return sp.build_preview_html(cands, profile), cands

    def test_columns_match_candidates(self):
        html, cands = self._make({"tone": "浅色", "report_type": "经营分析"})
        self.assertEqual(len(re.findall(r'<section class="col', html)), len(cands))

    def test_self_contained(self):
        """断网/邮件打开必须还能看，不许引外部脚本或样式。"""
        html, _ = self._make({"tone": "深色", "report_type": "实时监控大屏"})
        self.assertIsNone(re.search(r"<script[^>]+src=", html))
        self.assertIsNone(re.search(r"<link[^>]+href=", html))
        self.assertNotIn("cdn.", html.lower())

    def test_tags_balanced(self):
        html, _ = self._make({"tone": "浅色", "report_type": "经营分析"})
        self.assertEqual(html.count("<div"), html.count("</div>"))
        self.assertEqual(html.count("<section"), html.count("</section>"))

    def test_each_column_uses_its_own_tokens(self):
        """
        每列的舞台底色必须等于该候选自己的 bg（含退化渐变归一后的结果）。
        注意：不能断言「各列底色互不相同」——同族风格底色相同是真实情况
        （浅色商务族多为白底），差异在强调色与形状上。
        """
        html, cands = self._make({"tone": "浅色", "report_type": "经营分析"})
        bgs = re.findall(r'class="stage" style="background:([^;"]+)', html)
        self.assertEqual(len(bgs), len(cands))
        for got, c in zip(bgs, cands):
            want = (c.get("tokens") or {}).get("bg_gradient") or \
                   (c.get("tokens") or {}).get("bg", "")
            self.assertEqual(got.strip(), want.strip(),
                             f"{c['code']} 的预览底色与自身 token 不符")

    def test_shape_and_weight_are_reflected(self):
        """
        同色系风格靠圆角/字重区分。预览若只换颜色，四列会长得一样，
        客户仍然选不出来。
        """
        html, cands = self._make({"tone": "浅色", "report_type": "经营分析"}, n=4)
        radii = re.findall(r'class="stage" style="[^"]*border-radius:(\d+)px', html)
        self.assertEqual(len(radii), len(cands))
        self.assertGreater(len(set(radii)), 1, "所有候选圆角相同，形状差异未体现")

        weights = re.findall(r'class="t" style="font-weight:(\d+)', html)
        self.assertEqual(len(weights), len(cands))
        for w in weights:
            self.assertIn(w, {"400", "500", "600", "700", "800", "900"})


class TestRenderStylePreviewAction(unittest.TestCase):
    """CLI 动作：写文件 + 参数校验。"""

    def test_writes_file(self):
        from conspect_tools.run import run
        s = run("select_style", {"profile": {"tone": "浅色", "report_type": "经营分析"}})
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            out = os.path.join(d, "p.html")
            r = run("render_style_preview",
                    {"candidates": s["candidates"], "output_path": out})
            self.assertEqual(r["status"], "ok")
            self.assertTrue(os.path.exists(out))
            self.assertGreater(r["size"], 2000)

    def test_missing_candidates_is_an_error(self):
        from conspect_tools.run import run
        r = run("render_style_preview", {})
        self.assertEqual(r["status"], "error")
        self.assertIn("candidates", r["message"])


if __name__ == "__main__":
    unittest.main()
