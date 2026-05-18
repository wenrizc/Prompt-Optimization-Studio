# Frontend

```bash
cd frontend
npm install
npm run dev
```

默认读取：

```text
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
NEXT_PUBLIC_DEFAULT_LLM_PROVIDER=openai
NEXT_PUBLIC_DEFAULT_LLM_MODEL=deepseek-v4-pro
```

可以复制：

```text
frontend/.env.example
```

并按需改成你自己的后端地址或默认模型。

推荐先在仓库根目录完成后端依赖和服务启动：

```bash
uv sync --extra dev
uv run alembic upgrade head
uv run studio-api --reload
```
