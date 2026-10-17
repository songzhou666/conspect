# CLI 与 AI 的分工与调用顺序

> 一句话原则：**CLI 负责算，AI 负责判断**。CLI 不写结论，AI 不写分析代码。

---

## 一、分工边界

| 层 | 负责 | 不负责 |
|----|------|--------|
| CLI（`conspect_tools/`） | 数据加载、清洗、聚合、统计、特征提取、图表配置生成、HTML 渲染、落盘、导出 | 业务判断、结论撰写、风格选择、板块取舍 |
| AI Agent | 数据解读、洞察与建议、板块选型、风格选型、质量审核 | 手写分析代码、手写 HTML、绕过 CLI 直接操作文件 |

**唯一例外**：AI 可以写 `.md` / `.json` 形式的**产物文件**（分析报告、板块方案、选型卡），
但报表产物（HTML / PDF / Word）必须由 CLI 渲染。

---

## 二、模块职责

| 模块 | 职责 |
|------|------|
| `data_processor.py` | 加载 Excel/CSV、格式分派、Sheet 枚举、清洗、维度识别 |
| `data_statistics.py` | 统计计算（集中度、熵、相关性、分布） |
| `data_feature_extractor.py` | 数据特征提取（供图表选型与板块判定） |
| `ai_agent.py` | 图表选型决策、洞察与建议、**板块选型**、**风格选型**、审核判定 |
| `style_loader.py` | 读取风格资产、翻译成主题字典、提供序列色 |
| `block_library.py` | 解析板块库、执行触发判定、板块裁剪 |
| `render_engine.py` | 组装 HTML（kpi_cards / section_group / chart / table / conclusion / prose） |
| `report_renderer.py` | 报告 Markdown / HTML / PDF / Word 渲染 |
| `exporter.py` | 落盘、中文副本、索引 |
| `review_data_loader.py` | 审核所需数据的加载与对账 |

---

## 三、五阶段的调用顺序

### 1. 读取数据

```powershell
'{"file_paths": ["e:/data/sales.xlsx"]}' | python run.py read_datamap
'{"requirements": "投屏用的深色科技感周报"}' | python run.py recognize_preferences
```

产出：文件/Sheet/列清单、质量分、风格候选。

### 2. 分析数据

```powershell
'{"file_paths": ["e:/data/sales.xlsx"]}' | python run.py analyze
'{"file_paths": ["e:/data/sales.xlsx"]}' | python run.py extract_features
'{"values": [1,2,3]}' | python run.py calc_statistics
'{"analysis": {...}}' | python run.py ai_generate_insights
```

产出：分析结果、数据特征、统计数据、洞察。特征字典要留到下一步。

### 3. 汇报内容选型

```powershell
# 核对板块库
python run.py list_blocks

# 生成板块组合（features 用上一步的产出）
'{"analysis": {...}, "features": {...}, "report_form": "投屏"}' | python run.py select_content

# 为图表驱动板块定图表类型
'{"features": {...}, "business_context": "经营周报"}' | python run.py ai_decide_chart
```

产出：板块清单 + 裁出清单 → 写 `_cs-content.md` → **等用户确认**。

### 4. 报表选型

```powershell
# 列出 6 族 38 风格（用于核对 L0 目录）
python run.py list_styles

# 打分产建议卡
'{"profile": {"tone": "浅色", "report_type": "经营分析", "density": "高"}}' | python run.py select_style
```

产出：选型卡 + 资产引用声明 → 写 `_cs-style.md` → **等用户确认**。

### 5. 生成报表

```powershell
# 装配布局（blocks 来自已确认的板块清单，顺序即页序）
'{"analysis": {...}, "insights": [...], "blocks": ["B01","B02","B04","B07"]}' | python run.py build_dashboard_layout

# 渲染（theme 传已确认的风格编号）
'{"layout": {...}, "theme": "A12"}' | python run.py render_dashboard

# 落盘（长文本必须用 content_file）
'{"content_file": "_content.html", "filename": "_cs-dashboard.html"}' | python run.py save_report
'{"content_file": "_content.md", "filename": "_cs-report.md"}' | python run.py save_with_chinese_name
'{"index": {...}}' | python run.py save_index
```

产出：看板 HTML、报告多格式、中文副本、索引、内核验报告。

---

## 四、错误处理约定

| CLI 返回 | 含义 | AI 应做 |
|---------|------|--------|
| `{"status":"ok", ...}` | 成功 | 继续 |
| `{"status":"error","message":"文件不存在"}` | 路径问题 | 请用户确认路径，不自行搜索磁盘 |
| `{"status":"error","message":"未读取到任何 Sheet"}` | 文件为空或结构异常 | 请用户检查文件 |
| `{"status":"error","message":"格式不支持"}` | `.xls` / `.json` | 提示另存为 `.xlsx` |
| `{"status":"error","message":"Unknown action"}` | 动作名拼错 | 查 `references/cli-usage.md` 的动作表 |
| 选了不存在的风格编号 | `style_loader` 回退默认风格 | 检查 `list_styles` 输出，不要凭记忆编号 |

**不要用 `python -c` 绕过**：Windows PowerShell 的引号嵌套会让内联脚本失败，
且内联代码跳过了工具层的异常降级与路径校验。
