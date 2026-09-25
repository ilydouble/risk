# 数据集选择与获取记录

核对日期：2026-09-25。

## 推荐顺序

| 数据集 | 数据内容 | 用途 | 获取 |
| --- | --- | --- | --- |
| SMEsD / ComRisk | 3976 家中国中小企业，企业/个人关系、诉讼事件、企业属性、行业/地区/资质超图、破产标签 | 优先验证 ComRisk 核心方法 | 作者 GitHub 直接提供，已下载 |
| HAT | 13489 企业、6855 个人、209195 边；股东与董事关系、破产标签 | 第二个图模型基准，需要独立适配 | 作者仓库公开数据，尚未下载核验文件 |
| American bankruptcy | 8262 家美国上市企业，78682 公司年度观测，1999–2018 年 | 海外企业财务基线/时序验证；无真实关系边 | 作者 GitHub 公开 CSV，CC BY 4.0 |
| Taiwanese Bankruptcy | 6819 样本、95 特征、破产标签 | 表格模型基线；无关系边 | UCI 直接下载，CC BY 4.0 |
| Polish Companies Bankruptcy | 64 财务比率；5 个不同预测期子集 | 财务与预测期限基线；无关系边 | UCI 直接下载，CC BY 4.0 |

不能把不同数据集的匿名企业拼成同一张图。表格数据的相似性构图只可称为人为构造的相似图，不能冒充真实股权/供应链传染网络。中国企业数据上测得的效果也不是海外企业效果。

## SMEsD 本地文件

位置：`backend/data/raw/smesd/`（被 gitignore 排除，不提交到公共仓库）。

- `train_data.pkl`
- `validate_data.pkl`
- `test_data.pkl`
- `split_data_idx.pkl`
- `meta_emb.pkl`
- `node2index.pkl`

来源提交：`a80524b3b67436cd2f74755f6ffa08a554ff2d02`。
下载已验证文件存在及 SHA-256；尚未完成内容转换/真实数据训练。
上游按破产时间划分训练（2014–2018）、验证（2019）、测试（2020–2021）。实际划分成员和特征观察时点需在适配时核验，不能将三个快照直接拼成单一静态图，否则可能泄漏未来信息。
上游未见明确 LICENSE 文件；公开可下载不等于无限制再分发授权。

## MSGraphFin 当前状态

已在用户登录浏览器确认文件列表，但点击原始文件会提示：
“目前只支持部分数据集的说明文件下载，数据文件请通过数据申请获取。”

路径：数据详情 → 加入购物车 → 工作台/个人中心/购物车 → 勾选数据集 → 普通下载 → 数据使用协议 → 后续申请。
已加入购物车，未接受协议、未提交申请。用户当前选择寻找其他可直接获取的数据。
本轮未找到可核实的 MSGraphFin 作者公开下载镜像。

## 官方/作者来源

- SMEsD：https://github.com/shaopengw/ComRisk/blob/main/SMEsD.md
- SMEsD 文件：https://github.com/shaopengw/ComRisk/tree/main/data
- HAT：https://github.com/hetergraphforbankruptcypredict/HAT
- 美国企业：https://github.com/sowide/bankruptcy_dataset
- 台湾企业：https://archive.ics.uci.edu/dataset/572/taiwanese+bankruptcy+prediction
- 波兰企业：https://archive.ics.uci.edu/dataset/365/polish+companies+bankruptcy
- MSGraphFin：https://nbsdc.cn/general/dataDetail?id=6742407e195d262b8b4468da&type=1
