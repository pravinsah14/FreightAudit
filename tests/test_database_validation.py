"""
Unit Tests for Database Integrity and Data Validation Suite
Verifies primary key uniqueness, foreign key constraints, enum values,
date ordering, and mathematical reconciliation.
"""

import pytest
from src.generator import FreightDataGenerator
from src.validator import DataValidator


@pytest.fixture(scope="module")
def dataset():
    gen = FreightDataGenerator(seed=20261022)
    gen.generate_all(scale="starter")
    return {
        "carriers": gen.carriers,
        "lanes": gen.lanes,
        "rate_cards": gen.rate_cards,
        "shipments": gen.shipments,
        "shipment_legs": gen.shipment_legs,
        "weight_measurements": gen.weight_measurements,
        "accessorials": gen.accessorials,
        "freight_invoices": gen.freight_invoices,
        "invoice_lines": gen.invoice_lines,
        "audit_exceptions": gen.audit_exceptions,
        "credit_notes": gen.credit_notes,
        "lifecycle_events": gen.lifecycle_events,
    }


def test_validator_passes_all_checks(dataset):
    """Step 8: Ensure all automated validation checks pass without errors."""
    validator = DataValidator(dataset)
    report = validator.run_all_validations()

    assert report.passed is True
    assert report.checks_failed == 0
    assert report.checks_passed > 25


def test_primary_key_uniqueness_on_all_tables(dataset):
    """Ensure no duplicate primary keys exist in any generated collection."""
    for entity_name, records, id_attr in [
        ("Carrier", dataset["carriers"], "carrier_id"),
        ("Lane", dataset["lanes"], "lane_id"),
        ("RateCard", dataset["rate_cards"], "rate_card_id"),
        ("Shipment", dataset["shipments"], "shipment_id"),
        ("ShipmentLeg", dataset["shipment_legs"], "leg_id"),
        ("WeightMeasurement", dataset["weight_measurements"], "measurement_id"),
        ("FreightInvoice", dataset["freight_invoices"], "invoice_id"),
        ("InvoiceLine", dataset["invoice_lines"], "line_id"),
        ("AuditException", dataset["audit_exceptions"], "exception_id"),
    ]:
        ids = [getattr(r, id_attr) for r in records]
        assert len(ids) == len(set(ids)), f"Duplicate primary keys detected in {entity_name}"


def test_arithmetic_invoice_totals_match_lines(dataset):
    """Verify that every invoice's billed_amount equals the sum of its itemized line totals."""
    line_map = {}
    for l in dataset["invoice_lines"]:
        line_map[l.invoice_id] = line_map.get(l.invoice_id, 0.0) + l.billed_total

    for inv in dataset["freight_invoices"]:
        expected_sum = round(line_map.get(inv.invoice_id, 0.0), 2)
        assert abs(inv.billed_amount - expected_sum) <= 0.02, (
            f"Invoice {inv.invoice_id} header total (${inv.billed_amount}) != sum of lines (${expected_sum})"
        )


def test_volumetric_weight_calculation(dataset):
    """Verify volumetric weight formula: (L * W * H) / 5000 = volumetric_weight_kg."""
    for wm in dataset["weight_measurements"]:
        expected = round((wm.dim_length_cm * wm.dim_width_cm * wm.dim_height_cm) / wm.dim_factor, 2)
        assert abs(wm.volumetric_weight_kg - expected) <= 0.05
        assert wm.billable_weight_kg == max(wm.actual_weight_kg, wm.volumetric_weight_kg)
