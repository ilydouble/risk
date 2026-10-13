# SMEsD 不确定性与复核分流对照

## 目标与边界

补充 RiskGNN+ 文稿 Table 3 的对照，检验证据不确定性是否在预测概率之外改善分流。
历史 `run_smesd_experiments.py` 只训练普通分类器，并以概率熵代替 DST 不确定性，
不能作为双分支证据学习的复现入口。本实验另设入口，不覆盖历史表格。

默认读取原始 `datasets/smesd`，六个文件SHA-256与`datasets/README.md`记录的固定
上游提交一致。遵循原版训练入口的2816/721/491划分，不删除或重分配企业索引。
验证集合仅按旧实验脚本的RandomState(seed=42)拆成361家选模、360家校准。

原始train/valid重复35家、train/test重复17家、valid/test重复1家。重叠企业的
标签、属性和司法事件相同；来源确属上游划分，但现有说明不足以解释其构造原因。
这不构成擅自改变主对照协议的依据；保留交集并记录覆盖率假设未获验证。
不将同ID在转导图中出现与监督目标重复混为一谈，也不据此断言原划分必然无问题。

`--split-policy deduplicated`仅作为敏感性分析：按训练优先、验证其次去重后
train/valid/test=2816/686/474，再用default_rng(seed=42)将验证拆为343/343。
去重只改变目标样本，冻结图与预训练嵌入不变，不能声称严格归纳或时间点有效。

## 模型与校准协议

- 训练 seeds=14/42/2026；CPU单线程；250 epochs；Adam lr=0.01；余弦调度；梯度裁剪0.25。
- 每5轮计算选模验证集合AUC并选取最佳检查点；校准和测试不参与选模。
- ComRisk 对照复用冻结兼容实现，不是未改动上游源码的逐字节复现。
- 两模型使用相同输入、图、嵌入、尺寸和训练预算；均关闭社区先验。
- 证据模型调用真实 `RiskGNNPlus`，保留主分类器，训练两个证据头及融合证据损失。
- 原划分主结果保留RiskGNN+的可学习混合门控，ComRisk沿用固定门控；先前去重
  敏感性分析另有两者均固定为sigmoid(1)的控制。证据头沿用当前实现的exp(clamped logits)，不是文稿中的
  Softplus。此配置不承诺复现旧表数值。
- 主分类交叉熵权重1；融合/自身/图证据损失权重0.5/0.15/0.15；融合KL权重0.001。
- 保形 epsilon=0.05，证据/熵惩罚 beta=0.2，均提前固定，不用测试结果调参。
- 校准阈值取第 ceil((n+1)(1-epsilon)) 小的真实标签分数；位置超过n时取无穷。
  修复旧代码 `np.quantile(method='higher')` 与精确次序统计量不一致的问题。
- 覆盖率保证以分数可交换性为前提；时间划分与图相关性不自动满足该前提。

## 对照与指标

保形预测四行：ComRisk普通CP、RiskGNN+普通CP(beta=0)、RiskGNN+熵CP、
RiskGNN+证据CP。报告经验覆盖率、自动比例、自动错误率、模糊集率、空集率。
覆盖率指真实标签是否在预测集合中，不是自动判断准确率。
额外逐seed匹配证据CP的自动处理数量，用两模型的概率置信度选出同样多的企业，
直接检查加入证据项是否优于相同工作量的概率排序；该排序对照不继承CP覆盖率保证。

固定人工预算为0/10/20/30/50/70/90%，分别按ComRisk最大类别概率、
RiskGNN+最大类别概率、RiskGNN+负融合不确定性排序，保留相同数量的自动判断。
排序只看测试输入对应的模型输出，不看测试标签；并列按稳定企业ID打破。
自动数量=floor(N×(1-budget))，因此实际复核比例会有取整差异。
另外给出仅用校准分数确定的部署阈值及其测试表现；实际复核率可能偏离预算。

所有方法报告错误放行（预测不违约但实际违约）、错误拒绝，以及相应组内错误率。
空预测集也计入非自动处理工作量，不解释为已验证的OOD检测。
原稿加法不确定性项在固定阈值下会抬高两个类别分数，可能缩小预测集，
因此不能假定高不确定性必然产生双标签集或触发人工复核。

三种子报告均值和样本标准差；固定预算额外保存相对ComRisk的逐种子配对差值。
没有自动样本时准确率/错误率记为null，不伪记为0。多种子不等于多个独立数据集。

## 运行与制品

从仓库根目录，在包含torch、PyG、pandas、sklearn、matplotlib的研究环境运行：

```bash
python models/riskgnn+/run_triage_comparison.py \
  --data-dir datasets/smesd --epochs 250 --seeds 14 42 2026 \
  --output models/runs/triage-smesd-original-20261012
```

`--gate-policy fixed`可运行固定门控控制实验。原划分主结果目录为
`models/runs/triage-smesd-original-20261012`。上一轮去重可学习/固定门控制品
分别保留在`models/runs/triage-smesd-trainable-20261012`和
`models/runs/triage-smesd-deduplicated-20261012`，仅作敏感性分析。
`--reuse-baselines <已完成运行目录>` 仅在数据/配置/来源源码/样本/标签一致时
复用ComRisk检查点和预测，并记录来源及预测文件哈希；不会复用证据模型。

输出目录必须不存在。制品包含配置/数据/源码SHA-256、源码快照、最佳检查点、
选模轮次、耗时、校准/测试预测和真实Dirichlet参数、逐种子及汇总JSON/CSV。
检查点不内嵌冻结嵌入；恢复需使用清单指定的原始数据。
`COMPLETE` 只在全部种子成功后写入；未完成目录不能作为完整矩阵。

无需重训即可重放（同一划分、标签及唯一种子才允许合并）：

```bash
python models/riskgnn+/evaluate_triage_comparison.py \
  --predictions models/runs/triage-smesd-original-20261012/seed_*/predictions.npz \
  --output models/runs/triage-smesd-original-20261012-replay
```

新预测文件显式保存split_policy；original模式允许保留上游跨集合ID交集，
同时清单及重放报告标明交集数量与覆盖率假设未验证。未显式声明original的
预测文件仍拒绝校准/测试ID重叠。不同政策/划分/标签的预测禁止混合汇总。
原划分结果用于补Table 3对照；去重结果另列，不直接替换旧表。
