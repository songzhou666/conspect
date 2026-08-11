# conspect 接力棒协议

> 定义 conspect Skill 的接力棒文件格式、生命周期和续跑机制（v3.0：全流程自动推进，无确认节点）。

## 命名规则

所有接力棒及产物文件使用 `_cs-` 前缀避免与其他Skill冲突。

| 文件 | 说明 |
|------|------|
| `_cs-baton.md` | 接力棒主文件 |
| `_cs-analysis.md` | 分析报告 |
| `_cs-design.md` | 设计文档 |
| `_cs-design-review.md` | 设计审查意见 |
| `_cs-implement.md` | 实现摘要 |
| `_cs-verify.md` | 验证报告 |
| `_cs-qa-{phase}.md` | 质量审核报告 |

## 接力棒格式

```markdown
# 接力棒 — {任务名称}

## 元数据
- state: {开始/分析/洞察生成/设计/设计审查/实现/报告生成/验证/完成}
- project: {项目路径}
- skill_name: conspect
- mode: {all/web/offline/static}   # 输出形态，默认 all
- created: {ISO 8601}
- updated: {ISO 8601}

## 用户偏好（v3.0：从初始需求自动识别）
- color_scheme: {ocean/warm/aurora/forest/minimal}
- custom_primary_color: {None 或 "#1890FF"}
- chart_preferences: {trend/comparison/composition/distribution}
- output_formats: {html/pdf/md/docx}
- layout: {dashboard/report}
- focus_dimensions: {None 或指定维度}
- focus_metrics: {None 或指定指标}

## 状态追踪
- [ ] 开始 — {描述}
- [ ] 分析 — {描述}
- [ ] 洞察生成 — {描述}
- [ ] 设计 — {描述}
- [ ] 设计审查 — {描述}
- [ ] 实现 — {描述}
- [ ] 报告生成 — {描述}
- [ ] 验证 — {描述}
- [ ] 完成 — {描述}

## 质量审核追踪
| 审核阶段 | 状态 | 分数 | 报告文件 |
|---------|------|------|---------|
| qa_analysis | 未审核 | - | - |
| qa_design | 未审核 | - | - |
| qa_implement | 未审核 | - | - |
| qa_report | 未审核 | - | - |
| qa_verify | 未审核 | - | - |

## 待办清单
（新需求/中断记录）
```

## 生命周期

1. **开始阶段**：创建接力棒，状态=开始
2. **自动推进**：每个阶段完成后更新状态，全流程零用户确认节点
3. **续跑机制**：读取 `state` 字段，从对应阶段续跑

## 续跑规则

- 如果接力棒存在 → 读取 state 字段 → 从对应阶段继续
- 如果接力棒不存在 → 创建新的接力棒 → 状态=开始
- 如果 state=完成 → 历史任务，可重置为新任务

## v3.0 变更

- 原"确认"状态已从 state 枚举中删除
- 原"确认阻断"规则已删除（不再有用户确认环节）
- 新增"洞察生成"作为分析→设计之间的自动过渡阶段
- 用户偏好（品牌色/图表/输出格式）在开始阶段从初始需求中识别并记录到接力棒
