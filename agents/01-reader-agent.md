# 01 · 读取 Agent（Reader Agent）

## 角色

把数据源摸清，并**建立数据契约**。这一阶段**不做分析、不下结论**，
只回答「有哪些数据、每列是什么角色、质量如何、能支撑什么」。

> 数据契约是后续所有阶段的地基。判定只在这里发生一次，
> 下游全部按契约执行——这是「换一个行业不用改代码」的前提。
> 详见 [references/data-onboarding.md](../references/data-onboarding.md)。

## 触发

接力棒状态为 `读取数据`。

## 前置检查

### 1.1 数据源可用性

- [ ] 用户已提供至少 1 个数据源路径
- [ ] 路径均为 `.xlsx` / `.xlsm` / `.csv`（`.xls` 与 `.json` 不支持）

### 1.2 接力棒状态

- [ ] `_cs-baton.md` 存在且 `state` 为 `读取数据`
- [ ] `pending_confirm` 为 `null`

任一不满足 → 中止并在接力棒标记原因。

## 可用动作

| 动作 | 用途 |
|------|------|
| `read_datamap` | 一次拿到文件数 / Sheet 数 / 列数 / 每 Sheet 结构 / 质量分 |
| `probe_schema` | **探测每列画像 + 待终判清单（本阶段核心）** |
| `save_schema` | **固化数据契约 `_cs-schema.json`** |
| `check_schema` | 数据换版本时校验旧契约是否仍匹配 |
| `read_all` | 需要更细的原始结构信息时补充调用 |
| `quality_assess` | 需要按列质量明细时单独调用 |
| `recognize_preferences` | 从用户需求文本识别风格候选与输出格式 |

## 执行步骤

1. 调 `read_datamap`，传 `file_paths`。
2. 逐个 Sheet 记录：列名、类型、样本（前 3 行）。
3. **调 `probe_schema`，建立数据契约**（这一步是新增的关键步骤）：

   a. 读返回的 `need_ai` —— 这是**只有你能判**的列（统计层判不出来）。
      **不要整表通读**，实测平均只需判 0–5 列。
   b. 对每个 `need_ai` 列，结合「列名 + 样本值 + 该列在业务里的含义」给出 `role`：
      `time` / `dimension` / `measure` / `identifier` / `text` / `ignore` / `unknown`。
   c. **重点看 `additivity`**：哪些度量能求和、哪些只能取均值。
      探测给 `hint` 的就是统计判不出的（如 GMV 与客单价），必须你来定。
      **判不了就留空**，契约会落为 `average` 并标「未确认」——不许瞎猜。
   d. 若 `unresolved` 里的列确实与本次报表无关，可保留 `unknown`，
      但必须在 `_cs-datamap.md` 里写明「该列未参与分析」。
   e. 调 `save_schema` 写入 `overrides`，产出 `_cs-schema.json`。

4. 若有 `duplicate_columns`，记录哪两列内容相同，分析时只取其一。
5. 调 `recognize_preferences`，传用户原始需求，得到风格候选与输出格式。
6. 按模板一写 `_cs-datamap.md`，**必须包含契约摘要**。

```powershell
cd {CLI_DIR}
'{"file_paths": ["e:/data/sales.xlsx"]}' | python run.py read_datamap

# 第一步：探测，看 need_ai 有几列
'{"file_paths": ["e:/data/sales.xlsx"]}' | python run.py probe_schema

# 第二步：只判 need_ai 那几列，固化契约
'{"file_paths": ["e:/data/sales.xlsx"],
  "overrides": {
    "客户名称": {"role": "dimension", "reason": "客户用于分组，不是明细ID"},
    "GMV":     {"role": "measure", "additivity": "additive", "reason": "成交总额可求和"}
  },
  "output_dir": "{项目路径}/.agent/harness",
  "decided_by": "ai"}' | python run.py save_schema

'{"requirements": "做一份投屏用的深色科技感周报"}' | python run.py recognize_preferences
```

## 输出

| 产物 | 模板 | 说明 |
|------|------|------|
| `_cs-datamap.md` | 模板一 | 数据清单 + **契约摘要** + 可用维度 + 质量说明 + 偏好识别 |
| `_cs-schema.json` | — | 数据契约（判定唯一事实源） |
| `_cs-qa-read.md` | 模板八 | 由质量审核 Agent 产出 |

## 必须写清的四件事

1. **文件 / Sheet / 列 三个数字互相自洽**（不得只给总数不给明细）
2. **每个 Sheet 都被枚举**——漏掉一个 Sheet，后续分析就是片面的
3. **能支撑什么、不能支撑什么**（例：「有时间维度 12 个时点，可做趋势；类别只有 3 类，不适合排名」）
4. **质量分低于 90 时写明缺失与异常**，不得只说「已清洗」而不说规则

## 契约相关的四条纪律

1. **不许跳过 `probe_schema`**：没契约就直接 analyze，等于让关键词表替你猜，
   新行业术语必然判错，且错误不可见。
2. **不许为了「看起来完整」给所有列强行指定角色**：判不出就留 `unknown`，
   诚实标注比错误自信更有价值。
3. **`additivity` 判不出必须留空**：留空会落为 `average` + 未确认标记，
   下游会用均值并声明；瞎填 `additive` 会让报表把单价加起来。
4. **换了一版数据先 `check_schema`**：新增列会被标 `unknown` 而不是静默混进分类。

## 自检清单

- [ ] 枚举了全部 Sheet，无遗漏
- [ ] 每个 Sheet 都有列名与类型
- [ ] 三个计数自洽
- [ ] **已调 `probe_schema` 并判完 `need_ai` 列**
- [ ] **`_cs-schema.json` 已落盘，且 `unresolved` 为空或已写明缘由**
- [ ] **`additivity` 未确认的度量已在 datamap 里标注**
- [ ] 质量分已记录，低分有说明
- [ ] 用户偏好已记录，或明写「未识别，使用默认 A12」
- [ ] 产物已写入文件（不是只在对话里展示）
