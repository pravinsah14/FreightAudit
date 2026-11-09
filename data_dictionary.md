# Freight Audit System - Data Dictionary

This document defines the schema, field specifications, data types, nullability, constraints, allowed values, units, uniqueness, and validation rules for all core entities in the Freight Audit & Invoice Reconciliation platform.

---

## 1. Carrier (`carriers`)
*Master table representing freight transportation carriers.*

| Field Name | Type | Required | Allowed Values / Format | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `carrier_id` | VARCHAR(32) | Yes | Regex: `^CAR-\d{6}$` (e.g. `CAR-000001`) | - | Primary Key | Must be deterministic and immutable. |
| `name` | VARCHAR(128) | Yes | Non-empty string | - | Unique | E.g. "Apex Logistics", "Vanguard Freight". |
| `code` | VARCHAR(16) | Yes | Uppercase alphanumeric (e.g. `APEX`, `VNGR`) | - | Unique | Standard SCAC (Standard Carrier Alpha Code). |
| `contact_email`| VARCHAR(128) | Yes | Valid email format | - | No | RFC 5322 compliant email address. |
| `mode` | VARCHAR(32) | Yes | `['FTL', 'LTL', 'INTERMODAL', 'PARCEL', 'AIR']` | - | No | Freight transport mode. |
| `status` | VARCHAR(16) | Yes | `['ACTIVE', 'SUSPENDED', 'INACTIVE']` | - | No | Carrier operational status. |
| `created_at` | TIMESTAMP | Yes | ISO 8601 UTC timestamp | - | No | Must be `<= CURRENT_TIMESTAMP`. |

---

## 2. Lane (`lanes`)
*Master table defining geographical freight transit routes.*

| Field Name | Type | Required | Allowed Values / Format | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `lane_id` | VARCHAR(32) | Yes | Regex: `^LANE-\d{6}$` (e.g. `LANE-000001`) | - | Primary Key | Unique identifier for the origin-destination pair. |
| `origin_city` | VARCHAR(64) | Yes | Non-empty string | - | No | Origin city name. |
| `origin_state`| VARCHAR(2) | Yes | 2-letter US/Regional state code (e.g. `CA`, `IL`) | - | No | Must be valid 2-letter uppercase state code. |
| `origin_zip` | VARCHAR(10) | Yes | 5-digit ZIP or ZIP+4 | - | No | Standard postal code format. |
| `dest_city` | VARCHAR(64) | Yes | Non-empty string | - | No | Destination city name. |
| `dest_state` | VARCHAR(2) | Yes | 2-letter US/Regional state code (e.g. `NY`, `TX`) | - | No | Must be valid 2-letter uppercase state code. |
| `dest_zip` | VARCHAR(10) | Yes | 5-digit ZIP or ZIP+4 | - | No | Standard postal code format. |
| `distance_miles` | DECIMAL(10,2) | Yes | Float > 0 | Miles | No | Must be positive number (`> 0`). |
| `transit_days` | INT | Yes | Integer >= 1 | Days | No | Estimated transit duration in business days. |

---

## 3. RateCard (`rate_cards`)
*Contracted pricing agreements between shipper and carrier by lane, service, and weight tier.*

| Field Name | Type | Required | Allowed Values / Format | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `rate_card_id` | VARCHAR(64) | Yes | `^RATE-CAR-\d{6}-2026-\d{2}$` | - | Primary Key | Deterministic format: `RATE-<carrier-id>-2026-01`. |
| `carrier_id` | VARCHAR(32) | Yes | FK -> `carriers.carrier_id` | - | No | Must exist in `carriers`. |
| `lane_id` | VARCHAR(32) | Yes | FK -> `lanes.lane_id` | - | No | Must exist in `lanes`. |
| `service_level`| VARCHAR(32) | Yes | `['STANDARD', 'EXPRESS', 'EXPEDITED', 'ECONOMY']` | - | No | Contracted service tier. |
| `weight_tier_min`| DECIMAL(10,2)| Yes | Float >= 0.00 | kg | No | Minimum billable weight for tier. |
| `weight_tier_max`| DECIMAL(10,2)| Yes | Float > weight_tier_min | kg | No | Maximum billable weight for tier (`max > min`). |
| `base_rate` | DECIMAL(10,2) | Yes | Float >= 0.00 | USD | No | Flat starting charge for the lane/tier. |
| `rate_per_kg` | DECIMAL(10,4) | Yes | Float >= 0.00 | USD/kg | No | Incremental rate per billable kg. |
| `min_charge` | DECIMAL(10,2) | Yes | Float >= 0.00 | USD | No | Floor price for any shipment on this card. |
| `fuel_surcharge_pct`| DECIMAL(5,2)| Yes | Float 0.00 to 50.00 | % | No | Contracted fuel surcharge percentage. |
| `effective_date`| DATE | Yes | YYYY-MM-DD | - | No | Date rate contract becomes valid. |
| `expiry_date` | DATE | Yes | YYYY-MM-DD | - | No | Date contract expires. Must be `>= effective_date`. |
| `status` | VARCHAR(16) | Yes | `['ACTIVE', 'EXPIRED', 'PENDING']` | - | No | Contract validity status. |

---

## 4. Shipment (`shipments`)
*Physical cargo consignment ordered by shipper and fulfilled by carrier.*

| Field Name | Type | Required | Allowed Values / Format | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `shipment_id` | VARCHAR(32) | Yes | Regex: `^SHP-2026-\d{6}$` | - | Primary Key | Deterministic format: `SHP-2026-000001`. |
| `carrier_id` | VARCHAR(32) | Yes | FK -> `carriers.carrier_id` | - | No | Must reference valid Carrier. |
| `lane_id` | VARCHAR(32) | Yes | FK -> `lanes.lane_id` | - | No | Must reference valid Lane. |
| `service_level`| VARCHAR(32) | Yes | `['STANDARD', 'EXPRESS', 'EXPEDITED', 'ECONOMY']` | - | No | Must match contracted service. |
| `shipment_date`| DATE | Yes | YYYY-MM-DD | - | No | Date shipment dispatched. |
| `delivery_date`| DATE | Optional| YYYY-MM-DD | - | No | If present, must be `>= shipment_date`. |
| `total_pieces` | INT | Yes | Integer >= 1 | Units | No | Count of packages / pallets. |
| `declared_value`| DECIMAL(12,2)| Yes| Float >= 0.00 | USD | No | Value for cargo insurance. |
| `status` | VARCHAR(16) | Yes | `['CREATED', 'IN_TRANSIT', 'DELIVERED', 'CANCELLED']` | - | No | Shipment lifecycle state. |
| `created_at` | TIMESTAMP | Yes | ISO 8601 UTC timestamp | - | No | Must be `<= CURRENT_TIMESTAMP`. |

---

## 5. ShipmentLeg (`shipment_legs`)
*Multi-stop route segments for a shipment.*

| Field Name | Type | Required | Allowed Values / Format | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `leg_id` | VARCHAR(48) | Yes | Regex: `^LEG-SHP-2026-\d{6}-\d{2}$` | - | Primary Key | Format: `LEG-<shipment_id>-01`. |
| `shipment_id` | VARCHAR(32) | Yes | FK -> `shipments.shipment_id` | - | No | Must exist in `shipments`. |
| `leg_sequence` | INT | Yes | 1, 2, 3... | - | No | Sequence index (`>= 1`). |
| `origin` | VARCHAR(64) | Yes | Non-empty string | - | No | Origin facility or hub. |
| `destination` | VARCHAR(64) | Yes | Non-empty string | - | No | Destination facility or hub. |
| `carrier_id` | VARCHAR(32) | Yes | FK -> `carriers.carrier_id` | - | No | Must exist in `carriers`. |
| `pickup_time` | TIMESTAMP | Yes | ISO 8601 UTC timestamp | - | No | Time of pickup for leg. |
| `delivery_time`| TIMESTAMP | Optional| ISO 8601 UTC timestamp | - | No | If present, `>= pickup_time`. |
| `status` | VARCHAR(16) | Yes | `['PENDING', 'IN_TRANSIT', 'COMPLETED']` | - | No | Leg execution status. |

---

## 6. WeightMeasurement (`weight_measurements`)
*Physical and dimensional measurements taken by warehouse scale or carrier scanner.*

| Field Name | Type | Required | Allowed Values / Format | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `measurement_id`| VARCHAR(32)| Yes | Regex: `^WM-2026-\d{6}$` | - | Primary Key | Unique measurement event identifier. |
| `shipment_id` | VARCHAR(32) | Yes | FK -> `shipments.shipment_id` | - | No | Must reference valid Shipment. |
| `actual_weight_kg`| DECIMAL(10,2)| Yes| Float > 0 | kg | No | Scale weight of cargo. |
| `dim_length_cm` | DECIMAL(8,2) | Yes| Float > 0 | cm | No | Cargo outer length. |
| `dim_width_cm` | DECIMAL(8,2) | Yes| Float > 0 | cm | No | Cargo outer width. |
| `dim_height_cm` | DECIMAL(8,2) | Yes| Float > 0 | cm | No | Cargo outer height. |
| `dim_factor` | INT | Yes | Typically 5000 (IATA standard) | cm³/kg| No | Divisor for volumetric weight conversion. |
| `volumetric_weight_kg`| DECIMAL(10,2)| Yes| `(L * W * H) / dim_factor` | kg | No | Derived volumetric weight. |
| `billable_weight_kg` | DECIMAL(10,2)| Yes| `max(actual_weight, volumetric_weight)`| kg | No | Derived billable weight standard. |
| `measured_by` | VARCHAR(32) | Yes | `['WAREHOUSE_SCANNER', 'CARRIER_TERMINAL', 'SUPPLIER_SCALE']` | - | No | Audit party responsible. |
| `measured_at` | TIMESTAMP | Yes | ISO 8601 UTC timestamp | - | No | Recorded timestamp. |

---

## 7. Accessorial (`accessorials`)
*Catalog of standard accessorial/value-added freight services.*

| Field Name | Type | Required | Allowed Values / Format | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `accessorial_id`| VARCHAR(32) | Yes | Regex: `^ACC-\d{6}$` | - | Primary Key | Catalog identifier. |
| `code` | VARCHAR(32) | Yes | `['LIFTGATE', 'RESIDENTIAL', 'DETENTION', 'INSIDE_PICKUP', 'HAZMAT', 'FUEL_SURCHARGE', 'STORAGE']` | - | Unique | Unique accessorial standard code. |
| `description` | VARCHAR(128) | Yes | Non-empty string | - | No | Human readable description. |
| `standard_rate` | DECIMAL(10,2)| Yes| Float >= 0.00 | USD | No | Contracted standard flat rate or unit rate. |
| `rate_type` | VARCHAR(16) | Yes | `['FLAT', 'PERCENTAGE', 'HOURLY', 'PER_PIECE']` | - | No | Rate application logic. |
| `requires_preapproval`| BOOLEAN | Yes | `0` (False) or `1` (True) | - | No | Whether dispatcher authorization is required. |

---

## 8. FreightInvoice (`freight_invoices`)
*Billed invoices submitted by carriers for payment.*

| Field Name | Type | Required | Allowed Values / Format | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `invoice_id` | VARCHAR(32) | Yes | Regex: `^FINV-2026-\d{6}$` | - | Primary Key | Deterministic format: `FINV-2026-000001`. |
| `invoice_number`| VARCHAR(64) | Yes | Carrier assigned invoice number | - | No | Natural key from carrier. |
| `carrier_id` | VARCHAR(32) | Yes | FK -> `carriers.carrier_id` | - | No | Must reference valid Carrier. |
| `shipment_id` | VARCHAR(32) | Yes | FK -> `shipments.shipment_id` (or orphan in edge case) | - | No | Must reference valid Shipment (or flagged as unknown in edge case). |
| `invoice_date` | DATE | Yes | YYYY-MM-DD | - | No | Issue date. Must be `>= shipment.shipment_date`. |
| `due_date` | DATE | Yes | YYYY-MM-DD | - | No | Payment due date. Must be `>= invoice_date`. |
| `currency` | VARCHAR(3) | Yes | `USD` | - | No | ISO currency code. |
| `billed_amount` | DECIMAL(12,2)| Yes| Float >= 0.00 | USD | No | Sum of invoice line amounts (`billed_total`). |
| `expected_amount`| DECIMAL(12,2)| Yes| Float >= 0.00 | USD | No | Derived expected cost based on contract & weights. |
| `variance_amount`| DECIMAL(12,2)| Yes| `billed_amount - expected_amount` | USD | No | Net overcharge (>0) or undercharge (<0). |
| `status` | VARCHAR(24) | Yes | `['RECEIVED', 'PENDING_AUDIT', 'APPROVED', 'DISPUTED', 'PARTIALLY_APPROVED', 'REJECTED', 'PAID']` | - | No | Commercial payment workflow state. |
| `audit_status` | VARCHAR(16) | Yes | `['PENDING', 'PASSED', 'FAILED']` | - | No | Technical audit outcome. |
| `created_at` | TIMESTAMP | Yes | ISO 8601 UTC timestamp | - | No | System record creation timestamp. |

---

## 9. InvoiceLine (`invoice_lines`)
*Itemized charge line items belonging to a freight invoice.*

| Field Name | Type | Required | Allowed Values / Format | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `line_id` | VARCHAR(48) | Yes | Regex: `^FLINE-FINV-2026-\d{6}-\d{2}$` | - | Primary Key | Format: `FLINE-<invoice-id>-01`. |
| `invoice_id` | VARCHAR(32) | Yes | FK -> `freight_invoices.invoice_id` | - | No | Must exist in `freight_invoices`. |
| `line_number` | INT | Yes | 1, 2, 3... | - | No | Sequential position within invoice. |
| `line_type` | VARCHAR(24) | Yes | `['BASE_FREIGHT', 'FUEL_SURCHARGE', 'ACCESSORIAL', 'TAX', 'DISCOUNT']` | - | No | Categorization of billing line. |
| `accessorial_id`| VARCHAR(32) | Optional| FK -> `accessorials.accessorial_id` | - | No | Linked accessorial when `line_type == 'ACCESSORIAL'`. |
| `description` | VARCHAR(128) | Yes | Non-empty string | - | No | Line item description. |
| `quantity` | DECIMAL(10,2)| Yes| Float >= 0.00 | - | No | Units or weight billed. |
| `billed_unit_rate`| DECIMAL(10,4)| Yes| Float >= 0.00 | USD | No | Unit charge applied by carrier. |
| `billed_total` | DECIMAL(12,2)| Yes| `quantity * billed_unit_rate` (or flat) | USD | No | Must equal arithmetic sum of unit * qty. |
| `expected_unit_rate`| DECIMAL(10,4)| Yes| Float >= 0.00 | USD | No | Contracted unit rate according to RateCard. |
| `expected_total`| DECIMAL(12,2)| Yes| Float >= 0.00 | USD | No | Audited expected amount. |
| `variance_amount`| DECIMAL(12,2)| Yes| `billed_total - expected_total` | USD | No | Discrepancy amount. |
| `variance_reason`| VARCHAR(256) | Optional| Text | - | No | Explanation of discrepancy if variance != 0. |

---

## 10. AuditException (`audit_exceptions`)
*Exceptions raised during automated freight audit indicating non-compliance or overcharges.*

| Field Name | Type | Required | Allowed Values / Format | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `exception_id` | VARCHAR(32) | Yes | Regex: `^FEX-2026-\d{6}$` | - | Primary Key | Format: `FEX-2026-000001`. |
| `invoice_id` | VARCHAR(32) | Yes | FK -> `freight_invoices.invoice_id` | - | No | Must exist in `freight_invoices`. |
| `line_id` | VARCHAR(48) | Optional| FK -> `invoice_lines.line_id` | - | No | Linked line item if line-specific. |
| `shipment_id` | VARCHAR(32) | Optional| FK -> `shipments.shipment_id` | - | No | Linked shipment ID if resolved. |
| `carrier_id` | VARCHAR(32) | Yes | FK -> `carriers.carrier_id` | - | No | Responsible carrier. |
| `exception_type`| VARCHAR(32) | Yes | `['UNKNOWN_SHIPMENT', 'EXPIRED_RATE_CARD', 'WEIGHT_TIER_MISAPPLIED', 'DUPLICATE_SURCHARGE', 'DUPLICATE_INVOICE', 'UNAUTHORIZED_ACCESSORIAL', 'BASE_RATE_MISMATCH', 'CREDIT_EXCEEDS_EXCEPTION']` | - | No | Rule violation classification. |
| `severity` | VARCHAR(16) | Yes | `['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']` | - | No | Triage urgency level. |
| `disputed_amount`| DECIMAL(12,2)| Yes| Float > 0.00 | USD | No | Amount in contention. |
| `status` | VARCHAR(24) | Yes | `['OPEN', 'INVESTIGATING', 'APPROVED_FOR_DISPUTE', 'RESOLVED', 'OVERRIDDEN']` | - | No | Exception resolution lifecycle state. |
| `resolution_notes`| TEXT | Optional| Text | - | No | Narrative documenting audit resolution. |
| `assigned_to` | VARCHAR(64) | Optional| Email / Analyst Name | - | No | Logistics analyst assigned. |
| `created_at` | TIMESTAMP | Yes | ISO 8601 UTC timestamp | - | No | Recorded timestamp. |
| `resolved_at` | TIMESTAMP | Optional| ISO 8601 UTC timestamp | - | No | Must be `>= created_at` when present. |

---

## 11. CreditNote (`credit_notes`)
*Recovery credit adjustments issued by carriers or requested by shippers for settled exceptions.*

| Field Name | Type | Required | Allowed Values / Format | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `credit_note_id`| VARCHAR(32) | Yes | Regex: `^CN-2026-\d{6}$` | - | Primary Key | Format: `CN-2026-000001`. |
| `credit_note_number`| VARCHAR(64)| Yes| Alphanumeric string | - | Unique | Carrier reference code. |
| `exception_id` | VARCHAR(32) | Yes | FK -> `audit_exceptions.exception_id` | - | No | Must reference an approved dispute exception. |
| `invoice_id` | VARCHAR(32) | Yes | FK -> `freight_invoices.invoice_id` | - | No | Must reference original invoice. |
| `carrier_id` | VARCHAR(32) | Yes | FK -> `carriers.carrier_id` | - | No | Must match carrier on invoice. |
| `credit_amount` | DECIMAL(12,2)| Yes| Float > 0.00 | USD | No | Credit balance issued. Must reconcile (`credit_amount <= exception.disputed_amount` in valid cases). |
| `reason` | VARCHAR(256) | Yes | Text explanation | - | No | Reason code description. |
| `status` | VARCHAR(16) | Yes | `['DRAFT', 'ISSUED', 'RECONCILED', 'REJECTED']` | - | No | Settlement status. |
| `issue_date` | DATE | Yes | YYYY-MM-DD | - | No | Date issued. Must be `>= invoice.invoice_date`. |
| `created_at` | TIMESTAMP | Yes | ISO 8601 UTC timestamp | - | No | Creation timestamp. |

---

## 12. AuditLifecycleEvent (`audit_lifecycle_events`)
*Immutable event ledger tracking all state changes, evaluations, dispute actions, and overrides.*

| Field Name | Type | Required | Allowed Values / Format | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `event_id` | VARCHAR(48) | Yes | Regex: `^EVT-2026-\d{8}$` | - | Primary Key | Sequential immutable event record ID. |
| `entity_type` | VARCHAR(32) | Yes | `['INVOICE', 'EXCEPTION', 'CREDIT_NOTE', 'SHIPMENT']` | - | No | Entity being updated. |
| `entity_id` | VARCHAR(48) | Yes | Foreign record primary key | - | No | Target entity ID. |
| `event_type` | VARCHAR(32) | Yes | `['STATUS_CHANGE', 'EXCEPTION_RAISED', 'DISPUTE_SUBMITTED', 'CREDIT_ISSUED', 'OVERRIDE_APPLIED']` | - | No | Type of lifecycle action. |
| `previous_state`| VARCHAR(32) | Optional| String | - | No | State prior to event. |
| `new_state` | VARCHAR(32) | Yes | String | - | No | State after event. |
| `actor` | VARCHAR(64) | Yes | `['SYSTEM_AUDITOR', 'LOGISTICS_ANALYST', 'OPERATIONS_MANAGER', 'CARRIER_PORTAL']` | - | No | Identity triggering event. |
| `notes` | TEXT | Optional| Free text | - | No | Audit rationale. |
| `timestamp` | TIMESTAMP | Yes | ISO 8601 UTC timestamp | - | No | Exact time event occurred. |

---

## 13. Entity Cardinality & Relationships

```
Carrier (1) ────< RateCard (N)
Carrier (1) ────< Shipment (N)
Lane (1) ───────< RateCard (N)
Lane (1) ───────< Shipment (N)
Shipment (1) ───< ShipmentLeg (N)
Shipment (1) ───< WeightMeasurement (1..N)
Shipment (1) ───< FreightInvoice (1..N) [or 0..1 in normal flow, N in duplicate anomaly]
FreightInvoice (1) ──< InvoiceLine (N)
FreightInvoice (1) ──< AuditException (0..N)
InvoiceLine (0..1) ──< AuditException (0..N)
AuditException (1) ──< CreditNote (0..1)
Accessorial (1) ─────< InvoiceLine (0..N)
```
