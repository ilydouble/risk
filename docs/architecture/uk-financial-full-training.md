# 英国全量财务版决策模型

## 训练范围

独立运行目录：`/root/autodl-tmp/lrr/uk-financial-full-20261018`。
底座为缓存的 `Qwen/Qwen3-0.6B`，revision固定为
`c1899de289a04d12100db370d81485cdf75e47ca`。
环境复用 `/root/turgutino/jev/venv`；JevForge源码引用此前已经复制、摘要固定的工程。
不修改原始训练工程、依赖或已完成的小样本模型。

本次“全量”指既有研究划分的全部合格财务样本，不把验证、测试或校准标签用于梯度更新。
财务版本保留约定的历史基本字段、多期财务及趋势，不加入关系摘要。

| 集合 | 样本数 | 用途 |
| --- | ---: | --- |
| 训练 | 35,942 | 完整一轮梯度更新 |
| 校准 | 4,046 | 从原39,988条训练期数据按企业/配对连通组留出 |
| 验证 | 45,148 | 完整固定方案评估 |
| 测试 | 42,510 | 完整固定方案评估 |

训练2019–2020、验证2022、测试2024，跨集合企业和配对隔离。
输入文件与索引摘要逐一对照全量manifest，不进行二次抽样或静默token截断。
训练/校准/验证/测试均正负各半，实际最长输入1598tokens，在2048预算内。
标签为未来12个月首次观测主要正式破产程序，不能扩大解释为任意不良事件。
匹配病例对照队列中的概率不能直接作为英国企业总体发生率。
2024测试集已有历史诊断，不作为从未查看的新验收集。

## 固定方案与批量实现

LoRA r16/alpha32，all-linear，dropout 0，seed42，固定一轮；
AdamW学习率1e-4、weight decay 0.01、10% warmup，末端降到最高学习率的10%。
有效批量32、micro batch16、评估批量16，BF16、非重入梯度检查点，输入预算2048tokens。
每个训练行恰好使用一次；打乱后在1024行窗口按长度分组，再打乱批次以减少填充。
训练中随机交换候选选项，并同步变换标签。

`scripts/jevforge_batch.py`实现左侧填充的共享候选树前向及向量化原始损失：
树交叉熵 + 合法质量KL + 非法token top64/tail KL + 两个位置top64/tail KL，lambda=1。
没有把原生目标替换成普通聊天SFT或单一二分类交叉熵。
训练参考分布通过关闭adapter获得；每批检查有限损失及原生root合法质量健康界限。

预检同时对照原始逐例树前向、损失值及梯度。
FP32对照用于检验数学一致性，BF16对照沿用原生score差0.25容差；
不同填充/批量下BF16可出现概率数值变化，不能声称逐位等价。
实际误差保存于 `results/equivalence.json`。
64例micro16预检reserved峰值5.69GiB；micro32没有吞吐收益。
关闭梯度检查点的实验超过20GiB预算，因此正式训练保留检查点。

GPU分配器预算20GiB，只限制本进程PyTorch，不设置其他任务配额。
默认省略重复的全量底座基线评估；`--baseline`可以另行启用。
完整验证、测试与校准均会执行。固定一轮，不依据本次验证/测试结果追加调参。

## 启动与制品

在全新的、已准备好full目录及固定JevForge副本的workspace执行，拒绝覆盖results。
服务器实际命令记录在 `command.json`。

```bash
/root/turgutino/jev/venv/bin/python -u \
  /root/autodl-tmp/lrr/uk-financial-full-20261018/train_uk_financial_full.py \
  --workspace /root/autodl-tmp/lrr/uk-financial-full-20261018 \
  --micro-batch 16 --batch-size 32 --eval-batch 16 --gpu-gib 20
```

- `run.log`、`run.pid`：独立后台进程日志与PID。
- `runtime.json`、`source-copy-manifest.json`：依赖、GPU、脚本和原始工程摘要。
- `results/config.json`、`equivalence.json`：样本数、token上限及计算一致性。
- `results/train_log.jsonl`、`training.json`：每步损失、完整覆盖计数与显存/耗时。
- `results/adapter/`：最终LoRA权重、配置和tokenizer；推理仍需固定底座。
- `results/calibration.json`：独立校准样本ID、标签、概率和温度。
- `results/finetuned.{valid,test}.json`：全量逐样本ID、标签、原始及校准概率。
- `results/summary.json`：ROC-AUC、PR-AP、KS、Brier、logloss及固定0.5阈值指标。
- `results/status.json`：运行阶段，只有`complete`表示训练、评估和重载均完成。

温度只在训练期独立校准集拟合，原始及校准指标同时保存。
保存后从底座与adapter独立重载5例，最大概率差不得超过1e-5。
本轮为一轮训练，仅保存最终adapter，不提供中途优化器恢复。
