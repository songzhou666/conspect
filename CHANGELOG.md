# Changelog

本文档记录 conspect Skill 的版本变更历史。

---

## [v3.1] — 2026-08-11

### 概述

本次升级聚焦**渲染能力**（解决实测生成的 HTML"大量图表并排堆砌、配色简陋、缺数据解读"问题），
在 v3.0 全流程托管机制不变的前提下，重构了看板 UI 能力，并修复多项渲染 Bug。

### 渲染能力升级（核心）

1. **分区式看板布局（`build_dashboard_layout`）**
   - 图表自动按主题分组：核心概览 / 维度对比 / 构成分析 / 转化与漏斗 / 交叉分析 / 其他分析
   - 每个分区含标题 + 描述 + 独立网格列数，替代"20 个图表平铺堆砌"的旧布局
2. **便当盒网格（Bento Grid）**
   - 图表卡片支持 `span` 跨列：趋势/漏斗/堆叠等主图自动占双列，次要图表单列
   - 卡片圆角 14px、柔和阴影、悬停抬升动效
3. **每图表数据解读区**
   - 每个图表下方自动匹配分析洞察文字，标注洞察级别（核心/机会/风险/基础）标签
   - 洞察级别映射分析阶段的风险/机会/核心发现
4. **配色主题扩展至 8 套**（参考 `docs/UI_style.md`）
   - 新增 `bento`（苹果浅灰底+白卡，参考 #21 便当盒）、`editorial`（杂志纸感，参考 #47）、`aurora_dark`（极光深色大屏，参考 #10）
   - 原 5 套 ocean/warm/aurora/forest/minimal 保留
5. **强制 RenderEngine 渲染**
   - 03-implementer-agent 新增 P0 禁令：禁止 AI 自写 HTML/JS/CSS 脚本，必须走
     `build_dashboard_layout → render_dashboard → save_report` 三步流程

### Bug 修复

| Bug | 原因 | 修复 |
|-----|------|------|
| 图表空渲染（只有框架无数据） | 分析阶段产出 `categories/values` 格式，渲染引擎 ChartBuilder 期望 `x/y/series` | 新增 `AIAgent._normalize_chart_data()`，在布局构建时统一数据标准化 |
| `TypeError: Object of type function is not JSON serializable` | `horizontal_bar`/`scatter`/`word_cloud` 的 ECharts option 含 lambda 函数 | lambda 全部替换为可序列化写法（`symbolSize: [5,50]` 范围映射等） |
| KPI 卡片字符串值崩溃 | `f"{value:,}"` 对字符串抛 ValueError | 字符串值跳过千分位格式化 |

### 工具层变更

| 文件 | 变更 |
|------|------|
| `conspect_tools/ai_agent.py` | 新增 `_normalize_chart_data()`；主图 span 自动推导；fallback 布局同步标准化 |
| `conspect_tools/render_engine.py` | 移除 3 处 lambda；KPI 字符串值兼容 |
| `conspect_tools/run.py` | `render_dashboard` 自动从 preferences/layout 读取主题，回退 ocean；返回实际 theme |
| `agents/03-implementer-agent.md` | 新增"禁止自写 HTML 脚本（P0）"与 v3.0 三步渲染流程 |

---

## [v3.0] — 2026-08-11

### 概述

本次升级聚焦"全流程托管 AI 自动生成"目标：
- 删除"确认"用户介入节点，新增"洞察生成"和"报告生成"阶段，状态机由 8 阶段升级为 9 阶段
- 新增"洞察生成"阶段，作为分析→设计的自动过渡
- 所有 Python 工具层增加异常降级处理，失败时返回兜底结果而非崩溃
- 新增用户偏好识别器，从初始需求自动提取配色/图表/输出格式等偏好

### 状态机变更

**v2.0（8 阶段）**：
```
开始 → 分析 → 确认 → 设计 → 设计审查 → 实现 → 验证 → 完成
```

**v3.0（9 阶段，删除"确认"，新增"洞察生成"和"报告生成"）**：
```
开始 → 分析 → 洞察生成 → 设计 → 设计审查 → 实现 → 报告生成 → 验证 → 完成
```

- 删除 `确认` 阶段（用户介入节点）
- 新增 `洞察生成` 阶段（自动推进）
- 新增 `报告生成` 阶段（独立于实现）

### 新增功能

#### 1. 用户偏好识别器（`UserPreferenceRecognizer`）
- 替代原"确认阶段"的人工输入
- 从用户初始需求文本中自动识别：
  - 配色主题（ocean/warm/aurora/forest/minimal）
  - 自定义品牌色（如 `#1890FF`）
  - 图表类型偏好（折线/柱状/饼图等）
  - 输出格式（html/pdf/md/docx）
  - 排版方式（dashboard/report）
- 识别失败时使用默认值，不阻断流程

#### 2. 异常降级处理
- `AIAgent.decide_chart()` — 异常时返回默认柱状图
- `AIAgent.generate_insights()` — 异常时返回空列表
- `AIAgent.generate_recommendations()` — 异常时返回空列表
- `AIAgent.review_design()` / `review_implement()` — 异常时降级为通过（score=70）
- `AIAgent.generate_insights_safe()` — 新增安全版，返回结构化字典含状态信息

#### 3. 新增 CLI 动作
- `recognize_preferences` — 识别用户偏好（替代原确认环节）
- `ai_generate_insights_safe` — 降级版洞察生成

#### 4. 配置增强（`config.py`）
- `STABILITY_CONFIG` — 重试策略、超时、降级、日志
- `DEFAULT_USER_PREFERENCES` — 用户偏好默认值
- `AUTO_FLOW_CONFIG` — 全流程自动推进配置
- `ERROR_CODES` — 统一错误码
- `ensure_harness_dir()` — 确保产物目录存在

#### 5. 诊断日志
- `ai_agent.py` 和 `run.py` 新增模块级日志器
- `main()` 异常时记录 `logger.exception` 诊断信息
- `KeyboardInterrupt` 优雅退出（exit code 130）

### 文档更新

| 文件 | 变更 |
|------|------|
| `SKILL.md` | 版本号 v2.0→v3.0，更新状态机 Mermaid 图，删除"确认"阶段 |
| `SKILL-execution.md` | 状态路由表更新，删除 7.3"确认阶段"，新增"洞察生成阶段" |
| `protocols/phase-protocol.md` | 更新状态图，新增"洞察生成"和"报告生成"节点 |
| `protocols/baton-protocol.md` | 接力棒格式新增 `user_preferences` 字段 |
| `agents/00-master-controller.md` | 主控伪代码更新，新增 `识别用户偏好()` 步骤 |
| `agents/04-verifier-agent.md` | 删除"用户确认"检查项，新增"用户偏好满足"检查 |
| `SKILL.chunks/chunk-02-workflow.md` | 更新阶段定义表，删除"确认"阶段 |
| `SKILL.chunks/chunk-05-quality.md` | L2 验证"用户满意度"改为"用户偏好满足" |
| `references/trigger-guide.md` | 命令触发说明更新为 8 阶段，删除确认环节描述 |
| `references/examples.md` | 步骤表删除"确认"行，改为"洞察生成"自动推进 |
| `references/faq-deep.md` | 接力棒模板删除"确认"状态，新增"洞察生成"和"报告生成" |
| `1-manifest/skill-manifest.yaml` | 版本号 v2.0→v3.0，新增 `display_name`/`language`/`tags` 字段 |

### Python 工具层变更

| 文件 | 变更类型 | 主要变更 |
|------|---------|---------|
| `conspect_tools/config.py` | 重大升级 | 新增 `STABILITY_CONFIG`、`DEFAULT_USER_PREFERENCES`、`AUTO_FLOW_CONFIG`、`ERROR_CODES`；新增 `ensure_harness_dir()`、`get_stability_config()`、`get_default_preferences()` |
| `conspect_tools/ai_agent.py` | 重大升级 | 新增 `UserPreferenceRecognizer` 类；所有决策方法增加 try/except 降级；新增 `recognize_preferences()` 和 `generate_insights_safe()` |
| `conspect_tools/run.py` | 升级 | 新增 `recognize_preferences` 和 `ai_generate_insights_safe` 动作；`main()` 增加异常诊断日志和优雅退出 |

### 兼容性

- **向后兼容**：所有 v2.0 的 CLI 动作继续可用
- **状态机变更**：v2.0 接力棒中的"确认"状态在 v3.0 中会被自动跳过（不阻断）
- **配置兼容**：v2.0 的配置项保留，v3.0 新增配置项有默认值

### 升级依据

本次升级聚焦以下改进方向：
1. **稳定性**：所有决策点增加异常降级，避免单点故障阻断全流程
2. **丝滑性**：删除用户确认环节，状态机自动推进
3. **可观测性**：新增诊断日志和错误码体系
4. **完整性**：补全 frontmatter 元数据（tags、language）

---

## [v2.0] — 历史版本

- 8 阶段状态机（含"确认"环节）
- 用户需在确认阶段人工确认分析结果
- 无异常降级处理
- 无用户偏好自动识别
