# Prompt Optimization Studio

本仓库现在包含一个可运行的本地 Prompt Optimization Studio：

- FastAPI + SQLite 后端
- 本地 worker / jobs 执行链
- dataset import / split / quality report
- prompt 版本管理
- baseline evaluation
- optimization runs
- artifact 持久化、manifest 与文件下载
- Next.js 前端工作流控制台与总览仪表盘

## 快速启动

### 1. 安装依赖

```bash
# 后端
uv sync --extra dev

# 前端
cd frontend && npm install && cd ..
```

### 2. 数据库迁移

```bash
uv run alembic upgrade head
```

### 3. 构建前端静态文件

```bash
cd frontend && npm run build && cd ..
```

构建产物在 `frontend/out/`，FastAPI 启动时会自动挂载该目录。

### 4. 启动后端（同时提供前端和 API）

```bash
uv run studio-api --reload
```

访问 http://127.0.0.1:8000 ，浏览器会自动跳转到对应语言页面（`/en/` 或 `/zh/`）。

如果你想显式指定地址：

```bash
uv run studio-api --reload --host 127.0.0.1 --port 8000
```

健康检查：

```text
GET /health
```

### 前端开发模式

如果需要前端热更新开发，可以单独启动 dev server：

```bash
cd frontend && npm run dev
```

dev server 默认地址：http://127.0.0.1:3000

后端地址不同时可设置：

```text
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

## 当前已实现

- 项目 CRUD
- 内置任务模板目录（`classification` / `extraction` / `qa` / `json_generation` / `rewriting` / `rate`）
- Prompt 校验与版本化
- Dataset 创建、导入、样例编辑、批量审核、split
- Dataset split、重复检查、质量摘要
- Evaluation 创建、worker 执行、report/artifact 保存
- Optimization run 创建、worker 执行、report/artifact 保存
- Jobs、run logs、artifacts / manifest 查询与 artifact 文件下载
- 评测与优化报告的 executive summary、风险提示、artifact 清单、失败样本与 regression 查看
- Next.js 多页面前端工作流、首页总览仪表盘、报告查看器

## 内置任务模板

项目创建页现在内置了 6 种任务模板：

- `classification`
- `extraction`
- `qa`
- `json_generation`
- `rewriting`
- `rate`

每个内置任务都会自带：

- `task_display_name`
- `task_description`
- `input_schema_json`
- `output_schema_json`
- `default_metric_config_json`
- `task_definition_json`
- `report_profile_json`

行为规则如下：

- 前端选择内置任务后，会自动把上述字段填成对应模板
- 这些字段在前端仍然可以继续手动修改
- 提交时，以用户当前编辑后的值为准
- 如果调用后端 API 创建内置任务项目时省略了这些字段，后端会自动按所选内置任务兜底填充
- 如果调用方显式传入了这些字段，后端不会覆盖它们

可通过以下接口读取当前内置任务目录：

```text
GET /api/v1/projects/builtin-tasks
```

如需按语言获取任务显示名和任务描述，可带上 `locale`：

```text
GET /api/v1/projects/builtin-tasks?locale=en
GET /api/v1/projects/builtin-tasks?locale=zh
```

调用项目创建接口时，也可以传入可选的 `template_locale`，让后端兜底填充的默认 `task_display_name` / `task_description` 跟随语言：

```json
{
  "name": "中文分类项目",
  "task_kind": "builtin",
  "task_key": "classification",
  "template_locale": "zh"
}
```

## 执行模式

为了保证本地无额外依赖也能跑通闭环，后端会根据环境自动选择执行模式：

- 未配置 `OPENAI_API_KEY` 时回退到 `mock`
- 配置了 `OPENAI_API_KEY` 后走 `openai` / OpenAI-compatible 路径

其中：

- `mock` 便于本地快速验证链路
- `openai` 可用于官方 OpenAI 或 OpenAI-compatible 服务

真实 DSPy / OpenAI 能力已经预留适配层：

- `backend/prompt_optimization_studio/services/dspy_runtime.py`
- `backend/prompt_optimization_studio/services/openai_client.py`

默认环境文件支持 OpenAI-compatible 配置，例如 DeepSeek。后端环境中可配置：

```text
OPENAI_API_KEY=...
OPENAI_BASE_URL=...
OPENAI_DEFAULT_MODEL=deepseek-v4-pro
```

前端只保留生成数据集的默认模型配置：

```text
NEXT_PUBLIC_DEFAULT_GENERATION_MODEL=deepseek-v4-pro
```

创建项目时应配置默认 `metric`，运行页会自动复用该配置；创建 evaluation /
optimization run 时不再手动传入模型 provider、model、random_seed 或 metric：

```json
{
  "project_id": 1,
  "dataset_id": 1,
  "prompt_id": 1
}
```

优化运行仍可额外传入：

```json
{
  "project_id": 1,
  "dataset_id": 1,
  "prompt_id": 1,
  "optimizer_name": "bootstrap_fewshot",
  "optimizer_config_snapshot_json": {
    "max_labeled_demos": 4,
    "max_bootstrapped_demos": 4
  }
}
```

如果你走官方 OpenAI，不填 `OPENAI_BASE_URL` 即可；如果你走兼容网关或代理，可以把它指向对应的基础地址。当前代码已经对 OpenAI-compatible `chat.completions` 和官方 `responses` 做了兼容分流。

## 已验证的真实联调

当前仓库已经完成以下真实在线 smoke test：

- DeepSeek-compatible 平台级 `generate_text`
- DeepSeek-compatible 平台级 structured generation
- DeepSeek + DSPy 的真实 baseline evaluation
- DeepSeek + DSPy 的真实 `BootstrapFewShot`

说明：

- `MIPROv2` 与 `GEPA` 的真实执行路径已经接入并带有前置校验
- 当前仓库里没有再做高成本长跑 smoke test，以避免不必要的在线调用成本
- `GEPA` 会强制要求 `gepa_feedback_metric`

## Env Files

后端示例配置：

```text
.env.example
```

当前本地开发默认使用：

```text
.env
```

`uv run ...` 会直接读取根目录 `.env`，不需要手动 `activate` 虚拟环境。

前端示例配置：

```text
frontend/.env.example
```

当前前端本地开发默认使用：

```text
frontend/.env.local
```

## 报告与 Artifacts

报告查看页现在支持：

- evaluation / optimization report 切换查看
- `executive_summary`
- score breakdown、warnings、failed examples、regression examples
- artifact manifest 查看
- artifact 内容预览
- artifact 原始文件下载

相关接口：

```text
GET /api/v1/artifacts/{owner_type}/{owner_id}
GET /api/v1/artifacts/{owner_type}/{owner_id}/manifest
GET /api/v1/artifacts/item/{artifact_id}
GET /api/v1/artifacts/item/{artifact_id}/download
```

## 数据目录

默认本地数据位于：

```text
data/app.db
data/uploads
data/artifacts
data/reports
data/generated
```

## 推荐的 `uv` 工作流

安装依赖：

```bash
uv sync --extra dev
```

数据库迁移：

```bash
uv run alembic upgrade head
```

构建前端并启动：

```bash
cd frontend && npm run build && cd ..
uv run studio-api --reload
```

运行后端快速检查：

```bash
uv run python -m compileall backend
```

如果你希望更新锁文件：

```bash
uv lock
```
