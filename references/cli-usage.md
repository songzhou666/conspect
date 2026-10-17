# CLI 工具层使用指南

> **何时读本文件**：需要调用 CLI、不确定用哪个动作、或 CLI 报错时。
> 日常流程只需 SKILL.md 的「CLI 速查表」。

---

## 一、定位 CLI 目录（{CLI_DIR}）

所有数据操作必须通过 CLI 工具层执行。先定位 `run.py`：

```
glob **/conspect_tools/run.py
```

若命中多个副本，优先选择**非系统目录**（如 `c:\Users\{user}\.trae-cn\` 之外的、
位于项目盘符下的）。定位后验证：

```
ls {CLI_DIR}/run.py
```

记下该目录为 `{CLI_DIR}`，后续所有调用统一 `cd {CLI_DIR}`。

---

## 二、三种传参方式（按优先级）

### 方式 1（推荐）：标准输入管道

PowerShell 单引号内的双引号是字面量，经管道传给 stdin，完全绕开引号转义问题。

```powershell
cd {CLI_DIR}
'{"file_paths": ["e:/data/sales.xlsx"]}' | python run.py analyze
```

原理：`'...'` 原样保留 → `|` 传给 stdin → `sys.stdin.read()` 读到有效 JSON。

### 方式 2：`--params-file` 从文件读取

参数太长或含大量中文时使用。**必须用编辑器的写文件工具创建** JSON 文件
（终端里的 `write` 是 `Write-Output` 别名，只打印不落盘）。

```
步骤 1：写文件 {CLI_DIR}/_params.json，内容 {"file_paths": ["e:/data/sales.xlsx"]}
步骤 2：cd {CLI_DIR}
        python run.py analyze --params-file _params.json
        （短参 -p 等价）
```

### 方式 3：单引号内联 JSON

仅在前两种不可用时使用。

```powershell
cd {CLI_DIR}
python run.py analyze '{"file_paths": ["e:/data/sales.xlsx"]}'
```

**单引号内不要给双引号加反斜杠**：`'{"k": "v"}'` 正确；`'{\"k\": \"v\"}'` 会 JSON 解析失败。

---

## 三、传长内容：`content_file`

`save_report` / `save_with_chinese_name` 需要整份报告内容。**长文本不要塞进命令行 JSON**，
改用 `content_file`：

```
步骤 1：用编辑器写文件工具把内容写到 {CLI_DIR}/_content.md（或任意临时文件）
步骤 2：cd {CLI_DIR}
        python run.py save_report '{"content_file": "_content.md", "filename": "_cs-report.md", "output_dir": "e:/proj/.agent/harness"}'
```

规则：

- 优先级 `content_file` > `content`；两者都给时用 `content_file`
- 路径不存在 → 返回 `status: error`，提示「content_file 不存在」
- `is_binary` 为 true 时按字节读取（用于 PDF/PNG/DOCX 等二进制产物）
- 读取时会归一化换行，避免 Windows 下写出 `\r\r\n`

---

## 四、完整动作清单

> 本表与 `conspect_tools/run.py` 的 `run()` 分派一一对应。新增动作时须同步本表。

### 4.1 数据加载与契约

**先建契约，再分析。** 这是「换行业不用改代码」的前提，详见
[../references/data-onboarding.md](data-onboarding.md)。

| 动作 | 参数 | 用途 |
|------|------|------|
| `probe_schema` | `file_paths`、`sheet?` | **探测每列画像 + 待终判清单（不写盘）** |
| `save_schema` | `file_paths`、`overrides`、`output_dir?`、`filename?`、`decided_by?` | **固化数据契约 `_cs-schema.json`** |
| `check_schema` | `file_paths`、`schema_file`、`sheet?` | 校验旧契约与新版数据是否匹配 |
| `read_datamap` | `file_paths` | 文件/Sheet/列/类型/样本/质量分一次汇总 |
| `load` | `file_paths` | 加载数据，返回 Sheet 列表 |
| `read_all` | `file_paths` | 返回原始结构信息（列名/类型/前 3 行样本） |
| `analyze` | `file_paths`、`schema_file?`、`fill_strategy?` | **全链路分析**（按契约判角色→聚合→统计→**图表候选**） |
| `cross_tabulate` | `file_paths`、`row_dim`、`col_dim`、`metric?`、`agg_func?` | 任意两维度交叉聚合 |
| `quality_assess` | `file_paths`、`fill_strategy?` | 按列数据质量评分 |
| `compare_data` | `data1`、`data2`、`tolerance?` | 两数据集一致性比较 |

**`probe_schema` 的返回怎么读**

| 字段 | 含义 | 你要做什么 |
|------|------|-----------|
| `columns[]` | 每列的完整画像（role / confidence / evidence / reason / additivity / 统计事实） | 核对判定是否合理 |
| `summary` | high / medium / low / unknown 各几列 | 判断数据可判性 |
| `need_ai` | **只有你能判的列**（统计层判不出来的） | 逐条给 role |
| `unresolved` | 完全判不出的列 | 给 role，或留 unknown 并声明不参与分析 |
| `duplicate_columns` | 内容完全相同的列 | 分析时只取其一 |
| `ready` | 是否可直接进入计算 | `false` 说明还有 unknown |

实测：8 个行业 59 个关键列，`need_ai` 平均只有 0–5 列。**不要整表通读**。

**`save_schema` 的 `overrides` 写法**

```json
{
  "客户名称": {"role": "dimension", "reason": "客户用于分组，不是明细ID"},
  "GMV":     {"role": "measure", "additivity": "additive", "reason": "成交总额可求和"},
  "客单价":   {"role": "measure", "additivity": "average",  "reason": "单价求和无意义"}
}
```

只需给 `role`；`additivity` 可省略——省略时按统计特征推断，
推断不出就落 `average` 并标 `additivity_confirmed: false`（安全侧），
报表口径必须据此声明。**判不出就留空，不要瞎填。**

**`analyze` 的返回字段（每个 Sheet 一份）**

| 字段 | 内容 | 谁消费 |
|------|------|--------|
| `rows` / `columns` | 行数 / 列名列表 | 全局 |
| `dimensions` | `{"时间":[], "分类":[], "数值":[]}`，另带 `_provenance` 说明判定来源 | 选型判定 |
| `statistics` | 每个数值列的基础统计、分布、异常点、集中度、趋势，含 `aggregation`（sum/mean 及依据） | Agent 解读 |
| `data_quality` | 每列缺失数/缺失率/唯一值/类型/评级 | 质量说明板块 |
| `contract` | 契约摘要（`decided_by`/`summary`/`views`/`unresolved`/`note`） | 报表口径声明 |
| `charts` | **图表候选**：`chart_type`/`title`/`data`/`description`/`block` | 装配阶段直接消费 |
| `data_issues` | 数据议题：全空列 / 高缺失列 / 疑似明细ID / 常数列 / **角色未判定** / **内容重复列**，每条带可执行建议 | 质量说明板块 |
| `table_role` | `fact` / `dimension`，含 `measure`（`amount` 金额型 / `count` 记录型 / `none`）与理由 | 选型阶段定主线 |
| `warnings` | 图表或议题生成失败的原因（不静默吞异常） | 排查 |

**`dimensions._provenance` 必须核对**

| source | 含义 | 处置 |
|--------|------|------|
| `contract` | 用了你提供/确认过的契约 | 正常继续 |
| `auto_contract` | 未传 `schema_file`，现场统计探测生成 | **报表口径必须声明「未经复核」**，并列出 `note` 里的不确定列 |

`_provenance.excluded` 会列出被排除的 identifier / text / ignore / unknown 列，
用于核对「该进的没进、不该进的没进」。

> 图表候选由 `chart_advisor` 基于真实数据算出，**不要自己手搓图表数据**。
> 它已内置这些业务规则，都是真实数据踩出来的：

| 规则 | 内容 |
|------|------|
| 可加总性判别 | 数量/金额求和；单价/比率/**单位成本**取均值。否则出现「平均单价 5.5 万」 |
| 标识列排除 | 电话/联系方式/编号/经纬度/照片文件名等「长得像数字」的列一律不当指标 |
| 健康度过滤 | 缺失 >30% 的列不参与聚合；全空列、常数列排除 |
| 无度量退化为计数 | 没有金额/数量列、行数 ≥100 的表（拜访流水/工单/日志）以「记录数」为指标，否则整表一张图都出不来 |
| 时间自算 | `aggregated.by_dimension` 不含时间维度，趋势图由 advisor 按时间重算 |
| 中文日期解析 | 「2025年06月27日 15:27」这类写法 `pd.to_datetime` 直解会 100% 失败，必须先归一；同一列混着不同精度时会逐格式补齐 |
| 分类维度择优 | 按覆盖率 → 类别数（3–10 最宜）→ 业务相关性排序；内容重复的列去重 |
| 漏斗识别 | 列名含「漏斗/阶段/转化」且 ≤8 类时用 `funnel` 图，柱状图看不出逐级收敛 |

**`table_role.measure` 的含义**：`amount` 表示有金额/数量度量可求和；
`count` 表示无度量但行数够多、以记录数计数；`none` 表示只是维表。
报表主线只取 `role == "fact"` 的表。

**`read_datamap` 的质量分口径**：`quality_score` 取**最差 Sheet 的分**，不是平均值——
一份数据里某张表质量差，整份报表的可信度就受限于它。同时返回 `quality_by_sheet`
（各表分）、`quality_sheet`（最差表名）、`quality_avg`（平均分，仅供参考）。

### 4.2 特征与统计

| 动作 | 参数 | 用途 |
|------|------|------|
| `extract_features` | `data` | 提取数据特征（供图表选型） |
| `calc_statistics` | `values`、`dimension_data?`、`time_series?` | 计算统计数据 |

### 4.3 选型（v4.0 新增）

| 动作 | 参数 | 用途 |
|------|------|------|
| `select_content` | `analysis`、`insights?`、`features?`、`report_form?`、`requirements?` | **汇报内容选型**：按板块库触发条件产出板块组合与裁出清单 |
| `select_style` | `profile`（`tone`/`report_type`/`density`/`keywords`/`family`/`media`）、`blocks?` | **报表选型**：按调性硬过滤 + 加权打分产出选型建议卡 |
| `render_style_preview` | `candidates`（必填）、`profile?`、`output_path?`、`title?` | 生成候选风格的**可视对比页**（HTML 文件） |
| `list_styles` | 无 | 列出 6 族 38 风格（代码核对用） |
| `list_blocks` | 无 | 列出 22 板块与触发条件 |

**`select_content` 的三个要点**

- 每个板块带回 `engine_charts`（引擎真能画的类型）与 `chart_notes`（降级说明）。
  板块库写「帕累托 / 瀑布」，引擎画不出，会如实标注为「帕累托 → bar（降级）」。
- 每个板块还带 `purpose`——**白话用途**，如 B08 →「总量由哪些部分构成，各占多少比例」。
  给客户看板块清单时必须用它，不能只报编号（`B08` 对客户没有意义），
  也不要只报名称（「结构构成」仍是术语，客户未必知道指饼图）。
- **无图可用的板块会被自动裁出**：触发条件成立不代表真有图。例如「存在数值列且
  非重复值 ≥20」会被电话号码满足（2500 个唯一值），但那张表其实出不了数值图。
  这类板块进 `dropped` 并注明「无可用图表」，不会留到装配阶段变成空洞缺口。
- 分析族板块（B07–B14）若在 `analysis.charts` 里找不到可消费的图，说明数据不足支撑该视角，
  应接受裁出结果，不要强行保留。

**`select_style` 的 `blocks` 参数**：传入内容选型选中的板块 id 列表后，
会按「风格推荐板块 ∩ 实际选中板块」计算契合度加分。

**选型卡必须用人话，不许只给编号**（v5.1）

每张卡都带 `describe`，已把技术字段翻成可直接判断的信息：

| 字段 | 含义 | 示例 |
|------|------|------|
| `palette` | 色系一句话（由色值计算得出，**不含十六进制**） | `近黑底（带蓝调） + 青强调，多彩并列` |
| `form` | 形状与字体 | `小圆角 6px · 标题 48px 超粗` |
| `mood` | 气质 | `霓虹闪烁的赛博夜` |
| `scenes` | 适合场景 | `实时监控大屏、发布会演示` |
| `avoid` | 不建议用于（taboos 摘要） | `不用于打印：暗底大面积输出…` |
| `series_mode` | 数据系列用色组织方式 | `同色系深浅` / `少量撞色` / `多彩并列` |

备选卡片另带 `diff_from_recommend`，说明**与推荐款差在哪**。
同族候选的 `report_use`（场景/密度/载体）是族级属性、完全一致，
只列各自属性会让客户看到几段雷同文字仍然选不出来——所以差异必须显式给出。

**`render_style_preview`**：把候选按各自真实 token 画成一小段报表并排展示
（封面条 / KPI 卡 / 柱图），客户看一眼就知道是不是想要的样子。
纯 HTML + 内联样式，约 18KB，断网可开、可邮件发送。

```powershell
# 1) 选型，拿 candidates
'{"profile": {"tone": "浅色", "report_type": "经营分析"}}' | python run.py select_style
# 2) 原样传入，生成对比页
'{"candidates": [...], "profile": {...}, "output_path": "out/preview.html"}' | python run.py render_style_preview
```

> 两个渲染陷阱，改动预览时必须保留：
> `bg_gradient` 里的 `conic-gradient` 是**环形进度条**不是页面背景（铺满会变成巨大饼图），
> 只有 `linear-gradient` 才当背景；三色标以上全部相同的退化渐变视同无渐变
> （加载层已归一为 `None`，否则浅色风格会被渲染成深底）。

**置信度按族计算**：`report_use` 是族级属性，同族风格的推荐板块/密度/载体天然相同，
所以同族并列是正常现象。`confidence` 反映的是「该用哪个族」的确定程度，
族内择一由默认偏好决定；返回的 `family_ties` 列出同分同族风格，可直接换款。

### 4.4 AI 决策

| 动作 | 参数 | 用途 |
|------|------|------|
| `ai_decide_chart` | `features`、`business_context?` | 图表选型决策 |
| `ai_generate_insights` | `statistics`、`business_context?` | 生成洞察 |
| `ai_generate_insights_safe` | `statistics`、`business_context?` | 生成洞察（降级版，返回结构化字典含状态） |
| `recognize_preferences` | `user_requirement` | 从初始需求识别配色/图表/格式偏好 |

### 4.5 审核

| 动作 | 参数 | 用途 |
|------|------|------|
| `ai_review_style` | `analysis`、`design` | 报表选型阶段 AI 审核 |
| `ai_review_render` | `design`、`implement` | 生成报表阶段 AI 审核 |
| `load_review_context` | `project_root?`、`*_file` | 加载审核上下文 |

### 4.6 渲染

| 动作 | 参数 | 用途 |
|------|------|------|
| `build_dashboard_layout` | `analysis`、`insights?`、`blocks?`、`preferences?` | 按板块清单组装布局（板块顺序即页序） |
| `render_dashboard` | `layout`、`theme?` | 渲染报表 HTML；`theme` 传风格编号（如 `A12`），留空取默认 |
| `render_report` | `report_design`、`format`、`theme?` | 渲染报告内容（返回内容，不写盘） |

**产出是离线自包含的**：ECharts 会从 `assets/vendor/echarts.min.js` 内联进 HTML，
所以生成的报表在断网、内网、邮件附件里都能正常显示图表——不要去改回 CDN 引用，
投屏现场打不开就是事故。代价是 HTML 约 1MB（图表数据本身很小）。
若确需小文件，代码里可传 `RenderEngine(theme_name=..., inline_assets=False)` 退回 CDN。

图表内的文字（坐标轴刻度、图例）会自动保证与背景对比度 ≥4.5:1，
不受风格 `text_secondary` 偏浅的影响——这是渲染层的兜底，资产不需要为此改色。

**`build_dashboard_layout` 的 `blocks` 参数（v4.1 起真正驱动装配）**

- `blocks` 元素可为板块 id（`"B07"`）或 `select_content` 返回的板块 dict，两种都接受。
- 板块顺序即页序，不重排、不增删。
- 返回里带三个可用于自检的字段：

| 返回字段 | 含义 |
|---------|------|
| `mode` | `blocks`（板块驱动）或 `theme`（未传 blocks 的兼容路径） |
| `blocks` | 实际落地的板块 id 列表，应与传入一致 |
| `gaps` | 内容缺口清单：哪个板块、为什么没落地 |
| `layout._gaps` | 同上（在 layout 内，便于随 layout 一起传递） |

> `gaps` 非空不代表失败——它是**可观测的诚实记录**。
> 例如某板块无匹配图表、某段文案缺失、板块库要求 ≥3 条发现但只有 1 条，
> 都会记入 gaps，供 QA-5 核对。渲染前应先看 gaps 是否需要补内容或裁板块。

**图表容量**：每个板块能放几张图有上限，排名板块（B09）5 张（支持多维拆解），
趋势/构成/分布/关联类各 2 张。超出容量的图不会被丢弃，而是收进末尾的
「补充图表」区（`_block="_orphan"`），并逐条记入 gaps（「超出板块 B09 的容量」）。
这条规则的意义：**任何一张算出来的图，要么渲染、要么留痕，不允许静默消失**。

### 4.7 保存

| 动作 | 参数 | 用途 |
|------|------|------|
| `save_report` | `content` / `content_file`、`filename`、`is_binary?`、`output_dir?` | 保存单个产物 |
| `save_with_chinese_name` | 同上 | 保存并生成中文命名副本 |
| `save_index` | `index`、`filename?`、`output_dir?` | 保存看板与报告的关联索引 |

### 4.8 旧版兼容动作

以下动作保留用于向后兼容，**新流程不要使用**：

`select_charts`、`render`、`export_offline`、`generate_insights`、
`review_design`、`review_implement`、`verify_end_to_end`、`final_judgment`、`generate_review_report`

---

## 五、调用失败时怎么办

见 [recovery.md](recovery.md) 的「观测 → 含义 → 下一步」决策表。

**核心纪律**：CLI 失败时**不要**放弃 CLI 改写成内联 Python（`python -c`）。
Windows PowerShell 不支持内联 Python 的引号嵌套，且内联代码绕过了工具层的
异常降级与路径校验。正确做法是按决策表逐层排查。
