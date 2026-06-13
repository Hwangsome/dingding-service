"""测试配置和共享 fixtures。

提供 FastAPI 测试客户端、Mock 的 Settings 和 SpreadsheetClient，
所有 mock 数据尽量贴近真实钉钉 API 响应结构。
"""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from dingding_service.spreadsheet.config import Settings
from dingding_service.spreadsheet.main import create_app
from dingding_service.spreadsheet.routes import get_client, get_settings


@pytest.fixture
def app():
    """创建测试用 FastAPI 应用实例（每次测试新实例，避免状态泄漏）。"""
    return create_app()


@pytest.fixture
def client(app):
    """FastAPI TestClient 实例。"""
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides(app):
    """每个测试前后清除依赖覆盖，防止测试间相互影响。"""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mock_settings():
    """Mock 的 Settings，包含有效配置。

    提供测试用的钉钉应用凭证和工作簿 ID，用于正常业务流程测试。
    """
    return Settings(
        dingtalk_client_id="test_app_key",
        dingtalk_client_secret="test_app_secret",
        workbook_id="test_workbook_123",
        operator_union_id="test_union_456",
    )


@pytest.fixture
def unconfigured_settings():
    """未配置的 Settings（缺少 workbook/operator）。

    用于测试服务在配置不完整时的降级行为，验证 503 响应。
    """
    return Settings(
        dingtalk_client_id="test_app_key",
        dingtalk_client_secret="test_app_secret",
        workbook_id="",
        operator_union_id="",
    )


@pytest.fixture
def mock_client():
    """Mock 的 SpreadsheetClient，模拟钉钉 API 响应。

    所有方法返回的数据结构与真实钉钉 API 一致（含 value/values/displayValues 等字段）。
    已移除钉钉底层不支持的 API（cellProperties 等）。
    """
    mock = AsyncMock()
    mock.get_token = AsyncMock(return_value="fake_token_abc123")
    mock.list_sheets = AsyncMock(
        return_value={
            "value": [
                {"id": "kgqie6hm", "name": "Sheet1"},
                {"id": "sheet2_id", "name": "Sheet2"},
            ]
        }
    )
    mock.create_sheet = AsyncMock(return_value={"id": "new_sheet_id", "name": "NewSheet"})
    mock.delete_sheet = AsyncMock(return_value={})
    mock.get_range = AsyncMock(
        return_value={
            "values": [["a", "b"], ["c", "d"]],
            "displayValues": [["a", "b"], ["c", "d"]],
            "formulas": [["", ""], ["", ""]],
            "backgroundColors": [["#FFFFFF", "#FFFFFF"], ["#FFFFFF", "#FFFFFF"]],
            "fontSizes": [["10", "10"], ["10", "10"]],
            "fontWeights": [["normal", "normal"], ["normal", "normal"]],
            "hyperlinks": [["", ""], ["", ""]],
            "alignments": [["general", "general"], ["general", "general"]],
        }
    )
    mock.update_range = AsyncMock(return_value={})
    mock.insert_rows_before = AsyncMock(return_value={})
    mock.insert_cols_before = AsyncMock(return_value={})
    mock.clear_range = AsyncMock(return_value={})
    mock.get_sheet_info = AsyncMock(
        return_value={
            "id": "kgqie6hm",
            "name": "Sheet1",
            "rowCount": 100,
            "columnCount": 26,
        }
    )
    mock.search_users = AsyncMock(
        return_value={
            "list": [
                {"userId": "user_001", "name": "张三", "avatar": "https://example.com/avatar1.png"},
                {"userId": "user_002", "name": "李四", "avatar": "https://example.com/avatar2.png"},
            ]
        }
    )
    mock.get_user_detail = AsyncMock(
        return_value={
            "userId": "user_001",
            "unionId": "union_789",
            "name": "张三",
            "mobile": "13800138000",
            "dept_id_list": [1, 2],
        }
    )
    return mock


@pytest.fixture
def setup_standard_mocks(mock_settings, mock_client, app):
    """应用标准依赖覆盖，用于 API CRUD 测试。

    将 mock_settings 和 mock_client 注入到 FastAPI 依赖系统中，
    使所有路由使用测试替身而非真实钉钉 API 调用。
    """

    async def _override_get_client():
        return mock_client

    app.dependency_overrides[get_settings] = lambda: mock_settings
    app.dependency_overrides[get_client] = _override_get_client
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def sample_write_data():
    """示例写入数据，包含中文内容。"""
    return {
        "range": "A1:B2",
        "values": [["测试1", "测试2"], ["测试3", "测试4"]],
    }
