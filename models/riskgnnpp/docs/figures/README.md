# 论文插图

三张图已嵌入[假设性论文](../riskgnnpp-paper-hypothetical.md)。图中不包含假设实验数值。

| 图 | 内容 | 矢量与位图 |
| --- | --- | --- |
| 1 | 数据来源、关系语义、预测与复核任务 | [SVG](figure-1-problem.svg) · [PDF](figure-1-problem.pdf) · [PNG](figure-1-problem.png) |
| 2 | 当前 RiskGNN++ 的主预测、证据与复核路径 | [SVG](figure-2-architecture.svg) · [PDF](figure-2-architecture.pdf) · [PNG](figure-2-architecture.png) |
| 3 | 既有 UK AP 与 UK / SMEsD AURC | [SVG](figure-3-existing-results.svg) · [PDF](figure-3-existing-results.pdf) · [PNG](figure-3-existing-results.png) |

图 1 中的图结构为概念示意，不表示实际抽样、边频率或标签。
图 2 对照 `riskgnn_pp/model.py` 绘制；辅助聚合图头及各项损失权重详见正文。
图 3 数据来自当前实证稿第 5.2–5.4 节，十个种子使用同一数据划分。
AP 误差棒是种子间样本标准差，不是置信区间；AURC 只绘制均值，不推造区间。
UK 和 SMEsD 的 AURC 面板使用不同横轴范围。所有 p 值为既有配对 t 检验结果。

## 再生成

绘图脚本：[render_figures.py](render_figures.py)。数据：[existing-results.json](existing-results.json)。
已验证的环境：Python、Matplotlib 3.10.6、PyMuPDF 1.24.14。
图 1–2 使用 SVG 元素绘制，PyMuPDF 导出 PDF / PNG；图 3 使用 Matplotlib。

```bash
MPLCONFIGDIR=/tmp/riskgnnpp-matplotlib python models/riskgnnpp/docs/figures/render_figures.py
```

运行命令只绘图，不训练模型或重新计算实验。PDF 适合论文排版，SVG 保留可编辑文本，PNG 用于预览。
