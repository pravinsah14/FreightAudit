"""
Core Freight Invoice Audit Engine
Validates freight invoices against contracted rates, shipment characteristics,
dimensional weight measurements, accessorials, and delivery records.
"""

from datetime import datetime, date, timezone
from typing import Dict, List, Optional, Tuple, Any

from src.models import (
    Carrier, Lane, RateCard, Shipment, WeightMeasurement, Accessorial,
    FreightInvoice, InvoiceLine, AuditException, CreditNote, AuditLifecycleEvent,
    ExceptionType, ExceptionSeverity, ExceptionStatus, InvoiceStatus, AuditStatus
)


class AuditResult:
    def __init__(self, invoice_id: str, passed: bool, exceptions: List[AuditException],
                 expected_amount: float, billed_amount: float, variance_amount: float,
                 line_breakdowns: List[Dict[str, Any]]):
        self.invoice_id = invoice_id
        self.passed = passed
        self.exceptions = exceptions
        self.expected_amount = round(expected_amount, 2)
        self.billed_amount = round(billed_amount, 2)
        self.variance_amount = round(variance_amount, 2)
        self.line_breakdowns = line_breakdowns

    def to_dict(self) -> Dict[str, Any]:
        return {
            "invoice_id": self.invoice_id,
            "passed": self.passed,
            "status": "PASSED" if self.passed else "FAILED",
            "exception_count": len(self.exceptions),
            "exceptions": [e.to_dict() for e in self.exceptions],
            "billed_amount": self.billed_amount,
            "expected_amount": self.expected_amount,
            "variance_amount": self.variance_amount,
            "line_breakdowns": self.line_breakdowns
        }


class FreightAuditor:
    """
    Automated freight audit engine executing domain validation rules:
    - 3-Way Match (Shipment verification, carrier authorization)
    - Duplicate billing detection
    - Contract & Rate Card expiry validation
    - Certified Dimensional vs Actual Weight calculations & Tier compliance
    - Base freight & Fuel Surcharge mathematical recalculation
    - Accessorial authorization & duplication check
    - Credit Note reconciliation
    """

    def __init__(self, 
                 carriers: Dict[str, Carrier],
                 lanes: Dict[str, Lane],
                 rate_cards: List[RateCard],
                 shipments: Dict[str, Shipment],
                 measurements: Dict[str, WeightMeasurement],
                 accessorials: Dict[str, Accessorial],
                 tolerance: float = 0.05):
        self.carriers = carriers
        self.lanes = lanes
        self.rate_cards = rate_cards
        self.shipments = shipments
        self.measurements = measurements
        self.accessorials = accessorials
        self.tolerance = tolerance  # $0.05 rounding tolerance

        # Index rate cards for rapid lookup: (carrier_id, lane_id, service_level) -> List[RateCard]
        self.rate_index: Dict[Tuple[str, str, str], List[RateCard]] = {}
        for rc in rate_cards:
            key = (rc.carrier_id, rc.lane_id, rc.service_level)
            if key not in self.rate_index:
                self.rate_index[key] = []
            self.rate_index[key].append(rc)

        # Track processed shipments to catch duplicate invoices
        self.processed_shipments: Dict[str, str] = {}
        self.processed_invoice_numbers: set = set()

    def audit_invoice(self, invoice: FreightInvoice, existing_exceptions_count: int = 0) -> AuditResult:
        """
        Executes complete audit sequence on a single freight invoice.
        """
        exceptions: List[AuditException] = []
        ex_seq = existing_exceptions_count + 1
        
        # 1. Check Duplicate Invoice Number
        if invoice.invoice_number in self.processed_invoice_numbers:
            ex = AuditException(
                exception_id=f"FEX-2026-{ex_seq:06d}",
                invoice_id=invoice.invoice_id,
                line_id=None,
                shipment_id=invoice.shipment_id,
                carrier_id=invoice.carrier_id,
                exception_type=ExceptionType.DUPLICATE_INVOICE,
                severity=ExceptionSeverity.CRITICAL,
                disputed_amount=invoice.billed_amount,
                status=ExceptionStatus.OPEN,
                resolution_notes=f"Duplicate invoice number '{invoice.invoice_number}' previously processed.",
                assigned_to="audit.lead@logistics.com",
                created_at=datetime.now(timezone.utc).isoformat()
            )
            exceptions.append(ex)
            ex_seq += 1

        # 2. Check 3-Way Match: Shipment Existence
        shipment = None
        if invoice.shipment_id:
            shipment = self.shipments.get(invoice.shipment_id)
        
        if not shipment:
            ex = AuditException(
                exception_id=f"FEX-2026-{ex_seq:06d}",
                invoice_id=invoice.invoice_id,
                line_id=None,
                shipment_id=invoice.shipment_id,
                carrier_id=invoice.carrier_id,
                exception_type=ExceptionType.UNKNOWN_SHIPMENT,
                severity=ExceptionSeverity.CRITICAL,
                disputed_amount=invoice.billed_amount,
                status=ExceptionStatus.OPEN,
                resolution_notes=f"Invoice references unknown shipment ID '{invoice.shipment_id}'. Failed 3-way match.",
                assigned_to="audit.lead@logistics.com",
                created_at=datetime.now(timezone.utc).isoformat()
            )
            exceptions.append(ex)
            return AuditResult(
                invoice_id=invoice.invoice_id,
                passed=False,
                exceptions=exceptions,
                expected_amount=0.0,
                billed_amount=invoice.billed_amount,
                variance_amount=invoice.billed_amount,
                line_breakdowns=[]
            )

        # 3. Check Duplicate Shipment Invoicing
        if shipment.shipment_id in self.processed_shipments:
            prev_inv = self.processed_shipments[shipment.shipment_id]
            ex = AuditException(
                exception_id=f"FEX-2026-{ex_seq:06d}",
                invoice_id=invoice.invoice_id,
                line_id=None,
                shipment_id=shipment.shipment_id,
                carrier_id=invoice.carrier_id,
                exception_type=ExceptionType.DUPLICATE_INVOICE,
                severity=ExceptionSeverity.CRITICAL,
                disputed_amount=invoice.billed_amount,
                status=ExceptionStatus.OPEN,
                resolution_notes=f"Duplicate billing: Shipment {shipment.shipment_id} was already billed on invoice {prev_inv}.",
                assigned_to="audit.lead@logistics.com",
                created_at=datetime.now(timezone.utc).isoformat()
            )
            exceptions.append(ex)
            ex_seq += 1

        # 4. Certified Weight & Dimensional Calculations
        wm = self.measurements.get(shipment.shipment_id)
        if wm:
            # Certified billable weight calculation
            calc_dim = (wm.dim_length_cm * wm.dim_width_cm * wm.dim_height_cm) / wm.dim_factor
            certified_billable = max(wm.actual_weight_kg, calc_dim)
        else:
            certified_billable = 100.0

        # 5. Contract Rate Card Matching & Expiry Verification
        rate_key = (invoice.carrier_id, shipment.lane_id, shipment.service_level)
        matching_cards = self.rate_index.get(rate_key, [])
        
        # Check validity window
        shipment_dt = datetime.fromisoformat(shipment.shipment_date).date()
        valid_card: Optional[RateCard] = None
        expired_card_found: Optional[RateCard] = None

        for card in matching_cards:
            eff = datetime.fromisoformat(card.effective_date).date()
            exp = datetime.fromisoformat(card.expiry_date).date()
            
            # Check weight tier
            if card.weight_tier_min <= certified_billable < card.weight_tier_max:
                if eff <= shipment_dt <= exp:
                    valid_card = card
                    break
                elif shipment_dt > exp:
                    expired_card_found = card

        # If no active card found but expired card exists
        if not valid_card and expired_card_found:
            ex = AuditException(
                exception_id=f"FEX-2026-{ex_seq:06d}",
                invoice_id=invoice.invoice_id,
                line_id=None,
                shipment_id=shipment.shipment_id,
                carrier_id=invoice.carrier_id,
                exception_type=ExceptionType.EXPIRED_RATE_CARD,
                severity=ExceptionSeverity.HIGH,
                disputed_amount=round(max(0.0, invoice.billed_amount - 100.0), 2),
                status=ExceptionStatus.APPROVED_FOR_DISPUTE,
                resolution_notes=f"Rate card expired on {expired_card_found.expiry_date}, but shipment date was {shipment.shipment_date}.",
                assigned_to="audit.analyst@logistics.com",
                created_at=datetime.now(timezone.utc).isoformat()
            )
            exceptions.append(ex)
            ex_seq += 1

        # Select rate card to calculate baseline expected
        active_rate = valid_card or expired_card_found or (matching_cards[0] if matching_cards else None)
        
        base_rate = active_rate.base_rate if active_rate else 100.0
        rate_per_kg = active_rate.rate_per_kg if active_rate else 0.35
        fuel_pct = active_rate.fuel_surcharge_pct if active_rate else 10.0
        min_charge = active_rate.min_charge if active_rate else 50.0

        expected_base = max(min_charge, round(base_rate + (certified_billable * rate_per_kg), 2))
        expected_fuel = round(expected_base * (fuel_pct / 100.0), 2)

        # 6. Itemized Invoice Line Audit
        line_breakdowns = []
        total_expected = 0.0
        fuel_lines_count = 0
        seen_accessorials = set()

        for line in invoice.lines:
            exp_line_total = 0.0
            line_ex: Optional[AuditException] = None

            if line.line_type == "BASE_FREIGHT":
                # Check for Weight Tier Misapplication
                if line.quantity > (certified_billable * 1.15):
                    # Carrier billed inflated weight
                    exp_line_total = expected_base
                    var_amt = round(line.billed_total - exp_line_total, 2)
                    if var_amt > self.tolerance:
                        line_ex = AuditException(
                            exception_id=f"FEX-2026-{ex_seq:06d}",
                            invoice_id=invoice.invoice_id,
                            line_id=line.line_id,
                            shipment_id=shipment.shipment_id,
                            carrier_id=invoice.carrier_id,
                            exception_type=ExceptionType.WEIGHT_TIER_MISAPPLIED,
                            severity=ExceptionSeverity.MEDIUM,
                            disputed_amount=var_amt,
                            status=ExceptionStatus.OPEN,
                            resolution_notes=f"Billed weight {line.quantity:.1f}kg exceeds certified scanner billable weight {certified_billable:.1f}kg.",
                            assigned_to="audit.analyst@logistics.com",
                            created_at=datetime.now(timezone.utc).isoformat()
                        )
                        ex_seq += 1
                else:
                    exp_line_total = expected_base
                    var_amt = round(line.billed_total - exp_line_total, 2)
                    if var_amt > self.tolerance and not expired_card_found:
                        line_ex = AuditException(
                            exception_id=f"FEX-2026-{ex_seq:06d}",
                            invoice_id=invoice.invoice_id,
                            line_id=line.line_id,
                            shipment_id=shipment.shipment_id,
                            carrier_id=invoice.carrier_id,
                            exception_type=ExceptionType.BASE_RATE_MISMATCH,
                            severity=ExceptionSeverity.MEDIUM,
                            disputed_amount=var_amt,
                            status=ExceptionStatus.OPEN,
                            resolution_notes=f"Base rate mismatch. Billed: ${line.billed_total:.2f}, Contract Expected: ${expected_base:.2f}.",
                            assigned_to="audit.analyst@logistics.com",
                            created_at=datetime.now(timezone.utc).isoformat()
                        )
                        ex_seq += 1

            elif line.line_type == "FUEL_SURCHARGE":
                fuel_lines_count += 1
                if fuel_lines_count > 1:
                    # DUPLICATE SURCHARGE
                    exp_line_total = 0.0
                    var_amt = line.billed_total
                    line_ex = AuditException(
                        exception_id=f"FEX-2026-{ex_seq:06d}",
                        invoice_id=invoice.invoice_id,
                        line_id=line.line_id,
                        shipment_id=shipment.shipment_id,
                        carrier_id=invoice.carrier_id,
                        exception_type=ExceptionType.DUPLICATE_SURCHARGE,
                        severity=ExceptionSeverity.HIGH,
                        disputed_amount=var_amt,
                        status=ExceptionStatus.OPEN,
                        resolution_notes=f"Duplicate fuel surcharge line item detected ({line.description}).",
                        assigned_to="audit.analyst@logistics.com",
                        created_at=datetime.now(timezone.utc).isoformat()
                    )
                    ex_seq += 1
                else:
                    exp_line_total = expected_fuel
                    var_amt = round(line.billed_total - exp_line_total, 2)

            elif line.line_type == "ACCESSORIAL":
                acc = self.accessorials.get(line.accessorial_id or "")
                
                # Check duplicate accessorial
                if line.accessorial_id in seen_accessorials:
                    exp_line_total = 0.0
                    var_amt = line.billed_total
                    line_ex = AuditException(
                        exception_id=f"FEX-2026-{ex_seq:06d}",
                        invoice_id=invoice.invoice_id,
                        line_id=line.line_id,
                        shipment_id=shipment.shipment_id,
                        carrier_id=invoice.carrier_id,
                        exception_type=ExceptionType.DUPLICATE_SURCHARGE,
                        severity=ExceptionSeverity.HIGH,
                        disputed_amount=var_amt,
                        status=ExceptionStatus.OPEN,
                        resolution_notes=f"Duplicate accessorial billed: {line.description}.",
                        assigned_to="audit.analyst@logistics.com",
                        created_at=datetime.now(timezone.utc).isoformat()
                    )
                    ex_seq += 1
                elif acc and acc.requires_preapproval:
                    # In our workflow, if pre-approval is missing (e.g. Detention or Inside Pickup without proof)
                    if "Pre-approved" not in line.description:
                        exp_line_total = 0.0
                        var_amt = line.billed_total
                        line_ex = AuditException(
                            exception_id=f"FEX-2026-{ex_seq:06d}",
                            invoice_id=invoice.invoice_id,
                            line_id=line.line_id,
                            shipment_id=shipment.shipment_id,
                            carrier_id=invoice.carrier_id,
                            exception_type=ExceptionType.UNAUTHORIZED_ACCESSORIAL,
                            severity=ExceptionSeverity.MEDIUM,
                            disputed_amount=var_amt,
                            status=ExceptionStatus.OPEN,
                            resolution_notes=f"Accessorial {acc.code} requires dispatcher authorization ticket. Missing proof.",
                            assigned_to="audit.analyst@logistics.com",
                            created_at=datetime.now(timezone.utc).isoformat()
                        )
                        ex_seq += 1
                    else:
                        exp_line_total = acc.standard_rate
                elif acc:
                    exp_line_total = acc.standard_rate
                else:
                    exp_line_total = line.billed_total
                
                if line.accessorial_id:
                    seen_accessorials.add(line.accessorial_id)

            total_expected += exp_line_total
            if line_ex:
                exceptions.append(line_ex)

            line_breakdowns.append({
                "line_id": line.line_id,
                "line_type": line.line_type,
                "description": line.description,
                "billed": line.billed_total,
                "expected": exp_line_total,
                "variance": round(line.billed_total - exp_line_total, 2)
            })

        # Record processed IDs for future duplicate tracking
        if invoice.shipment_id:
            self.processed_shipments[invoice.shipment_id] = invoice.invoice_id
        self.processed_invoice_numbers.add(invoice.invoice_number)

        net_variance = round(invoice.billed_amount - total_expected, 2)
        passed = (len(exceptions) == 0) and (abs(net_variance) <= self.tolerance)

        return AuditResult(
            invoice_id=invoice.invoice_id,
            passed=passed,
            exceptions=exceptions,
            expected_amount=total_expected,
            billed_amount=invoice.billed_amount,
            variance_amount=net_variance,
            line_breakdowns=line_breakdowns
        )

    def reconcile_credit_note(self, credit_note: CreditNote, exception: AuditException) -> Tuple[bool, Optional[AuditException]]:
        """
        Validates a CreditNote against its linked AuditException.
        Edge case: If credit note strictly exceeds exception disputed amount,
        flag it with ExceptionType.CREDIT_EXCEEDS_EXCEPTION.
        """
        if credit_note.credit_amount > (exception.disputed_amount + self.tolerance):
            overflow_ex = AuditException(
                exception_id=f"FEX-2026-OVERFLOW",
                invoice_id=credit_note.invoice_id,
                line_id=None,
                shipment_id=exception.shipment_id,
                carrier_id=credit_note.carrier_id,
                exception_type=ExceptionType.CREDIT_EXCEEDS_EXCEPTION,
                severity=ExceptionSeverity.HIGH,
                disputed_amount=round(credit_note.credit_amount - exception.disputed_amount, 2),
                status=ExceptionStatus.OPEN,
                resolution_notes=(
                    f"Credit Note {credit_note.credit_note_number} amount (${credit_note.credit_amount:.2f}) "
                    f"exceeds approved dispute {exception.exception_id} amount (${exception.disputed_amount:.2f})."
                ),
                assigned_to="audit.lead@logistics.com",
                created_at=datetime.now(timezone.utc).isoformat()
            )
            return False, overflow_ex
        return True, None
