"""钉钉在线表格的异常定义与全局错误处理。

本模块定义了所有 Spreadsheet 服务可能抛出的异常类型，
以及 FastAPI 的异常处理器（exception handler）注册函数。

层次结构:
    SpreadsheetError (基类)
    ├── ConfigError          — 配置缺失错误
    ├── AuthenticationError  — 钉钉 token 获取失败
    ├── APIError             — 钉钉 OpenAPI 调用失败，包含 status_code 和 request_id
    ├── ValidationError      — 请求参数校验错误
    └── RateLimitError       — API 调用频率超限

Usage:
    from .errors import ConfigError, APIError, register_error_handlers

    raise ConfigError("DINGTALK_Client_ID 未配置")
"""

import logging
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from .models import ErrorResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 错误码常量
# ---------------------------------------------------------------------------


class ErrorCode:
    """预定义的错误码，用于在响应中标识错误类别。"""

    # 通用错误 (1000 段)
    UNKNOWN = "E1000"
    VALIDATION = "E1001"
    CONFIG_MISSING = "E1002"

    # 认证与授权 (2000 段)
    TOKEN_FAILED = "E2000"
    AUTH_FAILED = "E2001"

    # 钉钉 API 错误 (3000 段)
    API_ERROR = "E3000"
    RATE_LIMIT = "E3001"
    NOT_FOUND = "E3002"

    # 内部错误 (9000 段)
    INTERNAL = "E9000"


# ---------------------------------------------------------------------------
# 异常类层次
# ---------------------------------------------------------------------------


class SpreadsheetError(Exception):
    """Spreadsheet 模块的基类异常。

    所有异常都包含一个可选的 request_id 字段，用于在分布式追踪中关联请求。

    Attributes:
        request_id: 产生异常的请求追踪 ID（可选）
    """

    def __init__(self, message: str = "", request_id: str = "") -> None:
        super().__init__(message)
        self.request_id = request_id


class ConfigError(SpreadsheetError):
    """配置缺失错误。

    当依赖的环境变量（如 DINGTALK_Client_ID、WORKBOOK_ID）未设置时抛出。

    Example:
        raise ConfigError("WORKBOOK_ID 未配置，请检查 .env 文件")
    """


class AuthenticationError(SpreadsheetError):
    """钉钉 Token 认证失败。

    获取 accessToken 时网络不通、appKey/appSecret 无效，
    或返回的 token 为空时抛出。
    """


class APIError(SpreadsheetError):
    """钉钉 OpenAPI 调用返回的业务错误。

    封装钉钉 API 返回的 HTTP 状态码和错误详情，便于调用方区分错误类型。

    Attributes:
        status_code: 钉钉 API 返回的 HTTP 状态码
    """

    def __init__(self, message: str = "", status_code: int = 500, request_id: str = "") -> None:
        super().__init__(message, request_id)
        self.status_code = status_code


class ValidationError(SpreadsheetError):
    """请求参数验证错误。

    当接口入参不满足业务约束时抛出（区别于 Pydantic 的格式校验）。
    """


class RateLimitError(APIError):
    """钉钉 API 频率限制错误。

    当调用过于频繁触发钉钉限流时抛出，建议调用方实现退避重试。
    """


# ---------------------------------------------------------------------------
# FastAPI 异常处理器
# ---------------------------------------------------------------------------


async def spreadsheet_exception_handler(request: Request, exc: SpreadsheetError) -> JSONResponse:
    """Spreadsheet 模块异常的全局处理器。

    将 SpreadsheetError 及其子类统一序列化为 ErrorResponse JSON 格式，
    并在日志中记录异常信息。

    Args:
        request: 发生异常的 HTTP 请求
        exc:     捕获到的 SpreadsheetError 实例

    Returns:
        JSONResponse: 包含 error_code、detail、request_id 的错误响应
    """
    status_code = 500
    error_code = ErrorCode.INTERNAL

    if isinstance(exc, ConfigError):
        status_code = 503
        error_code = ErrorCode.CONFIG_MISSING
    elif isinstance(exc, AuthenticationError):
        status_code = 401
        error_code = ErrorCode.AUTH_FAILED
    elif isinstance(exc, RateLimitError):
        status_code = 429
        error_code = ErrorCode.RATE_LIMIT
    elif isinstance(exc, APIError):
        status_code = exc.status_code
        error_code = ErrorCode.API_ERROR
    elif isinstance(exc, ValidationError):
        status_code = 422
        error_code = ErrorCode.VALIDATION

    logger.error(
        "SpreadsheetError | code=%s status=%d message=%s request_id=%s",
        error_code,
        status_code,
        exc,
        exc.request_id,
    )
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(
            detail=str(exc),
            error_code=error_code,
            request_id=exc.request_id,
        ).model_dump(exclude_none=True),
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """兜底的全局异常处理器。

    捕获所有未被 SpreadsheetError 处理的异常，返回 500 通用错误。
    完整的异常栈会被记录到日志中，但不会泄露给客户端。

    Args:
        request: 发生异常的 HTTP 请求
        exc:     未处理的异常实例

    Returns:
        JSONResponse: 500 通用错误响应
    """
    logger.exception("未捕获的异常 | path=%s method=%s", request.url.path, request.method)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            detail="服务器内部错误，请稍后重试",
            error_code=ErrorCode.INTERNAL,
        ).model_dump(exclude_none=True),
    )


def register_error_handlers(app: Any) -> None:
    """在 FastAPI 应用上注册所有异常处理器。

    按优先级注册：先注册 SpreadsheetError 处理器（细粒度），
    再注册 Exception 兜底处理器（粗粒度）。

    Args:
        app: FastAPI 应用实例
    """
    app.add_exception_handler(SpreadsheetError, spreadsheet_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
    logger.info("错误处理器注册完成")
