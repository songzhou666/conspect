# AI 审核 Agent 拉起方式

> 本文档定义 AI 审核 Agent 的拉起方式、输入参数和输出结果。

---

## 一、拉起时机

- 每个阶段完成后，主控 Agent **自动拉起** AI 审核 Agent
- 审核不通过 → 阻断流程，必须修复

---

## 二、拉起流程

```
主控 Agent → 读取 AI 审核 Agent 指南 → 准备审核上下文 → 激活子 Agent（Task） → 子 Agent 执行审核 → 返回审核报告
```

---

## 三、输入参数

```json
{
  "phase": "analysis/design/implement/report",
  "context": {
    "raw_data_file": "path/to/raw_data.json",
    "analysis_file": "path/to/_cs-analysis.md",
    "design_file": "path/to/_cs-design.md",
    "implement_file": "path/to/_cs-implement.md"
  },
  "business_context": "<根据数据源自动识别的业务场景>"
}
```

---

## 四、输出结果

```json
{
  "review_file": "path/to/_cs-ai-review-analysis.md",
  "passed": true/false,
  "score": 85.0,
  "issues": [...]
}
```

---

## 五、审核不通过处理

1. 主控 Agent 读取审核报告
2. 提取"待修复问题清单"
3. 回退到对应阶段
4. 修复问题
5. 重新拉起 AI 审核 Agent
6. 直到审核通过
