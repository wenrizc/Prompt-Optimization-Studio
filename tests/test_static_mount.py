"""静态前端挂载回归测试。"""

from __future__ import annotations

from pathlib import Path

from backend import main


def test_project_root_points_to_repository_root() -> None:
    """确保项目根目录定位到当前仓库根目录。"""
    assert Path(__file__).resolve().parents[1] == main._PROJECT_ROOT


def test_default_static_dir_points_to_frontend_out() -> None:
    """确保默认静态目录指向仓库下的 frontend/out。"""
    expected = Path(__file__).resolve().parents[1] / "frontend" / "out"

    assert expected == main._PROJECT_ROOT / "frontend" / "out"
