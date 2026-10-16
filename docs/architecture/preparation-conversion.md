# 案例转换与企业导入

## 使用流程

数据准备保存原始 CSV 后进入助手。助手读取案例、报告与原映射，与用户确认不确定规则。
通过 preparation_save_plan 保存可执行草稿，默认立即执行试运行并返回真实报告。
明确只保存时传 run_trial=false，之后可调用 preparation_trial。
顶部“转换核验与导入”卡片显示数量变化、拒绝原因、前后样例及摘要；用户核对规则与样例，
勾选确认后点击“确认并导入”。成功后直接跳转到选中该数据集的概览或检索。
原数据准备页也展示同一转换结果；刷新后可继续。

## 工具与 HTTP 契约

- preparation_save_plan：绑定登录账号保存结构化规则，默认立即试运行；同步更新映射草稿，清除旧确认状态。
- preparation_trial：执行固定规则并持久化核验结果；不写入正式企业记录。
- preparation_result：查询最新匹配规则或指定任务的结果，包括状态与导入来源ID。
- 助手没有正式导入工具；不能把口头确认或试运行通过等同于已经导入。
- POST /api/v1/data-prep/conversion/save-plan：保存规则。
- POST /api/v1/data-prep/conversion/trial：试运行。
- POST /api/v1/data-prep/conversion/get：查询规则及结果。
- POST /api/v1/data-prep/conversion/import：任务ID与 confirm=true，用户界面明确确认后调用。
- 全部 HTTP 接口沿用会话认证、四字段信封和稳定错误码；OpenAPI 导出生成前端类型。

## 规则与边界

固定执行器 enterprise-csv-v1，不运行模型生成的 Python、SQL、表达式或网络请求。
原文件上限2 MiB、50000行、100列；转换产物上限16 MiB。
规则必须显式覆盖全部字段，可选择 ignore；唯一企业标识必须保留为文本。
目标支持 enterprise.id/name/community/label、features.<key>、attributes.<key>。
类型支持 text/number/integer/label/ignore。数值必须有限；整数限制在安全整数范围。
missingValues 定义缺失识别值，missing 指定 reject/null/fill；fill 必须明确给值。
未知行业可保留为原分类，不能自动猜测。标签须明确源值到0/1的映射与业务定义。
标签是数据属性，不是在线预测或校准违约概率。

去重可选择完全相同原始行保留一条；相同企业编号但内容不同会拒绝，不自动求和或取平均。
输出企业记录统一使用 import 快照，source_split 可作为来源属性保存，不据此生成训练划分。
不做任意聚合、编码、标准化、训练集拟合补值、图关系构建；复杂需求需扩展受控规则。

试运行返回 ready 或 blocked；输入数必须可由输出、去重和拒绝数解释。
存在任何拒绝记录或输出为空时禁止导入，不自动部分导入。
错误最多展示20条，成功样例最多5条，样例长文本截断至200字符；完整产物独立保存。
本版在受限输入内同步执行，并在线程中完成转换；不提供虚假的后台进度百分比。
服务重启前未提交的任务可重试，已完成任务可以恢复。

## 持久化与导入不变量

V0011 为准备记录增加 conversion_plan，新增 data_preparation_conversions。
任务冻结原文件摘要、映射摘要、规则、执行器版本、完整产物及产物摘要。
相同账号、案例、执行器和规则版本复用任务；修改映射后旧任务失效。
保存、试运行、导入均先锁准备记录；正式导入再次核验版本、产物摘要和企业记录结构。
Dataset、EnterpriseImport、EnterpriseRecord 与任务导入状态在同一事务提交。
并发或重复确认同一任务返回原数据集ID，不重复生成企业记录。
账号从 HTTP 鉴权或助手执行上下文绑定，模型不能传入 owner。

普通 CSV 导入的数据集标记 browseOnly=true、supportedRunnerIds=[]；
复用账号企业概览、检索和问数服务，不调用模型服务、不冒充训练标准包。
原文件与任务产物保存在业务数据库，无需重复上传到对象存储。
企业记录没有自动生成关系、预测或决策。

## 验证

单元测试覆盖规则白名单、标签语义、缺失处理、冲突拒绝、前导零和演示CSV数量核验。
隔离 PostgreSQL 覆盖账号隔离、方案变更失效、试运行不写企业数据、并发幂等导入、
以及导入后概览和检索。Strands MockTransport 测试验证真实工具协议调用、绑定账号、
错误脱敏及无导入工具。


## 工具参数与失败反馈

保存工具向模型提供由 ConversionPlan 生成的完整 JSON Schema，避免裸 dict 被解释成任意对象。
columns 为数组，labelMeaning 为字符串，values 为源文本到整数0/1的映射；分类字段使用text。
工具内部仍执行独立校验，失败返回最多8个路径和错误消息，不回传原始参数或异常上下文。
源字段覆盖校验会分别列出缺失和不存在的字段，不能凭历史回答补造字段。
asset_read 必须使用目录中的 preparation:<UUID>，读取失败须先修复读取，不得继续生成方案。
两次保存失败后助手应解释错误并停止修复尝试，不能改变业务语义绕过参数校验。
调用次数或生成预算耗尽返回 ASSISTANT_EXECUTION_LIMIT，页面展示真实原因，
不误报模型地址/模型名错误；异步Agent流在原执行上下文内关闭，避免trace清理异常。

保存工具的 run_trial 默认为 true，避免模型漏调下一工具却虚报试运行结果。
显式仅保存时可传 false；返回 task=null 不代表已执行。
保存成功但试运行异常时返回 planSaved 标记，后续可查询或重新试运行，不误报草稿未保存。
