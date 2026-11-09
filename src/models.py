"""
Data Models for Freight Audit & Reconciliation System
Defines all core entities, data structures, and enums.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime, date


class CarrierMode:
    FTL = "FTL"
    LTL = "LTL"
    INTERMODAL = "INTERMODAL"
    PARCEL = "PARCEL"
    AIR = "AIR"
    ALL = [FTL, LTL, INTERMODAL, PARCEL, AIR]


class ServiceLevel:
    STANDARD = "STANDARD"
    EXPRESS = "EXPRESS"
    EXPEDITED = "EXPEDITED"
    ECONOMY = "ECONOMY"
    ALL = [STANDARD, EXPRESS, EXPEDITED, ECONOMY]


class InvoiceStatus:
    RECEIVED = "RECEIVED"
    PENDING_AUDIT = "PENDING_AUDIT"
    APPROVED = "APPROVED"
    DISPUTED = "DISPUTED"
    PARTIALLY_APPROVED = "PARTIALLY_APPROVED"
    REJECTED = "REJECTED"
    PAID = "PAID"
    ALL = [RECEIVED, PENDING_AUDIT, APPROVED, DISPUTED, PARTIALLY_APPROVED, REJECTED, PAID]


class AuditStatus:
    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    ALL = [PENDING, PASSED, FAILED]


class ExceptionType:
    UNKNOWN_SHIPMENT = "UNKNOWN_SHIPMENT"
    EXPIRED_RATE_CARD = "EXPIRED_RATE_CARD"
    WEIGHT_TIER_MISAPPLIED = "WEIGHT_TIER_MISAPPLIED"
    DUPLICATE_SURCHARGE = "DUPLICATE_SURCHARGE"
    DUPLICATE_INVOICE = "DUPLICATE_INVOICE"
    UNAUTHORIZED_ACCESSORIAL = "UNAUTHORIZED_ACCESSORIAL"
    BASE_RATE_MISMATCH = "BASE_RATE_MISMATCH"
    CREDIT_EXCEEDS_EXCEPTION = "CREDIT_EXCEEDS_EXCEPTION"
    ALL = [
        UNKNOWN_SHIPMENT,
        EXPIRED_RATE_CARD,
        WEIGHT_TIER_MISAPPLIED,
        DUPLICATE_SURCHARGE,
        DUPLICATE_INVOICE,
        UNAUTHORIZED_ACCESSORIAL,
        BASE_RATE_MISMATCH,
        CREDIT_EXCEEDS_EXCEPTION
    ]


class ExceptionSeverity:
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    ALL = [CRITICAL, HIGH, MEDIUM, LOW]


class ExceptionStatus:
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    APPROVED_FOR_DISPUTE = "APPROVED_FOR_DISPUTE"
    RESOLVED = "RESOLVED"
    OVERRIDDEN = "OVERRIDDEN"
    ALL = [OPEN, INVESTIGATING, APPROVED_FOR_DISPUTE, RESOLVED, OVERRIDDEN]


class CreditNoteStatus:
    DRAFT = "DRAFT"
    ISSUED = "ISSUED"
    RECONCILED = "RECONCILED"
    REJECTED = "REJECTED"
    ALL = [DRAFT, ISSUED, RECONCILED, REJECTED]


@dataclass
class Carrier:
    carrier_id: str
    name: str
    code: str
    contact_email: str
    mode: str
    status: str = "ACTIVE"
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Lane:
    lane_id: str
    origin_city: str
    origin_state: str
    origin_zip: str
    dest_city: str
    dest_state: str
    dest_zip: str
    distance_miles: float
    transit_days: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RateCard:
    rate_card_id: str
    carrier_id: str
    lane_id: str
    service_level: str
    weight_tier_min: float
    weight_tier_max: float
    base_rate: float
    rate_per_kg: float
    min_charge: float
    fuel_surcharge_pct: float
    effective_date: str
    expiry_date: str
    status: str = "ACTIVE"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Shipment:
    shipment_id: str
    carrier_id: str
    lane_id: str
    service_level: str
    shipment_date: str
    delivery_date: Optional[str]
    total_pieces: int
    declared_value: float
    status: str = "DELIVERED"
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ShipmentLeg:
    leg_id: str
    shipment_id: str
    leg_sequence: int
    origin: str
    destination: str
    carrier_id: str
    pickup_time: str
    delivery_time: Optional[str]
    status: str = "COMPLETED"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WeightMeasurement:
    measurement_id: str
    shipment_id: str
    actual_weight_kg: float
    dim_length_cm: float
    dim_width_cm: float
    dim_height_cm: float
    dim_factor: int = 5000
    volumetric_weight_kg: float = 0.0
    billable_weight_kg: float = 0.0
    measured_by: str = "WAREHOUSE_SCANNER"
    measured_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Accessorial:
    accessorial_id: str
    code: str
    description: str
    standard_rate: float
    rate_type: str = "FLAT"
    requires_preapproval: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class InvoiceLine:
    line_id: str
    invoice_id: str
    line_number: int
    line_type: str
    accessorial_id: Optional[str]
    description: str
    quantity: float
    billed_unit_rate: float
    billed_total: float
    expected_unit_rate: float = 0.0
    expected_total: float = 0.0
    variance_amount: float = 0.0
    variance_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FreightInvoice:
    invoice_id: str
    invoice_number: str
    carrier_id: str
    shipment_id: Optional[str]
    invoice_date: str
    due_date: str
    currency: str = "USD"
    billed_amount: float = 0.0
    expected_amount: float = 0.0
    variance_amount: float = 0.0
    status: str = "RECEIVED"
    audit_status: str = "PENDING"
    created_at: str = ""
    lines: List[InvoiceLine] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['lines'] = [l.to_dict() if isinstance(l, InvoiceLine) else l for l in self.lines]
        return d


@dataclass
class AuditException:
    exception_id: str
    invoice_id: str
    line_id: Optional[str]
    shipment_id: Optional[str]
    carrier_id: str
    exception_type: str
    severity: str
    disputed_amount: float
    status: str = "OPEN"
    resolution_notes: Optional[str] = None
    assigned_to: Optional[str] = None
    created_at: str = ""
    resolved_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CreditNote:
    credit_note_id: str
    credit_note_number: str
    exception_id: str
    invoice_id: str
    carrier_id: str
    credit_amount: float
    reason: str
    status: str = "ISSUED"
    issue_date: str = ""
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AuditLifecycleEvent:
    event_id: str
    entity_type: str
    entity_id: str
    event_type: str
    previous_state: Optional[str]
    new_state: str
    actor: str
    notes: Optional[str] = None
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GroundTruthRecord:
    invoice_id: str
    shipment_id: Optional[str]
    carrier_id: str
    has_anomaly: bool
    anomaly_types: str  # Comma-separated or JSON list
    expected_audit_decision: str  # PASSED or FAILED
    expected_disputed_amount: float
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
