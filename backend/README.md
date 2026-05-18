# Backend 目录说明

本文档用于说明 `backend/` 下各个文件夹与关键入口文件的职责，帮助快速定位代码。

## 目录总览

```text
backend/
├─ api/
│  └─ routes/
├─ core/
├─ db/
├─ models/
├─ prompt_optimization_studio.egg-info/
├─ schemas/
├─ services/
├─ workers/
├─ cli.py
├─ main.py
└─ __init__.py
```

## 顶层目录说明

### `api/`

API 接口层，负责对外暴露 HTTP 能力。

- `router.py`
  统一汇总并注册所有子路由。
- `dependencies.py`
  放 FastAPI 的公共依赖注入逻辑，例如数据库会话。
- `routes/`
  按资源类型拆分接口文件，避免所有接口堆在一个模块中。

适合修改这里的场景：

- 新增一个 API 端点。
- 调整请求参数、响应结构或路由路径。
- 增加接口级的参数校验和依赖注入。

### `api/routes/`

具体业务资源对应的路由实现目录，每个文件通常对应一组 REST 接口。

- `projects.py`：项目管理接口。
- `prompts.py`：Prompt 的创建、版本化与查询接口。
- `datasets.py`：数据集导入、拆分、编辑、质量检查等接口。
- `evaluations.py`：评测任务创建、查询与触发相关接口。
- `optimization_runs.py`：优化运行创建、查询与控制接口。
- `jobs.py`：后台任务队列与执行状态查询接口。
- `artifacts.py`：产物清单、内容查看、文件下载接口。
- `run_logs.py`：运行日志查询接口。
- `custom_task_templates.py`：自定义任务模板生成与管理接口。

### `core/`

核心基础设施层，放“全局都可能会用到”的基础能力，不直接承载具体业务流程。

- `config.py`
  使用 `pydantic-settings` 读取环境变量与 `.env` 配置。
- `constants.py`
  集中放常量定义。
- `exceptions.py`
  统一封装项目内使用的异常与错误响应。
- `runtime.py`
  负责运行时目录初始化等基础动作。

适合修改这里的场景：

- 新增环境变量配置项。
- 统一调整错误处理方式。
- 补充系统级常量或运行时初始化逻辑。

### `db/`

数据库接入层，负责 SQLAlchemy 的基础装配。

- `base.py`
  ORM 声明式基类。
- `session.py`
  数据库引擎、会话工厂和会话依赖。

这层主要解决“怎么连库、怎么拿会话”的问题，不负责具体业务逻辑。

### `models/`

数据库模型层，定义数据表结构与 ORM 映射关系。

当前主要实体包括：

- `project.py`：项目。
- `prompt.py`：Prompt。
- `dataset.py`：数据集。
- `evaluation.py`：评测记录。
- `optimization_run.py`：优化运行记录。
- `job.py`：后台任务。
- `artifact.py`：运行产物。
- `run_log.py`：运行日志。
- `custom_task_template.py`：自定义任务模板。
- `mixins.py`：模型共享字段或公共混入逻辑。

适合修改这里的场景：

- 新增表字段或新实体。
- 调整实体之间的关系。
- 配合 Alembic 做数据库结构演进。

### `schemas/`

数据契约层，定义接口入参与出参的数据结构，通常基于 Pydantic。

它和 `models/` 的分工不同：

- `models/` 面向数据库持久化。
- `schemas/` 面向 API 输入输出与服务层数据交换。

常见用途：

- 定义创建、更新、列表、详情等请求响应模型。
- 约束字段类型、默认值和序列化行为。
- 保持接口层与数据库层解耦。

### `services/`

业务服务层，是后端最核心的业务实现区域。

这里封装“系统真正做事的逻辑”，例如：

- `dataset_service.py`
  数据集创建、导入、样例处理、质量分析等。
- `evaluation_service.py`
  评测执行、结果汇总、报告生成。
- `optimization_service.py`
  Prompt 优化运行主流程。
- `job_service.py`
  后台任务领取、状态流转、进度更新。
- `artifact_service.py`
  产物保存、清单生成、读取下载。
- `dataset_generation.py`
  生成式构造数据集样例。
- `custom_task_template_generator.py`
  生成自定义任务模板内容。
- `task_catalog.py`
  内置任务模板目录与相关定义。
- `metric_factory.py`
  指标构造与评估逻辑适配。
- `dspy_runtime.py`、`dspy_program_factory.py`
  DSPy 运行时适配与程序构造。
- `openai_client.py`
  OpenAI / OpenAI-compatible 调用封装。
- `report_summary.py`
  报告摘要生成。
- `run_defaults.py`
  运行默认参数处理。
- `validators.py`
  业务规则校验。
- `runtime_service.py`
  运行环境信息收集。

如果你在排查“某个功能具体怎么执行”，大多数时候应该先看这里。

### `workers/`

后台任务执行层，用于消费任务队列并驱动长耗时流程。

- `worker.py`
  本地 Worker，负责轮询数据库中的待执行任务。
- `job_router.py`
  按任务类型把任务分发到评测或优化等具体处理逻辑。

适合修改这里的场景：

- 调整任务领取与执行流程。
- 扩展新的 `job_type`。
- 处理任务取消、失败恢复、进度推进等逻辑。

### `prompt_optimization_studio.egg-info/`

Python 打包元数据目录，一般由安装或构建过程自动生成。

通常不需要手动修改。若目录内容异常，优先通过重新安装依赖或重新构建解决。

## 顶层文件说明

### `main.py`

FastAPI 应用入口，负责：

- 创建应用实例。
- 注册 CORS。
- 挂载 API 路由。
- 挂载前端静态资源。
- 在启动时初始化运行目录和数据库表。

### `cli.py`

命令行启动入口，主要用于通过 `uv run studio-api ...` 启动后端服务。

### `__init__.py`

将 `backend` 标记为 Python 包，通常不承载主要业务逻辑。

## 一次请求的大致流向

可以把后端理解成下面这条链路：

1. `api/routes/*.py` 接收 HTTP 请求。
2. `schemas/*.py` 校验输入输出。
3. `services/*.py` 执行业务逻辑。
4. `models/*.py` 与 `db/*.py` 完成数据库读写。
5. 如果是长任务，则由 `jobs` + `workers` 异步执行。

## 快速定位建议

- 想找接口定义：先看 `api/routes/`
- 想找业务主流程：先看 `services/`
- 想找数据库表结构：先看 `models/`
- 想找请求/响应字段：先看 `schemas/`
- 想找配置项：先看 `core/config.py`
- 想找后台任务执行：先看 `workers/` 和 `services/job_service.py`

