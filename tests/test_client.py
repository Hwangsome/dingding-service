"""钉钉 SpreadsheetClient 单元测试。

直接测试 SpreadsheetClient 内部逻辑（token 缓存/刷新、API 调用、错误处理），
通过 mock httpx.AsyncClient 来隔离外部 HTTP 调用。

注意：httpx.Response.json() 是同步方法，因此 mock 响应对象使用 Mock 而非 AsyncMock。
"""

import time

import pytest
from unittest.mock import AsyncMock, MagicMock

from dingding_service.spreadsheet.client import SpreadsheetClient


class TestSpreadsheetClient:
    """SpreadsheetClient 单元测试。

    覆盖 token 缓存机制、API 调用成功/失败路径、
    以及完整响应数据的解析。
    """

    # ------------------------------------------------------------------
    # Fixtures
    # ------------------------------------------------------------------

    @pytest.fixture
    def client(self):
        """创建未认证的 SpreadsheetClient 实例（使用测试用 app_key/app_secret）。"""
        return SpreadsheetClient(app_key="test_key", app_secret="test_secret")

    def _make_response(self, is_error: bool = False, status_code: int = 200,
                       json_data: dict | None = None, text: str = ""):
        """创建模拟的 httpx 响应对象。

        httpx.Response 的方法（如 .json()）是同步的，
        因此使用 MagicMock 而非 AsyncMock 避免返回协程。

        Args:
            is_error:   是否模拟错误响应
            status_code: HTTP 状态码
            json_data:  响应的 JSON 数据
            text:       响应的文本内容

        Returns:
            MagicMock: 模拟的 httpx 响应对象
        """
        mock = MagicMock()
        mock.is_error = is_error
        mock.status_code = status_code
        mock.json.return_value = json_data or {}
        mock.text = text
        return mock

    # ------------------------------------------------------------------
    # Token 管理
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_token_cached(self, client):
        """验证 token 缓存机制：有效期内不重新请求。

        当 _token 已设置且未过期时，get_token 应直接返回缓存值，
        不应发起新的 HTTP 请求。
        """
        client._token = "cached_token"
        client._token_expires_at = time.time() + 3600  # 1 小时后才过期

        token = await client.get_token()

        assert token == "cached_token"

    @pytest.mark.asyncio
    async def test_get_token_refresh_on_expiry(self, client):
        """验证 token 过期后自动刷新。

        当 _token_expires_at 已过当前时间时，get_token 应重新请求 access token。
        """
        client._token = "expired_token"
        client._token_expires_at = time.time() - 10  # 已过期 10 秒

        mock_resp = self._make_response(
            json_data={"accessToken": "new_token_xyz", "expiresIn": 7200},
        )
        client._client.post = AsyncMock(return_value=mock_resp)

        token = await client.get_token()

        assert token == "new_token_xyz"
        client._client.post.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_token_failure_returns_empty(self, client):
        """验证 token 请求失败时返回空字符串。

        当钉钉 API 返回 401 错误时，get_token 应返回 "" 而非抛出异常。
        """
        mock_resp = self._make_response(
            is_error=True, status_code=401,
            json_data={"message": "Invalid appKey"},
        )
        client._client.post = AsyncMock(return_value=mock_resp)

        token = await client.get_token()

        assert token == ""

    # ------------------------------------------------------------------
    # list_sheets
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_list_sheets_success(self, client):
        """验证获取工作表列表成功。

        正常返回包含 value 数组的响应，每个元素包含 id 和 name 字段。
        """
        client._token = "fake_token"
        client._token_expires_at = time.time() + 3600

        mock_resp = self._make_response(
            json_data={"value": [{"id": "s1", "name": "Sheet1"}]},
        )
        client._client.request = AsyncMock(return_value=mock_resp)

        result = await client.list_sheets("wb1", "u1")

        assert "value" in result
        assert result["value"][0]["id"] == "s1"
        assert result["value"][0]["name"] == "Sheet1"

    @pytest.mark.asyncio
    async def test_list_sheets_api_error(self, client):
        """验证 API 错误时返回错误字典。

        当钉钉 API 返回 400 错误时，client 应返回包含 error 和 status_code 的字典。
        """
        client._token = "fake_token"
        client._token_expires_at = time.time() + 3600

        mock_resp = self._make_response(
            is_error=True, status_code=400,
            json_data={"message": "bad request"},
        )
        client._client.request = AsyncMock(return_value=mock_resp)

        result = await client.list_sheets("wb1", "u1")

        assert "error" in result
        assert "status_code" in result
        assert result["status_code"] == 400

    # ------------------------------------------------------------------
    # get_range
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_range_full_response(self, client):
        """验证读取单元格返回完整属性（值、格式、超链接等）。

        钉钉 API 返回的单元格数据包含 values、displayValues、formulas、
        backgroundColors、fontSizes、fontWeights、hyperlinks、alignments 等字段。
        """
        client._token = "fake_token"
        client._token_expires_at = time.time() + 3600

        full_response = {
            "values": [["a", "b"], ["c", "d"]],
            "displayValues": [["a", "b"], ["c", "d"]],
            "formulas": [["", ""], ["", ""]],
            "backgroundColors": [["#FFFFFF", "#FFFFFF"], ["#FFFFFF", "#FFFFFF"]],
            "fontSizes": [["10", "10"], ["10", "10"]],
            "fontWeights": [["normal", "normal"], ["normal", "normal"]],
            "hyperlinks": [[{"url": "https://example.com"}, ""], ["", ""]],
            "alignments": [["general", "general"], ["general", "general"]],
        }

        mock_resp = self._make_response(json_data=full_response)
        client._client.request = AsyncMock(return_value=mock_resp)

        result = await client.get_range("wb1", "u1", "s1", "A1:B2")

        assert result["values"][0][0] == "a"
        assert result["hyperlinks"][0][0]["url"] == "https://example.com"
        assert result["backgroundColors"][0][0] == "#FFFFFF"
        assert result["fontSizes"][0][0] == "10"
        assert result["fontWeights"][0][0] == "normal"

    # ------------------------------------------------------------------
    # 异常处理
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_http_error_returns_error_dict(self, client):
        """验证网络异常时返回错误字典。

        当 httpx 抛出 HTTPError（如连接超时）时，
        client 应捕获异常并返回包含 error 字段的字典。
        """
        client._token = "fake_token"
        client._token_expires_at = time.time() + 3600
        import httpx
        client._client.request = AsyncMock(side_effect=httpx.TimeoutException("Connection timeout"))

        result = await client.get_range("wb1", "u1", "s1", "A1:B2")

        assert "error" in result
