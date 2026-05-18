# 项目问题与 DSPy 集成审查报告

## 1. 审查范围与结论

本次审查基于当前仓库代码、现有测试以及基础静态检查结果，重点检查了：

- 后端 API、Schema、服务层和 Worker 执行链
- 前端与后端的字段契约一致性
- 项目中的 JSON 配置字段是否缺失、重复或逻辑不一致
- 项目与 DSPy 的集成方式是否存在目标错位或结果失真

我实际执行了以下检查：

- `pytest -q`
- `uv run python -m compileall backend`
- `uv run ruff check backend tests`

结果是：

- 测试通过
- `compileall` 通过
- `ruff check` 明确失败，而且失败量很大

结论可以先概括为一句话：

**这个项目的“本地功能闭环”已经搭起来了，但任务契约、Prompt 契约、DSPy 优化目标、报告字段和静态约束之间存在明显错位。最严重的问题不在能不能跑，而在“跑出来的结果是否真正代表项目声称的语义”。**

---

## 2. 问题分级

为了便于阅读，下面按严重程度分为三层：

### 2.1 高优先级问题

这些问题会直接影响：

- DSPy 优化是否真正有效
- 项目声称支持的任务契约是否真实可用
- 结果是否误导用户

### 2.2 中优先级问题

这些问题短期不一定立刻崩，但会导致：

- 报告信息不完整
- JSON 字段不一致
- 运行结果难以解释

### 2.3 低优先级或治理类问题

这些问题更多是：

- 文档漂移
- lint/规范冲突
- 配置项形同虚设

---

## 3. 高优先级问题

## 3.1 DSPy 优化目标和项目评分目标不一致

这是当前项目里最重要的 DSPy 集成问题。

### 现象

在优化运行中，项目先用 `score_metric()` 计算真实分数，但在传给 DSPy 的优化器 metric 时，又把结果压成了布尔值：

- 非 GEPA 路径返回 `bool(result["correct"])`
- GEPA 路径才返回 `ScoreWithFeedback(score=float(result["score"]), feedback=...)`

证据：

- [backend/services/optimization_service.py](D:\project\Prompt-Optimization-Studio\backend\services\optimization_service.py:633)
- [backend/services/optimization_service.py](D:\project\Prompt-Optimization-Studio\backend\services\optimization_service.py:632)

### 为什么这是严重问题

项目里很多 metric 不是天然二值的，而是带连续分数的：

- `f1_token`
- `weighted_numeric_fields_accuracy`
- `llm_judge`
- `json_all_fields_accuracy`

但当前集成里，DSPy 优化器在非 GEPA 模式下看不到连续分数，只能看到：

- `True`
- `False`

这会带来两个直接后果：

1. **优化目标被阈值化**
   - 例如样本分数从 `0.20` 提升到 `0.79`
   - 如果阈值是 `0.8`
   - DSPy 看到的仍然都是 `False`
   - 这类提升不会被优化器感知

2. **评测目标和优化目标断裂**
   - Evaluation 报告展示的是均值分数
   - Optimization 内部却在按布尔正确率优化
   - 这意味着“优化器学的目标”和“最终报告展示的目标”不是同一个东西

### 具体影响

- `BootstrapFewShot` 实际优化的不是你看到的 score
- `MIPROv2` 实际搜索的不是你以为的连续指标
- 用户看到 `optimized_score` 的变化时，会误以为优化器一直在针对这个 score 做优化

### 本质

这是 **DSPy 优化信号和平台评分语义错位**。

---

## 3.2 项目宣称支持通用任务 schema，但实际运行链只支持单 `text` 输入

这是第二个核心问题。

### 现象

项目在 Project / Custom Task Template 层面允许定义：

- 任意 `input_schema_json`
- 任意 `output_schema_json`

但真正进入 DSPy 执行时，签名被固定成：

- `text -> answer`

证据：

- [backend/services/dspy_program_factory.py](D:\project\Prompt-Optimization-Studio\backend\services\dspy_program_factory.py:30)

同时，Prompt 模板校验强制要求：

- `user_template` 必须包含 `{text}`
- 不允许除 `text` 之外的变量

证据：

- [backend/schemas/prompt.py](D:\project\Prompt-Optimization-Studio\backend\schemas\prompt.py:39)
- [backend/schemas/prompt.py](D:\project\Prompt-Optimization-Studio\backend\schemas\prompt.py:44)
- [backend/services/validators.py](D:\project\Prompt-Optimization-Studio\backend\services\validators.py:90)
- [backend/services/validators.py](D:\project\Prompt-Optimization-Studio\backend\services\validators.py:95)

### 进一步的问题

即使 `input_json` 里有多个字段，真正渲染模板时也只是做最简单的字符串替换：

- `rendered = user_template`
- 对每个 key 直接 `replace`

证据：

- [backend/services/dspy_program_factory.py](D:\project\Prompt-Optimization-Studio\backend\services\dspy_program_factory.py:105)
- [backend/services/dspy_program_factory.py](D:\project\Prompt-Optimization-Studio\backend\services\dspy_program_factory.py:107)

但因为模板校验本身已经禁止 `{text}` 之外的变量，这段多字段替换逻辑在当前平台中几乎没有真实用武之地。

### 为什么这是严重问题

这意味着：

1. `input_schema_json` 的“通用输入结构能力”大部分是装饰性的
2. 自定义任务虽然允许定义多字段输入，但 Prompt 层无法真正消费
3. DSPy 运行层也无法构造多输入 signature

### 结果

系统对外看起来像支持“通用 JSON 任务”，但实际上真正打通的只有：

- 单文本输入
- 单字符串/对象输出

这会导致很多自定义任务配置 **能保存，但不能真正运行成预期任务**。

---

## 3.3 输出 schema 支持范围被高估，平台其实主要只支持 object 输出

### 现象

代码里已经有明确提示：

- 当前 MVP 主要优化的是 object-shaped output schemas

证据：

- [backend/services/validators.py](D:\project\Prompt-Optimization-Studio\backend\services\validators.py:109)

而 DSPy 包装指令又明确要求：

- 返回一个严格匹配 schema 的 JSON object

证据：

- [backend/services/dspy_program_factory.py](D:\project\Prompt-Optimization-Studio\backend\services\dspy_program_factory.py:55)

评测校验逻辑对输出类型的处理也基本只认真支持：

- `object`
- `string`

证据：

- [backend/services/evaluation_service.py](D:\project\Prompt-Optimization-Studio\backend\services\evaluation_service.py:449)
- [backend/services/evaluation_service.py](D:\project\Prompt-Optimization-Studio\backend\services\evaluation_service.py:466)

### 为什么这是问题

平台的 JSON schema 表面上很通用，但实际：

- array
- scalar number
- scalar boolean
- 更复杂嵌套结构

在 Prompt 约束、输出解析、指标校验、报告展示这几层并没有形成一致支持。

### 结果

当前“支持任意 JSON schema”并不成立。

更准确的描述应该是：

- **强支持 object**
- **部分兼容 string**
- **对其它 schema 类型只有零散支持**

---

## 3.4 自定义任务和项目契约在手工保存时没有做跨字段一致性校验

### 现象

项目里已经实现了一个很好的校验器：

- `validate_generated_template_alignment()`

这个函数会检查：

- `default_metric_config_json.field`
- `task_definition_json.target_field`
- `report_profile_json.primary_output_field`

是否和 `output_schema_json.properties` 对齐。

证据：

- [backend/services/validators.py](D:\project\Prompt-Optimization-Studio\backend\services\validators.py:29)

但是这个校验目前只在 **AI 生成草稿** 的 `CustomTaskTemplateDraftBundle` 上生效：

- [backend/schemas/custom_task_template_generation.py](D:\project\Prompt-Optimization-Studio\backend\schemas\custom_task_template_generation.py:44)

而在手工保存路径里：

- `custom_task_templates` 的 create / update 没有调用这个一致性校验
- `projects` 的 create / update 也没有调用这种跨字段校验

证据：

- [backend/api/routes/custom_task_templates.py](D:\project\Prompt-Optimization-Studio\backend\api\routes\custom_task_templates.py)
- [backend/api/routes/projects.py](D:\project\Prompt-Optimization-Studio\backend\api\routes\projects.py)

### 为什么这是严重问题

这会导致两类情况：

1. AI 自动生成的模板比手工保存的模板更安全
2. 用户完全可以保存一份结构上自相矛盾的任务契约

例如：

- `output_schema_json` 只有 `label`
- metric 却配置成 `field=result`
- `task_definition.target_field=score`
- `report_profile.primary_output_field=answer`

这些配置都能被手工写进数据库。

### 结果

平台的 JSON 契约并不是“保存时可靠”，而是“运行时可能才爆炸”。

---

## 3.5 Mock 模式下的优化运行会制造“已经优化”的假象

### 现象

优化路径里，如果运行时 provider 是 `mock`，编译阶段直接返回原始 program：

- `if runtime.provider == "mock": return program`

证据：

- [backend/services/optimization_service.py](D:\project\Prompt-Optimization-Studio\backend\services\optimization_service.py:514)

同时，预测阶段在 mock 模式下直接返回 gold：

- [backend/services/optimization_service.py](D:\project\Prompt-Optimization-Studio\backend\services\optimization_service.py:593)
- [backend/services/evaluation_service.py](D:\project\Prompt-Optimization-Studio\backend\services\evaluation_service.py:430)

但 `build_optimized_prompt()` 仍然会无条件给 `system_prompt` 附加：

- `Optimizer note: refined by ...`
- `Learned instructions: ...`

证据：

- [backend/services/optimization_service.py](D:\project\Prompt-Optimization-Studio\backend\services\optimization_service.py:477)
- [backend/services/optimization_service.py](D:\project\Prompt-Optimization-Studio\backend\services\optimization_service.py:482)

### 为什么这是严重问题

在 mock 模式下：

- 实际没有做真实 LLM 优化
- 实际没有真实模型预测误差
- 评测分数天然接近完美

但最终仍会生成：

- `optimized_prompt.json`
- `prompt_diff.json`
- “refined by optimizer” 的文案

### 结果

这会误导用户，以为系统已经跑出有意义的优化结果，实际上只是平台在 mock 路径里构造了一份“优化后外观”。

---

## 4. 中优先级问题

## 4.1 `optimized_prompt` 不是 DSPy 状态的可靠映射

### 现象

`build_optimized_prompt()` 的实现方式不是从 DSPy 中提取真实、可逆的 Prompt 结构，而是：

1. 保留原 `user_template`
2. 从 `optimized_program.predict.signature.instructions` 取文本
3. 把它附加到 `system_prompt`

证据：

- [backend/services/optimization_service.py](D:\project\Prompt-Optimization-Studio\backend\services\optimization_service.py:475)
- [backend/services/optimization_service.py](D:\project\Prompt-Optimization-Studio\backend\services\optimization_service.py:483)

### 问题点

这有几个风险：

1. DSPy 优化器不一定真的通过“修改 signature.instructions”完成优化
2. 一些优化器可能主要优化 demos，而不是指令文本
3. 即使指令有变化，这段文本也可能是 DSPy 包装层的整段 instructions，而不是“纯净的业务 Prompt 增量”

### 结果

当前 `optimized_prompt` 更像是：

- 平台对 DSPy 状态的一种推测性导出

而不是：

- 真实、稳定、可直接回写的 Prompt 资产

---

## 4.2 优化运行的 artifact 字段语义不一致

### 现象

优化运行最终会写出一个叫 `predictions.json` 的 artifact：

- [backend/services/optimization_service.py](D:\project\Prompt-Optimization-Studio\backend\services\optimization_service.py:418)
- [backend/services/optimization_service.py](D:\project\Prompt-Optimization-Studio\backend\services\optimization_service.py:419)

但这个文件里写入的其实只有：

- `optimized_results`

而不是：

- `baseline_results + optimized_results`

与此同时，内存中的 result 里其实同时存在：

- `baseline_results`
- `optimized_results`

证据：

- [backend/services/optimization_service.py](D:\project\Prompt-Optimization-Studio\backend\services\optimization_service.py:193)
- [backend/services/optimization_service.py](D:\project\Prompt-Optimization-Studio\backend\services\optimization_service.py:194)

### 为什么这是问题

文件名叫 `predictions.json`，用户自然会理解为“完整预测结果”。

但实际上它只存了优化后的预测，不包含 baseline。

### 结果

artifact 命名和内容不一致，后续做自动分析或离线复盘时容易误判。

---

## 4.3 Evaluation 报告把“渲染后的 Prompt 文本”错误写成了 `input_json`

### 现象

评测循环里，报告记录使用的是：

- `"input_json": {"text": dsp_example.text}`

证据：

- [backend/services/evaluation_service.py](D:\project\Prompt-Optimization-Studio\backend\services\evaluation_service.py:215)

但 `dsp_example.text` 不是原始样本输入，而是：

- 经过 `user_template` 渲染后的最终文本

### 为什么这是问题

这意味着报告里的 `input_json.text` 不再是原始数据集输入，而变成了：

- Prompt 模板 + 输入拼接后的运行文本

### 结果

报告层会出现语义污染：

- 用户以为看到的是原始样本
- 实际看到的是运行时拼接后的 Prompt 输入

这会降低调试价值，也会让失败样本分析产生偏差。

---

## 4.4 数据导入时对 scalar 输出的归一化策略过于武断

### 现象

导入数据集时，如果 `output_field` 对应的值不是 object，系统直接包成：

- `{"answer": value}`

证据：

- [backend/services/dataset_service.py](D:\project\Prompt-Optimization-Studio\backend\services\dataset_service.py:515)
- [backend/services/dataset_service.py](D:\project\Prompt-Optimization-Studio\backend\services\dataset_service.py:518)

### 为什么这是问题

如果项目实际输出字段是：

- `label`
- `score`
- `result`

那导入时直接硬转成 `answer`，就会和项目任务契约失配。

### 结果

导入时没有立刻报错，但后续评测或 schema 校验阶段可能才失败。

这不是“宽容”，而是把错误延后。

---

## 4.5 Synthetic 样本的 `metadata_json` 在 mock 和真实 LLM 模式下不一致

### 现象

mock 生成模式的 `metadata_json` 只有：

- `source`
- `command`

证据：

- [backend/services/dataset_generation.py](D:\project\Prompt-Optimization-Studio\backend\services\dataset_generation.py:48)

真实 LLM 生成模式的 `metadata_json` 额外带：

- `generation_model`
- `batch_index`

证据：

- [backend/services/dataset_generation.py](D:\project\Prompt-Optimization-Studio\backend\services\dataset_generation.py:162)
- [backend/services/dataset_generation.py](D:\project\Prompt-Optimization-Studio\backend\services\dataset_generation.py:163)

### 为什么这是问题

同样都是 `synthetic_generated` 数据集，但 metadata 结构不稳定。

### 结果

后续如果要：

- 统一统计 synthetic 数据来源
- 对比不同模型生成质量
- 做数据 lineage

就会遇到字段缺失和模式分叉。

---

## 4.6 项目级 resource limit 配置大多没有真正生效

### 现象

配置里定义了很多上限：

- `max_generated_examples`
- `max_examples_per_run`
- `max_lm_calls`
- `max_metric_calls`
- `max_runtime_seconds`

证据：

- [backend/core/config.py](D:\project\Prompt-Optimization-Studio\backend\core\config.py:43)
- [backend/core/config.py](D:\project\Prompt-Optimization-Studio\backend\core\config.py:44)
- [backend/core/config.py](D:\project\Prompt-Optimization-Studio\backend\core\config.py:46)
- [backend/core/config.py](D:\project\Prompt-Optimization-Studio\backend\core\config.py:47)
- [backend/core/config.py](D:\project\Prompt-Optimization-Studio\backend\core\config.py:48)

但当前代码中，真正用到的几乎只有：

- GEPA compile 时把 `max_metric_calls` 透传给优化器配置

证据：

- [backend/services/optimization_service.py](D:\project\Prompt-Optimization-Studio\backend\services\optimization_service.py:579)

### 为什么这是问题

这些配置给人的感觉是“平台有资源治理能力”，但实际上大多数没有执法逻辑。

### 结果

当前这些字段大多只是“看起来像治理参数”，不是真正的平台保护机制。

---

## 4.7 Prompt 与 Project 契约之间缺少硬约束

### 现象

Prompt 创建时只做了：

- 模板变量校验
- output schema 是不是 object

但没有强制要求：

- Prompt 的 `output_schema_json` 必须和 Project 的 `output_schema_json` 一致

这意味着用户可以创建一个和项目任务契约偏离的 Prompt。

### 结果

系统允许出现下面这种状态：

- Project 说输出字段是 `label`
- Prompt 却写成输出字段 `answer`
- Dataset 又按 Project 契约准备

这类不一致不会在 Prompt 创建时被阻止，而是会拖到运行期才暴露。

---

## 5. 低优先级与治理类问题

## 5.1 Lint 体系和项目中文文档规范明显冲突

### 现象

当前项目要求：

- 公共模块/函数/类写中文文档字符串

但 `ruff check backend tests` 实际会报大量：

- `RUF002`
- `RUF003`

原因是 Ruff 把中文全角标点当成 ambiguous unicode。

此外，测试文件还存在：

- `E402`
- import block 排序问题

### 为什么这是问题

这意味着当前仓库的规范系统是自相矛盾的：

1. AGENTS/代码规范鼓励中文文档
2. Ruff 当前配置却大量拒绝中文全角标点

### 结果

开发者无法同时满足：

- 项目要求
- 静态检查

这会导致 lint 在 CI 中长期不可用，或者只能靠忽略规则混过去。

---

## 5.2 README 与实际代码存在明显漂移

### 现象

README 仍声称内置任务包含：

- `classification`
- `extraction`
- `qa`
- `json_generation`
- `rewriting`
- `rate`

但当前代码里真正定义的内置任务只有：

- `qa`
- `json_generation`
- `rate`

证据：

- [README.md](D:\project\Prompt-Optimization-Studio\README.md:79)
- [backend/services/task_catalog.py](D:\project\Prompt-Optimization-Studio\backend\services\task_catalog.py)

### 为什么这是问题

这会直接误导：

- 用户
- API 调用方
- 新开发者

### 结果

文档承诺和运行行为不一致。

---

## 6. DSPy 集成问题专题说明

这一节单独展开目前项目与 DSPy 集成上最本质的问题。

## 6.1 目前项目没有真正用上 DSPy 的“结构化任务建模能力”

当前实现把所有任务都压成：

- `text -> answer`

这意味着项目没有充分利用 DSPy 可以表达的：

- 多输入字段
- 更贴近业务结构的 signature
- 不同任务类型的显式 typed contract

当前做法更像是：

- “把一切任务先压成字符串，再交给 DSPy”

这是一个可跑的 MVP 方案，但不是强语义集成。

## 6.2 DSPy 优化结果和平台导出的 optimized prompt 不是一回事

当前平台假设：

- 优化后 DSPy program 的 `signature.instructions`
- 就可以代表“优化后的 Prompt”

但这并不总成立。

DSPy 优化器可能改变的是：

- demos
- compile state
- internal search result

而不是简单改写某一段 instructions 文本。

所以当前 `optimized_prompt.json` 更像“平台推导版本”，不是 DSPy 的权威状态导出。

## 6.3 非 GEPA 优化器被迫优化二值目标

这会让 DSPy 的搜索空间利用率大幅下降。

很多本来能通过连续分数反映的改进，在当前集成里全部被折叠成：

- 对
- 不对

这对 `MIPROv2` 尤其不理想，因为它更适合利用更细粒度的反馈信号。

## 6.4 Mock 模式下的 DSPy 集成只是在“走流程”，不是在“做优化”

当前 mock 路径能验证：

- API 是否通
- Job/Worker 是否通
- artifact 是否通

但它不能验证：

- DSPy 优化是否有效
- metric 设计是否合理
- Prompt 是否真的 improved

因此 mock 模式适合作为平台联调模式，不适合作为“优化效果验证模式”。

---

## 7. JSON 字段问题专题说明

当前项目的 JSON 字段问题主要不是“少写一个字段”这么简单，而是三类更深层的问题：

## 7.1 看似丰富，实际无效

代表例子：

- `input_schema_json`

表面支持任意输入结构，实际上 Prompt 和 DSPy 只消费 `{text}`。

## 7.2 字段能存，但没有一致性校验

代表例子：

- `default_metric_config_json`
- `task_definition_json`
- `report_profile_json`

这些字段之间本应共享同一个输出主字段，但手工保存路径没有校验。

## 7.3 同名字段内容并不一致

代表例子：

- `predictions.json`
  - evaluation 下是完整 prediction 列表
  - optimization 下只存 optimized 结果

还有：

- `metadata_json`
  - mock synthetic 和真实 LLM synthetic 结构不一致

## 7.4 运行快照字段很多，但约束链不完整

项目保存了大量 snapshot：

- `prompt_snapshot_json`
- `dataset_split_snapshot_json`
- `model_config_json`
- `metric_config_json`

这是优点。

但问题在于：

- snapshot 很完整
- snapshot 进入运行前的约束并不完整

结果就是“错误的契约也能被完整快照化”。

---

## 8. 总结

当前项目已经具备了一个完整的本地 Prompt 优化工作台骨架，但目前最主要的问题不是缺少页面，而是 **契约层、优化层和报告层没有完全对齐**。

可以把核心问题浓缩成 6 句话：

1. 平台声称支持通用任务 schema，但实际运行链只真正支持单 `text` 输入。
2. DSPy 优化器在非 GEPA 模式下优化的是二值正确率，不是平台报告展示的连续分数。
3. mock 模式会生成“看起来优化过”的结果，容易误导使用者。
4. 自定义任务和项目的 JSON 契约可以手工保存成自相矛盾的状态。
5. 一些关键 artifact 和报告字段命名、内容、语义不一致。
6. lint 规范、中文文档规范和仓库当前实现之间存在直接冲突。

如果只从“能不能跑”看，这个项目已经能跑。

但如果从“结果是否可信、契约是否自洽、DSPy 是否真的被正确利用”来看，当前项目仍然处于：

**工作流成型了，但语义一致性和优化真实性还没有收口。**

---

## 9. 优先修复建议

如果要按收益排序，我建议优先处理：

1. 让非 GEPA 优化器直接消费连续 score，而不是 `bool(correct)`。
2. 明确平台只支持哪些输入/输出 schema，或者真正扩展到多字段输入 signature。
3. 在 Custom Task Template 和 Project 的手工保存路径上补齐跨字段一致性校验。
4. 修正 mock 模式下“假优化”的结果表达，避免生成误导性的 optimized prompt。
5. 统一 artifact 语义，尤其是 optimization 下 `predictions.json` 的内容命名。
6. 修复 Ruff 规则与中文文档规范的冲突。

如果你需要，我下一步可以继续生成第二份文档：

- “逐文件问题清单与修改建议”

或者我可以直接开始修这些问题。 
