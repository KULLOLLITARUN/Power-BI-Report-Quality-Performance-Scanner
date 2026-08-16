"""Unit and integration tests for pbiscan Studio FastAPI server endpoints."""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from pbiscan.server import app

GOLDEN_DIR = Path(__file__).parent.parent / "golden"


class TestStudioServerApi:
    """Test suite for FastAPI backend endpoints."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_health_check(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "pbiscan-studio"
        assert data["version"] == "1.4.0"

    def test_scan_project_golden_fixture(self, client):
        fixture_path = str(GOLDEN_DIR / "test_calc_group_variants")
        response = client.post("/api/scan", json={"path": fixture_path})
        assert response.status_code == 200
        data = response.json()

        assert "scores" in data
        assert "findings" in data
        assert "tables" in data
        assert "relationships" in data
        assert "measures" in data
        assert "pages" in data
        assert "semantic_references" in data
        assert "dax_graph" in data

        # Check semantic reference payload
        sem_refs = data["semantic_references"]
        assert sem_refs["total_count"] >= 1
        assert "ActualSales" in sem_refs["active_roots"]

        # Check DAX graph DAG payload
        dax_graph = data["dax_graph"]
        assert "nodes" in dax_graph
        assert "edges" in dax_graph
        assert "has_cycles" in dax_graph

    def test_scan_nonexistent_path_returns_404(self, client):
        response = client.post("/api/scan", json={"path": "non_existent_folder_12345"})
        assert response.status_code == 404
        assert "Path does not exist" in response.json()["detail"]

    def test_browse_filesystem(self, client):
        response = client.post("/api/browse", json={"path": str(GOLDEN_DIR)})
        assert response.status_code == 200
        data = response.json()
        assert "current_path" in data
        assert "pbip_projects" in data
        assert len(data["pbip_projects"]) >= 1
