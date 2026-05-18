"""命令行入口模块，用于启动 Prompt Optimization Studio API 服务。"""

from __future__ import annotations

import argparse

import uvicorn

from backend.core.config import get_settings


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。

    Returns:
        配置好 host、port、reload、log-level 等参数的 ArgumentParser 实例。
    """
    parser = argparse.ArgumentParser(
        prog="studio-api",
        description="Run the Prompt Optimization Studio FastAPI server.",
    )
    parser.add_argument("--host", default=None, help="Bind host. Defaults to HOST env or 127.0.0.1.")
    parser.add_argument("--port", type=int, default=None, help="Bind port. Defaults to PORT env or 8000.")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for local development.",
    )
    parser.add_argument(
        "--log-level",
        default="info",
        choices=["critical", "error", "warning", "info", "debug", "trace"],
        help="Uvicorn log level.",
    )
    return parser


def main() -> None:
    """解析命令行参数并启动 Uvicorn 服务器。"""
    parser = build_parser()
    args = parser.parse_args()

    settings = get_settings()
    host = args.host or settings.host
    port = args.port or settings.port

    uvicorn.run(
        "backend.main:app",
        host=host,
        port=port,
        reload=args.reload,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
