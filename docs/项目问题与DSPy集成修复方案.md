# 项目问题与 DSPy 集成修复方案

## 1. 文档目的

本文档针对 [项目问题与DSPy集成审查报告.md](D:\project\Prompt-Optimization-Studio\docs\项目问题与DSPy集成审查报告.md) 中列出的所有问题，给出一份可执行的修复方案。

目标不是泛泛而谈“建议优化”，而是明确：

1. 每个问题应该改什么
2. 应该改哪些文件
3. 改完后系统行为会怎样变化
4. 哪些点适合一次性改完，哪些点应该分阶段推进
5. 哪些地方需要你拍板决定具体策略

本文会默认遵循一个原则：

- **优先修复语义错误和结果误导问题**
- **其次再修复字段一致性和接口契约问题**
- **最后再处理 lint、文档和治理问题**

## 1.1 已确认设计决策

你已经确认了以下 5 个关键设计决策，本文档后续方案均以此为准：

1. `Prompt.output_schema_json` 不允许独立编辑，直接继承 `Project.output_schema_json`
2. optimization 导出的 `optimized_prompt` artifact 改名为 `derived_prompt_candidate`
3. 多字段 input signature 这一轮就做，不延期
4. 当前平台正式支持的 output schema 只限定为 `object` 和 `string`
5. 保留中文文档，调整 Ruff，而不是强行把中文文档改成英文/半角体系

这 5 个决策意味着本轮改造不再是“小修小补”，而是一次明确的契约收口：

- Project 成为唯一任务输出契约中心
- Prompt 层不再拥有独立 output schema 主权
- DSPy 集成从“单 text 字符串适配”升级为“按输入字段建模”
- 文档、lint、实现三者都要向同一套真实边界收敛

---

## 2. 总体修复策略

我建议把修复工作拆成 4 个阶段，而不是一次性重写。

### 阶段 1：校正结果语义

先修复那些“系统能跑，但结果不可信”的问题：

1. DSPy 优化 metric 从布尔信号改为连续分数信号
2. mock 模式下去掉“伪优化”表达
3. 优化 artifact 命名和内容对齐
4. evaluation report 中恢复原始输入语义

### 阶段 2：校正任务契约

然后修复“字段能存但实际无效”的问题：

1. Project / Custom Task Template 的跨字段一致性校验
2. Prompt 与 Project schema 强一致，改成继承模型
3. Dataset 导入时按项目输出 schema 归一化，而不是硬塞 `answer`

### 阶段 3：重构 DSPy 集成模型

这是结构性变更：

1. 从单 `text -> answer` 升级到多字段 input signature
2. 明确支持的 output schema 范围
3. 重构 Prompt 模板变量约束

### 阶段 4：治理与收尾

1. resource limit 真正落地
2. lint 规则与中文文档规范对齐
3. README 与代码同步
4. 增补测试

---

## 3. 修复优先级总览

建议优先级如下：

### P0

- 优化器 metric 语义修复
- mock 模式误导性输出修复
- artifact/report 关键字段修复

### P1

- Project / Custom Task / Prompt 契约一致性校验
- Dataset 导入归一化修复

### P2

- 多字段 DSPy signature 改造
- output schema 支持边界重定义

### P3

- lint / README / resource limit / 测试体系完善

---

## 4. 逐项修复方案

## 4.1 修复：DSPy 优化目标和平台评分目标不一致

### 当前问题

当前 `build_optimizer_metric()` 在非 GEPA 模式下返回：

- `bool(result["correct"])`

这会把：

- `f1_token`
- `weighted_numeric_fields_accuracy`
- `llm_judge`
- `json_all_fields_accuracy`

这类连续分数 metric，全部降级成二值成功/失败信号。

本地 `dspy==3.1.3` 里：

- `BootstrapFewShot` 明确支持 numerical metric，并带 `metric_threshold`
- `MIPROv2` 也支持 callable metric 供 `Evaluate` 使用

所以这不是 DSPy 限制，而是当前项目自己的 metric adapter 设计错误。

### 目标行为

优化器应尽量直接消费连续分数：

- `BootstrapFewShot`：返回 `float score`
- `MIPROv2`：返回 `float score`
- `GEPA`：返回 `ScoreWithFeedback(score, feedback)`

只有在某些特殊 metric 明确只能二值化时，才回退为布尔。

### 建议修改

#### 方案 A：统一返回浮点分数

在 `build_optimizer_metric()` 中：

- 非 GEPA 路径返回 `float(result["score"])`
- GEPA 路径返回 `ScoreWithFeedback`

同时：

- `BootstrapFewShot` 使用 `metric_threshold`
- 默认 threshold 从项目 metric 配置推导

推荐原因：

- 改动最小
- 最符合平台报告里的 score 语义
- DSPy 3.1.3 已经支持这个方向

#### 方案 B：按 optimizer 区分返回值

- `BootstrapFewShot` 返回 float
- `MIPROv2` 返回 float
- 某些未来 optimizer 仍允许 bool

推荐程度低于方案 A，因为会让 adapter 逻辑更复杂。

### 具体修改文件

- `backend/services/optimization_service.py`

重点改动：

1. `build_optimizer_metric()`
2. `_compile_bootstrap_fewshot()`
3. `create_optimization_run_and_job()` 中保存 optimizer 相关阈值快照

### 建议新增函数

建议新增：

- `resolve_metric_threshold(metric_config: dict[str, Any]) -> float | None`

用途：

- 从 `correct_threshold`
- 或 `pass_threshold`
- 或默认值

推导 BootstrapFewShot 的 `metric_threshold`

### 风险

风险不在 DSPy，而在你们已有评测结果会发生变化。

因为以前优化器在追 bool(correct)，现在会追 score。

### 回归测试建议

新增测试：

1. `build_optimizer_metric()` 对 `f1_token` 返回 float
2. `build_optimizer_metric()` 对 `weighted_numeric_fields_accuracy` 返回 float
3. `BootstrapFewShot` compile 时 metric_threshold 被正确传入
4. 优化后 score 改进但未跨阈值时，优化器仍能看到收益

---

## 4.2 修复：mock 模式下“伪优化”输出

### 当前问题

mock 模式下：

- compile 直接返回原始 program
- prediction 直接返回 gold

但最终仍会：

- 生成 `optimized_prompt`
- 生成 `prompt_diff`
- 在 `system_prompt` 后追加 `Optimizer note: refined by ...`

这会制造“已经完成有效优化”的错觉。

### 目标行为

mock 模式只应该表达：

- 平台链路跑通了
- 不是模型真的优化了

### 建议修改

#### 方案 A：mock 模式下不生成优化后 Prompt artifact

在 `execute_optimization_run()` 中：

- 如果 `runtime.provider == "mock"`
- `optimized_prompt = None`
- `prompt_diff = None`
- `compiled_program = None` 或仅保留基础状态

报告里明确写：

- `execution_mode = "mock"`
- `optimization_effective = false`

推荐原因：

- 最不误导用户
- 语义最诚实

#### 方案 B：仍生成 artifact，但字段中明确标记 `mock_placeholder`

例如：

```json
{
  "mock_placeholder": true,
  "reason": "No real optimization performed in mock mode"
}
```

推荐程度次于 A，因为仍会污染前端阅读体验。

### 具体修改文件

- `backend/services/optimization_service.py`
- `backend/schemas/optimization.py`
- `frontend/app/[lang]/reports/page.tsx`

### 前端展示建议

在 reports 页加一个明显提示：

- `This run was executed in mock mode; no real prompt optimization was performed.`

### 回归测试建议

新增测试：

1. mock 模式下 optimization report 显示 `execution_mode=mock`
2. mock 模式下不生成 `optimized_prompt` 或其内容带 `mock_placeholder`
3. reports 页面读取缺失 `optimized_prompt` artifact 时不报错

---

## 4.3 修复：`optimized_prompt` 不是 DSPy 权威状态映射

### 当前问题

当前 `optimized_prompt` 是通过：

- 读取 `optimized_program.predict.signature.instructions`
- 再附加到原 `system_prompt`

构造出来的。

但 DSPy 优化器未必只改 instruction，可能还改 demos 或内部状态。

### 目标行为

平台必须区分两类结果：

1. **DSPy 编译结果**
2. **平台可导出的业务 Prompt**

这两者不是同一个概念。

### 建议修改

#### 方案 A：把 `optimized_prompt` 改名成 `derived_prompt_candidate`

这是我最推荐的方案。

把当前 artifact 语义改成：

- 不是“权威优化后 Prompt”
- 而是“平台根据 DSPy 状态推导出的可编辑候选 Prompt”

同时保留：

- `compiled_program.json`
- `fewshot_demos.json`

让用户知道真正权威的是 DSPy 编译状态，不是这个导出文本。

#### 方案 B：继续叫 `optimized_prompt`，但加 metadata 标明导出策略

例如：

```json
{
  "export_strategy": "append_signature_instructions_to_system_prompt"
}
```

可以做，但不如直接改名清晰。

### 推荐修改

我建议：

1. artifact 类型由 `optimized_prompt` 改成 `derived_prompt_candidate`
2. `prompt_diff` 改成 `derived_prompt_diff`
3. 报告页文案改成“平台推导后的 Prompt 候选版本”

### 具体修改文件

- `backend/services/optimization_service.py`
- `backend/schemas/optimization.py`
- `frontend/app/[lang]/reports/page.tsx`

### 回归测试建议

1. 优化报告 artifact 列表更新
2. 前端 reports 页面正确读取新的 artifact 类型

---

## 4.4 修复：optimization `predictions.json` 内容与命名不一致

### 当前问题

当前 optimization 下的 `predictions.json` 实际只保存：

- `optimized_results`

但文件名看起来像完整预测。

### 目标行为

artifact 名称必须和内容严格对应。

### 建议修改

#### 方案 A：拆成两个 artifact

- `baseline_predictions.json`
- `optimized_predictions.json`

同时额外保留：

- `comparative_results.json`

推荐原因：

- 语义最清楚
- 便于前端和离线分析

#### 方案 B：保留一个 `predictions.json`，但内容改成：

```json
{
  "baseline_results": [...],
  "optimized_results": [...],
  "comparative_results": [...]
}
```

也可行，但文件内容更重。

### 推荐方案

推荐方案 A。

### 具体修改文件

- `backend/services/optimization_service.py`
- `backend/schemas/optimization.py`
- `frontend/app/[lang]/reports/page.tsx`

### 回归测试建议

1. artifact 列表包含三个文件
2. manifest 内容与实际文件一致
3. 报告页能分别预览 baseline / optimized / comparative

---

## 4.5 修复：evaluation 报告中 `input_json` 被污染

### 当前问题

当前报告里写的是：

- `{"text": dsp_example.text}`

但 `dsp_example.text` 已经是渲染后的 Prompt 文本，而不是原始样本输入。

### 目标行为

报告里应该同时区分：

1. `raw_input_json`
2. `rendered_input_text`

### 建议修改

把当前 prediction record 改成：

```json
{
  "raw_input_json": {...},
  "rendered_input_text": "...",
  "expected_output_json": {...},
  "prediction": {...}
}
```

并删除当前误导性的：

- `input_json: {"text": dsp_example.text}`

### 需要的代码改造

当前 `to_dspy_example()` 里没有保留原始 `input_json`。

建议在 `dspy.Example` 中附加：

- `raw_input_json=example.input_json`

然后在 evaluation / optimization 记录阶段直接使用。

### 具体修改文件

- `backend/services/dspy_program_factory.py`
- `backend/services/evaluation_service.py`
- `backend/services/optimization_service.py`

### 回归测试建议

1. report 中出现 `raw_input_json`
2. report 中出现 `rendered_input_text`
3. 原始输入与渲染输入语义分离

---

## 4.6 修复：Project / Custom Task Template 手工保存缺少跨字段一致性校验

### 当前问题

AI 草稿生成路径做了 `validate_generated_template_alignment()`，但手工保存路径没有。

### 目标行为

所有写入路径都必须共享同一套契约校验。

### 建议修改

抽出统一校验入口：

- `validate_task_contract_alignment(payload: dict[str, Any], *, task_kind: str) -> None`

内部调用：

- `validate_generated_template_alignment()`
- `ensure_task_key_allowed()`
- 额外补充 project 级字段规则

### 落地方式

在下面这些入口统一调用：

1. `POST /custom-task-templates`
2. `PATCH /custom-task-templates/{id}`
3. `POST /projects`
4. `PATCH /projects/{id}`

### 细节建议

Project 的 `builtin` 路径和 `custom` 路径可以分开：

- `builtin`：只允许覆盖模板字段，但覆盖后仍必须与 schema 对齐
- `custom`：完全按用户给定字段校验

### 具体修改文件

- `backend/services/validators.py`
- `backend/api/routes/custom_task_templates.py`
- `backend/api/routes/projects.py`

### 回归测试建议

1. 手工创建非法 custom task template 被拒绝
2. 手工更新非法 project 契约被拒绝
3. AI 草稿路径仍然能通过同样校验

---

## 4.7 修复：Prompt 与 Project output schema 缺少硬对齐

### 当前问题

Prompt 可以保存自己的 `output_schema_json`，但当前没有强制要求它与所属 Project 一致。

### 目标行为

必须明确平台立场：

### 已确认策略

这里采用你已确认的方案：

- `Prompt.output_schema_json` 不再允许独立编辑
- Prompt 的输出契约完全继承 Project

### 推荐改法

直接一步到位，不做“双轨兼容”：

1. Prompt 创建接口不再把 `output_schema_json` 作为用户输入来源
2. 后端创建 Prompt 时自动复制 `project.output_schema_json`
3. Prompt 新版本创建时同样自动沿用所属 Project 的当前 output schema
4. 前端 Prompt 页面把 `output_schema_json` 改为只读展示

### 数据模型说明

这里有两种实现路线：

#### 路线 A：数据库字段保留，但由后端托管

- `Prompt.output_schema_json` 字段仍保留
- 但用户不能编辑
- 创建/版本化时由后端写入 `project.output_schema_json`

优点：

- 改动小
- 兼容现有评测/快照逻辑

#### 路线 B：数据库字段删除

- 从 `Prompt` 模型中去掉 `output_schema_json`
- 运行时统一从 Project 取

不建议这一轮做。

原因：

- 牵涉数据库迁移
- 牵涉快照结构和历史兼容
- 当前收益不如路线 A 高

### 当前推荐

本轮采用路线 A。

### 具体修改文件

- `backend/api/routes/prompts.py`
- `backend/schemas/prompt.py`
- `frontend/app/[lang]/prompts/page.tsx`

### 前端修改建议

Prompt 页里的 `output_schema_json` 文本框改成：

- 只读展示
- 文案说明“继承自当前项目”

---

## 4.8 修复：Dataset 导入时 scalar 输出被硬转成 `answer`

### 当前问题

当前 `_normalize_output()` 对非 object 输出统一包成：

- `{"answer": value}`

这会和 `label` / `score` / `result` 等任务契约冲突。

### 目标行为

Dataset 导入应该根据 **项目 output schema** 做归一化，而不是根据硬编码字段名。

### 建议修改

把 `_normalize_output(value)` 改成：

- `_normalize_output(value, output_schema_json)`

策略：

#### 情况 1：schema 是 object 且只有一个字段

自动包到那个字段里。

例如：

- schema 只有 `label`
- scalar `"refund"` 归一化成 `{"label": "refund"}`

#### 情况 2：schema 是 object 且有多个字段

如果输入不是 object，直接报错，不做猜测。

#### 情况 3：schema 是 string

统一归一化成：

- `{"answer": value}`

或更进一步直接显式支持 string payload。

### 需要的接口改造

导入服务要拿到 Project 或 Dataset 契约，而不是只拿 `output_field`。

当前 `/datasets/import` 已经收到 `schema_json`，但这只是输入 schema，缺少 output schema。

因此建议在导入请求里新增：

- `output_schema_json`

或者更直接：

- 后端根据 `project_id` 自动加载 Project 的 `output_schema_json`

推荐后者，避免前端重复传契约。

### 具体修改文件

- `backend/services/dataset_service.py`
- `backend/api/routes/datasets.py`
- `backend/schemas/dataset.py`
- `frontend/app/[lang]/datasets/page.tsx`

### 回归测试建议

1. 单字段 object schema 时 scalar 自动映射到正确字段
2. 多字段 object schema 时 scalar 导入报错
3. `label` / `score` / `result` 三种典型字段都覆盖测试

---

## 4.9 修复：synthetic `metadata_json` 在 mock 与真实 LLM 模式下不一致

### 当前问题

mock 和真实 LLM 模式写入的 metadata 字段结构不同。

### 目标行为

所有 synthetic 示例都应至少包含统一字段：

- `source`
- `command`
- `generation_model`
- `batch_index`
- `generation_mode`

### 建议修改

统一 mock 路径和真实 LLM 路径的 metadata 结构：

#### mock

```json
{
  "source": "synthetic_generated",
  "command": "...",
  "generation_model": "mock",
  "batch_index": 1,
  "generation_mode": "mock"
}
```

#### openai

```json
{
  "source": "synthetic_generated",
  "command": "...",
  "generation_model": "deepseek-v4-pro",
  "batch_index": 1,
  "generation_mode": "openai"
}
```

### 具体修改文件

- `backend/services/dataset_generation.py`

### 回归测试建议

1. mock 模式 metadata 完整
2. openai 模式 metadata 完整
3. 两者字段集合一致

---

## 4.10 修复：resource limit 配置形同虚设

### 当前问题

配置里已经定义了：

- `max_generated_examples`
- `max_examples_per_run`
- `max_lm_calls`
- `max_metric_calls`
- `max_runtime_seconds`

但多数没有实际执法逻辑。

### 目标行为

每个限制项都要么：

1. 真正执行
2. 要么删除

不能长期保留“伪治理字段”。

### 建议逐项落地

#### `max_generated_examples`

在 dataset generate 请求处硬限制：

- `count <= settings.max_generated_examples`

#### `max_examples_per_run`

在 evaluation / optimization 创建阶段检查：

- 可执行样本数不能超过该上限

#### `max_metric_calls`

除了 GEPA 外，也可以：

- 在 optimization/evaluation 循环里用计数器守护

#### `max_runtime_seconds`

在 Worker 执行层引入超时控制：

- 运行开始记录时间
- 周期性检查
- 超时后安全失败

#### `max_lm_calls`

这个最难做，因为 DSPy 内部也会调 LM。

建议第一阶段先不深接 DSPy 内部 hook，而是：

- 先对平台显式调用的 OpenAI client 计数
- GEPA / MIPROv2 路径先只在文档中说明“暂未完全覆盖”

### 具体修改文件

- `backend/api/routes/datasets.py`
- `backend/services/evaluation_service.py`
- `backend/services/optimization_service.py`
- `backend/workers/job_router.py`

### 建议

这一项不建议和前面 P0/P1 混做，可以放在第三批。

---

## 4.11 修复：多字段 input signature 改造

这是最大的结构改造项。

### 当前问题

当前所有任务都被压成：

- `text -> answer`

这让：

- `input_schema_json`
- Prompt 模板变量
- DSPy signature

三者完全脱节。

### 已确认策略

这里采用你已确认的方案：

- 多字段 input signature 这一轮就做

这意味着本轮不是给出“未来方向”，而是要直接落地到代码。

### 目标行为

把项目输入契约真正映射到 DSPy signature。

### 本轮支持边界

为了控制复杂度，我建议本轮多字段 signature 只支持：

- 顶层 `object`
- 输入字段类型为 `string | number | integer | boolean`

暂不把以下类型映射为独立 signature 参数：

- `array`
- 嵌套 `object`

对于这些复杂字段，建议本轮先拒绝或要求调用方手工折叠成字符串字段。

### 推荐改造方案

#### 第一步：从 `input_schema_json` 生成输入字段列表

例如：

```json
{
  "type": "object",
  "properties": {
    "question": {"type": "string"},
    "context": {"type": "string"}
  },
  "required": ["question", "context"]
}
```

生成：

```python
["question", "context"]
```

#### 第二步：DSPy Signature 改成多字段输入

例如：

```python
dspy.Signature("question, context -> answer", instructions=instructions)
```

#### 第三步：Prompt 模板变量规则同步放开

当前只允许 `{text}`，改成：

- 允许所有 `input_schema_json.properties` 中出现的字段变量

例如：

- `{question}`
- `{context}`
- `{title}`
- `{body}`

#### 第四步：`to_dspy_example()` 直接构造多输入 Example

不再只传：

- `text=rendered_text`

而是同时传：

- `question=...`
- `context=...`

同时继续保留：

- `rendered_input_text`

用于日志和报告展示。

### 关于 `user_template`

多字段 signature 落地后，`user_template` 仍然保留，但语义要变成：

- 用于生成一份“模型看到的完整用户提示文本”
- 而不是平台唯一输入通道

换句话说，本轮建议采用：

- **DSPy signature 显式多字段输入**
- **内部仍保留一个渲染后的聚合文本字段作为 prompt 主体**

这比完全抛弃 `user_template` 风险小。

### 推荐的具体实现

建议把 signature 改成：

- `field_1, field_2, ..., rendered_prompt -> answer`

但这里我不建议这样做。

原因是：

- 会让 signature 里同时存在原始字段和拼接文本，职责混乱

更合理的做法是：

#### 方案 A：signature 只保留原始字段

例如：

```python
dspy.Signature("question, context -> answer", instructions=instructions)
```

程序内部在 `forward()` 里把这些字段渲染成 prompt 再调用 predictor。

这是更工程化的做法，但改动略大。

#### 方案 B：signature 仍然只接收原始字段，instructions 负责说明输出结构，不再把 `user_template` 拼进 instructions

这会改变当前 Prompt 工作流较多。

### 当前推荐

为了兼容现有工作流，我建议采用一个折中但清晰的实现：

1. signature 输入字段来自 `input_schema_json`
2. `PromptOptimizationProgram.forward()` 接收这些原始字段
3. `forward()` 内部调用统一渲染函数，根据 `user_template` 生成最终 prompt 文本
4. predictor 仍然调用单槽位预测器，但这是 Program 内部细节，不再暴露为平台输入契约

也就是：

- **平台契约是多字段**
- **DSPy 内部仍可通过模板渲染成文本 prompt**

这样能同时保住：

- 多字段输入能力
- 现有 `user_template` 设计
- 当前基于文本 prompt 的优化思路

### 具体修改文件

- `backend/services/dspy_program_factory.py`
- `backend/schemas/prompt.py`
- `backend/services/validators.py`
- `frontend/app/[lang]/prompts/page.tsx`
- `frontend/app/[lang]/projects/page.tsx`

### 回归测试建议

1. 多字段 schema 能生成正确 signature
2. Prompt 模板能校验多个变量
3. `to_dspy_example()` 能传递多输入字段
4. `question/context` 场景评测跑通

---

## 4.12 修复：重新定义 output schema 支持边界

### 当前问题

平台表面支持任意 JSON schema，实际上只有 object 最完整。

### 已确认策略

这里采用你已确认的方案：

- 当前平台正式支持的 output schema 只限定为 `object` 和 `string`

### 推荐策略

这轮直接把这个边界变成硬规则，而不是 warning。

#### `object`

完整支持：

- 输出解析
- metric 对齐
- report 展示

#### `string`

有限支持：

- 内部统一映射为 `{"answer": "..."}`
- 相关 metric 继续走当前 string/answer 兼容路径

#### 直接拒绝的类型

- `array`
- `number`
- `integer`
- `boolean`
- 顶层嵌套复杂结构但不含 object 主体约束的情况

### 实施建议

在以下写入入口加硬校验：

1. Project create / update
2. Custom Task Template create / update
3. Custom Task Template draft 生成结果校验

这样能保证错误 schema 在保存阶段就被挡住。

### 具体修改文件

- `backend/services/validators.py`
- `backend/services/evaluation_service.py`
- `backend/services/dspy_program_factory.py`
- `README.md`

---

## 4.13 修复：lint 规范与中文文档规范冲突

### 当前问题

Ruff 当前配置会大量拒绝中文全角标点。

### 目标行为

要么：

1. 项目允许中文 docstring 和中文全角标点
2. 要么全仓切回英文/半角风格

不能两边都要。

### 推荐方案

推荐保留中文文档，调整 Ruff 配置。

原因：

- 你们现有注释、文档和 AGENTS 都是中文
- 全仓改英文成本高且收益低

### 建议改法

在 Ruff 中忽略：

- `RUF001`
- `RUF002`
- `RUF003`

或者至少对 `backend/**` 和 `tests/**` 的 docstring/comment 场景放开。

同时修复真正有价值的问题：

- import 排序
- `E402`

### 具体修改文件

- `pyproject.toml`
- `tests/*.py`
- 少量 import block

### 回归标准

目标不是“零 lint 报错”，而是：

- lint 只报真正有意义的问题

---

## 4.14 修复：README 与代码漂移

### 当前问题

README 声称支持的 built-in task 比实际多。

### 目标行为

README 必须和 `task_catalog.py` 实际一致。

### 建议修改

更新 README 中：

1. 内置任务列表
2. 运行模式说明
3. output schema 支持边界
4. mock 模式语义说明
5. Prompt / Project 契约说明

---

## 5. 推荐实施顺序

我建议按下面顺序动手：

### 批次 1

1. 优化 metric 从 bool 改 float
2. mock 模式去伪优化
3. 优化 artifact 命名修正
4. evaluation report 输入字段修正

### 批次 2

1. Project / Custom Task 契约一致性校验
2. Prompt 与 Project schema 对齐
3. 多字段 input signature 改造
4. Prompt 模板变量规则重构

### 批次 3

1. Dataset scalar 输出归一化修复
2. synthetic metadata 统一
3. output schema 支持边界重定义

### 批次 4

1. resource limit 落地
2. lint 规则修正
3. README 更新
4. 补测试

### 为什么这样排

这个顺序是按“先修语义，再收契约，再落运行结构，再清治理”的原则排的。

其中最关键的调整有两个：

1. 多字段 input signature 不再放到靠后的“未来改造项”，而是在 Prompt / Project 契约收口之后立刻进入实现
2. Dataset 导入归一化和 synthetic metadata 统一，放到 signature 改造之后处理，因为它们依赖前面已经明确的输入/输出契约边界

---

## 6. 建议新增测试清单

建议至少新增这些测试：

### DSPy / optimization

1. optimizer metric 返回 float
2. BootstrapFewShot 使用 metric_threshold
3. GEPA 返回 `ScoreWithFeedback`
4. mock 模式下不产出误导性优化 Prompt

### 契约一致性

5. custom task template 手工保存非法字段引用时报错
6. project 手工保存非法字段引用时报错
7. prompt schema 与 project schema 不一致时报错

### dataset

8. scalar 输出根据单字段 schema 自动映射
9. 多字段 schema 下 scalar 输出导入失败
10. synthetic metadata 在 mock/openai 模式下字段一致

### reports / artifacts

11. optimization artifact 拆分后 manifest 正确
12. evaluation report 同时包含 `raw_input_json` 和 `rendered_input_text`

### signature

13. 多字段 input schema 生成正确 signature
14. Prompt 模板变量与 input schema 对齐

---

## 7. 已确认的实现口径

下面这些口径已经确认，可以直接作为后续代码修改的实现基线：

### 7.1 Prompt 输出契约

- Prompt 不再拥有独立 output schema
- Prompt 输出契约直接继承 Project

### 7.2 optimization Prompt artifact 命名

- `optimized_prompt` 改成 `derived_prompt_candidate`
- `prompt_diff` 建议同步改成 `derived_prompt_diff`

### 7.3 多字段 input signature

- 本轮直接落地，不延期

### 7.4 output schema 支持边界

- 当前平台只正式支持 `object` 和 `string`

### 7.5 lint / 文档规范

- 保留中文文档
- 调整 Ruff 以适配当前中文文档体系

## 7.6 基于已确认口径的详细落地方案

这一节不是重新讨论方向，而是把你已经确认的口径落成可编码的实现方案。

### Prompt 继承 Project output schema

建议实现为：

1. 数据库字段保留
2. Prompt create / update / version create 时，后端统一覆盖写入 `project.output_schema_json`
3. `PromptCreate` / `PromptUpdate` schema 中移除可写的 `output_schema_json`
4. 前端 Prompt 页只读展示当前 Project 的输出 schema

这样做的核心好处是：

- 不打破现有快照和运行记录结构
- 彻底消除 Prompt 与 Project 输出契约漂移
- 历史 Prompt 仍然可以保留当时的快照值

### `derived_prompt_candidate` 的语义

建议 artifact 内容明确包含：

```json
{
  "artifact_type": "derived_prompt_candidate",
  "export_strategy": "project_prompt_plus_compiled_instructions",
  "is_authoritative_dspy_state": false,
  "system_prompt": "...",
  "user_template": "...",
  "notes": "This prompt is derived from compiled DSPy state and is editable."
}
```

这样前端和后端都会明确知道：

- 这不是 DSPy 的权威编译态
- 这是平台为了继续编辑和复用而导出的候选 Prompt

### 多字段 input signature 的推荐实现

本轮我建议采用“平台多字段，Program 内部再渲染文本”的路线，而不是把现有流程全部推翻。

具体做法：

1. `input_schema_json` 的顶层必须是 `object`
2. 从 `properties` 中抽取顶层字段，生成平台输入字段列表
3. `PromptOptimizationProgram.forward()` 改成显式接收这些字段
4. `forward()` 内部仍然通过 `user_template` 生成最终 prompt 文本
5. 内部 predictor 可以继续面向文本提示工作，但这不再是平台暴露给 DSPy 的外层契约

这样改的关键收益是：

- Project / Dataset / Prompt / DSPy 四层终于共享同一套输入字段语义
- `user_template` 仍然保留，不需要把现有 Prompt 设计全部推倒
- 日志、报告、优化链路都能同时看到“原始输入字段”和“渲染后的提示文本”

### `string` output schema 的内部表示

虽然平台正式支持 `object` 和 `string`，但内部仍需要一个统一表示。

我建议：

1. 对外契约允许 `type: "string"`
2. 运行时统一把 string 结果归一到 `{"answer": "..."}` 这一内部结构
3. 报告层同时保留：
   - `raw_output_value`
   - `normalized_output_json`

这样做的原因是：

- metric 层和 artifact 层可以继续沿用统一 JSON 结构
- 对外又能保持“这个任务的真实输出是 string”这一语义

### Ruff 调整范围

建议这轮不要全局大幅放松 Ruff，而是做有边界的收口：

1. 忽略 `RUF001` / `RUF002` / `RUF003`
2. 保留 `E402`、import 排序、未使用导入等真正有价值的规则
3. 顺手修掉当前仓库里少量真实 lint 问题

目标不是“让 lint 静音”，而是：

- 让中文文档成为合法写法
- 让真正的工程问题继续被静态检查捕获

## 7.7 仍需继续讨论的实现细节

大的方向已经确认，但下面这些细节最好在开工前统一口径：

### 1. Prompt 历史版本是否绑定创建时 Project schema

推荐是：

- 是，Prompt 版本快照保存创建当时的 schema

原因是运行记录和历史复现都更稳定。

### 2. `derived_prompt_candidate` 是否允许一键回写成新 Prompt 版本

推荐是：

- 允许

但前端文案必须明确写成：

- “从优化结果生成候选 Prompt 版本”

而不是“应用真实优化 Prompt”。

### 3. 多字段 signature 的输入类型边界

推荐这轮只正式支持：

- `string`
- `number`
- `integer`
- `boolean`

顶层字段若为：

- `array`
- `object`

则保存阶段直接拒绝，避免运行时再做隐式序列化猜测。

### 4. `string` output schema 的 target field 文案

推荐统一约定：

- 对外无 target field
- 对内归一成 `answer`

这样可以避免在 Project 配置层又引入一套“string 类型时字段名叫什么”的额外歧义。

---

## 8. 最终建议

基于你已经确认的口径，我现在建议的实际开发顺序是：

1. 先做 `P0 + 契约收口`
2. 紧接着直接做多字段 input signature
3. 再处理 dataset / output schema 的归一化边界
4. 最后收 lint、README、测试

也就是说，当前最合适的落地顺序不是再继续抽象讨论，而是开始实际编码。

如果你愿意，我下一步可以直接开始做第一批代码修改：

1. Prompt 继承 Project schema
2. optimization artifact 改名为 `derived_prompt_candidate`
3. optimizer metric 改为连续分数
4. mock 模式去掉伪优化表达
5. Project / Custom Task 契约一致性校验

然后第二批继续做多字段 input signature。 
