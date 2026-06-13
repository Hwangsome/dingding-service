"""FastAPI 应用工厂与命令行入口。

本模块负责创建和配置 FastAPI 应用实例，包括：
  - 注册 lifespan 事件（启动横幅 / 关闭清理）
  - 注册中间件（CORS）
  - 注册错误处理器
  - 注册路由
  - 健康检查端点

Usage:
    # 开发模式
    python -m uvicorn dingding_service.spreadsheet.main:app --reload

    # 或通过模块入口
    python -c "from dingding_service.spreadsheet import main; main()"
"""

import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import Settings
from .errors import ErrorCode, register_error_handlers
from .models import HealthResponse
from .routes import get_client, get_settings, router

logger = logging.getLogger(__name__)

__version__ = "1.0.0"
"""服务版本号。"""


# ---------------------------------------------------------------------------
# 启动横幅
# ---------------------------------------------------------------------------


def _print_banner(settings: Settings) -> None:
    """打印服务启动横幅。

    在 stderr 输出带格式的横幅信息，包含版本号、环境类型、
    监听地址和 Swagger 文档地址。

    Args:
        settings: 应用配置（用于提取 host 和 port）
    """
    banner = (
        f"\n"
        f"{'=' * 60}\n"
        f"  钉钉在线表格 REST API 服务\n"
        f"  V{__version__}\n"
        f"{'=' * 60}\n"
        f"  环境:  {'production' if settings.port == 443 else 'development'}\n"
        f"  监听:  {settings.host}:{settings.port}\n"
        f"  文档:  http://{settings.host}:{settings.port}/docs\n"
        f"{'=' * 60}\n"
    )
    # 使用 stderr 避免干扰 uvicorn 的 stdout 日志管道
    print(banner, file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """异步应用生命周期管理器。

    startup 阶段：打印启动横幅并记录关键配置信息。
    shutdown 阶段：执行清理逻辑，记录优雅关闭日志。

    Args:
        _app: FastAPI 应用实例
    """
    # ---- startup ----
    settings = Settings()
    _print_banner(settings)

    configured = bool(settings.workbook_id and settings.operator_union_id)
    logger.info(
        "服务启动 | version=%s log_level=%s configured=%s",
        __version__,
        settings.log_level,
        configured,
    )
    logger.info("Swagger 文档地址: http://%s:%s/docs", settings.host, settings.port)
    if not configured:
        logger.warning("WORKBOOK_ID 或 OPERATOR_UNION_ID 未配置，部分端点将返回 503")

    yield

    # ---- shutdown ----
    logger.info("服务正在关闭，清理资源...")
    logger.info("服务已停止 | version=%s", __version__)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用实例。

    依次完成：
    1. 实例化 FastAPI（含 title / version / lifespan）
    2. 注册 CORS 中间件
    3. 注册自定义异常处理器
    4. 注册路由
    5. 注册全局 500 兜底处理器
    6. 注册健康检查端点

    Returns:
        配置完成的 FastAPI 应用实例
    """
    app = FastAPI(
        title="钉钉 Spreadsheet API",
        version=__version__,
        lifespan=lifespan,
    )

    # CORS 中间件 — 允许所有来源（开发阶段可放宽）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册模块自定义错误处理器（SpreadsheetError + 通用兜底）
    register_error_handlers(app)

    # 注册 API 路由
    app.include_router(router)

    # 全局 500 兜底 — 在所有异常处理器链之外的最后防线
    @app.exception_handler(500)
    async def internal_server_error_handler(request, exc) -> JSONResponse:
        """500 内部错误的兜底处理器。"""
        logger.exception("未处理的 500 错误 | path=%s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "服务器内部错误，请稍后重试",
                "error_code": ErrorCode.INTERNAL,
            },
        )

    # ------------------------------------------------------------------
    # Health endpoint（根级别，不在 /api 前缀下）
    # ------------------------------------------------------------------

    @app.get("/health", response_model=HealthResponse)
    async def health(
        settings: Settings = Depends(get_settings),
        client=Depends(get_client),
    ) -> HealthResponse:
        """健康检查端点。

        返回服务状态、Token 连通性和配置信息。
        用于负载均衡器健康检查和 Kubernetes 存活/就绪探针。

        Returns:
            HealthResponse:
                - status: "ok" / "unconfigured"
                - token_valid: 钉钉 accessToken 是否有效
                - workbook_id: 当前配置的工作簿 ID
        """
        if not settings.workbook_id or not settings.operator_union_id:
            return HealthResponse(status="unconfigured", token_valid=False, workbook_id="")
        token = await client.get_token()
        return HealthResponse(
            status="ok",
            token_valid=bool(token),
            workbook_id=settings.workbook_id,
        )

    return app


app = create_app()


# ---------------------------------------------------------------------------
# 命令行入口 — 对应 pyproject.toml [project.scripts]
# ---------------------------------------------------------------------------


def main() -> None:
    """命令行入口函数。

    从 Settings 读取 host 和 port 配置，启动 uvicorn 开发服务器。
    支持热重载（reload=True），适合开发调试。

    对应 pyproject.toml:
        [project.scripts]
        dingding-spreadsheet = "dingding_service.spreadsheet.main:main"
    """
    settings = Settings()
    uvicorn.run(
        "dingding_service.spreadsheet.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level=settings.log_level.lower(),
    )
