"""Tests for the /health endpoint."""

from unittest.mock import AsyncMock


class TestHealthEndpoint:
    """Verify health check behavior under various configurations."""

    def test_health_ok(self, client, mock_settings, mock_client):
        """When workbook_id and operator_union_id are configured, status is 'ok'."""
        from dingding_service.spreadsheet.routes import get_settings, get_client

        async def _override_get_client():
            return mock_client

        app = client.app
        app.dependency_overrides[get_settings] = lambda: mock_settings
        app.dependency_overrides[get_client] = _override_get_client

        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["token_valid"] is True
        assert data["workbook_id"] == "test_workbook_123"

    def test_health_unconfigured(self, client, unconfigured_settings):
        """When workbook_id is empty, status is 'unconfigured'."""
        from dingding_service.spreadsheet.routes import get_settings

        app = client.app
        app.dependency_overrides[get_settings] = lambda: unconfigured_settings

        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "unconfigured"
        assert data["token_valid"] is False
        assert data["workbook_id"] == ""

    def test_health_token_failure(self, client, mock_settings, mock_client):
        """When get_token returns empty, token_valid is False."""
        from dingding_service.spreadsheet.routes import get_settings, get_client

        mock_client.get_token = AsyncMock(return_value="")

        async def _override_get_client():
            return mock_client

        app = client.app
        app.dependency_overrides[get_settings] = lambda: mock_settings
        app.dependency_overrides[get_client] = _override_get_client

        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["token_valid"] is False

    def test_health_returns_response_model(self, client, mock_settings, mock_client):
        """Response matches HealthResponse schema."""
        from dingding_service.spreadsheet.routes import get_settings, get_client

        async def _override_get_client():
            return mock_client

        app = client.app
        app.dependency_overrides[get_settings] = lambda: mock_settings
        app.dependency_overrides[get_client] = _override_get_client

        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert sorted(data.keys()) == ["status", "token_valid", "workbook_id"]
