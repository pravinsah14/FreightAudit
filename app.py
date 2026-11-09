"""
Freight Audit & Reconciliation Platform - Flask REST API & Application Server
Serves the Interactive Web Dashboard, REST APIs, and Live Audit Workbench.
"""

import os
import json
import sqlite3
import hashlib
from datetime import datetime, timezone
from flask import Flask, jsonify, request, render_template, send_from_directory, abort

from src.auditor import FreightAuditor
from src.metrics import EvaluationMetrics
from src.generator import FreightDataGenerator
from src.exporter import DataExporter
from src.models import (
    Carrier, Lane, RateCard, Shipment, WeightMeasurement, Accessorial,
    FreightInvoice, InvoiceLine, AuditException, CreditNote, GroundTruthRecord,
    AuditLifecycleEvent, ExceptionType
)

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["JSON_SORT_KEYS"] = False

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "freight_audit.db")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def get_db_connection():
    if not os.path.exists(DB_PATH):
        # Auto-initialize starter data if database does not exist
        gen = FreightDataGenerator(seed=20261022)
        gen.generate_all(scale="starter")
        exporter = DataExporter(output_dir=DATA_DIR)
        exporter.export_all({
            "carriers": gen.carriers, "lanes": gen.lanes, "rate_cards": gen.rate_cards,
            "shipments": gen.shipments, "shipment_legs": gen.shipment_legs,
            "weight_measurements": gen.weight_measurements, "accessorials": gen.accessorials,
            "freight_invoices": gen.freight_invoices, "invoice_lines": gen.invoice_lines,
            "audit_exceptions": gen.audit_exceptions, "credit_notes": gen.credit_notes,
            "lifecycle_events": gen.lifecycle_events, "ground_truth": gen.ground_truth
        }, seed=20261022, scale="starter", db_path=DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/kpis", methods=["GET"])
def get_kpis():
    conn = get_db_connection()
    c = conn.cursor()

    total_invoices = c.execute("SELECT COUNT(*) FROM freight_invoices").fetchone()[0]
    passed_invoices = c.execute("SELECT COUNT(*) FROM freight_invoices WHERE audit_status = 'PASSED'").fetchone()[0]
    failed_invoices = c.execute("SELECT COUNT(*) FROM freight_invoices WHERE audit_status = 'FAILED'").fetchone()[0]
    total_billed = c.execute("SELECT COALESCE(SUM(billed_amount), 0.0) FROM freight_invoices").fetchone()[0]
    total_expected = c.execute("SELECT COALESCE(SUM(expected_amount), 0.0) FROM freight_invoices").fetchone()[0]
    total_overcharge = c.execute("SELECT COALESCE(SUM(disputed_amount), 0.0) FROM audit_exceptions").fetchone()[0]
    total_exceptions = c.execute("SELECT COUNT(*) FROM audit_exceptions").fetchone()[0]
    total_credits = c.execute("SELECT COALESCE(SUM(credit_amount), 0.0) FROM credit_notes").fetchone()[0]
    open_exceptions = c.execute("SELECT COUNT(*) FROM audit_exceptions WHERE status = 'OPEN'").fetchone()[0]

    # Breakdown by exception type
    ex_types = {}
    for r in c.execute("SELECT exception_type, COUNT(*), SUM(disputed_amount) FROM audit_exceptions GROUP BY exception_type"):
        ex_types[r[0]] = {
            "count": r[1],
            "total_disputed": round(r[2] or 0.0, 2)
        }

    conn.close()

    pass_rate = (passed_invoices / total_invoices * 100) if total_invoices > 0 else 0.0
    savings_pct = (total_overcharge / total_billed * 100) if total_billed > 0 else 0.0

    return jsonify({
        "total_invoices": total_invoices,
        "passed_invoices": passed_invoices,
        "failed_invoices": failed_invoices,
        "pass_rate_pct": round(pass_rate, 1),
        "total_billed": round(total_billed, 2),
        "total_expected": round(total_expected, 2),
        "total_overcharge": round(total_overcharge, 2),
        "savings_opportunity_pct": round(savings_pct, 1),
        "total_exceptions": total_exceptions,
        "open_exceptions": open_exceptions,
        "total_credit_notes_amount": round(total_credits, 2),
        "exceptions_by_type": ex_types
    })


@app.route("/api/invoices", methods=["GET"])
def get_invoices():
    status = request.args.get("status")
    carrier_id = request.args.get("carrier_id")
    search = request.args.get("search", "").strip().lower()
    limit = int(request.args.get("limit", 100))
    offset = int(request.args.get("offset", 0))

    conn = get_db_connection()
    c = conn.cursor()

    query = """
        SELECT i.*, c.name as carrier_name, c.mode as carrier_mode
        FROM freight_invoices i
        LEFT JOIN carriers c ON i.carrier_id = c.carrier_id
        WHERE 1=1
    """
    params = []

    if status and status != "ALL":
        if status in ["PASSED", "FAILED"]:
            query += " AND i.audit_status = ?"
            params.append(status)
        else:
            query += " AND i.status = ?"
            params.append(status)

    if carrier_id:
        query += " AND i.carrier_id = ?"
        params.append(carrier_id)

    if search:
        query += " AND (LOWER(i.invoice_id) LIKE ? OR LOWER(i.invoice_number) LIKE ? OR LOWER(i.shipment_id) LIKE ? OR LOWER(c.name) LIKE ?)"
        s_param = f"%{search}%"
        params.extend([s_param, s_param, s_param, s_param])

    query += " ORDER BY i.invoice_id ASC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    invoices = []
    for r in c.execute(query, params):
        inv = dict(r)
        invoices.append(inv)

    conn.close()
    return jsonify({"invoices": invoices, "count": len(invoices)})


@app.route("/api/invoices/<invoice_id>", methods=["GET"])
def get_invoice_detail(invoice_id):
    conn = get_db_connection()
    c = conn.cursor()

    # Invoice
    inv_row = c.execute("""
        SELECT i.*, c.name as carrier_name, c.contact_email as carrier_email, c.mode as carrier_mode
        FROM freight_invoices i
        LEFT JOIN carriers c ON i.carrier_id = c.carrier_id
        WHERE i.invoice_id = ?
    """, (invoice_id,)).fetchone()

    if not inv_row:
        conn.close()
        return jsonify({"error": f"Invoice {invoice_id} not found"}), 404

    invoice = dict(inv_row)

    # Lines
    lines = []
    for r in c.execute("SELECT * FROM invoice_lines WHERE invoice_id = ? ORDER BY line_number", (invoice_id,)):
        lines.append(dict(r))
    invoice["lines"] = lines

    # Linked Exceptions
    exceptions = []
    for r in c.execute("SELECT * FROM audit_exceptions WHERE invoice_id = ?", (invoice_id,)):
        exceptions.append(dict(r))
    invoice["exceptions"] = exceptions

    # Linked Shipment & Lane & Weight
    shipment = None
    lane = None
    weight_measurement = None

    if invoice.get("shipment_id"):
        s_row = c.execute("SELECT * FROM shipments WHERE shipment_id = ?", (invoice["shipment_id"],)).fetchone()
        if s_row:
            shipment = dict(s_row)
            l_row = c.execute("SELECT * FROM lanes WHERE lane_id = ?", (shipment["lane_id"],)).fetchone()
            if l_row:
                lane = dict(l_row)
            w_row = c.execute("SELECT * FROM weight_measurements WHERE shipment_id = ?", (shipment["shipment_id"],)).fetchone()
            if w_row:
                weight_measurement = dict(w_row)

    invoice["shipment"] = shipment
    invoice["lane"] = lane
    invoice["weight_measurement"] = weight_measurement

    # Lifecycle events
    events = []
    for r in c.execute("SELECT * FROM audit_lifecycle_events WHERE entity_id = ? ORDER BY timestamp DESC", (invoice_id,)):
        events.append(dict(r))
    invoice["lifecycle_events"] = events

    conn.close()
    return jsonify(invoice)


@app.route("/api/invoices/<invoice_id>/audit", methods=["POST"])
def reaudit_invoice(invoice_id):
    """Triggers an on-demand re-audit of the invoice with live explanations."""
    conn = get_db_connection()
    c = conn.cursor()

    # Load context
    carriers = {r["carrier_id"]: Carrier(**dict(r)) for r in c.execute("SELECT * FROM carriers")}
    lanes = {r["lane_id"]: Lane(**dict(r)) for r in c.execute("SELECT * FROM lanes")}
    rate_cards = [RateCard(**dict(r)) for r in c.execute("SELECT * FROM rate_cards")]
    shipments = {r["shipment_id"]: Shipment(**dict(r)) for r in c.execute("SELECT * FROM shipments")}
    measurements = {r["shipment_id"]: WeightMeasurement(**dict(r)) for r in c.execute("SELECT * FROM weight_measurements")}
    accessorials = {r["accessorial_id"]: Accessorial(
        accessorial_id=r["accessorial_id"], code=r["code"], description=r["description"],
        standard_rate=r["standard_rate"], rate_type=r["rate_type"], requires_preapproval=bool(r["requires_preapproval"])
    ) for r in c.execute("SELECT * FROM accessorials")}

    inv_row = c.execute("SELECT * FROM freight_invoices WHERE invoice_id = ?", (invoice_id,)).fetchone()
    if not inv_row:
        conn.close()
        return jsonify({"error": "Invoice not found"}), 404

    inv = FreightInvoice(**dict(inv_row))
    inv.lines = [InvoiceLine(**dict(r)) for r in c.execute("SELECT * FROM invoice_lines WHERE invoice_id = ? ORDER BY line_number", (invoice_id,))]

    auditor = FreightAuditor(carriers, lanes, rate_cards, shipments, measurements, accessorials)
    result = auditor.audit_invoice(inv)

    # Update database record
    new_audit_status = "PASSED" if result.passed else "FAILED"
    new_status = "APPROVED" if result.passed else "DISPUTED"
    c.execute("""
        UPDATE freight_invoices
        SET expected_amount = ?, variance_amount = ?, status = ?, audit_status = ?
        WHERE invoice_id = ?
    """, (result.expected_amount, result.variance_amount, new_status, new_audit_status, invoice_id))

    # Log lifecycle event
    evt_id = f"EVT-LIVE-{int(datetime.now(timezone.utc).timestamp())}"
    c.execute("""
        INSERT INTO audit_lifecycle_events (event_id, entity_type, entity_id, event_type, previous_state, new_state, actor, notes, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (evt_id, "INVOICE", invoice_id, "LIVE_REAUDIT", inv.audit_status, new_audit_status, "LOGISTICS_ANALYST",
          f"Manual re-audit initiated from UI. Result: {new_audit_status}. Net variance: ${result.variance_amount:.2f}",
          datetime.now(timezone.utc).isoformat()))

    conn.commit()
    conn.close()

    return jsonify(result.to_dict())


@app.route("/api/exceptions", methods=["GET"])
def get_exceptions():
    ex_type = request.args.get("type")
    severity = request.args.get("severity")
    status = request.args.get("status")

    conn = get_db_connection()
    c = conn.cursor()

    query = """
        SELECT e.*, c.name as carrier_name, i.invoice_number, i.billed_amount as invoice_billed
        FROM audit_exceptions e
        LEFT JOIN carriers c ON e.carrier_id = c.carrier_id
        LEFT JOIN freight_invoices i ON e.invoice_id = i.invoice_id
        WHERE 1=1
    """
    params = []

    if ex_type and ex_type != "ALL":
        query += " AND e.exception_type = ?"
        params.append(ex_type)

    if severity and severity != "ALL":
        query += " AND e.severity = ?"
        params.append(severity)

    if status and status != "ALL":
        query += " AND e.status = ?"
        params.append(status)

    query += " ORDER BY e.created_at DESC"

    exceptions = [dict(r) for r in c.execute(query, params)]
    conn.close()

    return jsonify({"exceptions": exceptions, "count": len(exceptions)})


@app.route("/api/exceptions/<exception_id>/resolve", methods=["POST"])
def resolve_exception(exception_id):
    data = request.json or {}
    new_status = data.get("status", "RESOLVED")
    notes = data.get("notes", "Resolved by logistics analyst.")
    actor = data.get("actor", "LOGISTICS_ANALYST")

    conn = get_db_connection()
    c = conn.cursor()

    ex_row = c.execute("SELECT * FROM audit_exceptions WHERE exception_id = ?", (exception_id,)).fetchone()
    if not ex_row:
        conn.close()
        return jsonify({"error": "Exception not found"}), 404

    prev_status = ex_row["status"]
    now_ts = datetime.now(timezone.utc).isoformat()

    c.execute("""
        UPDATE audit_exceptions
        SET status = ?, resolution_notes = ?, resolved_at = ?
        WHERE exception_id = ?
    """, (new_status, notes, now_ts, exception_id))

    # Record event
    evt_id = f"EVT-{int(datetime.now(timezone.utc).timestamp()*1000)}"
    c.execute("""
        INSERT INTO audit_lifecycle_events (event_id, entity_type, entity_id, event_type, previous_state, new_state, actor, notes, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (evt_id, "EXCEPTION", exception_id, "STATUS_CHANGE", prev_status, new_status, actor, notes, now_ts))

    conn.commit()
    conn.close()

    return jsonify({"success": True, "exception_id": exception_id, "status": new_status})


@app.route("/api/exceptions/<exception_id>/credit-note", methods=["POST"])
def create_credit_note_for_exception(exception_id):
    conn = get_db_connection()
    c = conn.cursor()

    ex_row = c.execute("SELECT * FROM audit_exceptions WHERE exception_id = ?", (exception_id,)).fetchone()
    if not ex_row:
        conn.close()
        return jsonify({"error": "Exception not found"}), 404

    ex = dict(ex_row)
    now_ts = datetime.now(timezone.utc).isoformat()
    issue_dt = datetime.now(timezone.utc).date().isoformat()

    # Generate sequential Credit Note ID
    existing_count = c.execute("SELECT COUNT(*) FROM credit_notes").fetchone()[0]
    cn_id = f"CN-2026-{(existing_count + 1):06d}"
    cn_num = f"CN-{ex['carrier_id']}-{(existing_count + 1):04d}"
    credit_amt = ex["disputed_amount"]
    reason = f"Credit adjustment for dispute {ex['exception_type']}: {ex['resolution_notes'] or 'Disputed variance settlement'}"

    c.execute("""
        INSERT INTO credit_notes (credit_note_id, credit_note_number, exception_id, invoice_id, carrier_id, credit_amount, reason, status, issue_date, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (cn_id, cn_num, exception_id, ex["invoice_id"], ex["carrier_id"], credit_amt, reason, "RECONCILED", issue_dt, now_ts))

    # Mark exception resolved
    c.execute("UPDATE audit_exceptions SET status = 'RESOLVED', resolved_at = ? WHERE exception_id = ?", (now_ts, exception_id))

    # Record lifecycle events
    c.execute("""
        INSERT INTO audit_lifecycle_events (event_id, entity_type, entity_id, event_type, previous_state, new_state, actor, notes, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (f"EVT-CN-{cn_id}", "CREDIT_NOTE", cn_id, "CREDIT_ISSUED", "DRAFT", "RECONCILED", "LOGISTICS_ANALYST",
          f"Credit note {cn_num} issued for amount ${credit_amt:.2f}", now_ts))

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "credit_note_id": cn_id,
        "credit_note_number": cn_num,
        "credit_amount": credit_amt,
        "status": "RECONCILED"
    })


@app.route("/api/credit-notes", methods=["GET"])
def get_credit_notes():
    conn = get_db_connection()
    c = conn.cursor()

    query = """
        SELECT cn.*, c.name as carrier_name, e.exception_type, e.disputed_amount
        FROM credit_notes cn
        LEFT JOIN carriers c ON cn.carrier_id = c.carrier_id
        LEFT JOIN audit_exceptions e ON cn.exception_id = e.exception_id
        ORDER BY cn.created_at DESC
    """
    notes = [dict(r) for r in c.execute(query)]
    conn.close()
    return jsonify({"credit_notes": notes, "count": len(notes)})


@app.route("/api/carriers", methods=["GET"])
def get_carriers():
    conn = get_db_connection()
    c = conn.cursor()

    invoices = []
    lines_by_inv = {}
    for r in c.execute("SELECT * FROM invoice_lines"):
        lines_by_inv.setdefault(r["invoice_id"], []).append(InvoiceLine(**dict(r)))

    for r in c.execute("SELECT * FROM freight_invoices"):
        inv = FreightInvoice(**dict(r))
        inv.lines = lines_by_inv.get(inv.invoice_id, [])
        invoices.append(inv)

    exceptions = [AuditException(**dict(r)) for r in c.execute("SELECT * FROM audit_exceptions")]
    scorecards = EvaluationMetrics.compute_carrier_scorecards(invoices, exceptions)

    # Carrier details map
    carrier_details = {r["carrier_id"]: dict(r) for r in c.execute("SELECT * FROM carriers")}
    for sc in scorecards:
        details = carrier_details.get(sc["carrier_id"], {})
        sc["name"] = details.get("name", "Unknown Carrier")
        sc["code"] = details.get("code", "")
        sc["mode"] = details.get("mode", "")

    conn.close()
    return jsonify({"scorecards": scorecards})


@app.route("/api/ground-truth/metrics", methods=["GET"])
def get_ground_truth_metrics():
    gt_path = os.path.join(DATA_DIR, "starter", "ground_truth.json")
    if not os.path.exists(gt_path):
        return jsonify({"error": "Ground truth file not generated yet."}), 404

    with open(gt_path, "r", encoding="utf-8") as f:
        gt_data = json.load(f)
        ground_truth = [GroundTruthRecord(**i) for i in gt_data]

    conn = get_db_connection()
    c = conn.cursor()
    audit_decisions = {r["invoice_id"]: r["audit_status"] for r in c.execute("SELECT invoice_id, audit_status FROM freight_invoices")}
    conn.close()

    metrics = EvaluationMetrics.compute_classification_metrics(ground_truth, audit_decisions)
    return jsonify(metrics)


@app.route("/api/generator/run", methods=["POST"])
def run_generator():
    data = request.json or {}
    seed = int(data.get("seed", 20261022))
    scale = data.get("scale", "starter")

    gen = FreightDataGenerator(seed=seed)
    gen.generate_all(scale=scale)

    exporter = DataExporter(output_dir=DATA_DIR)
    res = exporter.export_all({
        "carriers": gen.carriers, "lanes": gen.lanes, "rate_cards": gen.rate_cards,
        "shipments": gen.shipments, "shipment_legs": gen.shipment_legs,
        "weight_measurements": gen.weight_measurements, "accessorials": gen.accessorials,
        "freight_invoices": gen.freight_invoices, "invoice_lines": gen.invoice_lines,
        "audit_exceptions": gen.audit_exceptions, "credit_notes": gen.credit_notes,
        "lifecycle_events": gen.lifecycle_events, "ground_truth": gen.ground_truth
    }, seed=seed, scale=scale, db_path=DB_PATH)

    return jsonify({
        "success": True,
        "seed": seed,
        "scale": scale,
        "counts": {
            "carriers": len(gen.carriers),
            "shipments": len(gen.shipments),
            "invoices": len(gen.freight_invoices),
            "exceptions": len(gen.audit_exceptions)
        },
        "validation_passed": res["validation_passed"],
        "manifest_path": res["manifest_path"]
    })


@app.route("/api/generator/reproducibility", methods=["POST"])
def test_reproducibility():
    """Step 10: Regenerates twice with same seed and compares cryptographic SHA-256 hashes."""
    data = request.json or {}
    seed = int(data.get("seed", 20261022))
    scale = data.get("scale", "starter")

    # Pass 1
    gen1 = FreightDataGenerator(seed=seed)
    gen1.generate_all(scale=scale)

    temp_dir1 = os.path.join(DATA_DIR, "_repro_1")
    exp1 = DataExporter(output_dir=temp_dir1)
    res1 = exp1.export_all({
        "carriers": gen1.carriers, "lanes": gen1.lanes, "rate_cards": gen1.rate_cards,
        "shipments": gen1.shipments, "shipment_legs": gen1.shipment_legs,
        "weight_measurements": gen1.weight_measurements, "accessorials": gen1.accessorials,
        "freight_invoices": gen1.freight_invoices, "invoice_lines": gen1.invoice_lines,
        "audit_exceptions": gen1.audit_exceptions, "credit_notes": gen1.credit_notes,
        "lifecycle_events": gen1.lifecycle_events, "ground_truth": gen1.ground_truth
    }, seed=seed, scale=scale)

    # Pass 2
    gen2 = FreightDataGenerator(seed=seed)
    gen2.generate_all(scale=scale)

    temp_dir2 = os.path.join(DATA_DIR, "_repro_2")
    exp2 = DataExporter(output_dir=temp_dir2)
    res2 = exp2.export_all({
        "carriers": gen2.carriers, "lanes": gen2.lanes, "rate_cards": gen2.rate_cards,
        "shipments": gen2.shipments, "shipment_legs": gen2.shipment_legs,
        "weight_measurements": gen2.weight_measurements, "accessorials": gen2.accessorials,
        "freight_invoices": gen2.freight_invoices, "invoice_lines": gen2.invoice_lines,
        "audit_exceptions": gen2.audit_exceptions, "credit_notes": gen2.credit_notes,
        "lifecycle_events": gen2.lifecycle_events, "ground_truth": gen2.ground_truth
    }, seed=seed, scale=scale)

    # Compare hashes
    comparison = []
    all_matched = True
    for fname, h1 in res1["checksums"].items():
        h2 = res2["checksums"].get(fname)
        matched = (h1 == h2)
        if not matched:
            all_matched = False
        comparison.append({
            "file": fname,
            "pass_1_hash": h1[:16] + "...",
            "pass_2_hash": h2[:16] + "...",
            "full_hash": h1,
            "matched": matched
        })

    # Cleanup temp dirs
    import shutil
    shutil.rmtree(temp_dir1, ignore_errors=True)
    shutil.rmtree(temp_dir2, ignore_errors=True)

    return jsonify({
        "reproducibility_verified": all_matched,
        "seed": seed,
        "files_compared": len(comparison),
        "comparison": comparison
    })


@app.route("/api/data-dictionary", methods=["GET"])
def get_data_dictionary():
    dict_file = os.path.join(os.path.dirname(__file__), "data_dictionary.md")
    content = ""
    if os.path.exists(dict_file):
        with open(dict_file, "r", encoding="utf-8") as f:
            content = f.read()
    return jsonify({"markdown": content})


@app.route("/api/download/<scale>/<filename>", methods=["GET"])
def download_file(scale, filename):
    folder = os.path.join(DATA_DIR, scale)
    if os.path.exists(os.path.join(folder, filename)):
        return send_from_directory(folder, filename, as_attachment=True)
    elif os.path.exists(os.path.join(DATA_DIR, filename)):
        return send_from_directory(DATA_DIR, filename, as_attachment=True)
    abort(404)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
