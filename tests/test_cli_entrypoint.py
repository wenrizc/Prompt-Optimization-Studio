"""CLI 入口配置回归测试。"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend import cli


def test_backend_package_is_installable() -> None:
    """确保打包配置会暴露 backend 包名。"""
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    packages_find = pyproject["tool"]["setuptools"]["packages"]["find"]

    assert packages_find["where"] == ["."]
    assert packages_find["include"] == ["backend*"]


def test_studio_api_script_points_to_backend_cli() -> None:
    """确保控制台脚本入口指向实际存在的 backend.cli。"""
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["scripts"]["studio-api"] == "backend.cli:main"


def test_main_uses_backend_app_import_path(monkeypatch) -> None:
    """确保 CLI 启动时使用 backend.main 应用路径。"""
    captured: dict[str, object] = {}

    def fake_run(app: str, **kwargs: object) -> None:
        captured["app"] = app
        captured.update(kwargs)

    monkeypatch.setattr(cli.uvicorn, "run", fake_run)
    monkeypatch.setattr(
        cli.argparse.ArgumentParser,
        "parse_args",
        lambda self: cli.argparse.Namespace(host=None, port=None, reload=False, log_level="info"),
    )

    cli.main()

    assert captured["app"] == "backend.main:app"
