# Conspect v3.1 — AI 全自动报表渲染引擎

> 上传 Excel，一句话需求，AI 全自动生成**可直接投屏**的专业商务报表。开会再也不用熬夜做 PPT。

[![version](https://img.shields.io/badge/version-3.1-blue)](./1-manifest/skill-manifest.yaml)
[![level](https://img.shields.io/badge/level-L3-success)](./CHANGELOG.md)
[![python](https://img.shields.io/badge/python-3.10%2B-green)](#技术栈)
[![license](https://img.shields.io/badge/license-MIT-green)](#许可证)

---

## 这是什么

你一定遇到过这些场景：

- 📊 **明天 10 点要开周会**，PPT 还是空白的，数据散在 5 个 Excel 里
- 🤯 **老板要季度经营看板**，既要有图表又要有数据解读，还要能投屏展示
- 😱 **销售/运营/财务数据分析**，对比、占比、趋势、排名……每个图都要手调半天
- 💤 **没时间学 BI 工具**，Tableau/Power BI 太重，临时抱佛脚来不及

**Conspect 就是解决这个的——你给数据 + 说句话，剩下的全交给 AI。**

> 你："帮我把这份销售数据做成一份周报看板，重点看华东区的趋势和产品占比" + 上传 sales.xlsx
>
> Conspect：（9 阶段全自动，约 3-5 分钟）→ 产出一个可以直接投屏的 HTML 看板 + 多格式报告

---

## 核心能力

| 能力 | 说明 |
|------|------|
| **9 阶段全自动** | 分析 → 洞察生成 → 设计 → 设计审查 → 实现 → 报告生成 → 验证 → 完成，零用户打断 |
| **偏好自动识别** | 从你的初始需求自动提取配色/图表类型/输出格式偏好 |
| **多源数据合并** | 同时处理多个 Excel，自动关联维度、合并计算 |
| **专业图表选型** | 柱状/折线/饼图/散点/热力图……自动选最适合数据的图表 |
| **8 套商业级配色** | 商务蓝 / 暖橙 / 自然绿 / 科技紫 / 极简灰……开箱即用 |
| **多格式输出** | 交互式 HTML 看板 / PDF 报告 / Markdown / Word |
| **分区式看板** | 分区布局 + 便当盒网格 + 每图表自带数据解读区 |
| **零依赖 CLI** | Python 标准库 + pandas，不需要装 Tableau/Power BI |

---

## 快速开始（30 秒入门）

### 方式一：自然语言触发（最推荐）

直接对 AI 说：

> "帮我分析这份销售数据，出一份周报看板，重点看各区域销售趋势" + 上传 sales.xlsx

→ AI 启动 Conspect，3-5 分钟后产出看板和报告。

### 方式二：斜杠命令

```bash
/conspect start                 # 启动报表任务
/conspect start --offline       # 离线模式（内联 ECharts，无需联网）
/conspect status                # 查看当前进度
/conspect reset                 # 重置当前任务
```

### 方式三：CLI 工具

```powershell
# 全链路分析
python run.py analyze '{"file_paths": ["数据源.xlsx"]}'

# 用户偏好识别
python run.py recognize_preferences '{"user_requirement": "用蓝色调，出 PDF"}'

# 交叉分析（行×列透视）
python run.py cross_tabulate '{"file_paths": [...], "row_dim": "产品", "col_dim": "区域"}'

# 渲染报告
python run.py render_report '{"report_design": {...}, "format": "html"}'
```

### 产物位置

所有产物在 `{项目路径}/.agent/harness/`：

| 文件 | 说明 |
|------|------|
| `_cs-dashboard.html` | **交互式 Web 看板**（直接浏览器打开投屏） |
| `_cs-report.md` / `.html` / `.pdf` | 多格式分析报告 |
| `_cs-analysis.md` | 数据分析详细报告 |
| `_cs-insights.json` | AI 自动生成的洞察与建议 |
| `_cs-verify.md` | 数据验证报告 |
| `数据看板.html` / `分析报告.md` | 中文命名副本（方便找） |

---

## 状态机（9 阶段全自动）

```
开始 → 分析 → 洞察生成 → 设计 → 设计审查 → 实现 → 报告生成 → 验证 → 完成
 │                                          │
 └──── QA 审核不通过 ←─────── 自动回退重做（最多 2 次）
```

每个阶段的产出物是下一阶段的前置条件。QA 审核不通过自动回退，不会带着错误往前走。

---

## 偏好说明（可选，不说也能自动识别）

| 偏好类型 | 示例 |
|---------|------|
| 配色 | "用蓝色调"、"我想要暖色系"、"主色调用 #1890FF" |
| 图表 | "对比多用柱状图"、"占比用饼图"、"趋势用折线图" |
| 输出格式 | "生成 PDF 给我"、"做一个离线 HTML"、"两种都要" |
| 分析焦点 | "重点关注销售趋势"、"按区域分析"、"只看 TOP 10 产品" |

---

## 适用场景 vs 不适用场景

| ✅ 适用 | ❌ 不适用 |
|---------|----------|
| 周报/月报/季度汇报（需要投屏展示） | 简单数据整理（用 Excel 就行） |
| 销售/运营/财务数据分析看板 | 实时数据流处理（Conspect 处理静态文件） |
| 经营分析报告，需要 AI 洞察和建议 | 桌面 BI 工具替代（Tableau/Power BI 有自己的场景） |
| 老板突然要数据，来不及做图表 | 纯文本报告（无图表需求时不需要 Conspect） |
| 多个 Excel 需要合并分析 | — |

---

## 项目结构

```
conspect/
├── SKILL.md                    # 主入口（触发契约 + 状态机）
├── SKILL-execution.md          # 阶段执行手册
├── README.md                   # 本文件
├── CHANGELOG.md                # 版本变更
├── 1-manifest/
│   └── skill-manifest.yaml     # Skill 元数据
├── agents/                     # 10 个 Agent 定义
│   ├── 00-master-controller.md
│   ├── 01-analyzer-agent.md
│   ├── 02-designer-agent.md
│   ├── 03-implementer-agent.md
│   ├── 04-verifier-agent.md
│   ├── 05-quality-auditor-agent.md
│   ├── 06-visual-designer-agent.md
│   ├── 07-report-designer-agent.md
│   ├── 08-report-implementer-agent.md
│   └── 09-ai-reviewer-agent.md
├── conspect_tools/             # Python CLI 工具层
│   ├── run.py                  # CLI 入口
│   ├── config.py               # 配置管理
│   ├── ai_agent.py             # AI 洞察生成（含异常降级）
│   ├── data_processor.py       # 数据清洗与合并
│   ├── data_statistics.py      # 统计计算
│   ├── data_feature_extractor.py
│   ├── render_engine.py        # 渲染引擎
│   ├── report_renderer.py      # 报告渲染
│   ├── review_data_loader.py
│   ├── exporter.py             # 多格式导出
│   └── ...
├── protocols/
│   ├── phase-protocol.md       # 阶段流转协议
│   └── baton-protocol.md       # 接力棒协议
├── references/
│   ├── trigger-guide.md        # 触发指南
│   ├── chart-selection.md      # 图表选型参考
│   ├── examples.md             # 真实案例
│   ├── cli-ai-workflow.md
│   └── faq-deep.md             # 进阶 FAQ
└── SKILL.chunks/               # 分块按需加载
```

---

## 技术栈

| 层 | 技术 |
|----|------|
| 数据处理 | pandas + openpyxl |
| 可视化 | ECharts 5 |
| 渲染 | Jinja2 模板引擎 |
| 导出 | PDF（weasyprint） / Word（python-docx） |
| 运行环境 | Python 3.10+ |

---

## 版本记录

| 版本 | 日期 | 核心变化 |
|------|------|---------|
| v3.1 | 2026-08-11 | 渲染能力升级：分区式看板布局 + 便当盒网格 + 每图表数据解读区 + 8 套商业级配色 |
| v3.0 | 2026-08-11 | 全流程托管 AI 自动生成，删除确认环节，新增洞察生成和报告生成阶段 |
| v2.0 | — | 9 阶段状态机（含确认环节） |
| v1.0 | — | 初始版本 |

---

## 许可证

MIT
