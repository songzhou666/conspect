# 触发机制与使用指南

> 本文档定义 conspect Skill 的触发机制和使用方法，包括自然语义触发、命令触发、程序化调用和功能选择决策。

---

## 一、自然语义触发

| 意图 | 典型触发词 |
|------|-----------|
| 报表生成 | "生成报表"、"做报表"、"出报表"、"汇报" |
| 数据看板 | "看板"、"数据大屏"、"dashboard"、"驾驶舱" |
| 数据分析 | "分析数据"、"数据分析"、"数据透视"、"复盘" |
| 图表可视化 | "画图"、"出图"、"做图"、"可视化"、"图表" |
| Excel 处理 | "Excel"、"表格分析"、"多表合并"、"数据源" |
| 商务汇报 | "投屏"、"给老板看"、"周报"、"月报"、"总结" |

---

## 二、命令触发

| 命令 | 用途 | 说明 |
|------|------|------|
| `/conspect start` | 启动报表任务 | 进入 9 阶段状态机 |
| `/conspect start --offline` | 启动报表任务（离线模式） | 内联 ECharts 库，无需联网加载 |
| `/conspect status` | 查看当前进度 | 读取 `_cs-baton.md` 展示当前状态和进度 |
| `/conspect reset` | 重置当前任务 | 清空接力棒，从 开始 阶段重新启动 |

---

## 三、CLI 程序化调用

conspect 支持通过 CLI 工具层程序化调用，适用于自动化报表生成。

### CLI 命令调用

所有操作通过 `python run.py <action> '<params_json>'` 方式调用，具体命令见 SKILL.md 的「CLI 工具层速查表」。

```powershell
# 前置：先定位 {CLI_DIR}（run.py 所在目录）
cd {CLI_DIR}

# 全链路分析
python run.py analyze '{"file_paths": ["数据源文件.xlsx"]}'

# 交叉分析
python run.py cross_tabulate '{"file_paths": ["数据源文件.xlsx"], "row_dim": "维度A", "col_dim": "维度B"}'

# 渲染报告
python run.py render_report '{"report_design": {...}, "format": "html"}'
```

### API 接口调用

```python
# 通过 run.py 的 run() 函数直接调用
from conspect_tools.data_processor import DataProcessor
from conspect_tools.data_statistics import DataStatistics

processor = DataProcessor()
stats = DataStatistics()

dfs = processor.load_excel(["数据源文件.xlsx"])
```

> 程序化调用模式会跳过确认阶段，直接使用默认参数执行。如需要人工确认分析结果，不加 `--fast` 参数即可保留确认环节。

---

## 四、功能选择决策

当不确定用哪个功能入口时，按以下判断：

| 你的需求 | 推荐入口 | 说明 |
|---------|---------|------|
| "出一份周报/月报" | 直接说需求即可 | AI 自动识别为报表生成任务 |
| "对比分析多份数据" | 上传多文件后说"对比分析" | 自动进入多源分析模式 |
| "只想看数据概况/趋势" | 上传文件后说"做个简单分析" | 轻量模式，跳过设计阶段 |
| "做成投屏用的看板" | 生成后使用 Web 看板输出 | 默认输出交互式 HTML |
| "发邮件给别人看" | 生成后选择离线 HTML 输出 | 单文件，无需联网打开 |

---

## 五、定制化使用

在对话中可通过以下方式传递偏好：

| 偏好类型 | 示例 | 效果 |
|---------|------|------|
| 配色风格 | "用蓝色调"、"我想要暖色系" | 自动切换对应主题 |
| 图表偏好 | "对比多用柱状图"、"占比用饼图" | 影响图表选型优先级 |
| 分析焦点 | "重点关注[维度A]趋势"、"按[维度B]分析" | 影响维度分析和结论 |
| 输出格式 | "生成 PDF 给我"、"做一个离线 HTML" | 切换输出形态 |
| 自定义品牌色 | "主色调用 #1890FF" | 在确认阶段提供即可生效 |
