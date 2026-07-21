# 数据流水线详解

## 数据导入

### 支持的输入格式

| 格式 | 说明 | 限制 |
|------|------|------|
| .xlsx | Excel 标准格式 | 单 Sheet 最大 100 万行 |
| .xls | Excel 97-2003 格式 | 单 Sheet 最大 6.5 万行 |
| .csv | 逗号分隔值 | UTF-8 编码，支持 GBK 自动检测 |
| .json | JSON 数组格式 | 需为对象数组，每个对象一条记录 |

### 多文件批量导入策略

1. **文件遍历**：读取用户指定的文件列表或目录下所有可识别文件
2. **Sheet 解析**：对每个 Excel 文件，遍历所有 Sheet
3. **Schema 映射**：自动识别各列数据类型（数值/日期/文本），不一致时以第一个文件的 Schema 为准
4. **横向合并**：同 Schema 的多个 Sheet/文件按行追加合并
5. **纵向关联**：不同 Schema 的数据集保持独立，分别生成图表

### 文件预处理

```
输入文件 → 格式检测 → 编码检测(CSV) → Sheet枚举 → 列类型推断 → 内存DataFrame
```

## 数据清洗

### 空值处理策略

| 字段类型 | 处理方式 |
|----------|----------|
| 数值型指标 | 连续缺失 ≤ 5% 用均值填充；> 5% 标记为不可靠列 |
| 分类型维度 | 用 "未知" 填充，不影响聚合 |
| 时间维度 | 缺失则尝试从文件名/Sheet名推断，推断失败则标记不可用 |
| 关键维度/指标 | 缺失率 > 50% 直接标记为"数据质量不达标"并报警 |

### 去重规则

- **完全重复行**：保留第一条，丢弃其余
- **部分重复**：同一维度组合下有多条相同指标值 → 保留第一条
- **时间序列重复**：同一时间点有多条数据 → 取末条（覆盖写入）

### 类型纠正

- 数字字符串自动转为 float/int
- 日期字符串自动解析为标准日期格式（YYYY-MM-DD）
- 百分数字符串转为小数（如 "85.3%" → 0.853）
- 货币字符串去除符号转为纯数值（如 "¥12,345" → 12345.0）

### 异常值标记

使用 IQR（四分位距）法检测数值型指标的异常值：

```
IQR = Q3 - Q1
下界 = Q1 - 1.5 * IQR
上界 = Q3 + 1.5 * IQR
超界值标记为异常，不剔除但在报表中备注
```

## 维度识别

### 自动识别规则

| 维度类型 | 判定规则 | 示例 |
|----------|----------|------|
| 时间维度 | 列名含"时间/日期/年/月/日/季/周"，或数据类型为 datetime | 2024年、1月、Q1 |
| 分类维度 | 字符串类型，唯一值数量 ≤ 总行数 20% | 地区、部门、产品线 |
| 排序维度 | 数值型且唯一值少，或列名含"排名/序号/等级" | 排名、星级、级别 |
| 结构维度 | 有层级关系（父子结构），如"省-市-区" | 组织架构、地理层级 |
| 度量指标 | 数值类型，唯一值多，适合聚合计算 | 收入、数量、比率、增长率 |

### 维度优先级

当一列可同时归属多个维度类型时，按以下优先级判定：

```
时间维度 > 结构维度 > 分类维度 > 排序维度 > 度量指标
```

## 指标计算

### 基础指标

| 指标 | 计算方式 | 适用场景 |
|------|----------|----------|
| 合计 | SUM | 总量汇总 |
| 均值 | AVG | 平均水平 |
| 最大值 | MAX | 峰值监测 |
| 最小值 | MIN | 谷值监测 |
| 计数 | COUNT | 数量统计 |
| 去重计数 | COUNT_DISTINCT | 唯一值数量 |

### 衍生指标

| 指标 | 计算方式 | 说明 |
|------|----------|------|
| 同比 | (本期值 - 同期值) / 同期值 * 100% | 与去年同期对比 |
| 环比 | (本期值 - 上期值) / 上期值 * 100% | 与上一周期对比 |
| 占比 | 子项值 / 合计值 * 100% | 各组成部分份额 |
| 排名 | 按指标值降序排列 | 排序比较 |
| 累计 | 按时间顺序逐期累加 | 年度累计趋势 |
| 目标达成率 | 实际值 / 目标值 * 100% | 进度监测 |

### 聚合规则

- 所有指标计算在 pandas 中按指定维度分组进行
- 支持多维度交叉聚合（如按"[分类维度]+[时间维度]"计算[核心指标]）
- 聚合结果缓存在临时 DataFrame 中，供图表选型使用

## 高级分析流水线

> 以下为增强分析能力，在基础指标计算完成后自动按启用规则执行。

### 信息熵计算

| 步骤 | 操作 | 说明 |
|------|------|------|
| 1. 概率分布计算 | `P(X=x) = count(x) / total` | 对每个分类维度计算取值概率 |
| 2. 信息熵 | `H(X) = -Σ P(x) × log₂(P(x))` | 量化维度不确定性 |
| 3. 条件熵 | `H(Y|X) = Σ P(x) × H(Y|X=x)` | 目标 Y 需先离散化（等频分箱） |
| 4. 互信息 | `I(X;Y) = H(Y) - H(Y|X)` | 维度与指标关联强度 |
| 5. 信息增益率 | `IGR = I(X;Y) / H(X)` | 归一化后的影响力，消除维度基数偏差 |

**实现伪代码**：
```python
def calc_entropy(series):
    probs = series.value_counts(normalize=True)
    return -sum(p * log2(p) for p in probs if p > 0)

def calc_mutual_info(x_series, y_series, n_bins=10):
    # Y 离散化
    y_binned = pd.cut(y_series, bins=n_bins, labels=False)
    h_y = calc_entropy(y_binned)
    # 条件熵
    h_y_given_x = 0
    for val in x_series.unique():
        mask = x_series == val
        h_y_given_x += sum(mask) / len(x_series) * calc_entropy(y_binned[mask])
    return h_y - h_y_given_x
```

### 贪心优化计算

| 场景 | 贪心策略 | 复杂度 |
|------|---------|--------|
| Top-K 维度筛选 | 每次选互信息最大的维度 | O(K × n) |
| 资源分配 | 按投入产出比降序选择 | O(n log n) |
| 特征降维 | 贪心前向选择 + R² 增量评估 | O(K × n × m) |

### 分布形态计算

使用 pandas 统计函数：
```python
cv = df[col].std() / df[col].mean() * 100        # 变异系数(%)
skewness = df[col].skew()                          # 偏度
kurtosis = df[col].kurtosis()                      # 峰度（超额峰度）
iqr = df[col].quantile(0.75) - df[col].quantile(0.25)
is_normal = abs(skewness) < 1 and abs(kurtosis) < 2  # 近似正态判定
```

### 集中度计算

```python
def calc_concentration(df, dim_col, metric_col):
    grouped = df.groupby(dim_col)[metric_col].sum().sort_values(ascending=False)
    total = grouped.sum()
    shares = grouped / total
    # CR4
    cr4 = shares.head(4).sum()
    # CR8
    cr8 = shares.head(8).sum()
    # HHI
    hhi = (shares * 100).pow(2).sum()
    # 基尼系数 (简化计算)
    sorted_vals = grouped.sort_values().values
    n = len(sorted_vals)
    index = np.arange(1, n + 1)
    gini = (2 * sum(index * sorted_vals)) / (n * sum(sorted_vals)) - (n + 1) / n
    return cr4, cr8, hhi, gini
```

### 趋势分解计算

```python
# 移动平均
df['MA3'] = df[metric_col].rolling(window=3).mean()
df['MA5'] = df[metric_col].rolling(window=5).mean()

# 指数平滑
alpha = 0.3
df['ES'] = df[metric_col].ewm(alpha=alpha, adjust=False).mean()

# 趋势强度
trend_strength = abs(df['MA3'].iloc[-1] - df['MA3'].iloc[3]) / df['MA3'].iloc[3] * 100

# 简单线性外推：基于最近 N 期拟合 y = ax + b
from numpy import polyfit
x = range(N)
y = df[metric_col].tail(N).values
a, b = polyfit(x, y, 1)
next_pred = a * N + b  # 下期预测
```

## 数据安全

| 安全策略 | 具体措施 |
|----------|----------|
| 原始数据隔离 | 原始明细数据仅在后端存储，前端渲染只传递聚合后的 JSON |
| 聚合数据脱敏 | 当分组后某组记录数 < 5 时，该组指标标记为 "数据量不足" |
| 临时文件清理 | 所有临时文件在任务完成后立即删除 |
| 内存释放 | 大 DataFrame 使用后显式 del + gc.collect() |

## 大数据量处理策略

| 场景 | 处理策略 |
|------|----------|
| 单文件 > 100 万行 | pandas 分块读取（chunksize=50,000），边读取边聚合 |
| 多文件合并 > 500 万行 | 不加载全部到内存，逐文件聚合后合并结果 |
| 前端渲染 | 仅传递聚合后的指标数据，数据量控制在 5000 条以内 |
| 超长时序 | 自适应降采样：超过 365 个时间点则按月聚合 |
