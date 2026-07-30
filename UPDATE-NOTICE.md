# Conspect Skill v2.1 更新通知

## 更新概述

本次更新聚焦于 **CLI 工具层的稳定性、AI 执行可靠性** 和 **分析能力增强**。彻底解决了 PowerShell 引号导致 CLI 调用失败的问题，并新增了交叉分析、数据质量评估等核心功能。

---

## 更新清单

### 1. CLI 调用方式改进（核心修复）

**问题**：AI 在 PowerShell 中调用 CLI 时频繁遇到 `ParserError`（引号嵌套）和 `Invalid JSON params`（`\"` 转义），导致 AI 放弃 CLI 自行写内联 Python 代码。

**修复**：

| 改动 | 说明 |
|------|------|
| 新增标准输入管道方案（推荐） | `'{"key": "val"}' \| python run.py <action>` — PowerShell 单引号内双引号为字面量，通过 stdin 传递 JSON，完全无转义问题 |
| 新增 `--params-file` 参数 | `python run.py <action> --params-file <file>` — 从 JSON 文件读取参数，绕过命令行引号 |
| 明确禁止内联 `python -c` | 新增 `[P0 阻断]` 禁止 `python -c "..."` 以及 CLI 失败后放弃 CLI |
| 新增失败处理流程 | 失败后先查 CLI_DIR → 改管道重试 → 改 params-file → 写 .py 脚本（非 -c） |
| 路径解析优先级调整 | Glob 全局搜索优先于系统目录，避免找到 `.trae-cn` 旧代码 |

### 2. 分析能力增强

| 改动 | 说明 |
|------|------|
| `analyze` 集成 DataStatistics | 现在自动输出：集中度(CR4/HHI/基尼)、趋势(方向/强度/波动)、分布(偏度/峰度)、异常检测、数据质量评分 |
| 新增 `cross_tabulate` 动作 | `python run.py cross_tabulate` — 任意两维度交叉分析，返回透视表+行/列合计 |
| 新增 `quality_assess` 动作 | `python run.py quality_assess` — 按列质量评分（空值扣分、唯一性检查、异常值检测） |
| 新增 `compare_data` 动作 | `python run.py compare_data` — 两数据集一致性比较 |
| 实现 `load_review_context` | 补齐 docstring 中已列但未实现的动作 |
| 输出大小优化 | 趋势 `moving_average_3` 抽样到 20 点，异常点限 10 条 |

### 3. Bug 修复

| 问题 | 修复 |
|------|------|
| `ImportError: cannot import name 'Config'` | `config.py` 新增 `Config` 类 |
| `ModuleNotFoundError: No module named 'chart_selector'` | 移除已不存在的模块的顶层 import，改为函数内部 `try/except` 懒导入 |
| `references/\*.md` 硬编码路径 | `data/sales.xlsx` → `数据源文件.xlsx` |
| `references/trigger-guide.md` 虚假 CLI 命令 | `python -m conspect.cli start` → 替换为真实 `python run.py` 命令 |
| emoji 残留 | 全线移除，替换为 `[通过]`/`[不通过]`/`[重要]` 等纯文本 |

### 4. AI 执行可靠性加固

| 改动 | 说明 |
|------|------|
| SKILL.md 新增 CLI 速查表 | 13 条命令一目了然，激活即加载 |
| 8 个 Agent 文件均加入 CLI 调用规范 | 每个涉及数据操作的 Agent 都标注了 `cd {CLI_DIR}` 前置和禁止 `python -c` |
| 新增 AI 自主分析职责 | `analyzer-agent.md` 强调 CLI 只做计算，AI 必须自主阅读原始数据做业务判断 |
| SKILL-execution.md 分析阶段增加 AI 自主阅读步骤 | 步骤 3：AI 自主阅读原始样本；步骤 4：综合分析 |

---

## 兼容性说明

- 所有旧动作（`select_charts`、`generate_insights`、`review_design` 等）保持向后兼容，返回友好提示
- 产物文件命名不变（`_cs-` 前缀）
- 接力棒格式不变
- `data/run.py` 中的 `sys.path.insert` 基于 `Path(__file__).parent.parent` 动态解析，无需硬编码

---

## 建议

首次使用建议先用 `conspect_tools/run.py` 的 **管道方案** 验证 CLI 可用：

```powershell
cd {CLI_DIR}
'{"file_paths": ["e:/数据源文件.xlsx"]}' | python run.py analyze
```
