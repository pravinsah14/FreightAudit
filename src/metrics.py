"""
Evaluation Metrics & Ground Truth Benchmark Module
Calculates classification metrics (Precision, Recall, F1, Confusion Matrix),
financial discrepancy statistics, and carrier scorecard metrics.
"""

from typing import Dict, List, Any
import math

from src.models import GroundTruthRecord, FreightInvoice, AuditException


class EvaluationMetrics:
    """
    Computes performance benchmarks by comparing Audit Engine decisions
    against independent Ground Truth labels.
    """

    @staticmethod
    def compute_classification_metrics(
        ground_truth: List[GroundTruthRecord],
        audit_decisions: Dict[str, str]  # invoice_id -> "PASSED" or "FAILED"
    ) -> Dict[str, Any]:
        """
        Calculates Confusion Matrix, Precision, Recall, F1, and Accuracy.
        Anomaly (FAILED) is treated as the POSITIVE class.
        Clean (PASSED) is treated as the NEGATIVE class.
        """
        tp = 0  # Ground truth has anomaly AND audit marked FAILED
        fp = 0  # Ground truth was clean BUT audit marked FAILED
        tn = 0  # Ground truth was clean AND audit marked PASSED
        fn = 0  # Ground truth had anomaly BUT audit marked PASSED

        for gt in ground_truth:
            actual_failed = (gt.expected_audit_decision == "FAILED" or gt.has_anomaly)
            predicted_decision = audit_decisions.get(gt.invoice_id, "PASSED")
            predicted_failed = (predicted_decision == "FAILED")

            if actual_failed and predicted_failed:
                tp += 1
            elif not actual_failed and predicted_failed:
                fp += 1
            elif not actual_failed and not predicted_failed:
                tn += 1
            elif actual_failed and not predicted_failed:
                fn += 1

        total = tp + fp + tn + fn
        accuracy = (tp + tn) / total if total > 0 else 0.0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        return {
            "total_evaluated": total,
            "confusion_matrix": {
                "true_positives": tp,
                "false_positives": fp,
                "true_negatives": tn,
                "false_negatives": fn
            },
            "accuracy": round(accuracy, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "accuracy_pct": f"{accuracy * 100:.2f}%",
            "precision_pct": f"{precision * 100:.2f}%",
            "recall_pct": f"{recall * 100:.2f}%",
            "f1_score_pct": f"{f1 * 100:.2f}%"
        }

    @staticmethod
    def compute_financial_kpis(
        invoices: List[FreightInvoice],
        exceptions: List[AuditException]
    ) -> Dict[str, Any]:
        total_billed = sum(i.billed_amount for i in invoices)
        total_expected = sum(i.expected_amount for i in invoices)
        total_overcharge = sum(e.disputed_amount for e in exceptions)
        total_invoices = len(invoices)
        passed_invoices = sum(1 for i in invoices if i.audit_status == "PASSED")
        failed_invoices = sum(1 for i in invoices if i.audit_status == "FAILED")
        
        pass_rate = (passed_invoices / total_invoices * 100) if total_invoices > 0 else 0.0
        savings_pct = (total_overcharge / total_billed * 100) if total_billed > 0 else 0.0

        # Exception type breakdown
        type_counts: Dict[str, int] = {}
        type_amounts: Dict[str, float] = {}
        for ex in exceptions:
            type_counts[ex.exception_type] = type_counts.get(ex.exception_type, 0) + 1
            type_amounts[ex.exception_type] = round(type_amounts.get(ex.exception_type, 0.0) + ex.disputed_amount, 2)

        return {
            "total_invoices": total_invoices,
            "passed_invoices": passed_invoices,
            "failed_invoices": failed_invoices,
            "pass_rate_pct": round(pass_rate, 2),
            "total_billed_amount": round(total_billed, 2),
            "total_expected_amount": round(total_expected, 2),
            "total_overcharge_detected": round(total_overcharge, 2),
            "savings_opportunity_pct": round(savings_pct, 2),
            "exception_type_counts": type_counts,
            "exception_type_amounts": type_amounts
        }

    @staticmethod
    def compute_carrier_scorecards(
        invoices: List[FreightInvoice],
        exceptions: List[AuditException]
    ) -> List[Dict[str, Any]]:
        carrier_stats: Dict[str, Dict[str, Any]] = {}
        
        for inv in invoices:
            cid = inv.carrier_id
            if cid not in carrier_stats:
                carrier_stats[cid] = {
                    "carrier_id": cid,
                    "total_invoices": 0,
                    "clean_invoices": 0,
                    "disputed_invoices": 0,
                    "total_billed": 0.0,
                    "total_disputed": 0.0,
                    "violation_types": {}
                }
            carrier_stats[cid]["total_invoices"] += 1
            carrier_stats[cid]["total_billed"] += inv.billed_amount
            if inv.audit_status == "PASSED":
                carrier_stats[cid]["clean_invoices"] += 1
            else:
                carrier_stats[cid]["disputed_invoices"] += 1

        for ex in exceptions:
            cid = ex.carrier_id
            if cid in carrier_stats:
                carrier_stats[cid]["total_disputed"] += ex.disputed_amount
                vt = ex.exception_type
                carrier_stats[cid]["violation_types"][vt] = carrier_stats[cid]["violation_types"].get(vt, 0) + 1

        scorecards = []
        for cid, stats in carrier_stats.items():
            tot = stats["total_invoices"]
            compliance_rate = (stats["clean_invoices"] / tot * 100) if tot > 0 else 0.0
            
            # Most frequent violation
            v_types = stats["violation_types"]
            primary_issue = max(v_types.keys(), key=lambda k: v_types[k]) if v_types else "NONE"

            scorecards.append({
                "carrier_id": cid,
                "total_invoices": tot,
                "clean_invoices": stats["clean_invoices"],
                "disputed_invoices": stats["disputed_invoices"],
                "compliance_score_pct": round(compliance_rate, 1),
                "total_billed": round(stats["total_billed"], 2),
                "total_disputed": round(stats["total_disputed"], 2),
                "primary_issue": primary_issue
            })

        scorecards.sort(key=lambda s: s["compliance_score_pct"])
        return scorecards
