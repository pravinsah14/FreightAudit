"""
Data Exporter Module for Freight Audit System
Exports generated and audited records to CSV, JSON, and SQLite database.
Generates source_manifest.json and validation_summary.json.
"""

import os
import csv
import json
import sqlite3
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Any

from src.models import (
    Carrier, Lane, RateCard, Shipment, ShipmentLeg, WeightMeasurement,
    Accessorial, FreightInvoice, InvoiceLine, AuditException, CreditNote,
    AuditLifecycleEvent, GroundTruthRecord
)
from src.validator import DataValidator


class DataExporter:
    """
    Exports structured freight datasets to disk in standard interchange formats.
    """

    def __init__(self, output_dir: str = "data"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def export_all(self, generator_data: Dict[str, Any], seed: int, scale: str, db_path: str = None) -> Dict[str, Any]:
        """
        Executes full export pipeline: CSV, JSON, SQLite, manifest, validation.
        """
        export_sub_dir = os.path.join(self.output_dir, scale)
        os.makedirs(export_sub_dir, exist_ok=True)

        # 1. Export CSV Files
        csv_files = self._export_csv_files(generator_data, export_sub_dir)

        # 2. Export JSON Files
        json_files = self._export_json_files(generator_data, export_sub_dir)

        # 3. Export to SQLite
        if not db_path:
            db_path = os.path.join(self.output_dir, "freight_audit.db")
        self._populate_sqlite_db(generator_data, db_path)

        # 4. Run Step 8 Validation & Export validation_summary.json
        validator = DataValidator(generator_data)
        validation_report = validator.run_all_validations()
        val_summary_path = os.path.join(self.output_dir, "validation_summary.json")
        with open(val_summary_path, "w", encoding="utf-8") as f:
            json.dump(validation_report.to_dict(), f, indent=2)

        # 5. Compute SHA256 Checksums of exported CSV files for Step 10 reproducibility
        checksums = {}
        for fname, fpath in csv_files.items():
            checksums[fname] = self.compute_file_sha256(fpath)

        # 6. Generate source_manifest.json
        manifest = {
            "title": "Freight Invoice Audit & Reconciliation Dataset Manifest",
            "generator_command": f"python generate_dataset.py --seed {seed} --scale {scale}",
            "fixed_seed": seed,
            "scale": scale,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "counts": {
                "carriers": len(generator_data.get("carriers", [])),
                "lanes": len(generator_data.get("lanes", [])),
                "rate_cards": len(generator_data.get("rate_cards", [])),
                "shipments": len(generator_data.get("shipments", [])),
                "shipment_legs": len(generator_data.get("shipment_legs", [])),
                "weight_measurements": len(generator_data.get("weight_measurements", [])),
                "accessorials": len(generator_data.get("accessorials", [])),
                "freight_invoices": len(generator_data.get("freight_invoices", [])),
                "invoice_lines": len(generator_data.get("invoice_lines", [])),
                "audit_exceptions": len(generator_data.get("audit_exceptions", [])),
                "credit_notes": len(generator_data.get("credit_notes", [])),
                "lifecycle_events": len(generator_data.get("lifecycle_events", [])),
                "ground_truth": len(generator_data.get("ground_truth", [])),
            },
            "csv_checksums_sha256": checksums,
            "validation": {
                "overall_passed": validation_report.passed,
                "total_checks": validation_report.checks_run,
                "passed_checks": validation_report.checks_passed
            }
        }

        manifest_path = os.path.join(self.output_dir, "source_manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        return {
            "manifest_path": manifest_path,
            "validation_summary_path": val_summary_path,
            "database_path": db_path,
            "csv_files": csv_files,
            "checksums": checksums,
            "validation_passed": validation_report.passed
        }

    @staticmethod
    def compute_file_sha256(filepath: str) -> str:
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _export_csv_files(self, data: Dict[str, Any], target_dir: str) -> Dict[str, str]:
        files = {}
        
        mapping = [
            ("carriers.csv", data.get("carriers", [])),
            ("lanes.csv", data.get("lanes", [])),
            ("rate_cards.csv", data.get("rate_cards", [])),
            ("shipments.csv", data.get("shipments", [])),
            ("shipment_legs.csv", data.get("shipment_legs", [])),
            ("weight_measurements.csv", data.get("weight_measurements", [])),
            ("accessorials.csv", data.get("accessorials", [])),
            ("freight_invoices.csv", data.get("freight_invoices", [])),
            ("invoice_lines.csv", data.get("invoice_lines", [])),
            ("audit_exceptions.csv", data.get("audit_exceptions", [])),
            ("credit_notes.csv", data.get("credit_notes", [])),
            ("audit_events.csv", data.get("lifecycle_events", [])),
            ("ground_truth.csv", data.get("ground_truth", [])),
        ]

        for fname, items in mapping:
            fpath = os.path.join(target_dir, fname)
            if items:
                # Convert first item to dict to extract fieldnames
                sample_dict = items[0].to_dict() if hasattr(items[0], "to_dict") else dict(items[0])
                # Remove nested lines if invoice
                fieldnames = [k for k in sample_dict.keys() if k != "lines"]
                
                with open(fpath, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    for item in items:
                        d = item.to_dict() if hasattr(item, "to_dict") else dict(item)
                        row = {k: d[k] for k in fieldnames}
                        writer.writerow(row)
            else:
                with open(fpath, "w", newline="", encoding="utf-8") as f:
                    f.write("")
            
            files[fname] = fpath

        return files

    def _export_json_files(self, data: Dict[str, Any], target_dir: str) -> Dict[str, str]:
        files = {}
        
        mapping = [
            ("ground_truth.json", data.get("ground_truth", [])),
            ("freight_invoices.json", data.get("freight_invoices", [])),
            ("rate_cards.json", data.get("rate_cards", [])),
            ("audit_exceptions.json", data.get("audit_exceptions", []))
        ]

        for fname, items in mapping:
            fpath = os.path.join(target_dir, fname)
            dict_items = [i.to_dict() if hasattr(i, "to_dict") else i for i in items]
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(dict_items, f, indent=2)
            files[fname] = fpath

        return files

    def _populate_sqlite_db(self, data: Dict[str, Any], db_path: str):
        schema_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "schema.sql")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Execute DDL schema
        if os.path.exists(schema_path):
            with open(schema_path, "r", encoding="utf-8") as f:
                cursor.executescript(f.read())

        # Clear existing rows to avoid duplicate inserts on re-generation
        tables = [
            "audit_lifecycle_events", "credit_notes", "audit_exceptions",
            "invoice_lines", "freight_invoices", "weight_measurements",
            "shipment_legs", "shipments", "rate_cards", "lanes", "accessorials", "carriers"
        ]
        for t in tables:
            cursor.execute(f"DELETE FROM {t}")

        # Insert Carriers
        for c in data.get("carriers", []):
            cursor.execute(
                "INSERT INTO carriers (carrier_id, name, code, contact_email, mode, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (c.carrier_id, c.name, c.code, c.contact_email, c.mode, c.status, c.created_at)
            )

        # Insert Lanes
        for l in data.get("lanes", []):
            cursor.execute(
                "INSERT INTO lanes (lane_id, origin_city, origin_state, origin_zip, dest_city, dest_state, dest_zip, distance_miles, transit_days) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (l.lane_id, l.origin_city, l.origin_state, l.origin_zip, l.dest_city, l.dest_state, l.dest_zip, l.distance_miles, l.transit_days)
            )

        # Insert Accessorials
        for a in data.get("accessorials", []):
            cursor.execute(
                "INSERT INTO accessorials (accessorial_id, code, description, standard_rate, rate_type, requires_preapproval) VALUES (?, ?, ?, ?, ?, ?)",
                (a.accessorial_id, a.code, a.description, a.standard_rate, a.rate_type, 1 if a.requires_preapproval else 0)
            )

        # Insert RateCards
        for rc in data.get("rate_cards", []):
            cursor.execute(
                "INSERT INTO rate_cards (rate_card_id, carrier_id, lane_id, service_level, weight_tier_min, weight_tier_max, base_rate, rate_per_kg, min_charge, fuel_surcharge_pct, effective_date, expiry_date, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (rc.rate_card_id, rc.carrier_id, rc.lane_id, rc.service_level, rc.weight_tier_min, rc.weight_tier_max, rc.base_rate, rc.rate_per_kg, rc.min_charge, rc.fuel_surcharge_pct, rc.effective_date, rc.expiry_date, rc.status)
            )

        # Insert Shipments
        for s in data.get("shipments", []):
            cursor.execute(
                "INSERT INTO shipments (shipment_id, carrier_id, lane_id, service_level, shipment_date, delivery_date, total_pieces, declared_value, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (s.shipment_id, s.carrier_id, s.lane_id, s.service_level, s.shipment_date, s.delivery_date, s.total_pieces, s.declared_value, s.status, s.created_at)
            )

        # Insert ShipmentLegs
        for sl in data.get("shipment_legs", []):
            cursor.execute(
                "INSERT INTO shipment_legs (leg_id, shipment_id, leg_sequence, origin, destination, carrier_id, pickup_time, delivery_time, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (sl.leg_id, sl.shipment_id, sl.leg_sequence, sl.origin, sl.destination, sl.carrier_id, sl.pickup_time, sl.delivery_time, sl.status)
            )

        # Insert WeightMeasurements
        for wm in data.get("weight_measurements", []):
            cursor.execute(
                "INSERT INTO weight_measurements (measurement_id, shipment_id, actual_weight_kg, dim_length_cm, dim_width_cm, dim_height_cm, dim_factor, volumetric_weight_kg, billable_weight_kg, measured_by, measured_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (wm.measurement_id, wm.shipment_id, wm.actual_weight_kg, wm.dim_length_cm, wm.dim_width_cm, wm.dim_height_cm, wm.dim_factor, wm.volumetric_weight_kg, wm.billable_weight_kg, wm.measured_by, wm.measured_at)
            )

        # Insert FreightInvoices
        for inv in data.get("freight_invoices", []):
            cursor.execute(
                "INSERT INTO freight_invoices (invoice_id, invoice_number, carrier_id, shipment_id, invoice_date, due_date, currency, billed_amount, expected_amount, variance_amount, status, audit_status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (inv.invoice_id, inv.invoice_number, inv.carrier_id, inv.shipment_id, inv.invoice_date, inv.due_date, inv.currency, inv.billed_amount, inv.expected_amount, inv.variance_amount, inv.status, inv.audit_status, inv.created_at)
            )

        # Insert InvoiceLines
        for line in data.get("invoice_lines", []):
            cursor.execute(
                "INSERT INTO invoice_lines (line_id, invoice_id, line_number, line_type, accessorial_id, description, quantity, billed_unit_rate, billed_total, expected_unit_rate, expected_total, variance_amount, variance_reason) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (line.line_id, line.invoice_id, line.line_number, line.line_type, line.accessorial_id, line.description, line.quantity, line.billed_unit_rate, line.billed_total, line.expected_unit_rate, line.expected_total, line.variance_amount, line.variance_reason)
            )

        # Insert AuditExceptions
        for ex in data.get("audit_exceptions", []):
            cursor.execute(
                "INSERT INTO audit_exceptions (exception_id, invoice_id, line_id, shipment_id, carrier_id, exception_type, severity, disputed_amount, status, resolution_notes, assigned_to, created_at, resolved_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (ex.exception_id, ex.invoice_id, ex.line_id, ex.shipment_id, ex.carrier_id, ex.exception_type, ex.severity, ex.disputed_amount, ex.status, ex.resolution_notes, ex.assigned_to, ex.created_at, ex.resolved_at)
            )

        # Insert CreditNotes
        for cn in data.get("credit_notes", []):
            cursor.execute(
                "INSERT INTO credit_notes (credit_note_id, credit_note_number, exception_id, invoice_id, carrier_id, credit_amount, reason, status, issue_date, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (cn.credit_note_id, cn.credit_note_number, cn.exception_id, cn.invoice_id, cn.carrier_id, cn.credit_amount, cn.reason, cn.status, cn.issue_date, cn.created_at)
            )

        # Insert Lifecycle Events
        for ev in data.get("lifecycle_events", []):
            cursor.execute(
                "INSERT INTO audit_lifecycle_events (event_id, entity_type, entity_id, event_type, previous_state, new_state, actor, notes, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (ev.event_id, ev.entity_type, ev.entity_id, ev.event_type, ev.previous_state, ev.new_state, ev.actor, ev.notes, ev.timestamp)
            )

        conn.commit()
        conn.close()
