"""
Unit Tests for Freight Audit Engine
Verifies detection of all required edge cases and normal scenarios.
"""

import pytest
from src.auditor import FreightAuditor
from src.models import (
    Carrier, Lane, RateCard, Shipment, WeightMeasurement, Accessorial,
    FreightInvoice, InvoiceLine, CreditNote, AuditException, ExceptionType
)


@pytest.fixture
def test_setup():
    carrier = Carrier(
        carrier_id="CAR-000001",
        name="Test Logistics",
        code="TEST",
        contact_email="test@logistics.com",
        mode="FTL",
        status="ACTIVE"
    )
    lane = Lane(
        lane_id="LANE-000001",
        origin_city="Chicago", origin_state="IL", origin_zip="60601",
        dest_city="Dallas", dest_state="TX", dest_zip="75201",
        distance_miles=920.0, transit_days=2
    )
    rate_card = RateCard(
        rate_card_id="RATE-CAR-000001-2026-01",
        carrier_id="CAR-000001",
        lane_id="LANE-000001",
        service_level="STANDARD",
        weight_tier_min=0.0,
        weight_tier_max=1000.0,
        base_rate=100.0,
        rate_per_kg=0.50,
        min_charge=120.0,
        fuel_surcharge_pct=10.0,
        effective_date="2026-01-01",
        expiry_date="2026-12-31",
        status="ACTIVE"
    )
    shipment = Shipment(
        shipment_id="SHP-2026-000001",
        carrier_id="CAR-000001",
        lane_id="LANE-000001",
        service_level="STANDARD",
        shipment_date="2026-04-10",
        delivery_date="2026-04-12",
        total_pieces=5,
        declared_value=2500.0,
        status="DELIVERED"
    )
    # 100x80x50 cm = 400,000 / 5000 = 80kg volumetric; actual is 60kg -> billable is 80kg
    measurement = WeightMeasurement(
        measurement_id="WM-2026-000001",
        shipment_id="SHP-2026-000001",
        actual_weight_kg=60.0,
        dim_length_cm=100.0,
        dim_width_cm=80.0,
        dim_height_cm=50.0,
        dim_factor=5000,
        volumetric_weight_kg=80.0,
        billable_weight_kg=80.0
    )
    accessorial = Accessorial(
        accessorial_id="ACC-000001",
        code="LIFTGATE",
        description="Liftgate Service",
        standard_rate=75.0,
        rate_type="FLAT",
        requires_preapproval=False
    )
    detention_acc = Accessorial(
        accessorial_id="ACC-000004",
        code="DETENTION",
        description="Detention Fee",
        standard_rate=85.0,
        rate_type="HOURLY",
        requires_preapproval=True
    )

    auditor = FreightAuditor(
        carriers={"CAR-000001": carrier},
        lanes={"LANE-000001": lane},
        rate_cards=[rate_card],
        shipments={"SHP-2026-000001": shipment},
        measurements={"SHP-2026-000001": measurement},
        accessorials={
            "ACC-000001": accessorial,
            "ACC-000004": detention_acc
        }
    )

    return {
        "auditor": auditor,
        "carrier": carrier,
        "lane": lane,
        "rate_card": rate_card,
        "shipment": shipment,
        "measurement": measurement
    }


def test_clean_invoice_passes_audit(test_setup):
    """Test that a perfectly matched invoice passes audit with 0 exceptions."""
    auditor = test_setup["auditor"]
    # Expected base: 100.0 + (80 * 0.50) = 140.0. Fuel: 10% = 14.0. Total = 154.0
    lines = [
        InvoiceLine(
            line_id="FLINE-FINV-01-01",
            invoice_id="FINV-2026-000001",
            line_number=1,
            line_type="BASE_FREIGHT",
            accessorial_id=None,
            description="Base Freight",
            quantity=80.0,
            billed_unit_rate=0.50,
            billed_total=140.0
        ),
        InvoiceLine(
            line_id="FLINE-FINV-01-02",
            invoice_id="FINV-2026-000001",
            line_number=2,
            line_type="FUEL_SURCHARGE",
            accessorial_id=None,
            description="Fuel Surcharge (10%)",
            quantity=1.0,
            billed_unit_rate=14.0,
            billed_total=14.0
        )
    ]
    invoice = FreightInvoice(
        invoice_id="FINV-2026-000001",
        invoice_number="INV-100001",
        carrier_id="CAR-000001",
        shipment_id="SHP-2026-000001",
        invoice_date="2026-04-15",
        due_date="2026-05-15",
        billed_amount=154.0,
        lines=lines
    )

    res = auditor.audit_invoice(invoice)
    assert res.passed is True
    assert len(res.exceptions) == 0
    assert res.expected_amount == 154.0
    assert res.variance_amount == 0.0


def test_edge_case_1_unknown_shipment(test_setup):
    """Edge Case 1: Invoice references unknown shipment ID (failed 3-way match)."""
    auditor = test_setup["auditor"]
    lines = [
        InvoiceLine(
            line_id="FLINE-FINV-02-01",
            invoice_id="FINV-2026-000002",
            line_number=1,
            line_type="BASE_FREIGHT",
            accessorial_id=None,
            description="Base Freight",
            quantity=80.0,
            billed_unit_rate=0.50,
            billed_total=140.0
        )
    ]
    invoice = FreightInvoice(
        invoice_id="FINV-2026-000002",
        invoice_number="INV-100002",
        carrier_id="CAR-000001",
        shipment_id="SHP-2026-999999",  # UNKNOWN ID
        invoice_date="2026-04-15",
        due_date="2026-05-15",
        billed_amount=140.0,
        lines=lines
    )

    res = auditor.audit_invoice(invoice)
    assert res.passed is False
    assert len(res.exceptions) == 1
    assert res.exceptions[0].exception_type == ExceptionType.UNKNOWN_SHIPMENT
    assert res.exceptions[0].disputed_amount == 140.0


def test_edge_case_2_expired_rate_card(test_setup):
    """Edge Case 2: Shipment date occurred after rate card expiry date."""
    auditor = test_setup["auditor"]
    # Modify rate card to be expired before shipment date (shipment is 2026-04-10)
    test_setup["rate_card"].expiry_date = "2026-03-31"

    lines = [
        InvoiceLine(
            line_id="FLINE-FINV-03-01",
            invoice_id="FINV-2026-000003",
            line_number=1,
            line_type="BASE_FREIGHT",
            accessorial_id=None,
            description="Base Freight",
            quantity=80.0,
            billed_unit_rate=0.80,
            billed_total=200.0
        )
    ]
    invoice = FreightInvoice(
        invoice_id="FINV-2026-000003",
        invoice_number="INV-100003",
        carrier_id="CAR-000001",
        shipment_id="SHP-2026-000001",
        invoice_date="2026-04-15",
        due_date="2026-05-15",
        billed_amount=200.0,
        lines=lines
    )

    res = auditor.audit_invoice(invoice)
    assert res.passed is False
    assert any(e.exception_type == ExceptionType.EXPIRED_RATE_CARD for e in res.exceptions)


def test_edge_case_3_weight_tier_misapplied(test_setup):
    """Edge Case 3: Billed weight heavily exceeds certified warehouse scanner weight."""
    auditor = test_setup["auditor"]
    # Certified weight is 80kg. Carrier billed 160kg
    lines = [
        InvoiceLine(
            line_id="FLINE-FINV-04-01",
            invoice_id="FINV-2026-000004",
            line_number=1,
            line_type="BASE_FREIGHT",
            accessorial_id=None,
            description="Base Freight (Inflated Weight)",
            quantity=160.0,  # 2x certified weight
            billed_unit_rate=0.50,
            billed_total=180.0
        ),
        InvoiceLine(
            line_id="FLINE-FINV-04-02",
            invoice_id="FINV-2026-000004",
            line_number=2,
            line_type="FUEL_SURCHARGE",
            accessorial_id=None,
            description="Fuel Surcharge",
            quantity=1.0,
            billed_unit_rate=18.0,
            billed_total=18.0
        )
    ]
    invoice = FreightInvoice(
        invoice_id="FINV-2026-000004",
        invoice_number="INV-100004",
        carrier_id="CAR-000001",
        shipment_id="SHP-2026-000001",
        invoice_date="2026-04-15",
        due_date="2026-05-15",
        billed_amount=198.0,
        lines=lines
    )

    res = auditor.audit_invoice(invoice)
    assert res.passed is False
    assert any(e.exception_type == ExceptionType.WEIGHT_TIER_MISAPPLIED for e in res.exceptions)


def test_edge_case_4_duplicate_surcharge(test_setup):
    """Edge Case 4: Duplicate surcharge / fuel line on same invoice."""
    auditor = test_setup["auditor"]
    lines = [
        InvoiceLine(
            line_id="FLINE-FINV-05-01",
            invoice_id="FINV-2026-000005",
            line_number=1,
            line_type="BASE_FREIGHT",
            accessorial_id=None,
            description="Base Freight",
            quantity=80.0,
            billed_unit_rate=0.50,
            billed_total=140.0
        ),
        InvoiceLine(
            line_id="FLINE-FINV-05-02",
            invoice_id="FINV-2026-000005",
            line_number=2,
            line_type="FUEL_SURCHARGE",
            accessorial_id=None,
            description="Contracted Fuel Surcharge (10%)",
            quantity=1.0,
            billed_unit_rate=14.0,
            billed_total=14.0
        ),
        InvoiceLine(
            line_id="FLINE-FINV-05-03",
            invoice_id="FINV-2026-000005",
            line_number=3,
            line_type="FUEL_SURCHARGE",
            accessorial_id=None,
            description="Secondary Fuel Surcharge (Duplicate)",
            quantity=1.0,
            billed_unit_rate=14.0,
            billed_total=14.0
        )
    ]
    invoice = FreightInvoice(
        invoice_id="FINV-2026-000005",
        invoice_number="INV-100005",
        carrier_id="CAR-000001",
        shipment_id="SHP-2026-000001",
        invoice_date="2026-04-15",
        due_date="2026-05-15",
        billed_amount=168.0,
        lines=lines
    )

    res = auditor.audit_invoice(invoice)
    assert res.passed is False
    assert any(e.exception_type == ExceptionType.DUPLICATE_SURCHARGE for e in res.exceptions)


def test_edge_case_5_credit_note_exceeds_exception(test_setup):
    """Edge Case 5: Credit note amount strictly exceeds approved exception dispute amount."""
    auditor = test_setup["auditor"]
    exception = AuditException(
        exception_id="FEX-2026-000099",
        invoice_id="FINV-2026-000001",
        line_id=None,
        shipment_id="SHP-2026-000001",
        carrier_id="CAR-000001",
        exception_type=ExceptionType.BASE_RATE_MISMATCH,
        severity="HIGH",
        disputed_amount=50.00
    )

    # Valid Credit Note ($50.00 <= $50.00)
    valid_cn = CreditNote(
        credit_note_id="CN-2026-000001",
        credit_note_number="CN-CAR-01-01",
        exception_id="FEX-2026-000099",
        invoice_id="FINV-2026-000001",
        carrier_id="CAR-000001",
        credit_amount=50.00,
        reason="Settlement for dispute"
    )
    is_valid, ex = auditor.reconcile_credit_note(valid_cn, exception)
    assert is_valid is True
    assert ex is None

    # Invalid Credit Note ($150.00 > $50.00)
    excessive_cn = CreditNote(
        credit_note_id="CN-2026-000002",
        credit_note_number="CN-CAR-01-02",
        exception_id="FEX-2026-000099",
        invoice_id="FINV-2026-000001",
        carrier_id="CAR-000001",
        credit_amount=150.00,  # Exceeds $50.00
        reason="Erroneous over-credit"
    )
    is_valid, overflow_ex = auditor.reconcile_credit_note(excessive_cn, exception)
    assert is_valid is False
    assert overflow_ex is not None
    assert overflow_ex.exception_type == ExceptionType.CREDIT_EXCEEDS_EXCEPTION
    assert overflow_ex.disputed_amount == 100.00  # $150 - $50
