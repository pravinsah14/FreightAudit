-- Freight Audit System DDL Schema (SQLite Compatible)
-- Compliant with Step 1 and Step 2 Data Modeling Specifications

PRAGMA foreign_keys = ON;

-- 1. Carrier Master Table
CREATE TABLE IF NOT EXISTS carriers (
    carrier_id VARCHAR(32) PRIMARY KEY,
    name VARCHAR(128) NOT NULL UNIQUE,
    code VARCHAR(16) NOT NULL UNIQUE,
    contact_email VARCHAR(128) NOT NULL,
    mode VARCHAR(32) NOT NULL CHECK(mode IN ('FTL', 'LTL', 'INTERMODAL', 'PARCEL', 'AIR')),
    status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE', 'SUSPENDED', 'INACTIVE')),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 2. Lane Master Table
CREATE TABLE IF NOT EXISTS lanes (
    lane_id VARCHAR(32) PRIMARY KEY,
    origin_city VARCHAR(64) NOT NULL,
    origin_state VARCHAR(2) NOT NULL,
    origin_zip VARCHAR(10) NOT NULL,
    dest_city VARCHAR(64) NOT NULL,
    dest_state VARCHAR(2) NOT NULL,
    dest_zip VARCHAR(10) NOT NULL,
    distance_miles DECIMAL(10,2) NOT NULL CHECK(distance_miles > 0),
    transit_days INT NOT NULL DEFAULT 1 CHECK(transit_days >= 1)
);

-- 3. Rate Card Master Table
CREATE TABLE IF NOT EXISTS rate_cards (
    rate_card_id VARCHAR(64) PRIMARY KEY,
    carrier_id VARCHAR(32) NOT NULL,
    lane_id VARCHAR(32) NOT NULL,
    service_level VARCHAR(32) NOT NULL CHECK(service_level IN ('STANDARD', 'EXPRESS', 'EXPEDITED', 'ECONOMY')),
    weight_tier_min DECIMAL(10,2) NOT NULL DEFAULT 0.0,
    weight_tier_max DECIMAL(10,2) NOT NULL,
    base_rate DECIMAL(10,2) NOT NULL CHECK(base_rate >= 0),
    rate_per_kg DECIMAL(10,4) NOT NULL CHECK(rate_per_kg >= 0),
    min_charge DECIMAL(10,2) NOT NULL CHECK(min_charge >= 0),
    fuel_surcharge_pct DECIMAL(5,2) NOT NULL DEFAULT 0.0 CHECK(fuel_surcharge_pct >= 0 AND fuel_surcharge_pct <= 50),
    effective_date DATE NOT NULL,
    expiry_date DATE NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE', 'EXPIRED', 'PENDING')),
    FOREIGN KEY (carrier_id) REFERENCES carriers(carrier_id) ON DELETE CASCADE,
    FOREIGN KEY (lane_id) REFERENCES lanes(lane_id) ON DELETE CASCADE,
    CHECK (expiry_date >= effective_date),
    CHECK (weight_tier_max > weight_tier_min)
);

-- 4. Shipment Transaction Table
CREATE TABLE IF NOT EXISTS shipments (
    shipment_id VARCHAR(32) PRIMARY KEY,
    carrier_id VARCHAR(32) NOT NULL,
    lane_id VARCHAR(32) NOT NULL,
    service_level VARCHAR(32) NOT NULL CHECK(service_level IN ('STANDARD', 'EXPRESS', 'EXPEDITED', 'ECONOMY')),
    shipment_date DATE NOT NULL,
    delivery_date DATE,
    total_pieces INT NOT NULL CHECK(total_pieces >= 1),
    declared_value DECIMAL(12,2) NOT NULL DEFAULT 0.0 CHECK(declared_value >= 0),
    status VARCHAR(16) NOT NULL DEFAULT 'CREATED' CHECK(status IN ('CREATED', 'IN_TRANSIT', 'DELIVERED', 'CANCELLED')),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (carrier_id) REFERENCES carriers(carrier_id),
    FOREIGN KEY (lane_id) REFERENCES lanes(lane_id),
    CHECK (delivery_date IS NULL OR delivery_date >= shipment_date)
);

-- 5. Shipment Legs Table (1:N with Shipments)
CREATE TABLE IF NOT EXISTS shipment_legs (
    leg_id VARCHAR(48) PRIMARY KEY,
    shipment_id VARCHAR(32) NOT NULL,
    leg_sequence INT NOT NULL CHECK(leg_sequence >= 1),
    origin VARCHAR(64) NOT NULL,
    destination VARCHAR(64) NOT NULL,
    carrier_id VARCHAR(32) NOT NULL,
    pickup_time TIMESTAMP NOT NULL,
    delivery_time TIMESTAMP,
    status VARCHAR(16) NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING', 'IN_TRANSIT', 'COMPLETED')),
    FOREIGN KEY (shipment_id) REFERENCES shipments(shipment_id) ON DELETE CASCADE,
    FOREIGN KEY (carrier_id) REFERENCES carriers(carrier_id)
);

-- 6. Weight Measurements Table (1:N with Shipments)
CREATE TABLE IF NOT EXISTS weight_measurements (
    measurement_id VARCHAR(32) PRIMARY KEY,
    shipment_id VARCHAR(32) NOT NULL,
    actual_weight_kg DECIMAL(10,2) NOT NULL CHECK(actual_weight_kg > 0),
    dim_length_cm DECIMAL(8,2) NOT NULL CHECK(dim_length_cm > 0),
    dim_width_cm DECIMAL(8,2) NOT NULL CHECK(dim_width_cm > 0),
    dim_height_cm DECIMAL(8,2) NOT NULL CHECK(dim_height_cm > 0),
    dim_factor INT NOT NULL DEFAULT 5000 CHECK(dim_factor > 0),
    volumetric_weight_kg DECIMAL(10,2) NOT NULL,
    billable_weight_kg DECIMAL(10,2) NOT NULL,
    measured_by VARCHAR(32) NOT NULL CHECK(measured_by IN ('WAREHOUSE_SCANNER', 'CARRIER_TERMINAL', 'SUPPLIER_SCALE')),
    measured_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (shipment_id) REFERENCES shipments(shipment_id) ON DELETE CASCADE
);

-- 7. Accessorial Master Catalog
CREATE TABLE IF NOT EXISTS accessorials (
    accessorial_id VARCHAR(32) PRIMARY KEY,
    code VARCHAR(32) NOT NULL UNIQUE,
    description VARCHAR(128) NOT NULL,
    standard_rate DECIMAL(10,2) NOT NULL CHECK(standard_rate >= 0),
    rate_type VARCHAR(16) NOT NULL CHECK(rate_type IN ('FLAT', 'PERCENTAGE', 'HOURLY', 'PER_PIECE')),
    requires_preapproval BOOLEAN NOT NULL DEFAULT 0
);

-- 8. Freight Invoice Table
CREATE TABLE IF NOT EXISTS freight_invoices (
    invoice_id VARCHAR(32) PRIMARY KEY,
    invoice_number VARCHAR(64) NOT NULL,
    carrier_id VARCHAR(32) NOT NULL,
    shipment_id VARCHAR(32), -- Nullable or orphan in anomaly case
    invoice_date DATE NOT NULL,
    due_date DATE NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    billed_amount DECIMAL(12,2) NOT NULL CHECK(billed_amount >= 0),
    expected_amount DECIMAL(12,2) NOT NULL DEFAULT 0.0 CHECK(expected_amount >= 0),
    variance_amount DECIMAL(12,2) NOT NULL DEFAULT 0.0,
    status VARCHAR(24) NOT NULL DEFAULT 'RECEIVED' CHECK(status IN ('RECEIVED', 'PENDING_AUDIT', 'APPROVED', 'DISPUTED', 'PARTIALLY_APPROVED', 'REJECTED', 'PAID')),
    audit_status VARCHAR(16) NOT NULL DEFAULT 'PENDING' CHECK(audit_status IN ('PENDING', 'PASSED', 'FAILED')),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (carrier_id) REFERENCES carriers(carrier_id),
    CHECK (due_date >= invoice_date)
);

-- 9. Invoice Lines Table (1:N with Freight Invoices)
CREATE TABLE IF NOT EXISTS invoice_lines (
    line_id VARCHAR(48) PRIMARY KEY,
    invoice_id VARCHAR(32) NOT NULL,
    line_number INT NOT NULL CHECK(line_number >= 1),
    line_type VARCHAR(24) NOT NULL CHECK(line_type IN ('BASE_FREIGHT', 'FUEL_SURCHARGE', 'ACCESSORIAL', 'TAX', 'DISCOUNT')),
    accessorial_id VARCHAR(32),
    description VARCHAR(128) NOT NULL,
    quantity DECIMAL(10,2) NOT NULL DEFAULT 1.0 CHECK(quantity >= 0),
    billed_unit_rate DECIMAL(10,4) NOT NULL CHECK(billed_unit_rate >= 0),
    billed_total DECIMAL(12,2) NOT NULL,
    expected_unit_rate DECIMAL(10,4) NOT NULL DEFAULT 0.0 CHECK(expected_unit_rate >= 0),
    expected_total DECIMAL(12,2) NOT NULL DEFAULT 0.0,
    variance_amount DECIMAL(12,2) NOT NULL DEFAULT 0.0,
    variance_reason VARCHAR(256),
    FOREIGN KEY (invoice_id) REFERENCES freight_invoices(invoice_id) ON DELETE CASCADE,
    FOREIGN KEY (accessorial_id) REFERENCES accessorials(accessorial_id)
);

-- 10. Audit Exceptions Table
CREATE TABLE IF NOT EXISTS audit_exceptions (
    exception_id VARCHAR(32) PRIMARY KEY,
    invoice_id VARCHAR(32) NOT NULL,
    line_id VARCHAR(48),
    shipment_id VARCHAR(32),
    carrier_id VARCHAR(32) NOT NULL,
    exception_type VARCHAR(32) NOT NULL CHECK(exception_type IN (
        'UNKNOWN_SHIPMENT',
        'EXPIRED_RATE_CARD',
        'WEIGHT_TIER_MISAPPLIED',
        'DUPLICATE_SURCHARGE',
        'DUPLICATE_INVOICE',
        'UNAUTHORIZED_ACCESSORIAL',
        'BASE_RATE_MISMATCH',
        'CREDIT_EXCEEDS_EXCEPTION'
    )),
    severity VARCHAR(16) NOT NULL CHECK(severity IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')),
    disputed_amount DECIMAL(12,2) NOT NULL CHECK(disputed_amount >= 0),
    status VARCHAR(24) NOT NULL DEFAULT 'OPEN' CHECK(status IN ('OPEN', 'INVESTIGATING', 'APPROVED_FOR_DISPUTE', 'RESOLVED', 'OVERRIDDEN')),
    resolution_notes TEXT,
    assigned_to VARCHAR(64),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    FOREIGN KEY (invoice_id) REFERENCES freight_invoices(invoice_id) ON DELETE CASCADE,
    FOREIGN KEY (line_id) REFERENCES invoice_lines(line_id),
    FOREIGN KEY (carrier_id) REFERENCES carriers(carrier_id)
);

-- 11. Credit Notes Table
CREATE TABLE IF NOT EXISTS credit_notes (
    credit_note_id VARCHAR(32) PRIMARY KEY,
    credit_note_number VARCHAR(64) NOT NULL UNIQUE,
    exception_id VARCHAR(32) NOT NULL,
    invoice_id VARCHAR(32) NOT NULL,
    carrier_id VARCHAR(32) NOT NULL,
    credit_amount DECIMAL(12,2) NOT NULL CHECK(credit_amount > 0),
    reason VARCHAR(256) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'ISSUED' CHECK(status IN ('DRAFT', 'ISSUED', 'RECONCILED', 'REJECTED')),
    issue_date DATE NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (exception_id) REFERENCES audit_exceptions(exception_id),
    FOREIGN KEY (invoice_id) REFERENCES freight_invoices(invoice_id),
    FOREIGN KEY (carrier_id) REFERENCES carriers(carrier_id)
);

-- 12. Audit Lifecycle Event History Table (Immutable Ledger)
CREATE TABLE IF NOT EXISTS audit_lifecycle_events (
    event_id VARCHAR(48) PRIMARY KEY,
    entity_type VARCHAR(32) NOT NULL CHECK(entity_type IN ('INVOICE', 'EXCEPTION', 'CREDIT_NOTE', 'SHIPMENT')),
    entity_id VARCHAR(48) NOT NULL,
    event_type VARCHAR(32) NOT NULL,
    previous_state VARCHAR(32),
    new_state VARCHAR(32) NOT NULL,
    actor VARCHAR(64) NOT NULL,
    notes TEXT,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for Query Performance and Relational Joins
CREATE INDEX IF NOT EXISTS idx_rate_cards_carrier_lane ON rate_cards(carrier_id, lane_id);
CREATE INDEX IF NOT EXISTS idx_shipments_carrier ON shipments(carrier_id);
CREATE INDEX IF NOT EXISTS idx_shipments_lane ON shipments(lane_id);
CREATE INDEX IF NOT EXISTS idx_weight_meas_shipment ON weight_measurements(shipment_id);
CREATE INDEX IF NOT EXISTS idx_invoices_carrier ON freight_invoices(carrier_id);
CREATE INDEX IF NOT EXISTS idx_invoices_shipment ON freight_invoices(shipment_id);
CREATE INDEX IF NOT EXISTS idx_lines_invoice ON invoice_lines(invoice_id);
CREATE INDEX IF NOT EXISTS idx_exceptions_invoice ON audit_exceptions(invoice_id);
CREATE INDEX IF NOT EXISTS idx_exceptions_status ON audit_exceptions(status);
CREATE INDEX IF NOT EXISTS idx_credit_notes_exception ON credit_notes(exception_id);
CREATE INDEX IF NOT EXISTS idx_lifecycle_entity ON audit_lifecycle_events(entity_type, entity_id);
