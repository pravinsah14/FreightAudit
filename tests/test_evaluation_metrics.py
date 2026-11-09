"""
Unit Tests for Evaluation Metrics & Ground Truth Benchmarking
"""

import pytest
from src.metrics import EvaluationMetrics
from src.models import GroundTruthRecord, FreightInvoice, AuditException


def test_confusion_matrix_and_metrics_calculation():
    ground_truth = [
        GroundTruthRecord("INV-1", "SHP-1", "CAR-1", True, "EXPIRED_RATE_CARD", "FAILED", 100.0, "Expired"),
        GroundTruthRecord("INV-2", "SHP-2", "CAR-1", True, "WEIGHT_TIER_MISAPPLIED", "FAILED", 50.0, "Weight"),
        GroundTruthRecord("INV-3", "SHP-3", "CAR-2", False, "NONE", "PASSED", 0.0, "Clean"),
        GroundTruthRecord("INV-4", "SHP-4", "CAR-2", False, "NONE", "PASSED", 0.0, "Clean")
    ]

    # Perfect prediction
    decisions_perfect = {
        "INV-1": "FAILED",
        "INV-2": "FAILED",
        "INV-3": "PASSED",
        "INV-4": "PASSED"
    }
    metrics = EvaluationMetrics.compute_classification_metrics(ground_truth, decisions_perfect)
    assert metrics["accuracy"] == 1.0
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1_score"] == 1.0
    assert metrics["confusion_matrix"]["true_positives"] == 2
    assert metrics["confusion_matrix"]["true_negatives"] == 2

    # Prediction with 1 false positive
    decisions_imperfect = {
        "INV-1": "FAILED",
        "INV-2": "FAILED",
        "INV-3": "FAILED",  # False positive!
        "INV-4": "PASSED"
    }
    metrics_imp = EvaluationMetrics.compute_classification_metrics(ground_truth, decisions_imperfect)
    assert metrics_imp["confusion_matrix"]["true_positives"] == 2
    assert metrics_imp["confusion_matrix"]["false_positives"] == 1
    assert metrics_imp["confusion_matrix"]["true_negatives"] == 1
    assert metrics_imp["precision"] == round(2 / 3, 4)
    assert metrics_imp["recall"] == 1.0


def test_financial_kpis_and_carrier_scorecards():
    invoices = [
        FreightInvoice("INV-1", "101", "CAR-1", "SHP-1", "2026-01-01", "2026-02-01", billed_amount=500.0, expected_amount=400.0, audit_status="FAILED"),
        FreightInvoice("INV-2", "102", "CAR-1", "SHP-2", "2026-01-02", "2026-02-02", billed_amount=300.0, expected_amount=300.0, audit_status="PASSED"),
    ]
    exceptions = [
        AuditException("EX-1", "INV-1", None, "SHP-1", "CAR-1", "BASE_RATE_MISMATCH", "MEDIUM", disputed_amount=100.0)
    ]

    kpis = EvaluationMetrics.compute_financial_kpis(invoices, exceptions)
    assert kpis["total_billed_amount"] == 800.0
    assert kpis["total_expected_amount"] == 700.0
    assert kpis["total_overcharge_detected"] == 100.0
    assert kpis["pass_rate_pct"] == 50.0

    scorecards = EvaluationMetrics.compute_carrier_scorecards(invoices, exceptions)
    assert len(scorecards) == 1
    assert scorecards[0]["carrier_id"] == "CAR-1"
    assert scorecards[0]["compliance_score_pct"] == 50.0
    assert scorecards[0]["primary_issue"] == "BASE_RATE_MISMATCH"
