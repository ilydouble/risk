# Baseline 来源与本地约定

本目录的模型源码来自论文作者公开的 ComRisk Git 仓库，用作 `models/riskgnn` 与 `models/riskgnn+` 的原始算法基线。

## 固定来源

- 仓库：<https://github.com/shaopengw/ComRisk>
- 提交：`a80524b3b67436cd2f74755f6ffa08a554ff2d02`
- 下载归档 SHA-256：`ca09a6c96c4ad76bf03a3b5174354cea7d0947b05bb18768364f938fc0c36c1b`
- 原始论文：Combining intra-risk and contagion risk for enterprise bankruptcy prediction using graph neural networks

以下文件与该提交逐字节一致：

- `README.md`
- `SMEsD.md`
- `gnn.py`
- `train.py`
- `utils.py`
- `sample.py`
- `metapath2vec`

上游没有提供 LICENSE 或 COPYING 文件。保留来源和论文引用不代表已取得重新分发授权；比赛或对外发布前需要单独核实代码与数据许可。

## 数据目录

上游代码把输入路径固定为 `./data/*.pkl`。为保持源码不变，本目录的 `data` 是相对符号链接：

```text
models/baseline/data -> ../../datasets/smesd
```

真实文件只保存在根目录 `datasets/smesd/`，不会复制进模型目录或提交 Git。文件哈希见 `datasets/README.md`。这些 pickle 只应从上述固定提交取得并在哈希一致时加载；不要加载来源不明的 pickle。

模型仍按上游逻辑写入 `models/baseline/model_save/`，该目录除 `.gitkeep` 外被忽略。

## 原始运行环境

上游 README 记录的环境为：

- Python 3.7.10
- PyTorch 1.8.1 CPU
- torch-geometric 1.7.0

上游没有提供完整锁文件。当前仓库的 Python 3.12 环境不等价，不能把“源码可读取”当作“原始实验已复现”。要复现论文结果，应另建兼容的隔离环境，并按上游说明替换 PyG 采样文件。

运行时必须让当前目录为 baseline，因为上游使用相对路径：

```bash
cd models/baseline
python train.py
```

`README.md` 和 `SMEsD.md` 保持上游原文；本文件只记录本仓库的集成方式和限制。
