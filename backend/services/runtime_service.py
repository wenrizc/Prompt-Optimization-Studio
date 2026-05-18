"""运行时环境信息收集服务。

收集当前运行环境中关键依赖包的版本信息。
"""

from importlib.metadata import PackageNotFoundError, version


def collect_package_versions() -> dict[str, str]:
    """收集关键依赖包的版本号。"""
    packages = ["fastapi", "sqlalchemy", "alembic", "openai", "dspy"]
    result: dict[str, str] = {}
    for package in packages:
        try:
            result[package] = version(package)
        except PackageNotFoundError:
            result[package] = "not-installed"
    return result
