# UK 决策模型发布、安装与离线交付

所有示例从仓库根目录执行。`scripts/uk-decision` 使用模型服务的 uv 锁定环境，
不执行训练，也不依赖数据库；首次运行需下载 Python 依赖，现场提前准备镜像与模型。

## 生成本地发布包

```bash
./scripts/uk-decision package \
  --adapter /path/to/adapter \
  --output models/runs/releases/uk-financial-0.6b-v1.tar.gz
```

默认定义位于 `models/uk_decision/releases/uk-financial-0.6b-v1/`，可通过 `--definition` 选择新版本。
adapter 必须与该版本记录的七个文件逐字节一致；不修改训练机路径或重新保存权重。
命令生成附件和同目录的 `uk-financial-0.6b-v1.tar.release.json`，已有输出不覆盖。
同一环境、输入与加载代码重复打包的字节摘要一致；归档头不记录打包机绝对路径和文件时间。
adapter 配置中的原训练机路径仍按原始字节保留，不用于定位当前底座。

包内单一顶层目录 `<模型版本>/` 包含：

- `adapter/`：全部原始七个文件，包括 tokenizer、模板和原始 README。
- `input-contract.json`：冻结特征白名单、问题及候选顺序、token 上限和输出定义。
- `manifest.json`：格式版本、底座 revision、文件大小/SHA-256、JevForge 版本及加载代码摘要。
- `README.md`：本仓库整理的模型说明，不替换 adapter 内的原始 README。
- `acceptance/input.json`、`acceptance/reference.json`：工程探针及分设备参考结果。
- `calibration.json`：仅在确实取得正式文件、版本定义标记 available 时加入；本版没有。

底座不重复包含在 LoRA 附件中。manifest 列出固定底座的十个文件及摘要，安装时单独准备。
清单格式与 runtime API 版本均为 1；原始权重和运行缓冲区始终绑定同一版本。

## 安装与校验

尚未发布到 Release 时，可以直接使用本地产物和配套下载清单：

```bash
./scripts/uk-decision install \
  --release models/uk_decision/releases/uk-financial-0.6b-v1/release.json \
  --archive models/runs/releases/uk-financial-0.6b-v1.tar.gz \
  --destination models/weights/uk-financial-0.6b-v1-verified \
  --base-from models/weights/uk-financial-0.6b-v1/base
```

`--base-from` 核验并复制已有底座；或使用 `--with-base` 联网下载固定 revision。
不提供这两个参数时仅安装 LoRA 包，之后可重复安装补齐底座。默认安装位置为 `models/weights/<版本>/`。
开发者的已有临时模型目录不会被接管或覆盖，请另选空目录；已正确安装的同版本可重复执行。
相对路径始终按执行命令时的目录解释。

```bash
./scripts/uk-decision verify \
  --model-dir models/weights/uk-financial-0.6b-v1-verified \
  --base models/weights/uk-financial-0.6b-v1-verified/base

uv run --project models/service --locked python -m scripts.predict_uk_decision \
  --model-dir models/weights/uk-financial-0.6b-v1-verified \
  --input models/weights/uk-financial-0.6b-v1-verified/acceptance/input.json --device cpu
```

完整包模式先核对 Git 中的 manifest 摘要、包内文件和底座，再加载模型。
可用 `--release` 指定其他版本的受信清单；`--base` 可指定不在包内的本地底座。
不会自动回退到其他权重、下载模型或覆盖包内校准参数。

## 手工发布与其他开发者下载

1. 对照模型说明检查原始来源、缺项和参考结果，确认附件适合当前协作范围。
2. 将生成的 `.release.json` 内容存入该版本定义目录的 `release.json` 并审阅提交。
3. 在 risk 仓库对应代码 tag 的 GitHub Release 中上传 `.tar.gz` 和下载清单；
   推荐 tag 为 `model-uk-financial-0.6b-v1`，附件名为 `uk-financial-0.6b-v1.tar.gz`。
4. 上传后重新下载核对 SHA-256，再将 Git 中 `publication_status` 从 prepared 改为 published。
   原始附件不可替换；修订内容创建新模型版本。
5. 协作者安装 uv、认证 GitHub CLI 后运行 `./scripts/uk-decision install --with-base`。
   工具按受信清单从固定仓库、tag 和附件名下载；认证交给 gh，不传递明文 token 参数。

当前清单标记 prepared，省略 `--archive` 会明确报错，不假装已有可下载的 Release。
GitHub Release 不自动提供输入语义或校准能力，这些仍以版本内协议和实际文件为准。

## 离线现场

提前下载并核验完整安装目录，连同固定代码构建的镜像传到现场。
镜像自带正式 CLI，容器只读挂载完整模型目录，禁用网络后先跑工程探针。
Docker 的 GPU 驱动支持及端到端接入见[服务部署](integration.md)；现场不下载权重或依赖。
CPU/float32 与 GPU/bfloat16 的参考概率不同，不能拿一种精度的结果强行要求另一种逐位一致。
