# CLI 和 AI Agent 调用顺序

> 文档定义 conspect Skill 中 CLI 工具层和 AI Agent 的分工，以及各阶段的调用顺序。

---

## 一、CLI 与 AI 分工

### CLI 工具层（数据支持）

**职责**：只负责数据加载、简单计算、文件操作

**模块**：
- `data_processor.py` - 数据加载、清洗、聚合
- `data_feature_extractor.py` - 数据特征提取
- `data_statistics.py` - 数据统计
- `review_data_loader.py` - 审核数据加载
- `exporter.py` - 文件导出

**CLI 命令**：
```bash
# 数据加载
python run.py load '{"file_paths": ["数据源文件.xlsx"]}'
python run.py read_all '{"file_paths": ["数据源文件.xlsx"]}'
python run.py analyze '{"file_paths": ["数据源文件.xlsx"]}'

# 数据特征提取
python run.py extract_features '{"data": {...}}'

# 数据统计
python run.py calc_statistics '{"values": [...]}'

# 审核数据加载
python run.py load_review_context '{"raw_data_file": "...", "analysis_file": "..."}'

# 数据比较
python run.py compare_data '{"data1": {...}, "data2": {...}}'

# 文件导出
python run.py save_report '{"content": "...", "filename": "report.md"}'
python run.py save_with_chinese_name '{"content": "...", "filename": "report.md"}'
```

### AI Agent（决策分析）

**职责**：负责所有需要理解和判断的工作

**模块**：
- `ai_agent.py` - AI Agent（图表选型、洞察生成、质量审核）

**CLI 命令**：
```bash
# AI Agent 图表选型决策
python run.py ai_decide_chart '{"features": {...}, "business_context": "<根据数据源自动识别的业务场景>"}'

# AI Agent 生成洞察
python run.py ai_generate_insights '{"statistics": {...}, "business_context": "<根据数据源自动识别的业务场景>"}'

# AI Agent 审核
python run.py ai_review_design '{"analysis": {...}, "design": {...}}'
python run.py ai_review_implement '{"design": {...}, "implement": {...}}'
```

---

## 二、各阶段调用顺序

### 分析阶段
```
1. 主控 Agent 调用 CLI 加载数据
   python run.py load '{"file_paths": ["数据源文件.xlsx"]}'
   
2. 主控 Agent 分析数据
   - 数据清洗、维度识别、指标计算
   
3. 主控 Agent 生成分析报告
   写入 _cs-analysis.md
   
4. 主控 Agent 拉起 AI 审核 Agent 审核分析结果
   → 审核通过 → 进入下一阶段
   → 审核不通过 → 修复后重新审核
```

### 洞察生成阶段
```
1. 主控 Agent 调用 CLI 提取数据特征
   python run.py extract_features '{"data": {...}}'
   
2. 主控 Agent 调用 CLI 计算统计数据
   python run.py calc_statistics '{"values": [...]}'
   
3. 主控 Agent 调用 AI Agent 生成洞察
   - 输入：统计数据 + 业务场景
   - 输出：洞察列表 + 建议列表
   
4. 主控 Agent 写入洞察数据
   写入 _cs-insights.json
```

### 设计阶段
```
1. 主控 Agent 读取分析报告
   读取 _cs-analysis.md
   
2. 主控 Agent 调用 CLI 提取数据特征
   python run.py extract_features '{"data": {...}}'
   
3. 主控 Agent 调用 AI Agent 图表选型决策
   - 输入：数据特征 + 业务场景
   - 输出：图表类型 + 选择理由
   
4. 主控 Agent 生成设计文档
   写入 _cs-design.md
   
5. 主控 Agent 拉起 AI 审核 Agent 审核设计结果
   → 审核通过 → 进入下一阶段
   → 审核不通过 → 修复后重新审核
```

### 实现阶段
```
1. 主控 Agent 读取设计文档
   读取 _cs-design.md
   
2. 主控 Agent 渲染看板
   生成 Web 看板 HTML
   
3. 主控 Agent 生成实现摘要
   写入 _cs-implement.md
   
4. 主控 Agent 拉起 AI 审核 Agent 审核实现结果
   → 审核通过 → 进入下一阶段
   → 审核不通过 → 修复后重新审核
```

### 报告生成阶段
```
1. 主控 Agent 读取洞察数据
   读取 _cs-insights.json
   
2. 主控 Agent 设计报告结构
   生成报告大纲
   
3. 主控 Agent 渲染多格式报告
   - Markdown、HTML、PDF、Word
   
4. 主控 Agent 生成中文命名副本
   python run.py save_with_chinese_name '{...}'
   
5. 主控 Agent 写入关联索引
   写入 _cs-index.json
```
