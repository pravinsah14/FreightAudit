#!/usr/bin/env python3
"""
CLI Command to execute the Freight Audit Engine on database or generated invoices.
Evaluates decisions against ground_truth.csv/json and computes metrics.
"""

import argparse
import sys
import os
import json
import sqlite3

from src.auditor import FreightAuditor
from src.metrics import EvaluationMetrics
from src.models import (
    Carrier, Lane, RateCard, Shipment, WeightMeasurement, Accessorial,
    FreightInvoice, InvoiceLine, GroundTruthRecord
)


def load_dataset_from_sqlite(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Carriers
    carriers = {}
    for r in cursor.execute("SELECT * FROM carriers"):
        carriers[r["carrier_id"]] = Carrier(**dict(r))

    # Lanes
    lanes = {}
    for r in cursor.execute("SELECT * FROM lanes"):
        lanes[r["lane_id"]] = Lane(**dict(r))

    # Rate cards
    rate_cards = []
    for r in cursor.execute("SELECT * FROM rate_cards"):
        rate_cards.append(RateCard(**dict(r)))

    # Shipments
    shipments = {}
    for r in cursor.execute("SELECT * FROM shipments"):
        shipments[r["shipment_id"]] = Shipment(**dict(r))

    # Weight Measurements
    measurements = {}
    for r in cursor.execute("SELECT * FROM weight_measurements"):
        measurements[r["shipment_id"]] = WeightMeasurement(**dict(r))

    # Accessorials
    accessorials = {}
    for r in cursor.execute("SELECT * FROM accessorials"):
        accessorials[r["accessorial_id"]] = Accessorial(
            accessorial_id=r["accessorial_id"],
            code=r["code"],
            description=r["description"],
            standard_rate=r["standard_rate"],
            rate_type=r["rate_type"],
            requires_preapproval=bool(r["requires_preapproval"])
        )

    # Invoices & Lines
    invoices = []
    lines_by_inv = {}
    for r in cursor.execute("SELECT * FROM invoice_lines ORDER BY line_number"):
        line = InvoiceLine(**dict(r))
        lines_by_inv.setdefault(line.invoice_id, []).append(line)

    for r in cursor.execute("SELECT * FROM freight_invoices ORDER BY invoice_id"):
        inv_dict = dict(r)
        inv = FreightInvoice(**inv_dict)
        inv.lines = lines_by_inv.get(inv.invoice_id, [])
        invoices.append(inv)

    conn.close()

    return carriers, lanes, rate_cards, shipments, measurements, accessorials, invoices


def main():
    parser = argparse.ArgumentParser(description="Freight Invoice Audit Engine Runner")
    parser.add_argument("--db", type=str, default="data/freight_audit.db", help="Path to SQLite database")
    parser.add_argument("--ground-truth", type=str, default="data/starter/ground_truth.json",
                        help="Path to separate ground truth file")
    parser.add_argument("--tolerance", type=float, default=0.05, help="Tolerance threshold in USD")

    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"Error: Database not found at '{args.db}'. Run 'python generate_dataset.py' first.")
        sys.exit(1)

    print(f"Loading data from database: {args.db}...")
    carriers, lanes, rate_cards, shipments, measurements, accessorials, invoices = load_dataset_from_sqlite(args.db)

    print(f"Loaded {len(carriers)} carriers, {len(lanes)} lanes, {len(rate_cards)} rate cards, "
          f"{len(shipments)} shipments, {len(invoices)} invoices.")

    print("\nExecuting Freight Audit Engine...")
    auditor = FreightAuditor(
        carriers=carriers,
        lanes=lanes,
        rate_cards=rate_cards,
        shipments=shipments,
        measurements=measurements,
        accessorials=accessorials,
        tolerance=args.tolerance
    )

    audit_decisions = {}
    all_audit_exceptions = []
    passed_count = 0
    failed_count = 0
    total_billed = 0.0
    total_expected = 0.0

    for inv in invoices:
        result = auditor.audit_invoice(inv, existing_exceptions_count=len(all_audit_exceptions))
        status = "PASSED" if result.passed else "FAILED"
        audit_decisions[inv.invoice_id] = status
        all_audit_exceptions.extend(result.exceptions)
        total_billed += result.billed_amount
        total_expected += result.expected_amount
        if result.passed:
            passed_count += 1
        else:
            failed_count += 1

    print("\n=== AUDIT RESULTS SUMMARY ===")
    print(f"Total Invoices Audited:  {len(invoices)}")
    print(f"Passed (Clean):          {passed_count} ({passed_count/len(invoices)*100:.1f}%)")
    print(f"Failed (Disputed):       {failed_count} ({failed_count/len(invoices)*100:.1f}%)")
    print(f"Total Billed Amount:     ${total_billed:,.2f}")
    print(f"Total Expected Amount:   ${total_expected:,.2f}")
    print(f"Total Exceptions Raised: {len(all_audit_exceptions)}")
    print(f"Total Overcharge Found:  ${(total_billed - total_expected):,.2f}")

    # Ground Truth Benchmarking
    if os.path.exists(args.ground_truth):
        print(f"\nBenchmarking against Ground Truth: {args.ground_truth}...")
        with open(args.ground_truth, "r", encoding="utf-8") as f:
            gt_data = json.load(f)
            ground_truth = [GroundTruthRecord(**item) for item in gt_data]

        metrics = EvaluationMetrics.compute_classification_metrics(ground_truth, audit_decisions)
        print("\n=== CLASSIFICATION BENCHMARK ===")
        print(f"Accuracy:  {metrics['accuracy_pct']} ({metrics['accuracy']})")
        print(f"Precision: {metrics['precision_pct']} ({metrics['precision']})")
        print(f"Recall:    {metrics['recall_pct']} ({metrics['recall']})")
        print(f"F1-Score:  {metrics['f1_score_pct']} ({metrics['f1_score']})")
        cm = metrics["confusion_matrix"]
        print(f"Confusion Matrix: TP={cm['true_positives']}, FP={cm['false_positives']}, TN={cm['true_negatives']}, FN={cm['false_negatives']}")

    # Carrier compliance scorecards
    print("\n=== CARRIER COMPLIANCE RANKING ===")
    scorecards = EvaluationMetrics.compute_carrier_scorecards(invoices, all_audit_exceptions)
    for s in scorecards[:5]:
        print(f"Carrier {s['carrier_id']}: Compliance {s['compliance_score_pct']}% | Billed ${s['total_billed']:,.2f} | Disputed ${s['total_disputed']:,.2f} | Issue: {s['primary_issue']}")

    print("\nAudit run completed successfully.")


if __name__ == "__main__":
    main()
