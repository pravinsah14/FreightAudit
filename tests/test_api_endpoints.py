"""
Integration Tests for Flask REST API Endpoints
Verifies that all API routes respond with valid JSON and correct HTTP status codes.
"""

import pytest
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_api_kpis_endpoint(client):
    res = client.get("/api/kpis")
    assert res.status_code == 200
    data = res.get_json()
    assert "total_invoices" in data
    assert "total_billed" in data
    assert "total_overcharge" in data
    assert "pass_rate_pct" in data


def test_api_invoices_endpoint(client):
    res = client.get("/api/invoices")
    assert res.status_code == 200
    data = res.get_json()
    assert "invoices" in data
    assert len(data["invoices"]) > 0

    first_inv = data["invoices"][0]
    inv_id = first_inv["invoice_id"]

    # Test single invoice detail endpoint
    res_detail = client.get(f"/api/invoices/{inv_id}")
    assert res_detail.status_code == 200
    detail_data = res_detail.get_json()
    assert detail_data["invoice_id"] == inv_id
    assert "lines" in detail_data


def test_api_exceptions_endpoint(client):
    res = client.get("/api/exceptions")
    assert res.status_code == 200
    data = res.get_json()
    assert "exceptions" in data


def test_api_ground_truth_metrics_endpoint(client):
    res = client.get("/api/ground-truth/metrics")
    assert res.status_code == 200
    data = res.get_json()
    assert "accuracy" in data
    assert "precision" in data
    assert "recall" in data
    assert "f1_score" in data
    assert "confusion_matrix" in data


def test_api_carrier_scorecards_endpoint(client):
    res = client.get("/api/carriers")
    assert res.status_code == 200
    data = res.get_json()
    assert "scorecards" in data


def test_api_reproducibility_endpoint(client):
    res = client.post("/api/generator/reproducibility", json={"seed": 20261022, "scale": "starter"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["reproducibility_verified"] is True
    assert data["files_compared"] > 0
