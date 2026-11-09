#!/usr/bin/env python3
"""
CLI Command for Synthetic Data Generation, Validation & Reproducibility Verification
Complies with Step 9 and Step 10 of challenge requirements.
"""

import argparse
import sys
import os
import json

from src.generator import FreightDataGenerator
from src.exporter import DataExporter
from src.validator import DataValidator


def main():
    parser = argparse.ArgumentParser(description="Freight Audit Synthetic Data Generator")
    parser.add_argument("--seed", type=int, default=20261022, help="Deterministic random seed (default: 20261022)")
    parser.add_argument("--scale", type=str, choices=["starter", "full"], default="starter",
                        help="Data volume scale: 'starter' (fast, ~250 shipments, 200 invoices) or 'full' (100 carriers, 20,000 shipments, 15,000 invoices)")
    parser.add_argument("--output-dir", type=str, default="data", help="Target output directory")
    parser.add_argument("--verify-reproducibility", action="store_true",
                        help="Step 10: Regenerate twice with same seed and compare row counts/checksums")

    args = parser.parse_args()

    print(f"=== Freight Audit Data Generator ===")
    print(f"Seed: {args.seed}")
    print(f"Scale: {args.scale}")
    print(f"Output Directory: {args.output_dir}")

    # Pass 1: Primary Generation
    print(f"\n[1/4] Generating entities (Pass 1)...")
    gen1 = FreightDataGenerator(seed=args.seed)
    data1 = gen1.generate_all(scale=args.scale)
    print(f"  Generated {data1['counts']['carriers']} carriers, {data1['counts']['lanes']} lanes, "
          f"{data1['counts']['rate_cards']} rate cards, {data1['counts']['shipments']} shipments, "
          f"{data1['counts']['freight_invoices']} invoices, {data1['counts']['audit_exceptions']} exceptions.")

    # Exporting
    print(f"\n[2/4] Exporting to CSV, JSON, and SQLite database...")
    exporter = DataExporter(output_dir=args.output_dir)
    export_result = exporter.export_all(
        generator_data={
            "carriers": gen1.carriers,
            "lanes": gen1.lanes,
            "rate_cards": gen1.rate_cards,
            "shipments": gen1.shipments,
            "shipment_legs": gen1.shipment_legs,
            "weight_measurements": gen1.weight_measurements,
            "accessorials": gen1.accessorials,
            "freight_invoices": gen1.freight_invoices,
            "invoice_lines": gen1.invoice_lines,
            "audit_exceptions": gen1.audit_exceptions,
            "credit_notes": gen1.credit_notes,
            "lifecycle_events": gen1.lifecycle_events,
            "ground_truth": gen1.ground_truth,
        },
        seed=args.seed,
        scale=args.scale
    )
    print(f"  Export complete:")
    print(f"  - Source Manifest: {export_result['manifest_path']}")
    print(f"  - Validation Summary: {export_result['validation_summary_path']}")
    print(f"  - SQLite DB: {export_result['database_path']}")

    # Validation
    print(f"\n[3/4] Data Integrity Validation (Step 8)...")
    if export_result["validation_passed"]:
        print("  ✓ ALL VALIDATION CHECKS PASSED (PK uniqueness, FK referential integrity, enums, dates, arithmetic)")
    else:
        print("  ✗ VALIDATION REPORTED WARNINGS OR FAILURES (see validation_summary.json)")

    # Step 10: Reproducibility Verification
    if args.verify_reproducibility:
        print(f"\n[4/4] Step 10: Verifying Reproducibility (Regenerating with identical seed {args.seed})...")
        gen2 = FreightDataGenerator(seed=args.seed)
        data2 = gen2.generate_all(scale=args.scale)
        
        # Compare record counts
        counts_match = (data1['counts'] == data2['counts'])
        print(f"  Row Counts Match: {'✓ SUCCESS' if counts_match else '✗ FAILED'}")
        if not counts_match:
            print(f"  Diff: {data1['counts']} vs {data2['counts']}")
            sys.exit(1)

        # Check export CSV content hashes
        temp_export_dir = os.path.join(args.output_dir, "_reproducibility_test")
        exp2 = DataExporter(output_dir=temp_export_dir)
        res2 = exp2.export_all(
            generator_data={
                "carriers": gen2.carriers,
                "lanes": gen2.lanes,
                "rate_cards": gen2.rate_cards,
                "shipments": gen2.shipments,
                "shipment_legs": gen2.shipment_legs,
                "weight_measurements": gen2.weight_measurements,
                "accessorials": gen2.accessorials,
                "freight_invoices": gen2.freight_invoices,
                "invoice_lines": gen2.invoice_lines,
                "audit_exceptions": gen2.audit_exceptions,
                "credit_notes": gen2.credit_notes,
                "lifecycle_events": gen2.lifecycle_events,
                "ground_truth": gen2.ground_truth,
            },
            seed=args.seed,
            scale=args.scale
        )

        mismatches = []
        for fname, hash1 in export_result["checksums"].items():
            hash2 = res2["checksums"].get(fname)
            if hash1 != hash2:
                mismatches.append((fname, hash1, hash2))

        if not mismatches:
            print("  ✓ ALL SHA256 CHECKSUMS MATCH EXACTLY. 100% REPRODUCIBILITY DEMONSTRATED.")
        else:
            print(f"  ✗ CHECKSUM MISMATCHES DETECTED: {len(mismatches)}")
            for m in mismatches:
                print(f"    - {m[0]}: {m[1]} != {m[2]}")
            sys.exit(1)
        
        # Cleanup temporary test dir
        import shutil
        if os.path.exists(temp_export_dir):
            shutil.rmtree(temp_export_dir, ignore_errors=True)

    print("\nGeneration and verification finished successfully.")


if __name__ == "__main__":
    main()
