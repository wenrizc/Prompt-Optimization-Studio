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

## Backend

```bash
uv sync --extra dev
uv run alembic upgrade head
uv run studio-api --reload
```

如果你想显式指定地址：

```bash
uv run studio-api --reload --host 127.0.0.1 --port 8000
```

后端默认地址：

```text
http://127.0.0.1:8000
```

健康检查：

```text
GET /health
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

前端默认地址：

```text
http://127.0.0.1:3000
```

如果后端地址不同，可设置：

```text
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

## 当前已实现

- 项目 CRUD
- Prompt 校验与版本化
- Dataset 创建、导入、样例编辑、批量审核、split
- Dataset split、重复检查、质量摘要
- Evaluation 创建、worker 执行、report/artifact 保存
- Optimization run 创建、worker 执行、report/artifact 保存
- Jobs、run logs、artifacts / manifest 查询与 artifact 文件下载
- 评测与优化报告的 executive summary、风险提示、artifact 清单、失败样本与 regression 查看
- Next.js 多页面前端工作流、首页总览仪表盘、报告查看器

## 执行模式

为了保证本地无额外依赖也能跑通闭环，系统同时支持：

- `provider=mock`
- `provider=openai`

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

前端也支持默认模型和 provider：

```text
NEXT_PUBLIC_DEFAULT_LLM_PROVIDER=openai
NEXT_PUBLIC_DEFAULT_LLM_MODEL=deepseek-v4-pro
NEXT_PUBLIC_DEFAULT_GENERATION_MODEL=deepseek-v4-pro
```

创建 evaluation / optimization run 时可以直接传入：

```json
{
  "model_config_json": {
    "provider": "openai",
    "model": "deepseek-v4-pro",
    "temperature": 0,
    "max_tokens": 4000
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

启动后端：

```bash
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
