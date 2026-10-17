# Changelog

本文档记录 conspect Skill 的版本变更历史。

---

## [v5.1] — 2026-10-17

### 概述：选型不再只给编号

用户反馈原话：**「风格选型时只提供了 A1（推荐），客户都不知道这个 A1 是指什么，
是什么风格，有什么色系，适合什么场景」**。

这不是资产不足——`style-system.json` 里本来就有 `label`（瑞士极简）、`mood`
（克制的秩序，让内容自己说话）、`school`、`keywords`、`report_use.types`、`taboos`。
缺的是**呈现层**：这些字段没有一个被翻译成客户能用来决断的话。

板块选型有同样问题：客户看到 `B01 / B02 / B08`，不知道哪一块是干什么的。

### 新增

| 能力 | 说明 |
|---|---|
| `describe` 字段 | 每张风格卡带 `palette`（色系）/ `form`（形状与字体）/ `mood` / `scenes` / `avoid` / `series_mode` |
| `diff_from_recommend` | 每个备选写明**与推荐款差在哪** |
| `purpose` 字段 | 22 个板块各配一句白话用途，如 B08 →「总量由哪些部分构成，各占多少比例」 |
| `render_style_preview` | 生成候选风格的**可视对比页**（HTML，约 18KB，断网可开） |
| `style_preview.py` | 呈现层模块：色值 → 中文、风格描述、对比页生成 |

### 三个关键设计

1. **色系由色值计算得出，不查表**
   写死 38 条中文描述必然腐坏（资产一增删就失真）。而从 HSL 推导
   `近黑底（带蓝调） + 青强调，多彩并列` 对任何色值恒成立。
   测试断言全部 38 个风格的 `palette` **不得含十六进制**。

2. **中文名打头，编号退后**
   写「瑞士极简（A1）」，不写「A1 瑞士极简」。客户判断风格时不需要先记住编号。

3. **备选必须给差异，否则等于没给**
   同族候选的 `report_use`（场景/密度/载体）是**族级**属性，完全一致。
   只列各自属性，客户会看到四段雷同文字，仍然选不出来。
   实测浅色商务族四个候选：底色全白、场景全同——差异只在**强调色与形状**。

### 同色系靠什么区分：形状与字体

这一条是测试逼出来的。原以为「换个颜色」就够了，实际浅色商务族
A12 / A1 / A8 / A17 全是白底，预览四列长得一模一样。真正区分它们的是：

| 风格 | 圆角 | 标题字号 | 字重 |
|---|---|---|---|
| 扁平无影 A12 | 小圆角 5px | 40px | 粗 |
| 瑞士极简 A1 | 直角 | 56px | 粗 |
| 无碍包容 A8 | 直角 | 40px | 超粗 |
| 包容无界 A17 | 直角 | 44px | 超粗 |

所以对比页按各自 `shapes.圆角` 与 `typography.weights` 真实绘制，
`form` 字段也参与差异判定。

### 修掉的两个资产陷阱

1. **`conic-gradient` 不是页面背景**
   `bg_gradient` 里混着 4 个 `conic-gradient`（如
   `conic-gradient(#0A84FF 0 67%, #1A1A1A 67% 100%)`），语义是**环形进度条**，
   从原稿组件样式里采集来的。铺满页面会变成一个占满屏幕的饼图。
   预览层按语法判类型：只有 `linear-gradient` 才当背景。

2. **退化渐变**
   A12 的 `bg_gradient` 是 `linear-gradient(#2C3E50,#2C3E50)`——首尾同色，视觉上是实色，
   而该风格 `bg` 是 `#FFFFFF`。当成真渐变会让浅色风格渲染成深底。
   在 `style_loader` 加载层归一为 `None`（一处修好，所有消费者受益，资产重新生成也不会复发）。

### 呈现层的两条铁律（写进 Agent 文档）

- 风格卡：中文名在前、色系用中文、必须附对比页
- 板块卡：每个板块带 `purpose`，不写裸编号

### 数字

| | v5.0 | v5.1 |
|---|---|---|
| 单测 | 225 | **260** |
| 新增模块 | — | style_preview.py |
| 新增 CLI | — | render_style_preview |

新增 35 个测试专盯呈现层：`palette` 无十六进制、`card_text` 首行是中文名、
`diff_note` 永不为空、conic 不进预览、每列用自己的 token、对比页无外链。

---

## [v5.0] — 2026-10-17

### 概述：从「关键词猜」到「契约驱动」

v4.x 的一条隐性假设是「靠中文关键词表就能认出列的角色」。这个假设在真实使用中站不住：
每来一个新行业、一套新术语（GMV、客单价、到店人次、POI 数、体积重），关键词表就漏一个，
而漏掉的表现是**报表里的数字错了却不报错**。更要命的是同一个判断散落在三处——

| 位置 | 判断方式 |
|------|---------|
| `data_processor.identify_dimensions` | 按 dtype + 70 个中文关键词 |
| `chart_advisor._usable_metrics` | 再用 `NON_METRIC_HINTS` 黑名单拦一次 |
| `ai_agent._features_from_analysis` | 又过滤一次标识列 |

三处不一致时下游拿到矛盾结论，且每加一个行业要三处同时改。这是「补丁套补丁」，
永远补不完。v5.0 的做法是**分层**：判定只发生一次，结果固化成契约，全链路只读契约。

### 一、新增三层架构

```
D 探测层  conspect_tools/schema_probe.py        只看数据，产出可复算的统计事实
S 判定层  judge_by_stats + AI 终判               硬证据直接定，模糊地带显式交出去
C 契约层  conspect_tools/schema_contract.py      落成 _cs-schema.json，全链路唯一事实源
E 计算层  data_processor / chart_advisor          按契约算，不再自行猜测
```

**关键设计决定：允许说「不知道」。**
探测层对判不出的列返回 `low` 置信或 `unknown` 角色，而不是硬塞进「分类」。
这不是能力不足的妥协，而是把错误从「静默发生」变成「显式可审」——
一张 29 列的表里有 2 列没判定，比 29 列都判了但错 3 列要安全得多。

### 二、七种角色 + 可加总性

| role | 下游能做什么 |
|------|-------------|
| `time` | 趋势、时间序列聚合 |
| `dimension` | 分类聚合、排名、构成 |
| `measure` | 求和 / 均值（受 additivity 约束） |
| `identifier` | **只能计数**，不得求和、不得当分类维度出图 |
| `text` | 不参与数值分析 |
| `ignore` | 全空 / 常量，完全不参与 |
| `unknown` | **不参与分析，但必须在报表中明示** |

`additivity` 对 measure 分 `additive`（可求和）/ `average`（只能取均值）。

### 三、探测层的硬证据判据

以下判断**不看列名**，只看数据本身：

| 判断 | 判据 |
|------|------|
| 时间列 | 日期可解析率 ≥90%（含中文「2025年06月27日 15:27」） |
| 全空 / 常量 | unique=0 / unique=1 |
| 电话、证件号 | 全唯一 + 整数 + ≥8 位 |
| 地址、链接、文件名 | 全唯一 + 平均 ≥20 字 |
| 枚举维度 | 2–30 类且类别数/总行数 <5% |
| **数值即度量** | dtype 是数字（唯一例外：仅 0/1 两值的整数列判维度） |

最后一条是重要修正：早期版本先判「低基数枚举」，导致「就诊人次」（1~3）、
「课时数」（1–5）、「不良数」（0–30）这类**小整数计数列被当成枚举维度**。
dtype 是硬信息，数值列必须优先当度量。

### 四、additivity 交给契约，不靠统计硬猜

**能力边界必须诚实**：GMV 与客单价都是正小数、都右偏分布，统计特征几乎一样，
但前者求和有意义、后者求和毫无意义。任何用分布形状区分二者的规则都是猜。

实测 22 个真实度量列，纯统计只能判对 9 个（40.9%）。所以：

- 探测层对判不出的度量返回 `hint`（不是 `unknown`，明确表示「统计判不了」）
- 契约落 `average`（安全侧：宁可少算总额，也不要把单价加出天文数字），
  并标记 `additivity_confirmed: false`
- 报表口径**必须**声明「该指标可加总性未确认，已按均值处理」

### 五、新增 CLI 三个动作

| 动作 | 用途 |
|------|------|
| `probe_schema` | 探测每列画像 + 待终判清单（不写盘） |
| `save_schema` | 合并终判，固化 `_cs-schema.json` |
| `check_schema` | 换数据后校验旧契约是否仍匹配 |

`probe_schema` 的 `need_ai` 是关键设计：只列**真正需要人判**的列（`low` 置信）。
早期版本把所有非 `high` 都塞进去，23 列的表会要求复核 18 次——那是无效劳动。
实测 8 个行业，`need_ai` 平均只有 0–5 列。

### 六、计算层改为读契约

- `identify_dimensions(df, contract=)` 优先按契约映射；无契约才走启发式，
  且返回值带 `_provenance` 标明来源（`contract` / `auto_contract`）
- `chart_advisor` 的度量筛选、维度筛选、可加总性、事实表判定全部支持 `contract` 参数；
  关键词表降级为「无契约时的兜底」
- `analyze` 新增 `schema_file` 参数，统计聚合按 `additivity` 选 `sum`/`mean`
  （原来一律 `sum`，会把单价加起来）
- `data_issues` 新增三类语义议题：角色未判定、内容重复列、标识列被当维度

### 七、修复

| 缺陷 | 后果 | 修法 |
|------|------|------|
| `_usable_metrics` 的 `provenance` 在循环内初始化 | 无度量列时循环不执行 → `UnboundLocalError` 被吞 → 图表静默为 0 | 提到循环外初始化 |
| 缺口不分级 | 「无图可画」与「文案待补」混报，QA-5 无法聚焦阻塞项 | 加 `severity`：`blocking` / `content` / `info` |
| B16 无风险输入的合规降级被当缺陷 | 板块库明确要求写「未识别到显著风险」，却报成缺口 | 标 `info` |
| 报表顶部 header 与封面板块重复 | 第一屏出现两次标题、两次数据源 | 有 cover 板块时不渲染 header |
| 小样本表直接判不可分析 | 18 行部门表跑不出报表 | 有可加总度量时降级为「描述性简报」并标 `small_sample` |

### 八、跨行业验证（8 个行业 / 59 关键列 / 22 度量列）

| 路径 | role 准确率 | additivity 准确率 | AI 需看的列 |
|------|-----------|------------------|-----------|
| 纯统计（无干预） | **100%** | 40.9%（其余显式标 hint） | — |
| AI 终判后 | **100%** | **100%** | 平均 2.75 列（0–5） |

行业覆盖：零售电商（GMV/客单价/退款率）、医疗门诊（ICD 编码/身份证/就诊人次）、
物流运输（里程/体积重/时速）、教育培训（课时/出勤率/成绩）、制造业（不良率/单件成本）、
脏数据混合（中文日期/千分位/全角空格/混合类型）、宽表稀疏（120 列 90% 缺失）、
小样本（18 行）。

端到端：8/8 全部通过，39 张图、离线自包含、标题去重。
补全 narrative 后缺口为 0（剩余缺口全为文案缺失，无 `blocking`）。

### 九、测试与文档

- 单测 190 → **225**。新增 `test_schema_contract.py`（30 个），
  `test_layout_assembly.py` 增 5 个缺口分级用例
- 一致性校验 15309 → **16153** 项，新增「契约协议一致性」检查：
  文档承诺的 role / additivity 取值必须与代码逐项一致（防「文档说支持 A、代码只认 B」）
- 新增 `references/data-onboarding.md`：讲清四层架构、角色体系、三层兜底、
  能力边界与实测数据
- `agents/01-reader-agent.md` 新增「建立数据契约」为必经步骤；
  `agents/02-analyzer-agent.md` 要求核对 `_provenance` 与 `additivity_confirmed`
- 产物清单新增 `_cs-schema.json`

### 十、迁移提示

v4.x 的调用方式仍可用，但会走 `auto_contract` 路径：

```powershell
# 推荐：先建契约
'{"file_paths": ["x.xlsx"]}' | python run.py probe_schema
'{"file_paths": ["x.xlsx"], "overrides": {...}}' | python run.py save_schema
'{"file_paths": ["x.xlsx"], "schema_file": "_cs-schema.json"}' | python run.py analyze
```

不建契约直接 `analyze` 不会报错，但 `dimensions._provenance.source` 会是
`auto_contract`，报表口径需声明「判定未经复核」。

---

## [v4.2] — 2026-10-17

### 概述

用第二份真实业务数据（`诊所拜访表.xlsx`，2500 行 × 29 列）做验收时，暴露出 v4.1 吃不下的
两类数据形态与一条数据丢失路径。这份表的特征与销售明细完全不同：**没有任何金额/数量度量**
（唯一的数字列是电话号码），日期是中文格式字符串，29 列里 20 列是标签枚举。
v4.1 在它上面只能产出 3 张图，其中两张还是「平均联系方式」这种荒谬指标。

本次把「无度量流水表」「中文日期」「标识列误判」三类问题一并解决，并补掉一条静默丢图路径。

### 一、支持中文日期（原解析率 0/2500）

`填写时间（自动）` 的值是「2025年06月27日 15:27」，`pd.to_datetime` 直接解析
**2500 条全失败**——不报错、只表现为「报表里没有趋势图」。

- 新增 `_to_datetime()`：先做中文年月日归一（年/月→`-`，日→删除），再按 8 种常见格式
  逐个精确尝试，取命中最多的一种
- 同一列混着不同精度（有的到秒、有的到分）时，用其余格式逐轮补齐剩余空位
- 全部失败时再用正则兜底，仍失败返回 NaT 而不是抛错
- 实测解析率 0/2500 → **2500/2500**，跨度 561 天，产出 19 个月节点的趋势图

> 实现时踩到一个坑：`str.replace(r"\s*日", "", regex=False)` 会把 `\s*日` 当**字面量**匹配，
> `日` 根本没被删掉，归一结果成了 `2025-06-27日 15:27`，后续解析依然全空。
> 必须 `regex=True`。这个错误只有实测才会暴露。

### 二、无度量表退化为「记录数」计数

拜访流水、工单、日志这类表没有金额可求和，分析对象就是记录数本身。
原实现「无可用指标 → 返回空图表列表」，导致整表一张图都出不来。

- 新增 `COUNT_MIN_ROWS = 100`：无可行度量但行数达标的表，以「记录数」为分析指标
- `table_role` 增加 `measure` 字段：`amount`（金额型）/ `count`（记录型）/ `none`（维表）
- 记录型表行数 ≥100 判为 `fact`，维表（30/24/15/8 行那种）仍为 `dimension`
- 时间序列与分类聚合都支持 count 语义（`groupby.size()`）

### 三、标识列不再被误判为指标

`联系方式` 是 int64、2500 个唯一值，被当成指标后产出
「平均联系方式按销售漏斗排名」「平均联系方式分布」——纯属荒谬。

- `NON_METRIC_HINTS` 扩充：电话/手机/**联系方式**/邮箱/地址/经纬度/坐标/编号/序号/
  邮编/卡号/身份证/代码/**照片**/**图片**/**链接**/url/lng/lat
- `_features_from_analysis` 同样过滤，避免电话号码抬高 `numeric_count` / `distinct_max`，
  把 B11（分布）等板块误触发而实际无图可画

### 四、图表维度择优

原实现按「类别数升序」取前 2 个维度，结果选中了缺失 40% 的二元标签，反而漏掉「省」（26 类）
与「销售漏斗」（6 类）这类真正有业务含义的维度。

- 排序改为：**漏斗/阶段维度最前** → 业务相关性 → 覆盖率（≥95% 优先）→ 类别数（3–10 最宜）
- 分类维度上限从 20 放宽到 50（排名可用 Top10，构成图另有 6 的上限）
- 内容完全相同的重复列去重（如「填写人」与「填写人(人员)」取值一致）
- 列名含「漏斗/阶段/转化」且 ≤8 类时用 `funnel` 图，柱状图看不出逐级收敛
- 构成图跳过已被排名图用掉的维度，避免「漏斗图 + 同一维度环形图」的重复内容

### 五、修复静默丢图

`consumed` 集合把**绑定给某板块的全部图表**预先算作已消费，用于防止其他板块借用。
但孤儿判定也用了它，于是「有归属、却超出该板块容量」的图既没渲染、也不进补充区、
更不记缺口——**凭空消失**。第二份数据的 6 张候选图实际只渲染了 4 张才暴露出来。

- 新增 `used` 集合记录「真正渲染的图」，孤儿判定改用 `used`
- 新增 `block_library.CAPACITY`：排名板块（B09）容纳 5 张（多维拆解），
  趋势/构成/分布/关联各 2 张
- 超出容量的图进「补充图表」区，并记缺口「超出板块 B09 的容量」
- 原则：**任何一张算出来的图，要么渲染、要么留痕，不允许静默消失**

### 六、选型阶段预演图表绑定

新增 `_drop_unservable()`：按与装配一致的规则（绑定独占 + 降级链匹配 + 一图一用）
预演一遍绑定，把「触发条件成立但没有图可画」的板块提前裁掉并注明原因。

- 裁出原因区分两类：「无可用图表」与「超出板块上限」，提示语不再混为一谈
- B06（迷你趋势卡）改为**暂不启用**：引擎没有 sparkline 组件，
  硬选进来只在装配阶段留一个空洞缺口。趋势统一由 B07 承载，文档已注明恢复条件

### 七、测试

- 单测 168 → **190**。`test_chart_advisor.py` 增 13 个（中文日期 5 / 计数度量 5 / 漏斗与维度择优 3），
  `test_layout_assembly.py` 增 9 个（图表容量与不丢失 3 / 选型预演 6）
- 三个校验器仍全通过：资产 342 项、一致性 15309 项、单测 190 个

### 八、第二份真实数据验收

`E:/skill_example/诊所拜访表.xlsx`（2500 行 × 29 列）五阶段实跑：

- 事实表判定：`fact` / `measure=count`（2500 行流水，以记录数为指标）
- 图表候选 6 个：趋势 1 / 漏斗 1 / 排名 3（经营标签、合作潜力、优先级）/ 构成 1
- 数据议题 11 条：6 项标签缺失超 34%、4 个逐行唯一列（GSP位置/经纬度/图片/链接）
- 板块 14 个，装配缺口 **0**，6 张图全部渲染，8 项渲染自检全通过
- 产物离线自包含（ECharts 内联），轴标签对比度达标

真实数据暴露的业务事实（已写入报表）：
优先级 A 客户成交率 **14.6%** 反而低于 B 客户 **16.7%**——分级体系未起到筛选作用；
KP 标签填写率仅 75.2%，近四分之一拜访未记录关键人，直接拉低「已试用→已成交」转化。

---

## [v4.1] — 2026-10-17

### 概述

v4.0 交付时留有 P1 功能缺口：`build_dashboard_layout` 收了 `blocks` 参数却不据此装配，
且 `analyze` **根本不产出 charts**。用真实业务数据实跑（72 行销售明细 + 4 张维表）时暴露：
整份报表只剩文字板块、零图表。本次把「数据 → 图表 → 板块 → 版面」这条链路打通，
并把三个只在真实数据下才现形的缺陷一并修掉。

### 一、打通装配链路（原 P1）

- `build_dashboard_layout` 新增 `blocks` 参数并**真正驱动装配**：板块顺序即页序，不重排不增删。
  支持板块 id 列表与 `select_content` 返回的板块 dict 两种入参。
- 装配改为**按图表类型绑定**，不再按标题关键词分组（原 `_group_charts_by_theme` 仅作无 blocks 时的兼容路径）。
- 一个板块可容纳多张同类图表（趋势/排名常有多张），避免其余图表沦为孤儿。
- 未绑定板块的图表收进「补充图表」区并在 `gaps` 登记，**数据不静默消失**。
- 返回新增 `mode` / `blocks` / `gaps`：缺图表、缺文案、条目数不足都如实记录，供 QA-5 核对。

### 二、新增图表建议器（`conspect_tools/chart_advisor.py`）

`analyze` 现在为每个 Sheet 产出 `charts`（含 `chart_type`/`title`/`data`/`description`/`block`），
图表由代码基于真实数据算出，不再依赖 Agent 手搓。内置三条业务规则：

| 规则 | 内容 |
|------|------|
| 可加总性判别 | 数量/金额求和；单价/比率/**单位成本**取均值。原实现会把单位成本求和，得出荒谬的巨额成本 |
| 健康度过滤 | 缺失 >30% 的列不参与聚合（否则 sum 严重低估）；排除全空列、常数列、电话/编号类标识列 |
| 时间自算 | `aggregated.by_dimension` **不含时间维度**，趋势图按时间分组重算；跨度 >3 年不画趋势（多为属性日期） |

同时产出 `data_issues`（全空列/高缺失列/疑似明细ID/常数列，每条带可执行建议）
与 `table_role`（`fact` / `dimension`，报表主线只取事实表）。

### 三、修复的既有缺陷

| 缺陷 | 后果 | 修法 |
|------|------|------|
| `DataProcessor.assess_quality` **方法不存在** | 被 try/except 吞掉，质量分恒为 `None`，选型阶段拿不到数据可信度信号 | 实现该方法：按列完整度加权（数值列权重 1.5）折算百分制 |
| 顶层质量分取各表**平均** | 主表 83 分被维表 100 分抹平 | 改取**最差表**分，并返回 `quality_by_sheet` / `quality_sheet` / `quality_avg` |
| `pd.cut` 缺 `retbins=True` | 解包得到两个数值而非 (counts, bins)，分布图必然失败后被 `except: pass` **静默吞掉** | 补 `retbins`；并把裸 `except` 改为记录到 `warnings` 上报 |
| 风格选型置信度按**风格级** gap 计算 | `report_use` 是族级属性，同族必然并列，导致恒为「低置信度 / 0 分差」 | 改按**族级** gap 计算；返回 `family` / `family_label` / `family_ties`，族内择一由默认偏好决定并如实说明 |
| `select_style` 不知道内容是什么 | 风格推荐与实际板块无关 | 新增 `blocks` 参数，按「推荐板块 ∩ 实际板块」计算契合度加分 |
| 关键词打分因 `score` 未取整 | 返回 `9.120000000000001` 之类的浮点尾巴 | 打分 `round(score, 2)` |
| 图表 `id` 按数据 hash 生成 | 两张数据相同的图会撞 id，后一个 `echarts.init` 拿到同一 DOM，图不渲染 | 改为「数据指纹 + 递增序号」，表格 id 同理 |
| 散点图 `symbolSize: [5,50]` | ECharts 按数据第 3 维映射大小；只有 `[x,y]` 时会用 y 值映射，销量 8~350 导致点大小差百倍、图不可读 | 仅当数据真有第 3 维才启用大小映射，否则固定 9px |
| 图表轴刻度用 `text_secondary` | 该色是为版式留白设计的浅灰（如 A12 的 `#9AA2AB` 对白底仅 **2.58:1**），12px 刻度在投影上几乎看不见 | 渲染层新增 `_readable()`，按背景自动加深到 ≥4.5:1，不改资产 |
| B08 按 `category_count` **最大**值判定 | 「所在城市」15 类会让 B08（结构构成）整块被误排除，而「产品类别」只有 4 类本可成图 | 改用 `category_min`（缺省回退到 `category_count`，兼容旧调用） |
| 报表依赖 CDN 加载 ECharts | 断网、内网、邮件附件打开时**没有任何图表**——投屏现场即事故 | 内置 `assets/vendor/echarts.min.js`（0.98MB）并默认内联，产物离线自包含 |
| B04 与 B06 用同一批 KPI | 迷你趋势卡把整组 KPI 重复渲染一遍，页面出现两行一模一样的指标 | B06 只取 B04 未覆盖的指标；无剩余则如实记 gap，趋势交给 B07 |
| 多图板块纵向堆叠 | 两张趋势图各占满行，占用两屏且留白过大 | 多图时统一 `span=1` 并排 |
| 目录导航 16 项单栏竖排 | 占掉一整屏，信息密度过低 | 改两栏 |

### 四、板块库与引擎能力对齐

板块库用业务语言描述图表（「帕累托 / 瀑布」「旭日 / 树图」），引擎只认 15 种 `chart_type`。
新增显式映射层：

- `ENGINE_CHARTS`：引擎真实支持的类型（与 `ChartBuilder.build` 分派表**逐项一致**，由校验脚本比对）
- `DECLARED_CHART_ALIASES`：声明词 → 降级链。帕累托/瀑布/直方图/箱线 → `bar`，旭日 → `treemap`，K 线 → `line`
- 声明词做空格归一（`K 线` 与 `K线` 不再漏配）
- `select_content` 为每个板块返回 `engine_charts` 与 `chart_notes`，**降级在选型阶段就可见**
- 「指标卡 / 表格 / 迷你折线」属非图形态，不计入降级说明

### 五、序列色可区分性校验（原 P2）

新增 `series_clash` 判据，不简单比色相——同色系深浅是合法手法，机械比色相会误伤：

- 两者都是灰阶 → 只看明度差（≥20）
- 一灰一彩 → 饱和度已提供区分度，判为可区分
- 都是彩色 → 色相差 ≥20° 即通过；否则要求明度差 ≥22

据此修掉三族的真实缺陷（`biz` 靠 27 的明度差合法通过，未误伤）：

| 族 | 原冲突 | 处置 |
|----|--------|------|
| glass | `#A0A8FF` × `#8A6DF2`：色相差 18.1°、明度差 12.5 | 改 `#7EE787`（补色相环绿区缺口） |
| editorial | `#C9A227` × `#B76E2E`：色相差 17.5°、明度差 2.2 | 改 `#7A8450` 橄榄绿 |
| organic | `#E9C46A` × `#D4A373`：色相差 12.8°、明度差 2.4 | 改 `#D98CA0` 柔和玫瑰 |

### 六、测试与校验

- 单测 113 → **162**。新增 `test_chart_advisor.py`（22 个）、`test_layout_assembly.py`（14 个），
  `test_block_library.py` 增 7 个图表能力用例，`test_style_system.py` 增 6 个色相判据用例。
- 资产校验 336 → **342** 项：新增族序列两两可区分、板块图表声明可映射、
  `ENGINE_CHARTS` 与引擎分派表一致三项。
- 一致性自检保持 **14953** 项全通过。

### 七、文档

- `references/cli-usage.md`：补 `analyze` 返回字段表、`select_content` 的图表能力、
  `select_style` 的 `blocks` 与族级置信度、`build_dashboard_layout` 的 `gaps` 用法
- `agents/02-analyzer-agent.md`：新增「图表候选的来源（不要手搓）」与 `data_issues`/`table_role` 处置
- `agents/03-content-selector-agent.md`：新增图表可用性核对步骤与两条执行约束
- `agents/05-renderer-agent.md`：新增 gap 处置步骤与装配完整性校验
- `agents/04-style-selector-agent.md`：说明族级置信度的正确理解与 `blocks` 传参

### 八、真实数据验收

`E:/skill_example/企业销售明细数据表.xlsx`（72 行销售明细 + 4 张维表，23 列）五阶段实跑：

- 事实表判定：销售明细 `fact`，其余 4 张 `dimension`
- 图表候选 7 个（趋势 2 / 排名 2 / 构成 1 / 分布 1 / 散点 1），全部带板块绑定
- 板块 16 个，装配缺口 **0**，HTML 34,766 字符，9 项渲染自检全通过
- 数据议题 4 条：销售额/毛利/毛利率缺失 66.7%、实际成交价全空

真实数据暴露的业务陷阱（已写入报表口径说明）：
销售额字段仅 24/72 有值，直接求合计 58.7 万，按「数量×单价×(1−折扣率)」派生为 160.9 万，
**低估 63.5%**。这类问题不靠派生或如实声明口径，报表就会给出错误结论。

---

## [v4.0] — 2026-10-17

### 概述

本次是一次**范式换代**：报表风格从「8 个硬编码配色字典」升级为「38 风格 × 6 族的分层资产库」，
报表内容从「KPI + 图表 + 结论」升级为「22 板块的可选内容库」，
状态机从 9 阶段重划为 5 阶段，并在两个选型环节加入用户确认。

### 一、阶段重划：9 → 5

| 旧阶段 | 新归属 |
|--------|--------|
| 开始 | → 读取数据（偏好识别并入） |
| 分析 | → 分析数据 |
| 洞察生成 | → 分析数据（伪阶段，不过门，合并为收尾步骤） |
| 设计 | **拆分** → 汇报内容选型（内容/图表/板块） + 报表选型（配色/字体/版式） |
| 设计审查 | → 报表选型（伪阶段，不过门，合并为自审节） |
| 实现 | → 生成报表（渲染部分） |
| 报告生成 | → 生成报表（多格式部分） |
| 验证 | → 生成报表（由阶段降为内核验回路） |
| 完成 | → 完成（保留为终止态） |

**质量门不再是阶段**：5 个阶段配 5 道门（QA-1 ~ QA-5），门是阶段之间的检查。

### 二、新增两个强制确认点

- **内容确认**：`_cs-content.md` 产出后，用户可「按此生成 / 增删板块 / 重新选型」
- **风格确认**：`_cs-style.md` 产出后，用户可「就用推荐 / 换风格 / 换族重选」

实现方式为接力棒的 `pending_confirm` 字段（`null|content|style`），非 null 时禁止推进。
状态枚举保持 5 个，不用「待确认」状态占位。

### 三、风格资产体系（全新）

- **38 风格 × 6 族**，替换原有 8 套硬编码主题（`ocean/warm/aurora/forest/minimal/bento/editorial/aurora_dark` 全部移除）
- 族按**报表使用场景**划分：商务通稿 / 数据大屏 / 玻璃光影 / 纸感编辑 / 自然柔和 / 表达张力
- **三级渐进式加载**：L0 总目录 → L1 族索引 → L2 单份正文
- **唯一事实源** `assets/style-system.json`，三份 md 全部由 `tools/gen_style_assets.py` 生成
- 每份 L2 正文统一 9 节，其中「图表配色序列 / 报表版式建议 / 数据展示禁忌」三节为报表场景新增
- **资产引用门控**：生成前必须声明 `[资产引用] {编号}→{风格名}`
- 剔除 11 个不适合静态数据报表的风格（6 个交互型 + 5 个与数据展示冲突），剔除理由记录在 manifest

### 四、报表板块库（全新）

- **22 板块 × 6 族**：开场 3 / 指标 3 / 分析 8 / 结论 3 / 说明 3 / 收尾 2
- 每板块带**触发条件**（可执行判定），满足才纳入
- 7 个必需板块无条件出现；分析族至少保留 2 个（防止裁剪把分析全砍掉）
- 新增 `prose` 板块类型，承载 11 个非图表板块，替代原先的 `custom` 逃生舱

### 五、代码

- 新增 `conspect_tools/style_loader.py`（资产加载与主题翻译）
- 新增 `conspect_tools/block_library.py`（板块库解析与触发判定）
- `render_engine.py`：删除 `ColorTheme.THEMES` 硬编码，改由资产层提供；新增 `_render_prose()` 与 `prose` 分支；间距随数据密度自适应
- `ai_agent.py`：新增 `select_content_plan()` 与 `select_style_card()`；配色关键词映射改为 38 风格编号；阶段枚举 `design/implement` → `style/render`
- `run.py`：新增 `read_datamap` / `select_content` / `select_style` / `list_styles` / `list_blocks` 五个动作
- 新增 `tools/import_sz_styles.py`、`tools/gen_style_assets.py`、`tools/check_style_assets.py`

### 六、修复的既有缺陷

- `render_engine.py` 模板误写 `@@keyframes`，导致全部入场动画从未生效 → 改为 `@keyframes`
- `agents/07-report-designer-agent.md` 阶段字段自相矛盾（旧 `设计` vs `报告生成`）→ Agent 重编后消除
- `SKILL-execution.md` 回退表漏 `REPORT_ISSUE` 行 → 回退边重写为 8 条完整清单
- `load_json` / `load_text` 遇空路径抛 `PermissionError` → 已在前一版本修复，本版回归测试覆盖

### 七、产物清单

23 项 → 21 项。新增 `_cs-datamap.md` / `_cs-content.md` / `_cs-style.md` / `_cs-render.md`；
删除 `_cs-design.md` / `_cs-design-review.md` / `_cs-implement.md` / `_cs-export.png` 及对应 QA 报告。

### 八、Agent

10 个 → 7 个，与 5 阶段一一对应：主控 / 读取 / 分析 / 内容选型 / 报表选型 / 渲染 / 质量审核。
原 `visual-designer`、`report-designer`、`report-implementer`、`ai-reviewer` 的职责分别并入
报表选型、渲染与质量审核。

### 九、测试

52 → 113 个。新增 `test_style_system.py`（资产完整性与对比度）、
`test_block_library.py`（板块解析与裁剪规则）、`test_render_engine.py`（38 风格渲染 + prose）。

---

## [v3.2] — 2026-10-16

### 概述

本次升级是一次**结构治理**：v1 到 v3.1 的迭代一直是「追加式」修改，旧内容从不删除，
导致同一事实在 4–5 处各写一遍，规则只能用「违反即无效」这类恐吓表达，
而恐吓本身又没有任何机制能检出。结果是投入了大量约束文字，换来一批自相矛盾。

v3.2 的做法不是继续加规则，而是**给规则找落点**：
把重复收拢为单一事实源、把假机制换成真机制、把不可检出的禁令换成可运行的自检脚本。

### 一、消灭自相矛盾（P0）

| # | 问题 | 处理 |
|---|------|------|
| 1 | 技能自身使用 emoji，却把 emoji 定为 P0 阻断 | 清除 `SKILL.md`（6 处）与 `README.md`（6 处）的 emoji；禁令措辞明确限定为「生成的产物文件」 |
| 2 | 完成阶段会把最终汇总报告写进 `_cs-report.md`，覆盖分析报告 | 完成阶段产物改为 `_cs-final-report.md`；两处明确说明二者不可互相覆盖 |
| 3 | 长文本无法作为命令行 JSON 字面量传入，报告/看板生成链路实际不可执行 | `run.py` 的 `save_report` 与 `save_with_chinese_name` 新增 `content_file` 参数（优先级高于 `content`）；读取时归一化换行，避免 Windows 下写出 `\r\r\n` |
| 4 | 文档要求「调用 `ReportRenderer.render_xxx()`」，但同一技能又禁止写 Python | 改为 CLI 流程：`render_report` → 写临时文件 → `save_report --content_file` |
| 5 | 接力棒字段在 Agent 与协议间不兼容（Agent 要求 `phase`/`current`，协议只有 `state`） | 统一为唯一状态字段 `state`；新增「阶段清单」章节承接子 Agent 自检记录 |
| 6 | `tests/test_ai_agent.py` 整份文件照着不存在的 API 写（调用全仓不存在的 `to_dict()`、字段名全错） | 依真实签名重写，新增字段契约测试防止再次漂移 |
| 7 | `tests/test_report_renderer.py` 按两参调用、断言写盘，与实现签名不符 | 依真实签名重写（渲染方法只返回内容，写盘由 Exporter 负责） |
| 8 | `tests/test_review_data_loader.py` 同样与实现不符，并暴露 `load_json` 遇空路径抛 `PermissionError` 的真实缺陷 | 重写测试；`load_json` / `load_text` 改用 `is_file()` 判断并守卫空路径 |
| 9 | 数据源格式能力边界矛盾（主文档说 `.xlsx/.xls/.csv`，chunk 说还支持 `.json`） | 实测确认真实支持范围，统一为 `.xlsx` / `.xlsm` / `.csv` |

### 二、数据源能力：补齐 `.csv`，如实声明 `.xls` / `.json`

实测发现 `data_processor.load_excel()` 硬编码 `pd.ExcelFile(path, engine='openpyxl')`，
把一切输入当作 xlsx 压缩包解——**`.csv` 与 `.json` 均抛 `BadZipFile`，实际只支持 `.xlsx`**。

- 新增 `.csv` 分支（`pd.read_csv`，依次尝试 utf-8-sig / gbk / utf-8），兑现文档承诺
- `.xls`（BIFF 格式，openpyxl 无法读取）与 `.json` 改为抛出**带指引的可读错误**：
  「不支持旧版 Excel 格式 .xls，请另存为 .xlsx」
- `config.py` 的 `supported_extensions` 由 `[".xlsx", ".xls", ".csv"]` 修正为 `[".xlsx", ".xlsm", ".csv"]`
- 新增 `requirements.txt`（此前环境不可复现）

### 三、单一事实源

- 新增 `artifacts/artifact-manifest.yaml`：**产物清单的唯一权威定义**
  （含阶段、必需标记、模板位置、中文副本映射）
- `SKILL.md`、`SKILL-execution.md`、`protocols/baton-protocol.md`、
  `agents/00-master-controller.md` 的产物清单一律改为引用它，删除原有 4 份互相矛盾的副本
- 状态机定义收敛到 `SKILL.md` 第三节；`protocols/phase-protocol.md` 只保留流转规则并引用之
- 审核报告命名统一为 `_cs-qa-{phase}.md`，废弃并存的 `_cs-ai-review-{phase}.md`
- 待办统一记录在接力棒「待办清单」章节，废弃独立的 `_cs-todo.md`

### 四、废除纸面分块机制，改为显式阅读路由

`SKILL.chunks/` 声称 `load_on_demand` / `auto_unload` / `max_active_chunks`，
但在整个 `.py` 中**零实现**，是纯纸面约定；且其内容与 SKILL.md、agents 大量重叠并存在冲突
（如声称后端为 Flask/FastAPI、`.json` 受支持）。

- 归档 `SKILL.chunks/` 全部 6 个文件
- 其中确有价值的内容迁移为正式参考文档：
  - 21 行图表类型映射表 → `references/chart-selection.md`
  - 商务视觉规范（配色/字体/布局/解读区样式）→ `references/visual-spec.md`，并修正 Flask/FastAPI 的错误描述
- `SKILL.md` 改为「按需阅读指引」表：**触发条件 → 读哪一份**，替代原「渐进式分块加载」章节

### 五、新增文件

| 文件 | 用途 |
|------|------|
| `artifacts/artifact-manifest.yaml` | 产物清单唯一事实源 |
| `references/cli-usage.md` | CLI 定位、三种传参方式、`content_file` 用法、完整 30 个动作清单 |
| `references/recovery.md` | 「观测 → 含义 → 下一步」故障恢复决策表（替代 90 行散文式说明） |
| `references/visual-spec.md` | 商务视觉规范 |
| `tools/check_refs.py` | 一致性自检：引用完整性 / emoji 禁令 / 产物清单 / 版本号 |
| `requirements.txt` | Python 依赖声明 |

### 六、文体与纪律调整

- 删除「违规即本 Skill 无效」「用户可判定本 Skill 无效」等恐吓式条款；
  数据安全的**实质约束**（数据不出本地、原始明细不上前端、只读、日志不落地）全部保留
- CLI 失败处理由长篇散文改为决策表，并明确「不要改用内联 Python 绕过」
- 验证链升级为**证据分级**：已确认 / 推断 / 未核实 / 未知；补入「CLI 未命中 ≠ 数据不存在」口径
- 清理 `[WARN]` / `[OK]` / `[禁止]` 等占位标签的过度使用与句中错位
- 修正 `agents/06` 的口语化措辞

### 七、篇幅与结构

| 指标 | v3.1 | v3.2 |
|------|------|------|
| `SKILL.md` | 622 行 | **350 行** |
| `SKILL-execution.md` | 1154 行 | 728 行 |
| 全量 Markdown | 约 6200 行 | 约 3300 行 |
| 产物清单定义处 | 4 处（互相矛盾） | 1 处 |
| 状态机定义处 | 5 处 | 2 处（契约 + 引用） |
| `SKILL-execution.md` 章节编号 | 含 `7.4x` / `7.5x` 非标准序号 | 顺延重编为 6.1–6.9 |

### 八、测试

| 项 | v3.1 | v3.2 |
|----|------|------|
| 可运行测试 | 3 个文件无法运行或断言必失败 | **52 个测试全部通过** |
| 覆盖 | 未触及 CLI 分发、格式分派、`content_file` | 新增格式契约、`content_file` 端到端、CSV 编码、审核上下文边界 |

### 兼容性

- **向后兼容**：所有旧 CLI 动作继续可用（`select_charts` / `render` / `export_offline` 等已标注为旧版兼容）
- **产物兼容**：`_cs-` 前缀与既有文件命名不变；新增 `_cs-final-report.md` 与 `_cs-report-design.md`
- **状态机兼容**：`phase` / `current` 字段不再使用，统一读 `state`；旧接力棒按 `state` 续跑
- **破坏性变更**：`.json` 数据源不再被静默接受（此前会以 `BadZipFile` 崩溃），现返回明确错误

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
4. **配色主题扩展至 8 套**（配色规范见 `references/visual-spec.md`）
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
