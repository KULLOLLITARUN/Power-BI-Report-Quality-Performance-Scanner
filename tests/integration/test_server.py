"""Integration tests for pbiscan Studio FastAPI backend API."""
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from pbiscan.server import app

client = TestClient(app)


def test_health_endpoint():
    """Test /api/health returns status ok."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "pbiscan-studio"
    assert "version" in data


def test_scan_golden_fixture():
    """Test /api/scan on a valid PBIP test fixture."""
    fixture_path = "tests/golden/test_bidirectional"
    response = client.post("/api/scan", json={"path": fixture_path})
    assert response.status_code == 200
    data = response.json()

    # Check top-level payload structure
    assert data["report_name"] == "test_bidirectional"
    assert "scores" in data
    assert "overall" in data["scores"]
    assert "findings" in data
    assert len(data["findings"]) >= 1
    assert "tables" in data
    assert "relationships" in data
    assert "measures" in data
    assert "pages" in data

    # Verify bidirectional finding
    finding_rules = [f["rule_id"] for f in data["findings"]]
    assert "MODEL_BIDIRECTIONAL" in finding_rules


def test_scan_enterprise_stress_fixture():
    """Test /api/scan on the complex TMDL enterprise stress fixture."""
    fixture_path = "tests/golden/test_enterprise_stress"
    response = client.post("/api/scan", json={"path": fixture_path})
    assert response.status_code == 200
    data = response.json()

    assert data["scores"]["overall"] > 0
    assert len(data["tables"]) == 5
    assert len(data["relationships"]) == 6
    assert len(data["measures"]) == 10

    # Ensure findings contain expected rule IDs
    rule_ids = {f["rule_id"] for f in data["findings"]}
    assert "MODEL_BIDIRECTIONAL" in rule_ids
    assert "MODEL_FACT_TO_FACT" in rule_ids
    assert "DAX_SUSPICIOUS_PATTERN" in rule_ids
    assert "DAX_DUPLICATE_MEASURE" in rule_ids
    assert "DAX_UNUSED_MEASURE" in rule_ids


def test_scan_nonexistent_path():
    """Test /api/scan returns 404 for invalid path."""
    response = client.post("/api/scan", json={"path": "non_existent_folder_xyz_123"})
    assert response.status_code == 404
    assert "does not exist" in response.json()["detail"]


def test_browse_endpoint():
    """Test /api/browse returns directories and pbip candidates."""
    response = client.post("/api/browse", json={"path": "tests/golden"})
    assert response.status_code == 200
    data = response.json()
    assert "current_path" in data
    assert "directories" in data
    assert "pbip_projects" in data
    assert len(data["directories"]) > 0 or len(data["pbip_projects"]) > 0


def test_spa_index_fallback():
    """Test catch-all route serves index.html or fallback."""
    response = client.get("/")
    assert response.status_code == 200

    # Non-API subpaths should also resolve gracefully
    response = client.get("/model-architecture")
    assert response.status_code == 200
