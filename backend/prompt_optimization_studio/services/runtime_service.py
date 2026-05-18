from importlib.metadata import PackageNotFoundError, version


def collect_package_versions() -> dict[str, str]:
    packages = ["fastapi", "sqlalchemy", "alembic", "openai", "dspy"]
    result: dict[str, str] = {}
    for package in packages:
        try:
            result[package] = version(package)
        except PackageNotFoundError:
            result[package] = "not-installed"
    return result
