# JevForge 上游源码

- 上游：https://github.com/pedroliveiraAI/LLMtoSystemOne
- 固定提交：`8986e521b8220dc41ff4de44fb418dc0da02afea`
- Python 包：`jevforge==0.1.0`，许可证见原始 `LICENSE`。
- 来源：协作者提供的副本；19 个 Python 文件、`pyproject.toml`、`LICENSE`
  已逐字节对照该上游提交。本目录保留原始实现，不应用本项目的代码风格改写。

## 纳入范围

保留完整 `jevforge/` 包、`pyproject.toml`、原始 README、许可证和上游测试。
不包含缓存、权重、实验结果、示例脚本、宣传图片或 `third_party/jevbench`。
`jevforge jevbench` 因此不在本副本的支持范围；UK 模型评分不依赖该评测工程。
上游 README 中其他未随附的资源链接仅作来源说明。

## 使用与更新

`models/service/pyproject.toml` 通过 uv 路径依赖安装本包，间接依赖统一锁在服务的
`uv.lock`；Docker 构建从当前仓库复制本目录，不访问上游 Git。

UK 专用输入、运行缓冲区恢复、校准与业务 HTTP 装配保留在本项目代码中。
更新上游时显式更改固定提交并审阅源码差异，保留版权声明，核对候选顺序、提示模板、
原始概率、保存重载与运行缓冲区；不能仅凭相同的 `0.1.0` 包版本判定兼容。
