"""钉钉在线表格 REST API 路由定义。

本模块使用 FastAPI APIRouter 定义所有 /api 前缀的 RESTful 端点，
包括依赖注入（Settings、SpreadsheetClient）和请求/响应处理逻辑。

端点一览:
    GET    /api/sheets                              — 列出工作表
    POST   /api/sheets                              — 创建工作表
    DELETE /api/sheets/{sheet_id}                    — 删除工作表
    GET    /api/sheets/{sheet_id}                    — 查询工作表信息
    GET    /api/sheets/{sheet_id}/range              — 读取单元格区域
    PUT    /api/sheets/{sheet_id}/range              — 写入单元格区域
    POST   /api/sheets/{sheet_id}/range/clear        — 清除单元格区域
    GET    /api/sheets/{sheet_id}/range/properties   — 获取单元格格式
    POST   /api/sheets/{sheet_id}/insertRowsBefore   — 插入行
    POST   /api/sheets/{sheet_id}/insertColumnsBefore— 插入列
"""

import logging
from collections.abc import AsyncGenerator
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Query

from .client import SpreadsheetClient
from .config import Settings
from .models import (
    ClearRangeRequest,
    CreateSheetRequest,
    InsertColsRequest,
    InsertRowsRequest,
    RangeWriteRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# 依赖注入
# ---------------------------------------------------------------------------


@lru_cache
def get_settings() -> Settings:
    """获取全局单例配置对象。

    使用 lru_cache 确保 Settings 仅初始化一次（读取 .env 文件），
    后续调用直接返回缓存实例。

    Returns:
        Settings: 从环境变量加载的应用配置
    """
    return Settings()


async def get_client(
    settings: Settings = Depends(get_settings),
) -> AsyncGenerator[SpreadsheetClient, None]:
    """获取 SpreadsheetClient 实例的依赖。

    每次请求创建一个新的客户端（复用 httpx 连接池），
    请求结束后自动关闭。

    Args:
        settings: 由 FastAPI 注入的应用配置

    Yields:
        SpreadsheetClient 实例，供端点函数使用
    """
    async with SpreadsheetClient(
        app_key=settings.dingtalk_client_id,
        app_secret=settings.dingtalk_client_secret,
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# 内部辅助函数
# ---------------------------------------------------------------------------


def _require_auth(settings: Settings) -> str:
    """仅校验钉钉凭证，不要求 workbook/operator 配置。

    Args:
        settings: 应用配置

    Returns:
        dingtalk_client_id 字符串

    Raises:
        HTTPException 503: 钉钉凭证未配置时
    """
    if not settings.dingtalk_client_id or not settings.dingtalk_client_secret:
        raise HTTPException(
            status_code=503,
            detail="钉钉凭证未配置，请先设置 DINGTALK_Client_ID 和 DINGTALK_Client_Secret",
        )
    return settings.dingtalk_client_id


def _require_config(settings: Settings) -> tuple[str, str]:
    """校验配置完整性，返回 workbook_id 和 operator_union_id。

    如果 workbook_id 或 operator_union_id 为空，抛出 503 异常。

    Args:
        settings: 应用配置

    Returns:
        (workbook_id, operator_union_id) 元组

    Raises:
        HTTPException 503: 配置不完整时
    """
    if not settings.workbook_id or not settings.operator_union_id:
        raise HTTPException(
            status_code=503,
            detail="工作簿 ID 或操作用户未配置，请先设置 WORKBOOK_ID 和 OPERATOR_UNION_ID",
        )
    return settings.workbook_id, settings.operator_union_id


async def _call(client: SpreadsheetClient, method: str, *args, **kwargs) -> dict:
    """调用客户端方法并统一处理业务错误。

    如果客户端返回了 error 字段，将其转换为 HTTP 500 异常。

    Args:
        client: SpreadsheetClient 实例
        method: 要调用的客户端方法名（如 "list_sheets"）
        *args:  传递给客户端方法的位置参数
        **kwargs: 传递给客户端方法的关键字参数

    Returns:
        dict: 客户端方法返回的成功结果

    Raises:
        HTTPException 500: 当客户端方法返回的 dict 包含 "error" 字段时
    """
    fn = getattr(client, method)
    result = await fn(*args, **kwargs)
    if "error" in result:
        logger.error("业务调用失败 | method=%s error=%s", method, str(result["error"])[:200])
        raise HTTPException(status_code=500, detail=result["error"])
    return result


# ---------------------------------------------------------------------------
# API 端点
# ---------------------------------------------------------------------------


@router.get("/sheets")
async def list_sheets(
    settings: Settings = Depends(get_settings),
    client: SpreadsheetClient = Depends(get_client),
) -> dict:
    """获取当前工作簿下的所有工作表列表。

    响应格式与钉钉 OpenAPI 一致，包含 value 数组，
    每个元素有 name（工作表名称）和 id（工作表 ID）。

    Returns:
        dict: 包含 sheets 或 value 列表的响应
    """
    logger.info("GET /api/sheets — 列出工作表")
    wid, operator = _require_config(settings)
    result = await _call(client, "list_sheets", wid, operator)
    return result


@router.post("/sheets", status_code=201)
async def create_sheet(
    body: CreateSheetRequest,
    settings: Settings = Depends(get_settings),
    client: SpreadsheetClient = Depends(get_client),
) -> dict:
    """在默认工作簿中创建新的工作表。

    Args:
        body: 创建工作表的请求体（含 name 字段）

    Returns:
        dict: 新建工作表信息（id 和 name）
    """
    logger.info("POST /api/sheets — 创建工作表 | name=%s", body.name)
    wid, operator = _require_config(settings)
    result = await _call(client, "create_sheet", wid, operator, body.name)
    return result


@router.delete("/sheets/{sheet_id}")
async def delete_sheet(
    sheet_id: str,
    settings: Settings = Depends(get_settings),
    client: SpreadsheetClient = Depends(get_client),
) -> dict:
    """删除指定的工作表。

    此操作不可逆，请谨慎调用。

    Args:
        sheet_id: 要删除的工作表 ID
    """
    logger.info("DELETE /api/sheets/%s — 删除工作表", sheet_id)
    wid, operator = _require_config(settings)
    result = await _call(client, "delete_sheet", wid, operator, sheet_id)
    return result


@router.get("/sheets/{sheet_id}/range")
async def read_range(
    sheet_id: str,
    range: str = "A1:C10",
    settings: Settings = Depends(get_settings),
    client: SpreadsheetClient = Depends(get_client),
) -> dict:
    """读取指定单元格区域的数据。

    返回区域内所有单元格的值，以二维数组体现。

    Args:
        sheet_id: 工作表 ID
        range:    单元格区域，如 "A1:C10"，默认读取前 10 行 3 列
    """
    logger.info("GET /api/sheets/%s/range — 读取区域 | range=%s", sheet_id, range)
    wid, operator = _require_config(settings)
    result = await _call(client, "get_range", wid, operator, sheet_id, range)
    return result


@router.put("/sheets/{sheet_id}/range")
async def write_range(
    sheet_id: str,
    body: RangeWriteRequest,
    settings: Settings = Depends(get_settings),
    client: SpreadsheetClient = Depends(get_client),
) -> dict:
    """向指定单元格区域写入数据。

    写入操作会覆盖目标区域的原有内容。

    Args:
        sheet_id: 工作表 ID
        body:     写入请求，包含 range 和 values 两个字段
    """
    logger.info(
        "PUT /api/sheets/%s/range — 写入区域 | range=%s rows=%d",
        sheet_id,
        body.range,
        len(body.values),
    )
    wid, operator = _require_config(settings)
    result = await _call(client, "update_range", wid, operator, sheet_id, body.range, body.values)
    return result


@router.post("/sheets/{sheet_id}/insertRowsBefore")
async def insert_rows_before(
    sheet_id: str,
    body: InsertRowsRequest,
    settings: Settings = Depends(get_settings),
    client: SpreadsheetClient = Depends(get_client),
) -> dict:
    """在指定行前插入空行。

    插入后下方行自动下移。

    Args:
        sheet_id: 工作表 ID
        body:     插入行请求，包含 row 和可选 row_count
    """
    logger.info(
        "POST /api/sheets/%s/insertRowsBefore — 插入行 | row=%d count=%d",
        sheet_id,
        body.row,
        body.row_count,
    )
    wid, operator = _require_config(settings)
    result = await _call(
        client, "insert_rows_before", wid, operator, sheet_id, body.row, body.row_count
    )
    return result


@router.post("/sheets/{sheet_id}/insertColumnsBefore")
async def insert_cols_before(
    sheet_id: str,
    body: InsertColsRequest,
    settings: Settings = Depends(get_settings),
    client: SpreadsheetClient = Depends(get_client),
) -> dict:
    """在指定列前插入空列。

    插入后右侧列自动右移。

    Args:
        sheet_id: 工作表 ID
        body:     插入列请求，包含 column 和可选 column_count
    """
    logger.info(
        "POST /api/sheets/%s/insertColumnsBefore — 插入列 | col=%d count=%d",
        sheet_id,
        body.column,
        body.column_count,
    )
    wid, operator = _require_config(settings)
    result = await _call(
        client, "insert_cols_before", wid, operator, sheet_id, body.column, body.column_count
    )
    return result


@router.get("/sheets/{sheet_id}")
async def get_sheet_info(
    sheet_id: str,
    settings: Settings = Depends(get_settings),
    client: SpreadsheetClient = Depends(get_client),
) -> dict:
    """查询单个工作表的元信息。

    返回工作表的名称、ID、行列数等基本信息。

    Args:
        sheet_id: 要查询的工作表 ID
    """
    logger.info("GET /api/sheets/%s — 查询工作表信息", sheet_id)
    wid, operator = _require_config(settings)
    result = await _call(client, "get_sheet_info", wid, operator, sheet_id)
    return result


@router.post("/sheets/{sheet_id}/range/clear")
async def clear_range(
    sheet_id: str,
    body: ClearRangeRequest,
    settings: Settings = Depends(get_settings),
    client: SpreadsheetClient = Depends(get_client),
) -> dict:
    """清除指定单元格区域的内容。

    仅清除数据，不影响单元格格式（背景色、边框等）。

    Args:
        sheet_id: 工作表 ID
        body:     清除请求，包含 range 字段
    """
    logger.info(
        "POST /api/sheets/%s/range/clear — 清除区域 | range=%s",
        sheet_id,
        body.range,
    )
    wid, operator = _require_config(settings)
    result = await _call(client, "clear_range", wid, operator, sheet_id, body.range)
    return result


# ---------------------------------------------------------------------------
# 配置查询 API — 无需 WORKBOOK_ID 和 OPERATOR_UNION_ID
# ---------------------------------------------------------------------------


@router.get("/users/search")
async def search_users(
    keyword: str = Query(..., description="搜索关键词（姓名或拼音）"),
    settings: Settings = Depends(get_settings),
    client: SpreadsheetClient = Depends(get_client),
) -> dict:
    """搜索钉钉通讯录用户。

    无需预先配置 WORKBOOK_ID 或 OPERATOR_UNION_ID，
    只需要钉钉应用凭证即可使用。
    返回的 userId 可用于 get_user_detail 获取 unionId。
    """
    _require_auth(settings)
    logger.info("GET /api/users/search — 搜索用户 | keyword=%s", keyword)
    result = await _call(client, "search_users", keyword)
    return result


@router.get("/users/{user_id}")
async def get_user_detail(
    user_id: str,
    settings: Settings = Depends(get_settings),
    client: SpreadsheetClient = Depends(get_client),
) -> dict:
    """获取用户详情。

    返回用户的 unionId、姓名、部门等信息。
    返回的 unionId 即 OPERATOR_UNION_ID 所需的值。
    """
    _require_auth(settings)
    logger.info("GET /api/users/%s — 用户详情", user_id)
    result = await _call(client, "get_user_detail", user_id)
    return result


@router.get("/documents/search")
async def search_documents(
    keyword: str = Query("", description="文档名称关键词"),
    operator_id: str = Query(..., description="操作人的 unionId"),
    settings: Settings = Depends(get_settings),
    client: SpreadsheetClient = Depends(get_client),
) -> dict:
    """搜索钉钉文档/表格。

    需要提供 operatorId（unionId）用于权限校验。
    返回的 dentryUuid 即 WORKBOOK_ID 所需的值。
    """
    _require_auth(settings)
    logger.info("GET /api/documents/search — 搜索文档 | keyword=%s", keyword)
    result = await _call(client, "search_documents", operator_id, keyword)
    return result
