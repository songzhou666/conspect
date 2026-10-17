#!/usr/bin/env python3
"""
conspect 一致性自检脚本

把「文档里写着但没人检查」的规则变成可机械执行的检查。检查项：

  1. 引用完整性 —— 所有 Markdown 相对链接都不得逃逸技能目录、不得悬空、必须指向文件
  2. emoji 禁令 —— 技能文档与产物模板中不得出现 emoji（对应 SKILL.md 的产物规范）
  3. 产物清单一致性 —— SKILL.md 提到的 `_cs-*.md/json/html` 必须在 artifact-manifest.yaml 中有定义
  4. 版本号一致性 —— frontmatter / manifest / README 徽章 三处版本号必须一致

用法：
    python tools/check_refs.py            # 从技能根目录运行
    python tools/check_refs.py --quiet    # 只输出失败项

退出码：0 = 全部通过；1 = 存在失败项
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent

# Markdown 相对链接：[文本](目标)
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
# 反引号里的产物名：`_cs-xxx.yyy`
ARTIFACT_RE = re.compile(r"`(_cs-[A-Za-z0-9_.\-]+)`")
# emoji 与常见符号（含各类图形符号、勾叉、警告）
EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F000-\U0001F2FF"
    "\u2705\u274C\u26A0\u2714\u2716\u2B50\u2757\u2753]"
)
VERSION_RE_FRONTMATTER = re.compile(r"^version:\s*([0-9]+(?:\.[0-9]+)*)\s*$", re.M)
VERSION_RE_MANIFEST = re.compile(r"^version:\s*([0-9]+(?:\.[0-9]+)*)\s*$", re.M)
VERSION_RE_BADGE = re.compile(r"badge/version-([0-9]+(?:\.[0-9]+)*)-")


class Report:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.checks = 0

    def ok(self) -> None:
        self.checks += 1

    def fail(self, message: str) -> None:
        self.checks += 1
        self.failures.append(message)


def iter_markdown() -> list[Path]:
    """技能目录下所有 Markdown，跳过归档/缓存目录。"""
    skip = {".git", "__pycache__", "node_modules"}
    return sorted(
        p
        for p in SKILL_ROOT.rglob("*.md")
        if not any(part in skip for part in p.parts)
    )


def check_links(report: Report) -> None:
    """检查相对链接：不逃逸、不悬空、指向文件。"""
    for md in iter_markdown():
        rel = md.relative_to(SKILL_ROOT)
        text = md.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for raw_target in LINK_RE.findall(line):
                target = raw_target.strip()
                # 跳过外链、锚点、邮件
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                # 去掉锚点与查询串
                target = target.split("#", 1)[0].split("?", 1)[0]
                if not target:
                    continue

                resolved = (md.parent / target).resolve()
                try:
                    resolved.relative_to(SKILL_ROOT)
                except ValueError:
                    report.fail(
                        f"[引用逃逸] {rel}:{lineno} -> {target}"
                        f"（指向技能目录之外）"
                    )
                    continue

                if not resolved.exists():
                    report.fail(f"[引用悬空] {rel}:{lineno} -> {target}（目标不存在）")
                elif resolved.is_dir():
                    report.fail(f"[引用指向目录] {rel}:{lineno} -> {target}")
                else:
                    report.ok()


def check_emoji(report: Report) -> None:
    """技能文档与模板中不得出现 emoji。"""
    for md in iter_markdown():
        rel = md.relative_to(SKILL_ROOT)
        text = md.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            found = EMOJI_RE.findall(line)
            if found:
                report.fail(
                    f"[emoji 违规] {rel}:{lineno} 含 {len(found)} 个："
                    f"{''.join(found)}"
                )
            else:
                report.ok()


def load_manifest_names() -> set[str]:
    """从 artifact-manifest.yaml 提取所有产物名（不依赖 pyyaml）。"""
    manifest = SKILL_ROOT / "artifacts" / "artifact-manifest.yaml"
    if not manifest.is_file():
        return set()
    text = manifest.read_text(encoding="utf-8")
    return set(re.findall(r"^\s*-\s*name:\s*(_cs-[A-Za-z0-9_.\-]+)\s*$", text, re.M))


def check_artifact_consistency(report: Report) -> None:
    """SKILL.md 提到的产物必须在 manifest 中有定义。"""
    defined = load_manifest_names()
    if not defined:
        report.fail("[产物清单] 无法从 artifacts/artifact-manifest.yaml 解析出任何产物名")
        return

    skill_md = SKILL_ROOT / "SKILL.md"
    if not skill_md.is_file():
        report.fail("[产物清单] SKILL.md 不存在")
        return

    text = skill_md.read_text(encoding="utf-8")
    mentioned = set(ARTIFACT_RE.findall(text))

    for name in sorted(mentioned - defined):
        report.fail(f"[产物未登记] SKILL.md 提到 `{name}`，但 manifest 中无定义")
    for _ in mentioned & defined:
        report.ok()


def check_version_consistency(report: Report) -> None:
    """frontmatter / manifest / README 徽章 版本号一致。"""
    versions: dict[str, str] = {}

    skill_md = SKILL_ROOT / "SKILL.md"
    if skill_md.is_file():
        head = skill_md.read_text(encoding="utf-8")[:600]
        m = VERSION_RE_FRONTMATTER.search(head)
        if m:
            versions["SKILL.md frontmatter"] = m.group(1)

    manifest = SKILL_ROOT / "1-manifest" / "skill-manifest.yaml"
    if manifest.is_file():
        m = VERSION_RE_MANIFEST.search(manifest.read_text(encoding="utf-8"))
        if m:
            versions["1-manifest/skill-manifest.yaml"] = m.group(1)

    readme = SKILL_ROOT / "README.md"
    if readme.is_file():
        m = VERSION_RE_BADGE.search(readme.read_text(encoding="utf-8"))
        if m:
            versions["README.md 徽章"] = m.group(1)

    if len(set(versions.values())) > 1:
        detail = " / ".join(f"{k}={v}" for k, v in versions.items())
        report.fail(f"[版本号不一致] {detail}")
    else:
        report.ok()


def _load_style_codes() -> set[str]:
    """从 assets/style-system.json 取全部风格编号。"""
    src = SKILL_ROOT / "assets" / "style-system.json"
    if not src.is_file():
        return set()
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except Exception:
        return set()
    return {s["code"] for s in data.get("styles", [])}


def _load_block_ids() -> set[str]:
    """从 assets/common/block_library.md 的总览表取全部板块编号。"""
    md = SKILL_ROOT / "assets" / "common" / "block_library.md"
    if not md.is_file():
        return set()
    return set(re.findall(r"^\|\s*(B\d{2})\s*\|", md.read_text(encoding="utf-8"), re.M))


def check_asset_refs(report: Report) -> None:
    """`[资产引用] 编号→风格名` 里的编号必须真实存在；文档提到的板块编号必须真实存在。"""
    codes = _load_style_codes()
    blocks = _load_block_ids()
    if not codes:
        report.fail("[资产] 无法从 assets/style-system.json 解析出风格编号")
        return
    if not blocks:
        report.fail("[板块] 无法从 assets/common/block_library.md 解析出板块编号")
        return

    for md in iter_markdown():
        rel = md.relative_to(SKILL_ROOT)
        text = md.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for code in re.findall(r"\[资产引用\]\s*(A\d+)\s*→", line):
                if code in codes:
                    report.ok()
                else:
                    report.fail(f"[资产引用无效] {rel}:{lineno} -> {code} 不在资产库中")
            for bid in re.findall(r"\b(B\d{2})\b", line):
                if bid in blocks:
                    report.ok()
                else:
                    report.fail(f"[板块引用无效] {rel}:{lineno} -> {bid} 不在板块库中")


def check_legacy_phases(report: Report) -> None:
    """
    旧的 9 阶段名不得再作为状态值出现。

    豁免：CHANGELOG（历史记录）、以及标题含「版本」或「历史」的章节
    （迁移说明里必须能提到旧名，否则读者无法对照）。
    """
    legacy = ["洞察生成", "设计审查", "报告生成"]
    for md in iter_markdown():
        rel = md.relative_to(SKILL_ROOT)
        if rel.name == "CHANGELOG.md":
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        excused = False
        for lineno, line in enumerate(text.splitlines(), start=1):
            if line.startswith("#"):
                excused = any(k in line for k in ("版本", "历史", "迁移", "变更"))
                report.ok()
                continue
            if excused:
                report.ok()
                continue
            hit = [w for w in legacy if w in line]
            if hit:
                report.fail(f"[旧阶段名残留] {rel}:{lineno} 含「{hit[0]}」")
            else:
                report.ok()


def check_schema_contract_docs(report: Report) -> None:
    """
    契约协议的一致性：文档里承诺的 role / additivity 取值，必须与代码一致。

    这类"文档说支持 A，代码只认 B"的漂移最难发现——调用方按文档写了契约，
    代码直接抛异常或静默忽略，且错误信息往往指向别处。
    """
    probe = SKILL_ROOT / "conspect_tools" / "schema_probe.py"
    contract = SKILL_ROOT / "conspect_tools" / "schema_contract.py"
    doc = SKILL_ROOT / "references" / "data-onboarding.md"
    if not (probe.exists() and contract.exists() and doc.exists()):
        report.fail("[契约] schema_probe / schema_contract / data-onboarding.md 缺文件")
        return

    probe_src = probe.read_text(encoding="utf-8")
    contract_src = contract.read_text(encoding="utf-8")
    doc_text = doc.read_text(encoding="utf-8")

    # 代码里声明的 role 集合
    m = re.search(r'ROLES\s*=\s*\(([^)]+)\)', probe_src)
    if not m:
        report.fail("[契约] schema_probe.ROLES 未找到")
        return
    roles = set(re.findall(r'"([a-z]+)"', m.group(1)))
    for _ in roles:
        report.ok()

    # 每个 role 都必须在文档的角色表里出现
    for r in sorted(roles):
        if f"`{r}`" not in doc_text:
            report.fail(f"[契约] role「{r}」在代码里有，data-onboarding.md 未说明")
        else:
            report.ok()

    # additivity 取值一致
    m2 = re.search(r'ADDITIVITIES\s*=\s*\(([^)]+)\)', contract_src)
    if not m2:
        report.fail("[契约] schema_contract.ADDITIVITIES 未找到")
        return
    adds = set(re.findall(r'"([a-z]+)"', m2.group(1)))
    for a in sorted(adds):
        if f"`{a}`" not in doc_text:
            report.fail(f"[契约] additivity「{a}」在代码里有，文档未说明")
        else:
            report.ok()

    # 探测层的「未定」标记不能在契约里落成正式值
    if '"hint"' in contract_src.split("ADDITIVITIES")[1][:200]:
        report.fail("[契约] hint 不应出现在契约的合法取值里（它只是探测层标记）")
    else:
        report.ok()

    # 技能必须声明「契约是判定唯一事实源」
    if "数据契约" not in doc_text or "唯一事实源" not in doc_text:
        report.fail("[契约] data-onboarding.md 未声明契约是判定的唯一事实源")
    else:
        report.ok()


def main() -> int:
    parser = argparse.ArgumentParser(description="conspect 一致性自检")
    parser.add_argument("--quiet", action="store_true", help="只输出失败项")
    args = parser.parse_args()

    report = Report()
    check_links(report)
    check_emoji(report)
    check_artifact_consistency(report)
    check_version_consistency(report)
    check_asset_refs(report)
    check_legacy_phases(report)
    check_schema_contract_docs(report)

    if report.failures:
        print(f"检查完成：{report.checks} 项，失败 {len(report.failures)} 项\n")
        for item in report.failures:
            print("  " + item)
        print("\n结果：FAILED")
        return 1

    if not args.quiet:
        print(f"检查完成：{report.checks} 项全部通过")
        print("  - 引用完整性（不逃逸 / 不悬空 / 指向文件）")
        print("  - emoji 禁令")
        print("  - 产物清单一致性")
        print("  - 版本号一致性")
        print("  - 资产引用与板块引用有效性")
        print("  - 旧阶段名零残留")
    print("结果：PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
