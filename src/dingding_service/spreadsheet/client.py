"""钉钉在线表格 HTTP 客户端。

本模块封装了钉钉 OpenAPI 的表格文档操作，提供：
  - 自动 Token 管理（缓存 + 过期刷新）
  - HTTP 连接复用（httpx.AsyncClient）
  - 统一的请求/错误处理

支持的 API:
  - 工作表管理：列出、创建、删除、查询信息
  - 单元格操作：读取、写入、清除区域
  - 行列操作：插入行、插入列
  - 文档搜索：按关键字检索钉钉文档

Usage:
    async with SpreadsheetClient(app_key="...", app_secret="...") as client:
        sheets = await client.list_sheets(wb_id, uid)
"""

import logging
import time
from os import getenv
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class SpreadsheetClient:
    """钉钉在线表格 HTTP 客户端。

    封装钉钉 OpenAPI 的表格操作，提供 token 自动管理和连接复用。
    支持 async with 上下文管理器，退出时自动关闭 HTTP 连接。

    Attributes:
        BASE_URL: 钉钉 API 基础地址（https://api.dingtalk.com）

    Example:
        async with SpreadsheetClient() as client:
            result = await client.list_sheets(wb_id, uid)
            print(result)
    """

    BASE_URL: str = "https://api.dingtalk.com"

    def __init__(self, app_key: str = "", app_secret: str = "") -> None:
        """初始化客户端实例。

        优先使用传入的凭证参数，若为空则回退到环境变量 DINGTALK_Client_ID 和
        DINGTALK_Client_Secret。初始化时即建立 httpx 异步客户端。

        Args:
            app_key:    钉钉应用的 AppKey，默认从 DINGTALK_Client_ID 环境变量读取
            app_secret: 钉钉应用的 AppSecret，默认从 DINGTALK_Client_Secret 环境变量读取
        """
        self._app_key = app_key or getenv("DINGTALK_Client_ID", "")
        self._app_secret = app_secret or getenv("DINGTALK_Client_Secret", "")
        self._token: str = ""
        self._token_expires_at: float = 0.0
        self._client: httpx.AsyncClient = httpx.AsyncClient(base_url=self.BASE_URL)
        logger.debug(
            "SpreadsheetClient 初始化完成 | app_key=%s...",
            self._app_key[:8] if self._app_key else "(空)",
        )

    async def get_token(self) -> str:
        """获取钉钉 accessToken。

        使用 OAuth2 客户端凭证模式（client_credentials）获取 accessToken。
        Token 会被缓存直到过期前 60 秒，避免重复请求。

        Returns:
            有效的 accessToken 字符串；获取失败时返回空字符串
        """
        # 缓存命中：token 存在且未过期
        if self._token and time.time() < self._token_expires_at:
            logger.debug(
                "Token 缓存命中 | 剩余有效期 %.0f 秒",
                self._token_expires_at - time.time(),
            )
            return self._token

        logger.info(
            "正在请求新的 accessToken | app_key=%s...",
            self._app_key[:8] if self._app_key else "(空)",
        )
        resp = await self._client.post(
            "/v1.0/oauth2/accessToken",
            json={"appKey": self._app_key, "appSecret": self._app_secret},
        )
        if resp.is_error:
            logger.error(
                "获取 accessToken 失败 | status=%d body=%s",
                resp.status_code,
                resp.text[:200],
            )
            return ""

        data = resp.json()
        self._token = data["accessToken"]
        self._token_expires_at = time.time() + data.get("expiresIn", 7200) - 60
        logger.info(
            "accessToken 获取成功 | 有效期 %d 秒",
            data.get("expiresIn", 7200),
        )
        return self._token

    async def _headers(self) -> dict[str, str]:
        """构建 API 请求的通用 HTTP 头。

        Returns:
            包含认证 token 和 Content-Type 的请求头字典
        """
        token = await self.get_token()
        return {
            "x-acs-dingtalk-access-token": token,
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        """统一的 HTTP 请求处理入口。

        所有 API 调用都通过此方法转发，统一处理：
          - 认证头注入
          - 网络异常捕获
          - HTTP 错误响应转换
          - 结构化日志记录

        Args:
            method: HTTP 方法（GET / POST / PUT / DELETE）
            path:   API 路径（如 /v1.0/doc/workbooks/{id}/sheets）
            **kwargs: 传递给 httpx.AsyncClient.request 的额外参数

        Returns:
            dict 包含：
                - 成功时：钉钉 API 返回的 JSON 数据
                - 失败时：{"error": ..., "status_code": ...} 或 {"error": str(exception)}
        """
        headers = kwargs.pop("headers", None) or await self._headers()
        logger.debug(
            "API 请求 | %s %s | params=%s",
            method,
            path,
            kwargs.get("params"),
        )

        try:
            resp = await self._client.request(method, path, headers=headers, **kwargs)
        except httpx.TimeoutException:
            logger.error("API 请求超时 | %s %s", method, path)
            return {"error": f"请求超时: {method} {path}"}
        except httpx.HTTPError as exc:
            logger.exception("HTTP 请求异常 | %s %s", method, path)
            return {"error": str(exc)}

        if resp.is_error:
            logger.warning(
                "API 调用失败 | %s %s | status=%d body=%s",
                method,
                path,
                resp.status_code,
                resp.text[:300],
            )
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            return {"error": str(detail), "status_code": resp.status_code}

        logger.debug(
            "API 响应成功 | %s %s | 数据量=%d",
            method,
            path,
            len(resp.content),
        )
        return resp.json()

    async def list_sheets(self, workbook_id: str, union_id: str) -> dict[str, Any]:
        """获取指定工作簿的所有工作表。

        Args:
            workbook_id: 表格文档唯一标识，从文档 URL 或搜索 API 获取
            union_id:    操作人的 unionId，用于权限校验

        Returns:
            dict 包含 value 列表（每项有 name 和 id 字段）
        """
        logger.info(
            "列出工作表 | workbook=%s operator=%s",
            workbook_id,
            union_id[:8] if union_id else "",
        )
        return await self._request(
            "GET",
            f"/v1.0/doc/workbooks/{workbook_id}/sheets",
            params={"operatorId": union_id},
        )

    async def create_sheet(self, workbook_id: str, union_id: str, name: str) -> dict[str, Any]:
        """在指定工作簿中创建新工作表。

        Args:
            workbook_id: 目标工作簿 ID
            union_id:    操作人的 unionId
            name:        新工作表的名称

        Returns:
            dict 包含新建工作表的 id 和 name
        """
        logger.info("创建工作表 | workbook=%s name=%s", workbook_id, name)
        return await self._request(
            "POST",
            f"/v1.0/doc/workbooks/{workbook_id}/sheets",
            params={"operatorId": union_id},
            json={"name": name},
        )

    async def delete_sheet(self, workbook_id: str, union_id: str, sheet_id: str) -> dict[str, Any]:
        """删除指定工作表。

        Args:
            workbook_id: 工作簿 ID
            union_id:    操作人的 unionId
            sheet_id:    要删除的工作表 ID

        Returns:
            成功时返回空 dict，失败时包含 error 信息
        """
        logger.warning("删除工作表 | workbook=%s sheet=%s", workbook_id, sheet_id)
        return await self._request(
            "DELETE",
            f"/v1.0/doc/workbooks/{workbook_id}/sheets/{sheet_id}",
            params={"operatorId": union_id},
        )

    async def get_range(
        self, workbook_id: str, union_id: str, sheet_id: str, range_str: str
    ) -> dict[str, Any]:
        """读取指定单元格区域的数据。

        返回区域内每个单元格的值，不含公式（公式会被计算为结果值）。

        Args:
            workbook_id: 工作簿 ID
            union_id:    操作人的 unionId
            sheet_id:    工作表 ID
            range_str:   单元格范围，如 "A1:C3"

        Returns:
            dict 包含 values 字段（二维数组）
        """
        logger.info(
            "读取单元格区域 | workbook=%s sheet=%s range=%s",
            workbook_id,
            sheet_id,
            range_str,
        )
        return await self._request(
            "GET",
            f"/v1.0/doc/workbooks/{workbook_id}/sheets/{sheet_id}/ranges/{range_str}",
            params={"operatorId": union_id},
        )

    async def update_range(
        self,
        workbook_id: str,
        union_id: str,
        sheet_id: str,
        range_str: str,
        values: list,
    ) -> dict[str, Any]:
        """向指定单元格区域写入数据。

        Args:
            workbook_id: 工作簿 ID
            union_id:    操作人的 unionId
            sheet_id:    工作表 ID
            range_str:   目标区域，如 "A1:C3"
            values:      二维数组数据，按行组织

        Returns:
            成功时返回空 dict
        """
        logger.info(
            "写入单元格区域 | workbook=%s sheet=%s range=%s rows=%d",
            workbook_id,
            sheet_id,
            range_str,
            len(values),
        )
        return await self._request(
            "PUT",
            f"/v1.0/doc/workbooks/{workbook_id}/sheets/{sheet_id}/ranges/{range_str}",
            params={"operatorId": union_id},
            json={"values": values},
        )

    async def insert_rows_before(
        self,
        workbook_id: str,
        union_id: str,
        sheet_id: str,
        row: int,
        row_count: int = 1,
    ) -> dict[str, Any]:
        """在指定行前插入空行。

        Args:
            workbook_id: 工作簿 ID
            union_id:    操作人的 unionId
            sheet_id:    工作表 ID
            row:         目标行号（从 1 开始）
            row_count:   插入行数，默认 1

        Returns:
            成功时返回空 dict
        """
        logger.info(
            "插入空行 | workbook=%s sheet=%s row=%d count=%d",
            workbook_id,
            sheet_id,
            row,
            row_count,
        )
        return await self._request(
            "POST",
            f"/v1.0/doc/workbooks/{workbook_id}/sheets/{sheet_id}/insertRowsBefore",
            params={"operatorId": union_id},
            json={"row": row, "rowCount": row_count},
        )

    async def insert_cols_before(
        self,
        workbook_id: str,
        union_id: str,
        sheet_id: str,
        column: int,
        column_count: int = 1,
    ) -> dict[str, Any]:
        """在指定列前插入空列。

        Args:
            workbook_id:  工作簿 ID
            union_id:     操作人的 unionId
            sheet_id:     工作表 ID
            column:       目标列号（从 1 开始）
            column_count: 插入列数，默认 1

        Returns:
            成功时返回空 dict
        """
        logger.info(
            "插入空列 | workbook=%s sheet=%s col=%d count=%d",
            workbook_id,
            sheet_id,
            column,
            column_count,
        )
        return await self._request(
            "POST",
            f"/v1.0/doc/workbooks/{workbook_id}/sheets/{sheet_id}/insertColumnsBefore",
            params={"operatorId": union_id},
            json={"column": column, "columnCount": column_count},
        )

    async def clear_range(
        self, workbook_id: str, union_id: str, sheet_id: str, range_str: str
    ) -> dict[str, Any]:
        """清除指定单元格区域的内容。

        仅清除数据，保留单元格格式（背景色、字体、边框等）。

        Args:
            workbook_id: 工作簿 ID
            union_id:    操作人的 unionId
            sheet_id:    工作表 ID
            range_str:   要清除的区域，如 "A1:C3"

        Returns:
            成功时返回空 dict
        """
        logger.info(
            "清除区域内容 | workbook=%s sheet=%s range=%s",
            workbook_id,
            sheet_id,
            range_str,
        )
        return await self._request(
            "POST",
            f"/v1.0/doc/workbooks/{workbook_id}/sheets/{sheet_id}/ranges/{range_str}/clear",
            params={"operatorId": union_id},
        )

    async def get_sheet_info(
        self, workbook_id: str, union_id: str, sheet_id: str
    ) -> dict[str, Any]:
        """查询单个工作表的元信息。

        Args:
            workbook_id: 工作簿 ID
            union_id:    操作人的 unionId
            sheet_id:    要查询的工作表 ID

        Returns:
            dict 包含工作表的名称、ID 等元信息
        """
        logger.info("查询工作表信息 | workbook=%s sheet=%s", workbook_id, sheet_id)
        return await self._request(
            "GET",
            f"/v1.0/doc/workbooks/{workbook_id}/sheets/{sheet_id}",
            params={"operatorId": union_id},
        )

    async def search_documents(
        self,
        union_id: str,
        keyword: str = "",
        max_results: int = 20,
    ) -> dict[str, Any]:
        """搜索钉钉文档。

        按关键字搜索当前企业空间中的文档，仅返回 alidoc（在线表格/文档）类型。

        Args:
            union_id:    操作人的 unionId
            keyword:     搜索关键字，为空时返回最近文档
            max_results: 最大返回条数，默认 20

        Returns:
            dict 包含搜索结果列表
        """
        logger.info("搜索文档 | keyword=%s max_results=%d", keyword, max_results)
        return await self._request(
            "POST",
            "/v2.0/storage/dentries/search",
            json={
                "operatorId": union_id,
                "keyword": keyword,
                "option": {
                    "dentryCategories": ["alidoc"],
                    "creatorIds": [],
                    "maxResults": max_results,
                },
            },
        )

    async def search_users(
        self, keyword: str, offset: int = 0, size: int = 10
    ) -> dict[str, Any]:
        """搜索通讯录用户。

        通过钉钉新版 API 搜索企业通讯录中的用户。

        Args:
            keyword: 搜索关键词（名称或拼音）
            offset:  分页偏移量
            size:    每页数量，最大 20

        Returns:
            dict 包含 list 数组，每项有 userId, name, avatar 等字段
        """
        logger.info("搜索用户 | keyword=%s", keyword)
        return await self._request(
            "POST",
            "/v1.0/contact/users/search",
            json={"queryWord": keyword, "offset": offset, "size": size},
        )

    async def get_user_detail(self, user_id: str) -> dict[str, Any]:
        """获取用户详情（含 unionId）。

        Args:
            user_id: 用户的 userId

        Returns:
            dict 包含 userId, unionId, name, mobile, dept_id_list 等
        """
        logger.info("获取用户详情 | userId=%s", user_id)
        return await self._request(
            "GET",
            f"/v1.0/contact/users/{user_id}",
        )

    async def close(self) -> None:
        """关闭 HTTP 客户端，释放连接池资源。"""
        await self._client.aclose()
        logger.debug("SpreadsheetClient HTTP 连接已关闭")

    async def __aenter__(self) -> "SpreadsheetClient":
        """异步上下文管理器入口。

        Returns:
            SpreadsheetClient 实例本身
        """
        return self

    async def __aexit__(self, *args: Any) -> None:
        """异步上下文管理器出口，自动关闭 HTTP 连接。"""
        await self.close()
