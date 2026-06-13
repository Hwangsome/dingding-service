"""钉钉 Spreadsheet CRUD API 端点集成测试。

所有测试通过 mock SpreadsheetClient 避免真实钉钉 API 调用。
测试覆盖：
  - 工作表管理（列表、创建、删除）
  - 单元格读写（范围读取、数据写入、清除）
  - 行列操作（前插行、前插列）
  - 单元格属性读取
  - 异常场景（配置缺失、参数校验失败、API 错误）
"""

from unittest.mock import AsyncMock

import pytest


class TestListSheets:
    """GET /api/sheets — 获取所有工作表列表。"""

    def test_list_sheets(self, client, setup_standard_mocks, mock_client):
        """验证获取工作表列表成功，返回包含 id 和 name 的数组。"""
        resp = client.get("/api/sheets")
        assert resp.status_code == 200
        data = resp.json()
        assert "value" in data
        assert len(data["value"]) == 2
        assert data["value"][0]["id"] == "kgqie6hm"
        assert data["value"][0]["name"] == "Sheet1"

    def test_list_sheets_empty(self, client, setup_standard_mocks, mock_client):
        """验证工作簿无工作表时返回空数组。"""
        mock_client.list_sheets = AsyncMock(return_value={"value": []})
        resp = client.get("/api/sheets")
        assert resp.status_code == 200
        assert resp.json()["value"] == []


class TestCreateSheet:
    """POST /api/sheets — 创建工作表。"""

    def test_create_sheet(self, client, setup_standard_mocks, mock_client):
        """验证创建工作表成功，返回 201 和新表信息。"""
        resp = client.post("/api/sheets", json={"name": "TestSheet"})
        assert resp.status_code == 201
        assert mock_client.create_sheet.await_count == 1

    def test_create_sheet_requires_name(self, client, setup_standard_mocks):
        """验证创建 sheet 时必须提供 name 字段，缺少时返回 422。"""
        resp = client.post("/api/sheets", json={})
        assert resp.status_code == 422

    def test_create_sheet_requires_json(self, client, setup_standard_mocks):
        """验证创建 sheet 时必须提供 JSON 请求体。

        场景：不发送 Content-Type: application/json 时返回 422 Unprocessable Entity。
        """
        resp = client.post("/api/sheets")
        assert resp.status_code == 422


class TestDeleteSheet:
    """DELETE /api/sheets/{sheet_id} — 删除工作表。"""

    def test_delete_sheet(self, client, setup_standard_mocks, mock_client):
        """验证删除已有工作表成功。"""
        resp = client.delete("/api/sheets/s1")
        assert resp.status_code == 200
        assert mock_client.delete_sheet.await_count == 1

    def test_delete_nonexistent_sheet(self, client, setup_standard_mocks, mock_client):
        """验证删除不存在的工作表时返回 500 错误。"""
        mock_client.delete_sheet = AsyncMock(return_value={"error": "not found"})
        resp = client.delete("/api/sheets/nonexistent")
        assert resp.status_code == 500
        assert "detail" in resp.json()


class TestReadRange:
    """GET /api/sheets/{sheet_id}/range — 读取单元格区域。"""

    def test_read_range(self, client, setup_standard_mocks, mock_client):
        """验证读取指定范围的单元格数据。"""
        resp = client.get("/api/sheets/s1/range?range=A1:B2")
        assert resp.status_code == 200
        data = resp.json()
        assert "values" in data
        assert "displayValues" in data
        assert "formulas" in data
        assert mock_client.get_range.await_count == 1

    def test_read_range_default_range(self, client, setup_standard_mocks, mock_client):
        """验证不指定 range 参数时使用默认值 A1:C10。"""
        resp = client.get("/api/sheets/s1/range")
        assert resp.status_code == 200
        assert mock_client.get_range.await_count == 1

    @pytest.mark.parametrize(
        "range_str,expected_rows",
        [
            ("A1:B2", 2),
            ("A1:A1", 1),
            ("A1:Z100", 100),
        ],
    )
    def test_read_range_sizes(
        self, client, setup_standard_mocks, mock_client, range_str, expected_rows
    ):
        """验证不同大小范围的读取能够正确处理。

        使用 parametrize 覆盖单格、小范围、大范围的读取场景，
        避免为每个范围大小编写重复的测试函数。
        """
        values = [[f"r{r}c{c}" for c in range(2)] for r in range(expected_rows)]
        mock_client.get_range = AsyncMock(return_value={"values": values})
        resp = client.get(f"/api/sheets/s1/range?range={range_str}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["values"]) == expected_rows


class TestWriteRange:
    """PUT /api/sheets/{sheet_id}/range — 写入单元格区域。"""

    def test_write_range(self, client, setup_standard_mocks, mock_client, sample_write_data):
        """验证写入字符串数据到指定区域。"""
        resp = client.put("/api/sheets/s1/range", json=sample_write_data)
        assert resp.status_code == 200
        assert mock_client.update_range.await_count == 1

    def test_write_range_invalid_body(self, client, setup_standard_mocks):
        """验证缺少 values 字段时返回 422。"""
        resp = client.put("/api/sheets/s1/range", json={"range": "A1:B2"})
        assert resp.status_code == 422

    def test_write_range_empty_values(self, client, setup_standard_mocks):
        """验证 values 为空列表时仍然可以写入（清空区域内容）。"""
        resp = client.put(
            "/api/sheets/s1/range",
            json={"range": "A1:B2", "values": []},
        )
        assert resp.status_code == 200

    def test_write_range_complex_data(self, client, setup_standard_mocks, mock_client):
        """验证写入包含数字、布尔值的复杂数据类型。

        钉钉 API 支持的数字类型包括整数、浮点数、布尔值。
        确认这些数据类型能正确序列化并通过 Pydantic 校验。
        """
        data = {
            "range": "A1:C2",
            "values": [[42, True, 3.14], [False, 0, -1]],
        }
        mock_client.update_range = AsyncMock(return_value={})
        resp = client.put("/api/sheets/s1/range", json=data)
        assert resp.status_code == 200
        assert mock_client.update_range.await_count == 1

    def test_write_range_chinese_characters(self, client, setup_standard_mocks, mock_client):
        """验证中文字符写入的正确性。

        钉钉表格广泛应用于中文环境，确保中文字符传输不会出现乱码或编码错误。
        """
        data = {
            "range": "A1:B2",
            "values": [["姓名", "分数"], ["张三", "95"]],
        }
        mock_client.update_range = AsyncMock(return_value={})
        resp = client.put("/api/sheets/s1/range", json=data)
        assert resp.status_code == 200
        assert mock_client.update_range.await_count == 1


class TestInsertRows:
    """POST /api/sheets/{sheet_id}/insertRowsBefore — 在指定行前插入行。"""

    def test_insert_rows(self, client, setup_standard_mocks, mock_client):
        """验证在第 2 行前插入 3 行，返回成功。"""
        resp = client.post(
            "/api/sheets/s1/insertRowsBefore",
            json={"row": 2, "row_count": 3},
        )
        assert resp.status_code == 200
        mock_client.insert_rows_before.assert_awaited_once_with(
            "test_workbook_123", "test_union_456", "s1", 2, 3
        )

    def test_insert_rows_default_count(self, client, setup_standard_mocks, mock_client):
        """验证不指定 row_count 时默认插入 1 行。"""
        resp = client.post(
            "/api/sheets/s1/insertRowsBefore",
            json={"row": 5},
        )
        assert resp.status_code == 200
        mock_client.insert_rows_before.assert_awaited_once_with(
            "test_workbook_123", "test_union_456", "s1", 5, 1
        )

    def test_insert_rows_invalid_body(self, client, setup_standard_mocks):
        """验证缺少必要字段时返回 422。"""
        resp = client.post("/api/sheets/s1/insertRowsBefore", json={})
        assert resp.status_code == 422

    def test_insert_rows_invalid_type(self, client, setup_standard_mocks):
        """验证 row 字段为非整数时返回 422。"""
        resp = client.post(
            "/api/sheets/s1/insertRowsBefore",
            json={"row": "abc", "row_count": 1},
        )
        assert resp.status_code == 422


class TestInsertCols:
    """POST /api/sheets/{sheet_id}/insertColumnsBefore — 在指定列前插入列。"""

    def test_insert_cols(self, client, setup_standard_mocks, mock_client):
        """验证在第 2 列前插入 3 列，返回成功。"""
        resp = client.post(
            "/api/sheets/s1/insertColumnsBefore",
            json={"column": 2, "column_count": 3},
        )
        assert resp.status_code == 200
        mock_client.insert_cols_before.assert_awaited_once_with(
            "test_workbook_123", "test_union_456", "s1", 2, 3
        )

    def test_insert_cols_default_count(self, client, setup_standard_mocks, mock_client):
        """验证不指定 column_count 时默认插入 1 列。"""
        resp = client.post(
            "/api/sheets/s1/insertColumnsBefore",
            json={"column": 1},
        )
        assert resp.status_code == 200
        mock_client.insert_cols_before.assert_awaited_once_with(
            "test_workbook_123", "test_union_456", "s1", 1, 1
        )

    def test_insert_cols_invalid_body(self, client, setup_standard_mocks):
        """验证缺少 column 字段时返回 422。"""
        resp = client.post("/api/sheets/s1/insertColumnsBefore", json={})
        assert resp.status_code == 422


class TestClearRange:
    """POST /api/sheets/{sheet_id}/range/clear — 清除单元格区域数据。"""

    def test_clear_range(self, client, setup_standard_mocks, mock_client):
        """验证清除指定单元格区域的数据。

        请求体包含 range 字段指定要清除的范围。
        成功清除后返回 200。
        """
        resp = client.post(
            "/api/sheets/s1/range/clear",
            json={"range": "A1:B2"},
        )
        assert resp.status_code == 200
        mock_client.clear_range.assert_awaited_once_with(
            "test_workbook_123", "test_union_456", "s1", "A1:B2"
        )

    def test_clear_range_missing_range(self, client, setup_standard_mocks):
        """验证不提供 range 字段时返回 422。"""
        resp = client.post(
            "/api/sheets/s1/range/clear",
            json={},
        )
        assert resp.status_code == 422


class TestGetSheetInfo:
    """GET /api/sheets/{sheet_id} — 获取单个工作表信息。"""

    def test_get_sheet_info(self, client, setup_standard_mocks, mock_client):
        """验证获取工作表的详细信息（id、名称、行列数）。"""
        resp = client.get("/api/sheets/s1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "kgqie6hm"
        assert data["name"] == "Sheet1"
        assert "rowCount" in data
        assert "columnCount" in data
        assert mock_client.get_sheet_info.await_count == 1

    def test_get_sheet_info_nonexistent(self, client, setup_standard_mocks, mock_client):
        """验证获取不存在的工作表时返回错误。"""
        mock_client.get_sheet_info = AsyncMock(return_value={"error": "sheet not found"})
        resp = client.get("/api/sheets/nonexistent")
        assert resp.status_code == 500
        assert "detail" in resp.json()


class TestErrorCases:
    """异常场景测试 — 配置缺失、参数错误、API 异常等。"""

    def test_503_unconfigured(self, client, unconfigured_settings):
        """验证 workbook_id 未配置时返回 503 Service Unavailable。"""
        from dingding_service.spreadsheet.routes import get_settings

        client.app.dependency_overrides[get_settings] = lambda: unconfigured_settings
        resp = client.get("/api/sheets")
        assert resp.status_code == 503
        assert "detail" in resp.json()

    def test_422_missing_content_type(self, client, setup_standard_mocks):
        """验证 POST 请求不含 Content-Type 时返回 422。"""
        resp = client.post("/api/sheets", data="not json")
        assert resp.status_code == 422

    def test_503_on_method_config_failure(self, client, unconfigured_settings):
        """验证所有端点（GET/POST/DELETE）在未配置时均返回 503。"""
        from dingding_service.spreadsheet.routes import get_settings

        app = client.app
        app.dependency_overrides[get_settings] = lambda: unconfigured_settings

        responses = [
            client.get("/api/sheets"),
            client.post("/api/sheets", json={"name": "test"}),
            client.delete("/api/sheets/s1"),
            client.get("/api/sheets/s1/range"),
        ]
        for resp in responses:
            assert resp.status_code == 503, f"期望 503，实际 {resp.status_code}"


class TestSearchUsers:
    """GET /api/users/search — 搜索通讯录用户。"""

    def test_search_users_success(self, client, setup_standard_mocks, mock_client):
        """验证搜索用户成功，返回用户列表。"""
        resp = client.get("/api/users/search", params={"keyword": "张三"})
        assert resp.status_code == 200
        data = resp.json()
        assert "list" in data
        assert len(data["list"]) == 2
        assert data["list"][0]["userId"] == "user_001"
        assert mock_client.search_users.await_count == 1

    def test_search_users_no_keyword(self, client, setup_standard_mocks):
        """验证不提供 keyword 时返回 422。"""
        resp = client.get("/api/users/search")
        assert resp.status_code == 422

    def test_search_users_no_auth(self, client, unconfigured_settings, mock_client):
        """验证只有钉钉凭证（无 workbook/operator）时可以正常使用。"""
        from dingding_service.spreadsheet.routes import get_client, get_settings

        client.app.dependency_overrides[get_settings] = lambda: unconfigured_settings
        async def _mock_client():
            return mock_client
        client.app.dependency_overrides[get_client] = _mock_client

        resp = client.get("/api/users/search", params={"keyword": "张三"})
        assert resp.status_code == 200
        data = resp.json()
        assert "list" in data
        assert mock_client.search_users.await_count == 1

    def test_search_users_no_creds(self, client):
        """验证完全没有钉钉凭证时返回 503。"""
        from dingding_service.spreadsheet.config import Settings
        from dingding_service.spreadsheet.routes import get_settings

        no_creds = Settings(
            dingtalk_client_id="",
            dingtalk_client_secret="",
            workbook_id="",
            operator_union_id="",
        )
        client.app.dependency_overrides[get_settings] = lambda: no_creds
        resp = client.get("/api/users/search", params={"keyword": "张三"})
        assert resp.status_code == 503
        assert "钉钉凭证未配置" in resp.json()["detail"]


class TestGetUserDetail:
    """GET /api/users/{user_id} — 获取用户详情。"""

    def test_get_user_detail_success(self, client, setup_standard_mocks, mock_client):
        """验证获取用户详情成功，返回 unionId 等信息。"""
        resp = client.get("/api/users/user_001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["userId"] == "user_001"
        assert data["unionId"] == "union_789"
        assert data["name"] == "张三"
        assert mock_client.get_user_detail.await_count == 1

    def test_get_user_detail_no_creds(self, client):
        """验证完全没有钉钉凭证时返回 503。"""
        from dingding_service.spreadsheet.config import Settings
        from dingding_service.spreadsheet.routes import get_settings

        no_creds = Settings(
            dingtalk_client_id="",
            dingtalk_client_secret="",
            workbook_id="",
            operator_union_id="",
        )
        client.app.dependency_overrides[get_settings] = lambda: no_creds
        resp = client.get("/api/users/user_001")
        assert resp.status_code == 503
        assert "钉钉凭证未配置" in resp.json()["detail"]


class TestSearchDocuments:
    """GET /api/documents/search — 搜索钉钉文档。"""

    def test_search_documents_success(self, client, setup_standard_mocks, mock_client):
        """验证搜索文档成功。"""
        mock_client.search_documents = AsyncMock(
            return_value={
                "dentries": [
                    {
                        "dentryUuid": "wb_test_001",
                        "name": "测试表格",
                        "creatorName": "张三",
                    }
                ]
            }
        )
        resp = client.get(
            "/api/documents/search",
            params={"operator_id": "union_789", "keyword": "测试"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "dentries" in data
        assert data["dentries"][0]["dentryUuid"] == "wb_test_001"
        assert mock_client.search_documents.await_count == 1

    def test_search_documents_missing_operator(self, client, setup_standard_mocks):
        """验证不提供 operator_id 时返回 422。"""
        resp = client.get("/api/documents/search", params={"keyword": "测试"})
        assert resp.status_code == 422

    def test_search_documents_no_creds(self, client):
        """验证完全没有钉钉凭证时返回 503。"""
        from dingding_service.spreadsheet.config import Settings
        from dingding_service.spreadsheet.routes import get_settings

        no_creds = Settings(
            dingtalk_client_id="",
            dingtalk_client_secret="",
            workbook_id="",
            operator_union_id="",
        )
        client.app.dependency_overrides[get_settings] = lambda: no_creds
        resp = client.get(
            "/api/documents/search",
            params={"operator_id": "union_789", "keyword": "测试"},
        )
        assert resp.status_code == 503
        assert "钉钉凭证未配置" in resp.json()["detail"]
