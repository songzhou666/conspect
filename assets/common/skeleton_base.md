# 通用报表骨架（兜底）

> 当所需风格不在资产内、或 L2 正文缺失时，按本骨架降级生成，**并在 `_cs-style.md` 中明示「以下基于通用骨架生成」**。
> 骨架内的 `:root` 变量取自 `style-system.json` 中任一风格的 `tokens`，不得自行编色。

## 一、骨架结构

```
仪表盘容器
├── 页头（报表标题 + 副标题 + 数据范围 + 生成日期）        → B01 封面页（并入页头）
├── prose 块（执行摘要）                                    → B02
├── kpi_cards 块（KPI 指标墙）                              → B04
├── section_group 块（分析分区，内含 chart / table / conclusion） → B07–B14 / B13
├── prose 块（风险与机会，双栏）                            → B16
├── conclusion 块（核心发现）                               → B15
├── prose 块（口径与指标定义）                              → B18
└── prose 块（结尾与下一步）                                → B22
```

## 二、可运行骨架

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>报表标题</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
  /* 变量取自 style-system.json 的 styles[].tokens，风格切换只改这一段 */
  :root{
    --bg:#FFFFFF; --card:#FFFFFF; --ink:#111111; --mu:#8A8A8A;
    --ac:#2B4C8C; --line:#E2E2E2;
    --font:'Noto Sans SC','PingFang SC','Microsoft YaHei',system-ui,sans-serif;
    --gap:20px; --pad:24px;
  }
  *{ margin:0; padding:0; box-sizing:border-box; }
  body{ font-family:var(--font); background:var(--bg); color:var(--ink);
        -webkit-font-smoothing:antialiased; line-height:1.6; }
  .wrap{ max-width:1440px; margin:0 auto; padding:32px 32px 64px; }

  /* 页头 */
  .header{ text-align:center; padding:24px 0 32px; }
  .header h1{ font-size:28px; color:var(--ac); letter-spacing:.01em; }
  .header .sub{ color:var(--mu); font-size:15px; margin-top:10px; }
  .header .meta{ color:var(--mu); font-size:13px; margin-top:14px; }
  .header .rule{ width:64px; height:3px; background:var(--ac); margin:18px auto 0; border-radius:2px; }

  /* 通用卡片 */
  .card{ background:var(--card); border:1px solid var(--line); border-radius:12px;
         padding:var(--pad); }
  .sec{ margin-bottom:var(--gap); }
  .sec-title{ font-size:20px; font-weight:600; margin-bottom:6px; }
  .sec-desc{ color:var(--mu); font-size:13px; margin-bottom:16px; }

  /* prose 块（封面/摘要/风险机会/口径/结尾/附录） */
  .prose-body{ font-size:15px; }
  .prose-body ol,.prose-body ul{ padding-left:22px; }
  .prose-body li{ margin-bottom:8px; }
  .prose-cols{ display:grid; grid-template-columns:1fr 1fr; gap:var(--gap); }
  .prose-badge{ display:inline-block; font-size:12px; padding:2px 10px; border-radius:999px;
                background:var(--bg); border:1px solid var(--line); color:var(--mu);
                margin-right:8px; }

  /* KPI 指标墙 */
  .kpi-row{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr));
            gap:var(--gap); }
  .kpi{ background:var(--card); border:1px solid var(--line); border-radius:12px;
        border-top:3px solid var(--ac); padding:20px 22px; }
  .kpi .label{ font-size:13px; color:var(--mu); }
  .kpi .value{ font-size:30px; font-weight:600; color:var(--ac); margin-top:8px;
               font-variant-numeric:tabular-nums; }
  .kpi .delta{ font-size:13px; color:var(--mu); margin-top:6px; }

  /* 分析分区 */
  .grid-2{ display:grid; grid-template-columns:repeat(2,1fr); gap:var(--gap); }
  .grid-3{ display:grid; grid-template-columns:repeat(3,1fr); gap:var(--gap); }
  .chart-box{ background:var(--card); border:1px solid var(--line); border-radius:12px;
              padding:20px 22px; }
  .chart-title{ font-size:16px; font-weight:600; margin-bottom:12px; }
  .chart-canvas{ width:100%; height:300px; }
  .chart-insight{ margin-top:14px; padding:12px 16px; background:var(--bg);
                  border-left:3px solid var(--ac); font-size:13px; color:var(--mu);
                  border-radius:0 6px 6px 0; }

  /* 表格 */
  table{ width:100%; border-collapse:collapse; font-size:14px; }
  th{ text-align:left; padding:10px 12px; border-bottom:2px solid var(--line);
      font-weight:600; color:var(--ink); }
  td{ padding:10px 12px; border-bottom:1px solid var(--line); color:var(--ink); }
  td.num{ text-align:right; font-variant-numeric:tabular-nums; }

  /* 结论 */
  .conclusion ol{ padding-left:22px; }
  .conclusion li{ margin-bottom:10px; }

  @media (max-width:1024px){
    .grid-3{ grid-template-columns:repeat(2,1fr); }
  }
  @media (max-width:640px){
    .wrap{ padding:20px 16px 48px; }
    .grid-2,.grid-3,.prose-cols{ grid-template-columns:1fr; }
    .kpi .value{ font-size:26px; }
  }
</style>
</head>
<body>
<div class="wrap">

  <!-- B01 封面页（并入页头） -->
  <header class="header">
    <h1>报表主标题</h1>
    <p class="sub">一句话核心结论</p>
    <p class="meta">数据范围：YYYY-MM-DD ~ YYYY-MM-DD ｜ 数据源：N 个文件 / M 条记录 ｜ 生成日期：YYYY-MM-DD</p>
    <div class="rule"></div>
  </header>

  <!-- B02 执行摘要 -->
  <section class="sec card">
    <h2 class="sec-title">执行摘要</h2>
    <div class="prose-body">
      <ol>
        <li>核心结论一（含关键数字）</li>
        <li>核心结论二（含关键数字）</li>
        <li>核心结论三（含关键数字）</li>
      </ol>
    </div>
  </section>

  <!-- B04 KPI 指标墙 -->
  <section class="sec">
    <div class="kpi-row">
      <div class="kpi"><div class="label">指标名</div><div class="value">0.00</div>
        <div class="delta">较上期 +0.0%（方向须同时用正负号或箭头标注）</div></div>
    </div>
  </section>

  <!-- B07–B14 分析分区 -->
  <section class="sec">
    <h2 class="sec-title">分析</h2>
    <p class="sec-desc">本节板块由「汇报内容选型」按触发条件确定。</p>
    <div class="grid-2">
      <div class="chart-box">
        <div class="chart-title">图表标题</div>
        <div class="chart-canvas" id="chart1"></div>
        <div class="chart-insight">数据解读：1–3 句白话业务解读，说清涨在哪、跌在哪、拐点是什么。</div>
      </div>
      <div class="chart-box">
        <div class="chart-title">明细表（B13）</div>
        <table>
          <thead><tr><th>维度</th><th style="text-align:right">数值</th><th style="text-align:right">占比</th></tr></thead>
          <tbody><tr><td>—</td><td class="num">0</td><td class="num">0.0%</td></tr></tbody>
        </table>
      </div>
    </div>
  </section>

  <!-- B16 风险与机会 -->
  <section class="sec card">
    <h2 class="sec-title">风险与机会</h2>
    <div class="prose-cols">
      <div><h3 class="sec-title" style="font-size:16px">风险</h3>
        <ul class="prose-body"><li>描述 + 影响面 + 信号指标</li></ul></div>
      <div><h3 class="sec-title" style="font-size:16px">机会</h3>
        <ul class="prose-body"><li>描述 + 抓取条件</li></ul></div>
    </div>
  </section>

  <!-- B15 核心发现 -->
  <section class="sec card conclusion">
    <h2 class="sec-title">核心发现</h2>
    <ol>
      <li>结论 + 支撑证据（指标 + 变化幅度）</li>
    </ol>
  </section>

  <!-- B18 口径与指标定义 -->
  <section class="sec card">
    <h2 class="sec-title">口径与指标定义</h2>
    <table>
      <thead><tr><th>指标</th><th>计算口径</th><th>数据来源</th><th>统计周期</th></tr></thead>
      <tbody><tr><td>—</td><td>—</td><td>—</td><td>—</td></tr></tbody>
    </table>
  </section>

  <!-- B22 结尾与下一步 -->
  <section class="sec card">
    <h2 class="sec-title">下一步</h2>
    <p class="prose-body">一句话复述核心结论 ｜ 下一步动作或下次回顾节点 ｜ 数据更新日期</p>
  </section>

</div>

<script>
  /* 图表系列色取自 style-system.json 的 families[].series（首位为所选风格的 --ac） */
  var SERIES = ["#2B4C8C","#4A7CF7","#6FC3A0","#F5A623","#E86868","#8B6CD6"];
  var CSS = getComputedStyle(document.documentElement);
  var AC = CSS.getPropertyValue('--ac').trim();
  var INK = CSS.getPropertyValue('--ink').trim();
  var MU = CSS.getPropertyValue('--mu').trim();
  var LINE = CSS.getPropertyValue('--line').trim();
  SERIES[0] = AC;

  var el = document.getElementById('chart1');
  if (el && window.echarts) {
    var chart = echarts.init(el);
    chart.setOption({
      color: SERIES,
      grid: { left: 48, right: 24, top: 24, bottom: 36 },
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: [], axisLine: { lineStyle: { color: LINE } },
               axisLabel: { color: MU } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: LINE } },
               axisLabel: { color: MU } },
      series: [{ type: 'line', data: [], smooth: true,
                 areaStyle: { opacity: 0.12 },
                 label: { color: INK } }]
    });
    window.addEventListener('resize', function () { chart.resize(); });
  }
</script>
</body>
</html>
```

## 三、降级纪律

1. **必须明示**：使用本骨架时，在 `_cs-style.md` 与最终交付说明中写明「未命中风格资产，基于通用骨架生成」。
2. **不得假称**：不得声称已取得风格资产，也不得用通用骨架冒充某个具体风格。
3. **变量优先**：即便降级，也必须把 `:root` 填成某一真实风格的 `tokens`，不得留空或使用未登记色值。
4. **板块不降级**：骨架只降级「样式」，板块组合仍须按 `assets/common/block_library.md` 完整执行。
