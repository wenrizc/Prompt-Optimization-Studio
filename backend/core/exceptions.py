"""HTTP 异常工厂模块。

提供快捷函数用于在路由层构造标准 HTTP 错误响应（404、400、409）。
"""

from fastapi import HTTPException, status


def not_found(detail: str) -> HTTPException:
    """构造 404 Not Found 异常。

    Args:
        detail: 错误详情描述。

    Returns:
        状态码为 404 的 HTTPException 实例。
    """
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def bad_request(detail: str) -> HTTPException:
    """构造 400 Bad Request 异常。

    Args:
        detail: 错误详情描述。

    Returns:
        状态码为 400 的 HTTPException 实例。
    """
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def conflict(detail: str) -> HTTPException:
    """构造 409 Conflict 异常。

    Args:
        detail: 错误详情描述。

    Returns:
        状态码为 409 的 HTTPException 实例。
    """
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
