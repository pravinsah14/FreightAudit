"""
Unit Tests for Synthetic Data Generator
Verifies deterministic ID formats, seed reproducibility, and entity generation.
"""

import re
import pytest
from src.generator import FreightDataGenerator


def test_deterministic_id_conventions():
    """Verify that all generated entities adhere strictly to the challenge naming conventions."""
    gen = FreightDataGenerator(seed=20261022)
    gen.generate_all(scale="starter")

    carrier_regex = re.compile(r"^CAR-\d{6}$")
    rate_card_regex = re.compile(r"^RATE-CAR-\d{6}-2026-\d{2,4}$")
    shipment_regex = re.compile(r"^SHP-2026-\d{6}$")
    invoice_regex = re.compile(r"^FINV-2026-\d{6}$")
    line_regex = re.compile(r"^FLINE-FINV-2026-\d{6}-\d{2}$")
    exception_regex = re.compile(r"^FEX-2026-\d{6}$")

    for c in gen.carriers:
        assert carrier_regex.match(c.carrier_id), f"Invalid carrier ID: {c.carrier_id}"

    for rc in gen.rate_cards:
        assert rate_card_regex.match(rc.rate_card_id), f"Invalid rate card ID: {rc.rate_card_id}"

    for s in gen.shipments:
        assert shipment_regex.match(s.shipment_id), f"Invalid shipment ID: {s.shipment_id}"

    for inv in gen.freight_invoices:
        assert invoice_regex.match(inv.invoice_id), f"Invalid invoice ID: {inv.invoice_id}"

    for line in gen.invoice_lines:
        assert line_regex.match(line.line_id), f"Invalid line ID: {line.line_id}"

    for ex in gen.audit_exceptions:
        assert exception_regex.match(ex.exception_id), f"Invalid exception ID: {ex.exception_id}"


def test_seed_reproducibility():
    """Step 10 requirement: Verify that regenerating twice with seed 20261022 produces identical records."""
    gen1 = FreightDataGenerator(seed=20261022)
    res1 = gen1.generate_all(scale="starter")

    gen2 = FreightDataGenerator(seed=20261022)
    res2 = gen2.generate_all(scale="starter")

    # Verify counts match
    assert res1["counts"] == res2["counts"]

    # Verify entity IDs and numbers match exactly
    for c1, c2 in zip(gen1.carriers, gen2.carriers):
        assert c1.carrier_id == c2.carrier_id
        assert c1.name == c2.name

    for s1, s2 in zip(gen1.shipments, gen2.shipments):
        assert s1.shipment_id == s2.shipment_id
        assert s1.shipment_date == s2.shipment_date

    for i1, i2 in zip(gen1.freight_invoices, gen2.freight_invoices):
        assert i1.invoice_id == i2.invoice_id
        assert i1.billed_amount == i2.billed_amount
        assert i1.variance_amount == i2.variance_amount


def test_different_seeds_produce_variation():
    """Verify that different seeds produce different randomized records."""
    gen1 = FreightDataGenerator(seed=11111)
    gen1.generate_all(scale="starter")

    gen2 = FreightDataGenerator(seed=99999)
    gen2.generate_all(scale="starter")

    # Invoices amounts should differ across seeds
    inv_amounts_1 = [i.billed_amount for i in gen1.freight_invoices[:10]]
    inv_amounts_2 = [i.billed_amount for i in gen2.freight_invoices[:10]]
    assert inv_amounts_1 != inv_amounts_2
