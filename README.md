# Conspect — 全自动报表渲染引擎

> 上传 Excel，一句话需求，AI 全自动生成可投屏的专业商务报表。

[![version](https://img.shields.io/badge/version-3.1-blue)](./1-manifest/skill-manifest.yaml)
[![level](https://img.shields.io/badge/level-L3-success)](./CHANGELOG.md)
[![license](https://img.shields.io/badge/license-MIT-green)](#许可证)

---

## 这是什么

Conspect 是一个通用的 AI Skill，把"Excel → 开会用的报表"这件事全自动托管给 AI。

- **一句话需求触发**：上传 Excel + "帮我出一份周报看板"
- **9 阶段全自动推进**：分析 → 洞察生成 → 设计 → 设计审查 → 实现 → 报告生成 → 验证 → 完成
- **零用户确认环节**（v3.0）：偏好从初始需求自动识别，不再中途打断你
- **多格式输出**：HTML 看板 / PDF / Markdown / Word，含中文命名副本

## 快速开始

### 1. 触发方式

```
/conspect start                 # 启动报表任务
/conspect start --offline       # 离线模式（内联 ECharts，无需联网）
/conspect status                # 查看当前进度
/conspect reset                 # 重置当前任务
```

或直接用自然语言：

> "帮我分析这份业务数据，出一份周报看板" + 上传 sales.xlsx

### 2. 在初始需求中说明偏好（可选）

v3.0 起偏好从初始需求自动识别，全程无确认环节：

| 偏好类型 | 示例 |
|---------|------|
| 配色 | "用蓝色调"、"我想要暖色系"、"主色调用 #1890FF" |
| 图表 | "对比多用柱状图"、"占比用饼图" |
| 输出格式 | "生成 PDF 给我"、"做一个离线 HTML" |
| 分析焦点 | "重点关注销售趋势"、"按区域分析" |

### 3. 产物位置

所有产物位于 `{项目路径}/.agent/harness/`：

| 文件 | 说明 |
|------|------|
| `_cs-dashboard.html` | 交互式 Web 看板 |
| `_cs-report.md` / `.html` / `.pdf` | 多格式分析报告 |
| `_cs-analysis.md` | 数据分析报告 |
| `_cs-insights.json` | AI 洞察与建议 |
| `_cs-verify.md` | 验证报告 |
| `数据看板.html` / `分析报告.md` | 中文命名副本 |

## 状态机（9 阶段全自动）

```
开始 → 分析 → 洞察生成 → 设计 → 设计审查 → 实现 → 报告生成 → 验证 → 完成
```

每个阶段产出物是下一阶段的前置条件，QA 审核不通过自动回退重做，最多重试 2 次。

## 能力边界

### ✅ 擅长

- 多源 Excel 数据分析与合并
- 商务报表/看板/数据大屏生成
- 投屏用 HTML 看板
- 多格式报告输出（HTML/PDF/MD/Word）

### ❌ 不做

- 简单数据整理（用 Excel 即可）
- 桌面 BI 工具替代（用 Tableau/Power BI）
- 纯文本报告（无图表需求时无需 conspect）
- 实时数据流处理（conspect 处理静态文件）

## CLI 工具层

```powershell
cd e:/Mytest_skill/.trae/skills/conspect/conspect_tools

# 全链路分析
python run.py analyze '{"file_paths": ["数据源.xlsx"]}'

# 用户偏好识别（v3.0 新增）
python run.py recognize_preferences '{"user_requirement": "用蓝色调，出 PDF"}'

# 安全降级洞察生成（v3.0 新增）
python run.py ai_generate_insights_safe '{"statistics": {...}}'

# 交叉分析
python run.py cross_tabulate '{"file_paths": [...], "row_dim": "产品", "col_dim": "区域"}'

# 渲染报告
python run.py render_report '{"report_design": {...}, "format": "html"}'
```

## 项目结构

```
conspect/
├── SKILL.md                    # 主文档（触发契约 + 状态机）
├── SKILL-execution.md          # 阶段执行手册
├── README.md                   # 本文件
├── CHANGELOG.md                # 版本变更记录
├── 1-manifest/
│   └── skill-manifest.yaml     # 技能清单
├── agents/                     # 7 个 Agent 定义
│   ├── 00-master-controller.md
│   ├── 01-analyzer-agent.md
│   ├── 02-designer-agent.md
│   ├── 03-implementer-agent.md
│   ├── 04-verifier-agent.md
│   ├── 05-quality-auditor.md
│   └── 06-visual-designer-agent.md
├── protocols/                  # 协议文档
│   ├── phase-protocol.md       # 阶段流转协议
│   └── baton-protocol.md       # 接力棒协议
├── references/                 # 深度参考
│   ├── trigger-guide.md
│   ├── examples.md
│   └── faq-deep.md
├── SKILL.chunks/               # 分块加载文档
└── conspect_tools/             # Python 工具层
    ├── run.py                  # CLI 入口
    ├── config.py               # 配置（v3.0 稳定性增强）
    ├── ai_agent.py             # AI Agent（v3.0 异常降级）
    ├── data_processor.py
    ├── data_statistics.py
    ├── render_engine.py
    └── ...
```

## 技术栈

- **数据层**：pandas + openpyxl
- **可视化**：ECharts 5
- **渲染**：Jinja2 模板引擎
- **导出**：PDF（weasyprint）/ Word（python-docx）

## 版本历史

详见 [CHANGELOG.md](./CHANGELOG.md)。

- **v3.1**（2026-08-11）：渲染能力升级——分区式看板布局 + 便当盒网格 + 每图表数据解读区 + 8 套商业级配色，修复图表数据标准化与渲染 Bug
- **v3.0**（2026-08-11）：全流程托管 AI 自动生成，删除确认环节，新增洞察生成和报告生成阶段
- **v2.0**：9 阶段状态机（含确认环节）
- **v1.0**：初始版本

## 许可证

MIT
