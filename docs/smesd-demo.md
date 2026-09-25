# SMEsD 基准演示

本项目将公开 SMEsD 的 474 家匿名测试企业与已选模型权重放在独立 `/benchmark` 专区。原工作台八家种子企业、文件上传/下载、报告和演示模型页维持原有数据与样式；两套编号不互相映射。

## 运行

```bash
cp .env.example .env
# 将基础设施的示例凭据改为本地独有值
docker compose up --build -d
```

访问 `http://localhost:18080`，先注册并登录，再进入侧栏 **SMEsD 基准**。依次查看检索 `C00010`、匿名企业画像、评分解释、一跳关系图与模型评估页。相关 POST 接口走现有 Caddy → Go 网关 → FastAPI 路径，使用 Session、同源校验和四字段响应信封。

## 核验

`C00010` 破产分类概率约 `0.726873`，原始一跳关系 16 条；保存的测试 ROC-AUC 约 `0.793637`。这些数字可用于确认权重和快照正确加载。完整训练集不随包提供，此处未重新训练模型。

```bash
cd backend
uv sync --dev
uv run pytest -q tests/test_model.py tests/test_demo_bundle.py tests/test_benchmark_api.py
uv run python -m risk_api.export_openapi
cd ../frontend
npm run api:generate
npm run lint && npm run type-check && npm run build
```

## 展示边界

企业编号为匿名样本，没有真实公司名称；线性演示分数不是业务评分卡。破产分类概率不是固定未来窗口违约概率，特征遮蔽敏感性不是 SHAP 或因果贡献；图谱关系只是原始一跳有向边，不代表已经验证的风险传播。数据来源、许可待核实状态与详细边界见[架构说明](architecture/benchmark.md)。
