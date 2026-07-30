# 主控 Agent 与子 Agent 通信方式

> 本文档定义 conspect Skill 中主控 Agent 与子 Agent 的通信方式、输入参数格式和输出结果格式。

---

## 一、通信方式

- 主控 Agent 读取子 Agent 指南（agents/09-ai-reviewer-agent.md）
- 主控 Agent 准备输入参数（JSON 格式）
- 主控 Agent 激活子 Agent（使用 Task 工具）
- 子 Agent 执行任务（独立上下文）
- 子 Agent 返回结果（JSON 格式）
- 主控 Agent 接收结果并处理

---

## 二、输入参数格式

```json
{
  "task": "review_analysis",
  "phase": "analysis",
  "context": {
    "raw_data_file": "path/to/raw_data.json",
    "analysis_file": "path/to/_cs-analysis.md"
  },
  "business_context": "<根据数据源自动识别的业务场景>",
  "output_file": "path/to/_cs-ai-review-analysis.md"
}
```

---

## 三、输出结果格式

```json
{
  "status": "completed",
  "passed": true,
  "score": 85.0,
  "issues": [],
  "report_file": "path/to/_cs-ai-review-analysis.md"
}
```

---

## 四、子 Agent 列表

| 子 Agent | 职责 | 指南文件 |
|---------|------|---------|
| AI 审核 Agent | 端到端审核 | agents/09-ai-reviewer-agent.md |
| 视觉设计师 Agent | 视觉审查 | agents/06-visual-designer-agent.md |
