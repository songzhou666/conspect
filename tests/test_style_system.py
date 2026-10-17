# -*- coding: utf-8 -*-
"""
风格资产体系测试（v4.0）

校验目标：
  1. style-system.json 可解析，风格数与族数符合设计（38 / 6）
  2. 每个风格的 token 齐全、hex 合法、ink/bg 对比度达标
  3. 族与风格的双向引用一致
  4. 图表序列色长度 6 且首位等于风格强调色
  5. 三级资产（L0/L1/L2）均已生成，L2 含统一 9 节
  6. style_loader.theme() 输出的兼容字典字段完整
"""

import json
import re
import unittest
from pathlib import Path

from conspect_tools import style_loader

SKILL = Path(__file__).resolve().parent.parent
ASSETS = SKILL / "assets"

EXPECTED_STYLES = 38
EXPECTED_FAMILIES = 6
REQUIRED_TOKEN_KEYS = ("bg", "card", "ink", "mu", "ac", "line")
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
BODY_SECTIONS = (
    "## 设计流派",
    "## 配色 Token",
    "## 字体与排版",
    "## 形状与特效",
    "## 组件样式特征",
    "## 图表配色序列",
    "## 报表版式建议",
    "## 数据展示禁忌",
)


def contrast(fg, bg):
    def lum(h):
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
        f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
    l1, l2 = lum(fg), lum(bg)
    if l1 < l2:
        l1, l2 = l2, l1
    return (l1 + 0.05) / (l2 + 0.05)


class TestStyleSystemSource(unittest.TestCase):
    """唯一事实源的结构与取值合法性。"""

    def setUp(self):
        self.data = json.loads(style_loader.asset_path().read_text(encoding="utf-8"))

    def test_asset_file_exists_and_not_degraded(self):
        self.assertTrue(style_loader.asset_path().exists())
        self.assertFalse(style_loader.is_degraded(),
                         "资产文件不可用，引擎已降级到内置兜底")

    def test_style_and_family_counts(self):
        self.assertEqual(len(self.data["styles"]), EXPECTED_STYLES)
        self.assertEqual(len(self.data["families"]), EXPECTED_FAMILIES)
        self.assertEqual(self.data["total_styles"], EXPECTED_STYLES)
        self.assertEqual(self.data["family_count"], EXPECTED_FAMILIES)

    def test_style_codes_unique(self):
        codes = [s["code"] for s in self.data["styles"]]
        self.assertEqual(len(codes), len(set(codes)), "风格编号重复")

    def test_every_style_has_complete_tokens(self):
        for s in self.data["styles"]:
            for key in REQUIRED_TOKEN_KEYS:
                self.assertIn(key, s["tokens"], f"{s['code']} 缺 token {key}")
                self.assertRegex(s["tokens"][key], HEX_RE,
                                 f"{s['code']} 的 {key} 不是合法 hex")

    def test_every_style_meets_contrast(self):
        failures = []
        for s in self.data["styles"]:
            cr = contrast(s["tokens"]["ink"], s["tokens"]["bg"])
            if cr < 4.5:
                failures.append(f"{s['code']} {s['label']}: {cr:.2f}")
        self.assertEqual(failures, [], "以下风格 ink/bg 对比度不足 4.5:1：" + "; ".join(failures))

    def test_family_membership_is_bidirectional(self):
        for fam in self.data["families"]:
            members = fam["styles"]
            self.assertEqual(len(members), fam["count"],
                             f"{fam['id']} 的 count 与实际成员数不符")
            for code in members:
                s = style_loader.get_style(code)
                self.assertIsNotNone(s, f"{fam['id']} 声明的 {code} 不存在")
                self.assertEqual(s["family"], fam["id"],
                                 f"{code} 的 family 字段与族成员列表不一致")

    def test_every_style_belongs_to_a_family(self):
        fam_ids = {f["id"] for f in self.data["families"]}
        for s in self.data["styles"]:
            self.assertIn(s["family"], fam_ids, f"{s['code']} 的族不存在")

    def test_family_series_has_six_colors(self):
        for fam in self.data["families"]:
            self.assertEqual(len(fam["series"]), 6, f"{fam['id']} 序列色不是 6 个")
            for c in fam["series"]:
                self.assertRegex(c, HEX_RE, f"{fam['id']} 序列色非法：{c}")

    def test_series_first_slot_is_style_accent(self):
        for s in self.data["styles"]:
            series = style_loader.series_for(s["code"])
            self.assertEqual(len(series), 6)
            self.assertEqual(series[0].upper(), s["tokens"]["ac"].upper(),
                             f"{s['code']} 序列首位未由强调色覆盖")

    def test_every_style_has_report_use_and_taboos(self):
        for s in self.data["styles"]:
            use = s.get("report_use") or {}
            for key in ("types", "blocks", "density", "media"):
                self.assertIn(key, use, f"{s['code']} 缺 report_use.{key}")
            self.assertIn(use["density"], ("高", "中", "低"),
                          f"{s['code']} 密度取值非法")
            self.assertTrue(s.get("taboos"), f"{s['code']} 没有数据展示禁忌")

    def test_recommended_blocks_are_valid_ids(self):
        from conspect_tools import block_library
        valid = set(block_library.ids())
        for s in self.data["styles"]:
            blocks = s["report_use"]["blocks"]
            unknown = [b for b in blocks if b not in valid]
            self.assertEqual(unknown, [], f"{s['code']} 引用了不存在的板块 {unknown}")


class TestGeneratedAssets(unittest.TestCase):
    """生成物是否齐全且与源一致。"""

    def test_catalog_exists(self):
        p = ASSETS / "catalog" / "catalog_l0.md"
        self.assertTrue(p.exists())
        text = p.read_text(encoding="utf-8")
        self.assertIn("风格全景", text)
        self.assertIn("选型规则", text)

    def test_one_index_per_family(self):
        for fam in style_loader.families():
            p = ASSETS / "index" / f"{fam['id']}.md"
            self.assertTrue(p.exists(), f"缺族索引 {fam['id']}.md")
            text = p.read_text(encoding="utf-8")
            self.assertIn("选型判别", text)

    def test_one_body_per_style_with_all_sections(self):
        for s in style_loader.styles():
            p = SKILL / s["body"]
            self.assertTrue(p.exists(), f"缺正文 {s['body']}")
            text = p.read_text(encoding="utf-8")
            for sec in BODY_SECTIONS:
                self.assertIn(sec, text, f"{s['code']} 正文缺章节 {sec}")

    def test_body_tokens_match_source(self):
        """正文里的 token 必须与 JSON 完全一致——这是「不漂移」的硬证据。"""
        for s in style_loader.styles():
            text = (SKILL / s["body"]).read_text(encoding="utf-8")
            for key, label in (("bg", "背景"), ("card", "卡片"), ("ink", "文字"),
                               ("mu", "次要文字"), ("ac", "强调"), ("line", "分割线")):
                expect = f"| {label} `--{key}` | `{s['tokens'][key]}` |"
                self.assertIn(expect, text,
                              f"{s['code']} 正文的 {key} 与 JSON 不一致")

    def test_catalog_lists_every_style(self):
        text = (ASSETS / "catalog" / "catalog_l0.md").read_text(encoding="utf-8")
        for s in style_loader.styles():
            self.assertIn(s["code"], text, f"L0 目录缺 {s['code']}")


class TestStyleLoaderAPI(unittest.TestCase):
    """加载器对外接口。"""

    def test_theme_dict_has_legacy_fields(self):
        t = style_loader.theme("A1")
        for key in ("primary", "secondary", "bg", "card_bg", "text",
                    "text_secondary", "border", "gradient", "series",
                    "name", "label", "family", "density", "gap", "pad"):
            self.assertIn(key, t, f"theme() 缺字段 {key}")

    def test_invalid_code_falls_back_to_default(self):
        t = style_loader.theme("不存在的编号")
        self.assertEqual(t["name"], style_loader.default_code())

    def test_families_and_styles_are_lists(self):
        self.assertIsInstance(style_loader.families(), list)
        self.assertIsInstance(style_loader.styles(), list)
        self.assertIsInstance(style_loader.codes(), list)

    def test_block_library_meta(self):
        meta = style_loader.block_library()
        self.assertEqual(meta["count"], 22)
        self.assertEqual(len(meta["families"]), 6)


def _load_checker():
    """加载资产校验器（tools/ 不在包路径内，用 importlib 载入）。"""
    import importlib.util
    path = Path(__file__).resolve().parent.parent / "tools" / "check_style_assets.py"
    spec = importlib.util.spec_from_file_location("_csa", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestSeriesDistinguishability(unittest.TestCase):
    """
    族序列色的可区分判据。

    判据不是简单比色相——同色系深浅是合法设计手法，机械比色相会误伤；
    而一灰一彩靠饱和度天然区分。这组测试把判据的边界钉死。
    """

    @classmethod
    def setUpClass(cls):
        cls.c = _load_checker()
        cls.data = json.loads(
            (Path(__file__).resolve().parent.parent
             / "assets" / "style-system.json").read_text(encoding="utf-8"))

    def test_all_families_distinguishable(self):
        """6 个族的序列色两两都必须可区分。"""
        for fam in self.data["families"]:
            s = fam["series"]
            for i in range(len(s)):
                for j in range(i + 1, len(s)):
                    good, dh, dl = self.c.series_clash(s[i], s[j])
                    self.assertTrue(
                        good, f"族 {fam['id']} 的 {s[i]}×{s[j]} 不可区分"
                              f"（色相差 {dh:.1f}°，明度差 {dl:.1f}）")

    def test_same_hue_differs_by_lightness_is_allowed(self):
        """同色相但明度差足够大 → 可区分（biz 族的深蓝/亮蓝）。"""
        good, dh, dl = self.c.series_clash("#2B4C8C", "#4A7CF7")
        self.assertTrue(good)
        self.assertLess(dh, 10)      # 色相确实很接近
        self.assertGreater(dl, 20)   # 靠明度拉开

    def test_hue_apart_is_allowed(self):
        good, _, _ = self.c.series_clash("#FF2D55", "#2C6BFF")
        self.assertTrue(good)

    def test_two_grays_need_lightness_gap(self):
        """双灰阶只能靠明度区分。"""
        self.assertFalse(self.c.series_clash("#808080", "#8A8A8A")[0])
        self.assertTrue(self.c.series_clash("#3A3A3A", "#C8C8C8")[0])

    def test_gray_vs_color_is_allowed(self):
        """一灰一彩：饱和度已提供区分度。"""
        self.assertTrue(self.c.series_clash("#7F8C8D", "#4A6B5A")[0])

    def test_regression_former_defects(self):
        """三个曾真实存在的不可区分组合，必须被判为不可分（防回退）。"""
        for a, b, why in [
            ("#C9A227", "#B76E2E", "editorial 金 vs 棕"),
            ("#E9C46A", "#D4A373", "organic 黄 vs 土黄"),
            ("#A0A8FF", "#8A6DF2", "glass 浅紫 vs 紫"),
        ]:
            self.assertFalse(self.c.series_clash(a, b)[0], f"{why} 应判为不可区分")


if __name__ == "__main__":
    unittest.main()
