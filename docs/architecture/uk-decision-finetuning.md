# UK 小型决策模型微调数据

目标：将最新 `datasets/uk_research` 转成结构化决策监督数据，供服务器已有训练代码适配。
0.6B候选底座为 `Qwen/Qwen3-0.6B`；它是因果语言模型，不能直接当作Laya检查点加载。
已确认服务器JevForge采用候选标签token评分，使用其原生LoRA及LLM-as-Jev损失。

## 构建

```bash
python3 scripts/prepare_uk_decisions.py \
  --output datasets/uk_decisions_20261018_smoke_v2 \
  --train-pairs 1000 --eval-pairs 250
```

全量构建时选择新目录并省略两个pair限制。已有输出拒绝覆盖。
输入为统一研究表和已验证的 `model-input/{train,valid,test}.json`。
脚本核对统一交付清单、原始特征/标签契约和三个快照的SHA256。

输出为三种划分各两份JSONL：

- `*.financial.jsonl`：财务、多期趋势和允许使用的历史基本字段。
- `*.graph.jsonl`：在相同财务输入上加入关系结构摘要。
- `sample-index.jsonl`：划分、行号、公司、样本、配对和时间，只用于审计。
- `manifest.json`：源摘要、样本数、输出摘要及研究限制。

每行包含 `state`、`questions`、`expected`，与Laya当前的硬标签训练格式一致。
所有样本使用同一问题和相同的两个选项，答案为 `event` 或 `no_event`。
未来如转换成聊天式SFT，只应将state和questions放进提示，将expected放进监督答案；
不能把sample-index、label、case/control角色、事件证据或未来事件日期拼入提示。

## 输入与标签

只使用feature-contract中的数值和分类白名单；移除冗余的逐字段missing标志，
省略不可用值。问题明确说明省略表示缺失、不表示零；零值、负值、币种保留。
不输入企业名称、公司编号、原始文档路径或哈希，降低身份记忆与元信息捷径。

标签口径是“未来12个月首次观测到主要正式破产程序”，不是任意不良事件或一般违约。
数据来自1:1匹配病例对照，输出概率只能先解释为研究队列条件概率，不能宣称英国总体风险。

关系摘要按原快照相同观察月份生成，仅包含群组类型、成员关系数、最大群组同伴数，
以及有向普通关系类型的数量。无邻居标签、事件传播或企业名称。
摘要使用该划分完整快照，而不是抽样后的群组，避免抽样改变结构定义。
它不等同于完整图编码，也不声称重建历史关系；当前源的普通边在切分后为空。

## 隔离和评估

复用既有划分：训练2019–2020、验证2022、测试2024，按企业和配对跨集合隔离。
完整校验12个月窗口及集合之间的观察/随访间隔；抽样按seed和pair哈希进行，保留完整病例对。
现有2024测试集已被此前模型诊断查看，不能当成从未查看的新验收集。

校准集应在训练集合内按企业/配对分组留出，不能逐行随机切分重复企业。
验证用于选轮数和阈值，最终测试只作固定方案评估。
至少报告ROC-AUC、PR-AUC、Brier、混淆矩阵和吞吐/显存，区分基线、微调、关系消融。
先做小规模前向/反向、保存/重载和推理一致性测试，再扩大训练。
训练和推理必须使用同一模板，检查真实token长度并禁止静默截断。

## 本轮已验证范围

本地已生成训练2000、验证500、测试500条，每份都有财务和关系摘要两个版本。
全量入口为 `datasets/uk_decisions_20261018`，训练39988、验证45148、测试42510条。
5项契约测试覆盖完整配对、抽样稳定、白名单、缺失/零/负数、非有限值和关系标签隔离。
服务器实际源为 `/root/turgutino/jev`，已复制274个源码及启动文件到
`/root/autodl-tmp/lrr/uk-decision-20261018`，保存源提交号及逐文件摘要。
RTX4090D 24GB上已有4B训练占约15.3GB；本轮保留它，拟用小批量LoRA限制显存。
独立SSH认证已由用户配置。固定缓存底座revision为
`c1899de289a04d12100db370d81485cdf75e47ca`。
真实分词预检最长1561tokens，2048预算内无截断。
训练按公司及匹配对连通分组留出200校准样本，其余1800用于优化，正负例各半。
3步LoRA实测成功保存，10.1M可训练参数，峰值allocated1.459GiB、reserved1.539GiB。
其他4B任务保持运行；autodl-tmp可用约0.9GB，只解压小样本且不重复下载权重。

## 服务器试跑

将 `scripts/run_uk_jevforge.py` 放入上述服务器目录，数据包解压smoke子目录。
目录中 `jevforge/` 为复制出的完整工程，训练环境复用原venv，无需修改原代码或安装依赖。

```bash
/root/turgutino/jev/venv/bin/python -u \
  /root/autodl-tmp/lrr/uk-decision-20261018/run_uk_jevforge.py \
  --workspace /root/autodl-tmp/lrr/uk-decision-20261018 \
  --max-steps 225 --batch-size 8 --gpu-gib 6
```

每种输入依次执行基线推理、1轮训练和微调后评估；batch_size为逐样本前向的梯度累积批量。
原生LoRA r16/alpha32、all-linear、学习率1e-4、seed42、bf16、梯度检查点。
不保存中间检查点，仅保留最终adapter；每阶段独立进程释放显存。
`--gpu-gib`限制PyTorch分配器预算，不是对整个GPU或其他进程的配额设置。
校准只用训练期独立200例拟合温度，不使用验证或测试标签拟合温度。
验证/测试报告原始及校准指标、固定0.5阈值混淆矩阵、吞吐和峰值显存。
重新加载adapter后复算5例，与第一次加载的最大概率误差须不超过1e-5。

`results/status.json`是进度；每版本的 `baseline.log/train.log/evaluate.log` 保留日志。
`baseline.json/evaluate.json/training-resource.json` 为真实结果。
已有adapter目录时拒绝覆盖，复跑应选新的独立workspace。

## 财务版已完成结果

1800训练/200校准/500验证/500测试，固定方案一轮225步，未按测试结果调参。
原始概率测试ROC-AUC从0.412480提升到0.745368，PR-AP0.705336、Brier0.216383。
验证AUC0.704512；固定0.5阈值测试Precision0.602667、Recall0.904、F1 0.7232。
混淆矩阵为 `[[101,149],[24,226]]`，行是真值0/1，列是预测0/1。
校准温度2.1147，校准后测试Brier0.223722，并未全面改善，报告保留两套概率指标。
训练用时635.6秒，峰值allocated1.517GiB/reserved1.607GiB，5例独立重载概率误差0。
这些是小样本匹配队列的单次试跑结果，不是英国企业总体风险或全量训练性能。

## 两版最终对比

| 输入 | 基线测试AUC | 微调验证AUC | 微调测试AUC | 测试PR-AP | 测试原始Brier |
| --- | ---: | ---: | ---: | ---: | ---: |
| 财务/历史基本信息 | 0.4125 | 0.7045 | 0.7454 | 0.7053 | 0.2164 |
| 加入关系结构摘要 | 0.3256 | 0.7884 | 0.6318 | 0.6213 | 0.3499 |

关系版一轮614.3秒、峰值reserved1.650GiB，重载概率误差0。
固定0.5阈值关系版测试Recall0.132、F1 0.2143，混淆矩阵 `[[225,25],[217,33]]`。
温度1.2519将关系版测试Brier降到0.3204，仍差于平衡样本恒报0.5的0.25。
两版均完成225步/1800有效训练例，所有损失有限，274份复制源码摘要仍一致。

按2022验证AUC会选关系版，但其2024测试显著下降，单一年份选模不足以保证跨年泛化。
本轮财务版测试更稳；关系摘要在该实验中没有带来跨年收益。
这与既有图覆盖漂移诊断相符，但尚不能单独归因于某类关系或断言真实关系没有价值。
不围绕本次已查看的测试集继续调参；后续应使用训练期滚动验证及新的独立留出验收。

本地完整证据：`datasets/uk_decision_pilot_20261018/results/summary.json`；
服务器完整报告：`/root/autodl-tmp/lrr/uk-decision-20261018/results/summary.json`。
证据压缩包另含训练/评估日志、逐样本概率、运行版本、模型/源码摘要及配置，不含权重。
两套权重分别保存在服务器 `results/{financial,graph}/adapter/`。

## 加载已训练的财务版

在服务器用原venv运行下面的Python代码。输入取一行同结构的JSONL；推理不读取expected。
输出是两类候选的原始归一化概率，温度校准参数另在evaluate.json中。

```python
import json
import sys
from pathlib import Path

root = Path("/root/autodl-tmp/lrr/uk-decision-20261018")
sys.path.insert(0, str(root / "jevforge"))
from jevforge.jev import Jev

base = (
    "/root/autodl-tmp/turgutino/jev/hf/hub/models--Qwen--Qwen3-0.6B/"
    "snapshots/c1899de289a04d12100db370d81485cdf75e47ca"
)
model = Jev.from_pretrained(
    base, adapter=str(root / "results/financial/adapter"),
    device="cuda", dtype="bfloat16",
)
with (root / "smoke/test.financial.jsonl").open() as stream:
    example = json.loads(next(stream))
q = example["questions"]["formal_insolvency_12m"]
probabilities = model.decide(
    json.dumps(example["state"], separators=(",", ":")),
    list(q["criteria"].values()), q["instructions"],
)
print(dict(zip(q["criteria"], probabilities, strict=True)))
```

参考：[Laya微调格式](https://github.com/NandhaKishorM/laya/blob/main/docs/finetune.md)、
[Qwen3-0.6B](https://huggingface.co/Qwen/Qwen3-0.6B)。
