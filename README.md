# FreightAudit.AI - Freight Invoice Audit & Automated Reconciliation System

An enterprise-grade, end-to-end freight invoice audit, contract matching, and discrepancy reconciliation platform. Built to validate freight invoices against contracted carrier rate cards, shipment characteristics, volumetric scanner measurements, accessorial authorizations, and delivery records.

Exposes granular line-level decisions and exceptions, preserves an immutable audit trail, and produces measurable evaluation metrics benchmarked against separate, un-leaked ground truth.

---

## 🌟 Key Highlights & Challenge Compliance

| Requirement | Implementation Details | Status |
| :--- | :--- | :---: |
| **Step 1: Data Dictionary** | Comprehensive documentation for all 11 core entities in [`data_dictionary.md`](file:///c:/Users/Lenovo/Desktop/Assignment/data_dictionary.md) specifying types, nullability, units, allowed values, uniqueness, and validation rules. | ✅ Passed |
| **Step 2: Generation Logic** | Generates master tables first (Carrier, Lane, RateCard, Accessorial), then operational records (Shipment, Leg, WeightMeasurement), then financial transactions (FreightInvoice, InvoiceLine). | ✅ Passed |
| **Step 3: Deterministic IDs** | Zero-padded, immutable naming conventions (`CAR-000001`, `RATE-<carrier>-2026-01`, `SHP-2026-000001`, `FINV-2026-000001`, `FLINE-<inv>-01`, `FEX-2026-000001`, `CN-2026-000001`). | ✅ Passed |
| **Step 4: Baseline Volume & Scale** | Parameterized `--scale starter` (~250 shipments, 200 invoices) and `--scale full` (100 carriers, 20,000 shipments, 15,000 invoices) using fixed seed `20261022`. | ✅ Passed |
| **Step 5: Labelled Edge Cases** | All 5 negative scenarios explicitly injected: (1) Unknown shipment; (2) Expired rate card; (3) Weight tier misapplied; (4) Surcharge duplicated; (5) Credit note exceeds exception amount. | ✅ Passed |
| **Step 6: Derived Calculations** | Volumetric weight `(L*W*H)/5000`, billable weight `max(actual, vol)`, expected freight `base + (weight * rate)`, fuel surcharge, and variance derived mathematically from source records. | ✅ Passed |
| **Step 7: Separate Ground Truth** | Exported to [`data/starter/ground_truth.json`](file:///c:/Users/Lenovo/Desktop/Assignment/data/starter/ground_truth.json) and `.csv` without leaking labels into audit engine inputs. | ✅ Passed |
| **Step 8: Data Validation** | Automated validation suite verifying PK uniqueness, FK referential integrity, allowed enums, date ordering, arithmetic reconciliation, and lifecycle transitions. | ✅ Passed (31/31) |
| **Step 9: Artifact Export** | Exported CSV, JSON, SQLite database (`data/freight_audit.db`), [`source_manifest.json`](file:///c:/Users/Lenovo/Desktop/Assignment/data/source_manifest.json), and [`validation_summary.json`](file:///c:/Users/Lenovo/Desktop/Assignment/data/validation_summary.json). | ✅ Passed |
| **Step 10: Reproducibility** | Double-pass regeneration with fixed seed verified via SHA-256 cryptographic hashes for 100% byte-for-byte reproducibility. | ✅ Passed |
| **Modern UI & UX** | High-fidelity Single-Page Web Dashboard featuring live KPI stat cards, interactive invoice inspector drawer, exception management queue, ground truth confusion matrix, and Step 10 studio. | ✅ Passed |
| **Comprehensive Test Suite** | 21 automated unit, integration, and API tests in `pytest` with 100% pass rate. | ✅ Passed (21/21) |

---

## 🏗️ System Architecture

```
                                  ┌────────────────────────┐
                                  │ Carrier Rate Contracts │
                                  │   (Lanes & Weight)     │
                                  └───────────┬────────────┘
                                              │
┌───────────────────────────┐                 ▼                 ┌───────────────────────────┐
│  Carrier Billed Invoices  │ ────► ┌───────────────────┐ ◄──── │   Warehouse Scanner Dims  │
│  & Line Item Accessorials │       │  Freight Audit    │       │     & Certified Scales    │
└───────────────────────────┘       │      Engine       │       └───────────────────────────┘
                                    └─────────┬─────────┘
                                              │
                      ┌───────────────────────┴───────────────────────┐
                      ▼                                               ▼
         ┌─────────────────────────┐                     ┌─────────────────────────┐
         │  Auto-Approved Invoices │                     │  Disputed Exceptions    │
         │     (Matched Rates)     │                     │     & Credit Notes      │
         └─────────────────────────┘                     └─────────────────────────┘
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.13)
- SQLite3 (standard library)

### 2. Setup & Installation
```powershell
# Clone or navigate to the repository directory
cd c:\Users\Lenovo\Desktop\Assignment

# Optional: Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install required dependencies
pip install -r requirements.txt
```

### 3. Generate the Dataset (Steps 2–9) & Verify Reproducibility (Step 10)
```powershell
# Generate starter dataset and run 2-pass SHA-256 reproducibility check
python generate_dataset.py --scale starter --verify-reproducibility
```
*Expected Output:*
```text
=== Freight Audit Data Generator ===
Seed: 20261022
Scale: starter
Output Directory: data

[1/4] Generating entities (Pass 1)...
  Generated 10 carriers, 20 lanes, 400 rate cards, 250 shipments, 200 invoices, 40 exceptions.
[2/4] Exporting to CSV, JSON, and SQLite database...
  - Source Manifest: data\source_manifest.json
  - Validation Summary: data\validation_summary.json
  - SQLite DB: data\freight_audit.db
[3/4] Data Integrity Validation (Step 8)...
  ✓ ALL VALIDATION CHECKS PASSED (31/31 passed)
[4/4] Step 10: Verifying Reproducibility (Regenerating with identical seed 20261022)...
  Row Counts Match: ✓ SUCCESS
  ✓ ALL SHA256 CHECKSUMS MATCH EXACTLY. 100% REPRODUCIBILITY DEMONSTRATED.
```

To generate the full challenge baseline volume (100 carriers, 20,000 shipments, 15,000 invoices):
```powershell
python generate_dataset.py --scale full
```

### 4. Run the Audit Engine & Benchmark against Ground Truth
```powershell
python run_audit.py
```
*Benchmark Evaluation Output:*
```text
=== AUDIT RESULTS SUMMARY ===
Total Invoices Audited:  200
Passed (Clean):          160 (80.0%)
Failed (Disputed):       40 (20.0%)
Total Billed Amount:     $70,628.65
Total Expected Amount:   $65,475.58
Total Overcharge Found:  $5,153.07

=== CLASSIFICATION BENCHMARK ===
Accuracy:  100.00% (1.0)
Precision: 100.00% (1.0)
Recall:    100.00% (1.0)
F1-Score:  100.00% (1.0)
Confusion Matrix: TP=40, FP=0, TN=160, FN=0
```

### 5. Launch the Web Application (Interactive UI & UX)
```powershell
python app.py
```
Open your web browser and navigate to:
👉 **`http://localhost:5000`**

---

## 🧪 Automated Test Suite

Run the complete test suite covering unit tests, negative scenarios, database integrity, and REST APIs:
```powershell
python -m pytest tests -v
```

### Test Coverage Summary:
- `tests/test_audit_engine.py`:
  - `test_clean_invoice_passes_audit`: Perfect 3-way match auto-approval.
  - `test_edge_case_1_unknown_shipment`: 3-way match failure on orphan invoice.
  - `test_edge_case_2_expired_rate_card`: Out-of-contract billing detection.
  - `test_edge_case_3_weight_tier_misapplied`: Scanner dimensional audit vs billed weight.
  - `test_edge_case_4_duplicate_surcharge`: Double billing of fuel surcharge or accessorials.
  - `test_edge_case_5_credit_note_exceeds_exception`: Flagging credits exceeding dispute caps.
- `tests/test_data_generator.py`:
  - `test_deterministic_id_conventions`: Strict regex format verification across all entities.
  - `test_seed_reproducibility`: Idempotence verification over repeated runs.
  - `test_different_seeds_produce_variation`: Randomized distribution across differing seeds.
- `tests/test_database_validation.py`:
  - `test_validator_passes_all_checks`: Step 8 integrity checks (31/31 passed).
  - `test_primary_key_uniqueness_on_all_tables`: Unique constraints on all 11 tables.
  - `test_arithmetic_invoice_totals_match_lines`: Header total == sum of line items.
  - `test_volumetric_weight_calculation`: `(L*W*H)/5000` volumetric formula.
- `tests/test_evaluation_metrics.py`:
  - Confusion matrix, precision, recall, and F1-score benchmarks.
  - Financial overcharge calculations and carrier scorecard compliance rankings.
- `tests/test_api_endpoints.py`:
  - REST endpoints for KPIs, invoice drawer details, live re-audits, and Step 10 checks.

---

## 📊 Domain Rules & Mathematical Formulas

1. **Dimensional Volumetric Weight Calculation:**
   $$\text{Volumetric Weight (kg)} = \frac{\text{Length (cm)} \times \text{Width (cm)} \times \text{Height (cm)}}{5000}$$

2. **Certified Billable Weight:**
   $$\text{Billable Weight} = \max(\text{Actual Scale Weight}, \text{Volumetric Weight})$$

3. **Contracted Base Freight Calculation:**
   $$\text{Expected Base} = \max\left(\text{Min Charge}, \text{Base Rate} + (\text{Billable Weight} \times \text{Rate per kg})\right)$$

4. **Contracted Fuel Surcharge:**
   $$\text{Expected Fuel} = \text{Expected Base} \times \left(\frac{\text{Fuel Surcharge \%}}{100}\right)$$

5. **Invoice Discrepancy & Variance:**
   $$\text{Variance Amount} = \text{Billed Amount} - \text{Expected Amount}$$
   If $\text{Variance} > \$0.05$, an `AuditException` is raised and the invoice is marked `FAILED / DISPUTED`.

---

## 📁 Repository Directory Structure

```
c:\Users\Lenovo\Desktop\Assignment\
├── app.py                      # Flask Application with REST APIs & Web Server
├── generate_dataset.py         # CLI generator & Step 10 reproducibility runner
├── run_audit.py                # Standalone CLI audit runner & ground truth evaluator
├── data_dictionary.md          # Step 1 comprehensive data dictionary & schema spec
├── schema.sql                  # SQLite DDL schema with PK, FK, & CHECK constraints
├── requirements.txt            # Python dependencies
├── README.md                   # Complete documentation & usage guide
├── static/                     # Modern UI assets
│   ├── css/style.css           # Design system, glassmorphism, dark/light theme
│   └── js/app.js               # SPA state manager, drawer inspector, Chart.js views
├── templates/
│   └── index.html              # Sleek, responsive web application dashboard
├── src/
│   ├── __init__.py
│   ├── models.py               # Data models, dataclasses, and enums
│   ├── generator.py            # Granular synthetic data generator with deterministic IDs
│   ├── auditor.py              # Core Freight Audit Engine & exception detectors
│   ├── validator.py            # Step 8 automated data validation suite
│   ├── metrics.py              # Confusion matrix, Precision/Recall/F1, and Scorecards
│   └── exporter.py             # CSV, JSON, SQLite exporter & SHA-256 hasher
├── data/                       # Generated datasets & reports
│   ├── starter/                # Fast starter dataset (CSV + JSON)
│   │   ├── carriers.csv
│   │   ├── lanes.csv
│   │   ├── rate_cards.csv
│   │   ├── shipments.csv
│   │   ├── weight_measurements.csv
│   │   ├── accessorials.csv
│   │   ├── freight_invoices.csv
│   │   ├── invoice_lines.csv
│   │   ├── audit_exceptions.csv
│   │   ├── credit_notes.csv
│   │   ├── audit_events.csv
│   │   ├── ground_truth.csv
│   │   └── ground_truth.json
│   ├── freight_audit.db        # Relational SQLite database
│   ├── source_manifest.json    # Provenance, fixed seed, timestamp, parameters
│   └── validation_summary.json # Step 8 validation report
└── tests/                      # Automated test suite (pytest)
    ├── __init__.py
    ├── test_audit_engine.py
    ├── test_data_generator.py
    ├── test_database_validation.py
    ├── test_evaluation_metrics.py
    └── test_api_endpoints.py
```

---

## 🎨 Web Dashboard & UI/UX Features

- **Executive KPI Row:** Live spend metrics, audit pass rates, total overcharges detected, and credit note recovery ledger.
- **Audit Workbench:** Filterable invoice table with search, carrier badges, discrepancy amounts, and status pills.
- **Interactive Invoice Inspector Drawer:** Side-by-side comparison of billed vs contract expected charges, 3-way match validation details, certified scale vs volumetric weight calculations, and one-click live re-audit.
- **Active Exception Queue:** Filter by exception type and severity. Action controls to issue credit notes or resolve disputes.
- **Ground Truth Benchmark Studio:** Live confusion matrix card with 100% precision, recall, and F1-score indicators.
- **Step 10 Studio:** Interactive 1-click button to execute two independent generation passes, verify SHA-256 checksums, and download CSV/JSON/SQLite seed files.
- **Data Dictionary Viewer:** Interactive schema documentation built right into the interface.
- **Theme Switcher:** Seamless Dark Mode / Light Mode toggle.

