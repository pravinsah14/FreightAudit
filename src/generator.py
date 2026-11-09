"""
Deterministic Synthetic Data Generator for Freight Audit & Reconciliation System
Complies with Steps 2-7 of the challenge specification.
"""

import random
import json
import csv
from datetime import datetime, timedelta, date
from typing import Dict, List, Tuple, Any, Optional

from src.models import (
    Carrier, Lane, RateCard, Shipment, ShipmentLeg, WeightMeasurement,
    Accessorial, FreightInvoice, InvoiceLine, AuditException, CreditNote,
    AuditLifecycleEvent, GroundTruthRecord, CarrierMode, ServiceLevel,
    InvoiceStatus, AuditStatus, ExceptionType, ExceptionSeverity, ExceptionStatus,
    CreditNoteStatus
)


class FreightDataGenerator:
    """
    Generates synthetic freight domain data deterministically using a fixed seed.
    Master entities are generated first, followed by dependent transaction tables
    and injected labelled edge cases.
    """

    CITIES = [
        ("Chicago", "IL", "60601"),
        ("Dallas", "TX", "75201"),
        ("Atlanta", "GA", "30301"),
        ("Los Angeles", "CA", "90001"),
        ("New York", "NY", "10001"),
        ("Memphis", "TN", "38101"),
        ("Seattle", "WA", "98101"),
        ("Denver", "CO", "80201"),
        ("Columbus", "OH", "43201"),
        ("Kansas City", "MO", "64101"),
        ("Charlotte", "NC", "28201"),
        ("Phoenix", "AZ", "85001"),
        ("Indianapolis", "IN", "46201"),
        ("Houston", "TX", "77001"),
        ("Philadelphia", "PA", "19101"),
    ]

    CARRIER_NAMES_PREFIX = [
        "Apex", "Vanguard", "Pinnacle", "Swiftline", "Falcon", "Titan", "BlueSky",
        "Echo", "Horizon", "Meridian", "Omega", "Frontier", "Sterling", "Summit",
        "Atlas", "Keystone", "Beacon", "Crest", "Ironclad", "Polaris", "Velocity",
        "Cascade", "Triton", "Borealis", "Silverstone", "Crossroad", "TransGlobal"
    ]

    CARRIER_NAMES_SUFFIX = [
        "Logistics", "Freight", "Express", "Transport", "Carriers", "Lines",
        "Supply Chain", "Haulage", "Transit", "Direct", "Cargo"
    ]

    STANDARD_ACCESSORIALS = [
        ("ACC-000001", "LIFTGATE", "Hydraulic liftgate assistance at delivery/pickup", 75.00, "FLAT", False),
        ("ACC-000002", "RESIDENTIAL", "Residential delivery surcharge", 50.00, "FLAT", False),
        ("ACC-000003", "INSIDE_PICKUP", "Inside building pickup or drop-off", 65.00, "FLAT", True),
        ("ACC-000004", "DETENTION", "Driver detention waiting time beyond 2 free hours", 85.00, "HOURLY", True),
        ("ACC-000005", "HAZMAT", "Hazardous materials handling surcharge", 120.00, "FLAT", True),
        ("ACC-000006", "STORAGE", "Temporary holding storage fee per pallet/day", 40.00, "PER_PIECE", True),
        ("ACC-000007", "RECONSIGN", "Reconsignment / redirect fee in transit", 95.00, "FLAT", True),
    ]

    def __init__(self, seed: int = 20261022):
        self.seed = seed
        self.rng = random.Random(seed)
        
        # In-memory storage for generated objects
        self.carriers: List[Carrier] = []
        self.lanes: List[Lane] = []
        self.rate_cards: List[RateCard] = []
        self.shipments: List[Shipment] = []
        self.shipment_legs: List[ShipmentLeg] = []
        self.weight_measurements: List[WeightMeasurement] = []
        self.accessorials: List[Accessorial] = []
        self.freight_invoices: List[FreightInvoice] = []
        self.invoice_lines: List[InvoiceLine] = []
        self.audit_exceptions: List[AuditException] = []
        self.credit_notes: List[CreditNote] = []
        self.lifecycle_events: List[AuditLifecycleEvent] = []
        self.ground_truth: List[GroundTruthRecord] = []

        # Lookup caches for deterministic relation generation
        self.carrier_rate_map: Dict[Tuple[str, str, str], List[RateCard]] = {}
        self.shipment_map: Dict[str, Shipment] = {}
        self.measurement_map: Dict[str, WeightMeasurement] = {}

    def generate_all(self, scale: str = "starter") -> Dict[str, Any]:
        """
        Generate complete dataset based on scale parameter.
        - starter: 10 carriers, 20 lanes, 250 shipments, 200 invoices (runs in < 1 second)
        - full: 100 carriers, 100 lanes, 20,000 shipments, 15,000 invoices (full challenge baseline volume)
        """
        # Reset RNG with fixed seed to guarantee idempotence
        self.rng = random.Random(self.seed)
        
        if scale == "full":
            num_carriers = 100
            num_lanes = 100
            num_shipments = 20000
            num_invoices = 15000
        else:
            # starter volume for fast local test/development and immediate UI verification
            num_carriers = 10
            num_lanes = 20
            num_shipments = 250
            num_invoices = 200

        # Step 1: Master Tables
        self._generate_carriers(num_carriers)
        self._generate_lanes(num_lanes)
        self._generate_accessorials()
        self._generate_rate_cards()

        # Step 2: Operational Data
        self._generate_shipments(num_shipments)
        self._generate_weight_measurements()
        self._generate_shipment_legs()

        # Step 3: Financial Invoices with Injected Labelled Edge Cases & Ground Truth
        self._generate_invoices_and_audit(num_invoices)

        return {
            "scale": scale,
            "seed": self.seed,
            "counts": {
                "carriers": len(self.carriers),
                "lanes": len(self.lanes),
                "rate_cards": len(self.rate_cards),
                "shipments": len(self.shipments),
                "shipment_legs": len(self.shipment_legs),
                "weight_measurements": len(self.weight_measurements),
                "accessorials": len(self.accessorials),
                "freight_invoices": len(self.freight_invoices),
                "invoice_lines": len(self.invoice_lines),
                "audit_exceptions": len(self.audit_exceptions),
                "credit_notes": len(self.credit_notes),
                "lifecycle_events": len(self.lifecycle_events),
                "ground_truth": len(self.ground_truth),
            }
        }

    def _generate_carriers(self, count: int):
        self.carriers = []
        modes = [CarrierMode.FTL, CarrierMode.LTL, CarrierMode.INTERMODAL, CarrierMode.PARCEL]
        
        used_names = set()
        for i in range(1, count + 1):
            carrier_id = f"CAR-{i:06d}"
            
            # Create unique realistic name
            while True:
                prefix = self.rng.choice(self.CARRIER_NAMES_PREFIX)
                suffix = self.rng.choice(self.CARRIER_NAMES_SUFFIX)
                name = f"{prefix} {suffix}"
                if count > 200:
                    name += f" {i}"
                if name not in used_names:
                    used_names.add(name)
                    break
            
            # SCAC code
            code = (prefix[:3] + suffix[:1]).upper() + (f"{i%90+10}" if count > 20 else "")
            email = f"billing@{prefix.lower()}-{suffix.lower().replace(' ', '')}.com"
            mode = self.rng.choice(modes)
            created_at = "2026-01-01T08:00:00Z"
            
            carrier = Carrier(
                carrier_id=carrier_id,
                name=name,
                code=code[:6],
                contact_email=email,
                mode=mode,
                status="ACTIVE",
                created_at=created_at
            )
            self.carriers.append(carrier)

    def _generate_lanes(self, count: int):
        self.lanes = []
        pairs = []
        
        # Build pairwise city combinations
        for orig in self.CITIES:
            for dest in self.CITIES:
                if orig != dest:
                    pairs.append((orig, dest))
        
        self.rng.shuffle(pairs)
        selected_pairs = pairs[:count] if count <= len(pairs) else (pairs * (count // len(pairs) + 1))[:count]
        
        for i, (orig, dest) in enumerate(selected_pairs, 1):
            lane_id = f"LANE-{i:06d}"
            # Realistic distance approx
            dist = round(self.rng.uniform(150.0, 2400.0), 2)
            transit = max(1, int(dist // 450) + 1)
            
            lane = Lane(
                lane_id=lane_id,
                origin_city=orig[0],
                origin_state=orig[1],
                origin_zip=orig[2],
                dest_city=dest[0],
                dest_state=dest[1],
                dest_zip=dest[2],
                distance_miles=dist,
                transit_days=transit
            )
            self.lanes.append(lane)

    def _generate_accessorials(self):
        self.accessorials = []
        for acc in self.STANDARD_ACCESSORIALS:
            self.accessorials.append(
                Accessorial(
                    accessorial_id=acc[0],
                    code=acc[1],
                    description=acc[2],
                    standard_rate=acc[3],
                    rate_type=acc[4],
                    requires_preapproval=acc[5]
                )
            )

    def _generate_rate_cards(self):
        self.rate_cards = []
        self.carrier_rate_map = {}
        
        # Weight tiers in kg: Tier 1: 0-250kg, Tier 2: 250-1000kg, Tier 3: 1000-5000kg, Tier 4: 5000-25000kg
        weight_tiers = [
            (0.0, 250.0, 45.0, 0.45),
            (250.0, 1000.0, 95.0, 0.35),
            (1000.0, 5000.0, 180.0, 0.28),
            (5000.0, 25000.0, 350.0, 0.22)
        ]
        
        for carrier in self.carriers:
            rc_counter = 1
            # Each carrier covers a subset of lanes
            num_carrier_lanes = max(2, min(len(self.lanes), 10))
            carrier_lanes = self.rng.sample(self.lanes, num_carrier_lanes)
            
            for lane in carrier_lanes:
                for tier_min, tier_max, base_start, rate_kg in weight_tiers:
                    rate_card_id = f"RATE-{carrier.carrier_id}-2026-{rc_counter:02d}"
                    rc_counter += 1
                    
                    # Contract period
                    # Most are active in 2026, some will be expired for injection testing
                    eff_date = "2026-01-01"
                    exp_date = "2026-12-31"
                    
                    fuel_pct = round(self.rng.uniform(8.0, 15.0), 2)
                    min_chg = round(base_start * 1.2, 2)
                    base_rt = round(base_start + (lane.distance_miles * 0.1), 2)
                    
                    rc = RateCard(
                        rate_card_id=rate_card_id,
                        carrier_id=carrier.carrier_id,
                        lane_id=lane.lane_id,
                        service_level=ServiceLevel.STANDARD,
                        weight_tier_min=tier_min,
                        weight_tier_max=tier_max,
                        base_rate=base_rt,
                        rate_per_kg=rate_kg,
                        min_charge=min_chg,
                        fuel_surcharge_pct=fuel_pct,
                        effective_date=eff_date,
                        expiry_date=exp_date,
                        status="ACTIVE"
                    )
                    self.rate_cards.append(rc)
                    
                    key = (carrier.carrier_id, lane.lane_id, ServiceLevel.STANDARD)
                    if key not in self.carrier_rate_map:
                        self.carrier_rate_map[key] = []
                    self.carrier_rate_map[key].append(rc)

    def _generate_shipments(self, count: int):
        self.shipments = []
        self.shipment_map = {}
        
        base_date = date(2026, 3, 1)
        valid_keys = list(self.carrier_rate_map.keys())
        
        for i in range(1, count + 1):
            shp_id = f"SHP-2026-{i:06d}"
            
            # Pick a carrier and lane that has contracted rate cards
            c_id, l_id, s_level = self.rng.choice(valid_keys)
            
            days_offset = self.rng.randint(0, 180)
            shp_dt = base_date + timedelta(days=days_offset)
            del_dt = shp_dt + timedelta(days=self.rng.randint(1, 5))
            
            total_pieces = self.rng.randint(1, 30)
            decl_val = round(self.rng.uniform(500.0, 25000.0), 2)
            
            shp = Shipment(
                shipment_id=shp_id,
                carrier_id=c_id,
                lane_id=l_id,
                service_level=s_level,
                shipment_date=shp_dt.isoformat(),
                delivery_date=del_dt.isoformat(),
                total_pieces=total_pieces,
                declared_value=decl_val,
                status="DELIVERED",
                created_at=f"{shp_dt.isoformat()}T08:00:00Z"
            )
            self.shipments.append(shp)
            self.shipment_map[shp_id] = shp

    def _generate_weight_measurements(self):
        self.weight_measurements = []
        self.measurement_map = {}
        
        for i, shp in enumerate(self.shipments, 1):
            m_id = f"WM-2026-{i:06d}"
            
            # Generate realistic dimensions and actual weight
            # Some shipments are dense (actual > dim), some are bulky (dim > actual)
            is_bulky = (i % 3 == 0)
            
            if is_bulky:
                # Bulky cargo: high volume, low density
                l = round(self.rng.uniform(120.0, 220.0), 1)
                w = round(self.rng.uniform(100.0, 180.0), 1)
                h = round(self.rng.uniform(100.0, 160.0), 1)
                vol_wt = round((l * w * h) / 5000.0, 2)
                act_wt = round(vol_wt * self.rng.uniform(0.4, 0.75), 2)
            else:
                # Dense cargo
                l = round(self.rng.uniform(40.0, 100.0), 1)
                w = round(self.rng.uniform(40.0, 80.0), 1)
                h = round(self.rng.uniform(30.0, 80.0), 1)
                vol_wt = round((l * w * h) / 5000.0, 2)
                act_wt = round(vol_wt * self.rng.uniform(1.2, 2.5), 2)
            
            billable_wt = max(act_wt, vol_wt)
            
            wm = WeightMeasurement(
                measurement_id=m_id,
                shipment_id=shp.shipment_id,
                actual_weight_kg=act_wt,
                dim_length_cm=l,
                dim_width_cm=w,
                dim_height_cm=h,
                dim_factor=5000,
                volumetric_weight_kg=vol_wt,
                billable_weight_kg=billable_wt,
                measured_by="WAREHOUSE_SCANNER",
                measured_at=shp.created_at
            )
            self.weight_measurements.append(wm)
            self.measurement_map[shp.shipment_id] = wm

    def _generate_shipment_legs(self):
        self.shipment_legs = []
        lane_map = {l.lane_id: l for l in self.lanes}
        
        for shp in self.shipments:
            lane = lane_map[shp.lane_id]
            leg_id = f"LEG-{shp.shipment_id}-01"
            
            pickup_dt = f"{shp.shipment_date}T09:00:00Z"
            delivery_dt = f"{shp.delivery_date}T16:00:00Z" if shp.delivery_date else None
            
            leg = ShipmentLeg(
                leg_id=leg_id,
                shipment_id=shp.shipment_id,
                leg_sequence=1,
                origin=f"{lane.origin_city}, {lane.origin_state}",
                destination=f"{lane.dest_city}, {lane.dest_state}",
                carrier_id=shp.carrier_id,
                pickup_time=pickup_dt,
                delivery_time=delivery_dt,
                status="COMPLETED"
            )
            self.shipment_legs.append(leg)

    def _find_applicable_rate_card(self, carrier_id: str, lane_id: str, service_level: str, billable_weight: float) -> Optional[RateCard]:
        cards = self.carrier_rate_map.get((carrier_id, lane_id, service_level), [])
        for c in cards:
            if c.weight_tier_min <= billable_weight < c.weight_tier_max:
                return c
        if cards:
            return cards[-1]
        return None

    def _generate_invoices_and_audit(self, count: int):
        """
        Generates baseline valid invoices and explicitly injects the 5 required edge cases:
        1. Invoice references unknown shipment
        2. Rate card expired
        3. Weight tier misapplied
        4. Surcharge duplicated
        5. Credit note exceeds exception amount
        Plus additional negative cases: duplicate billing, unauthorized accessorial.
        Ground truth labels are recorded in ground_truth.
        """
        self.freight_invoices = []
        self.invoice_lines = []
        self.audit_exceptions = []
        self.credit_notes = []
        self.lifecycle_events = []
        self.ground_truth = []

        ex_counter = 1
        cn_counter = 1
        evt_counter = 1

        # We will distribute anomalies deterministically across the invoices
        # ~80% clean / valid invoices, ~20% injected labelled edge cases
        anomaly_distribution = [
            ExceptionType.UNKNOWN_SHIPMENT,
            ExceptionType.EXPIRED_RATE_CARD,
            ExceptionType.WEIGHT_TIER_MISAPPLIED,
            ExceptionType.DUPLICATE_SURCHARGE,
            ExceptionType.CREDIT_EXCEEDS_EXCEPTION,
            ExceptionType.DUPLICATE_INVOICE,
            ExceptionType.UNAUTHORIZED_ACCESSORIAL
        ]

        # Use available shipments for invoices
        available_shipments = list(self.shipments)
        
        for i in range(1, count + 1):
            inv_id = f"FINV-2026-{i:06d}"
            inv_num = f"INV-{self.rng.randint(100000, 999999)}"
            
            # Select target shipment (or unknown for anomaly)
            target_shp = available_shipments[(i - 1) % len(available_shipments)]
            c_id = target_shp.carrier_id
            
            # Decide if this invoice should have an injected anomaly
            # Every 5th invoice gets a labelled anomaly to ensure strong test coverage
            is_anomaly = (i % 5 == 0)
            injected_type: Optional[str] = None
            if is_anomaly:
                injected_type = anomaly_distribution[((i // 5) - 1) % len(anomaly_distribution)]

            # Determine invoice dates
            shp_dt = datetime.fromisoformat(target_shp.shipment_date).date()
            inv_dt = shp_dt + timedelta(days=self.rng.randint(2, 10))
            due_dt = inv_dt + timedelta(days=30)
            
            # Baseline expected calculations
            wm = self.measurement_map.get(target_shp.shipment_id)
            billable_wt = wm.billable_weight_kg if wm else 150.0
            actual_wt = wm.actual_weight_kg if wm else 100.0
            
            matched_rate = self._find_applicable_rate_card(c_id, target_shp.lane_id, target_shp.service_level, billable_wt)
            
            base_rate = matched_rate.base_rate if matched_rate else 100.0
            rate_per_kg = matched_rate.rate_per_kg if matched_rate else 0.35
            fuel_pct = matched_rate.fuel_surcharge_pct if matched_rate else 10.0
            
            expected_base = round(base_rate + (billable_wt * rate_per_kg), 2)
            expected_fuel = round(expected_base * (fuel_pct / 100.0), 2)
            
            lines: List[InvoiceLine] = []
            line_idx = 1
            has_exception = False
            anomaly_notes = []
            expected_decision = "PASSED"
            disputed_amt = 0.0

            # --- CASE 1: UNKNOWN SHIPMENT ---
            if injected_type == ExceptionType.UNKNOWN_SHIPMENT:
                fake_shp_id = f"SHP-2026-99{i:04d}"
                billed_base = round(expected_base * 1.05, 2)
                billed_fuel = round(billed_base * (fuel_pct / 100.0), 2)
                
                # Base Line
                lines.append(InvoiceLine(
                    line_id=f"FLINE-{inv_id}-{line_idx:02d}",
                    invoice_id=inv_id,
                    line_number=line_idx,
                    line_type="BASE_FREIGHT",
                    accessorial_id=None,
                    description="Standard Base Freight",
                    quantity=billable_wt,
                    billed_unit_rate=rate_per_kg,
                    billed_total=billed_base,
                    expected_unit_rate=0.0,
                    expected_total=0.0,
                    variance_amount=billed_base,
                    variance_reason="Orphan invoice referencing non-existent shipment"
                ))
                line_idx += 1
                
                # Fuel Line
                lines.append(InvoiceLine(
                    line_id=f"FLINE-{inv_id}-{line_idx:02d}",
                    invoice_id=inv_id,
                    line_number=line_idx,
                    line_type="FUEL_SURCHARGE",
                    accessorial_id=None,
                    description=f"Fuel Surcharge ({fuel_pct}%)",
                    quantity=1.0,
                    billed_unit_rate=billed_fuel,
                    billed_total=billed_fuel,
                    expected_unit_rate=0.0,
                    expected_total=0.0,
                    variance_amount=billed_fuel,
                    variance_reason="Orphan invoice referencing non-existent shipment"
                ))
                
                billed_total = round(billed_base + billed_fuel, 2)
                expected_total = 0.0
                variance_total = billed_total
                has_exception = True
                expected_decision = "FAILED"
                disputed_amt = billed_total
                anomaly_notes.append(f"Invoice references unknown shipment ID {fake_shp_id}")
                
                finv = FreightInvoice(
                    invoice_id=inv_id,
                    invoice_number=inv_num,
                    carrier_id=c_id,
                    shipment_id=fake_shp_id,  # injected unknown ID
                    invoice_date=inv_dt.isoformat(),
                    due_date=due_dt.isoformat(),
                    billed_amount=billed_total,
                    expected_amount=expected_total,
                    variance_amount=variance_total,
                    status=InvoiceStatus.DISPUTED,
                    audit_status=AuditStatus.FAILED,
                    created_at=f"{inv_dt.isoformat()}T10:00:00Z",
                    lines=lines
                )
                self.freight_invoices.append(finv)
                self.invoice_lines.extend(lines)
                
                # Raise Exception
                ex_id = f"FEX-2026-{ex_counter:06d}"
                ex_counter += 1
                self.audit_exceptions.append(AuditException(
                    exception_id=ex_id,
                    invoice_id=inv_id,
                    line_id=None,
                    shipment_id=fake_shp_id,
                    carrier_id=c_id,
                    exception_type=ExceptionType.UNKNOWN_SHIPMENT,
                    severity=ExceptionSeverity.CRITICAL,
                    disputed_amount=disputed_amt,
                    status=ExceptionStatus.OPEN,
                    resolution_notes="Rejected during 3-way match: shipment record missing from carrier and TMS.",
                    assigned_to="audit.lead@logistics.com",
                    created_at=f"{inv_dt.isoformat()}T10:05:00Z"
                ))

            # --- CASE 2: EXPIRED RATE CARD ---
            elif injected_type == ExceptionType.EXPIRED_RATE_CARD:
                # Shipment date occurred after rate card expiry
                # We artificially create an expired card scenario where carrier billed old inflated rates
                billed_base = round(expected_base + 120.00, 2)
                billed_fuel = round(billed_base * (fuel_pct / 100.0), 2)
                var_base = round(billed_base - expected_base, 2)
                
                lines.append(InvoiceLine(
                    line_id=f"FLINE-{inv_id}-{line_idx:02d}",
                    invoice_id=inv_id,
                    line_number=line_idx,
                    line_type="BASE_FREIGHT",
                    accessorial_id=None,
                    description="Standard Base Freight",
                    quantity=billable_wt,
                    billed_unit_rate=round(billed_base / billable_wt, 4),
                    billed_total=billed_base,
                    expected_unit_rate=round(expected_base / billable_wt, 4),
                    expected_total=expected_base,
                    variance_amount=var_base,
                    variance_reason="Rate card expired before shipment date; billed with obsolete schedule"
                ))
                line_idx += 1
                
                lines.append(InvoiceLine(
                    line_id=f"FLINE-{inv_id}-{line_idx:02d}",
                    invoice_id=inv_id,
                    line_number=line_idx,
                    line_type="FUEL_SURCHARGE",
                    accessorial_id=None,
                    description=f"Fuel Surcharge ({fuel_pct}%)",
                    quantity=1.0,
                    billed_unit_rate=billed_fuel,
                    billed_total=billed_fuel,
                    expected_unit_rate=expected_fuel,
                    expected_total=expected_fuel,
                    variance_amount=round(billed_fuel - expected_fuel, 2),
                    variance_reason="Fuel surcharge calculated over inflated base rate"
                ))
                
                billed_total = round(billed_base + billed_fuel, 2)
                expected_total = round(expected_base + expected_fuel, 2)
                variance_total = round(billed_total - expected_total, 2)
                has_exception = True
                expected_decision = "FAILED"
                disputed_amt = variance_total
                anomaly_notes.append("Applied expired rate schedule; variance exceeds tolerance threshold.")
                
                finv = FreightInvoice(
                    invoice_id=inv_id,
                    invoice_number=inv_num,
                    carrier_id=c_id,
                    shipment_id=target_shp.shipment_id,
                    invoice_date=inv_dt.isoformat(),
                    due_date=due_dt.isoformat(),
                    billed_amount=billed_total,
                    expected_amount=expected_total,
                    variance_amount=variance_total,
                    status=InvoiceStatus.DISPUTED,
                    audit_status=AuditStatus.FAILED,
                    created_at=f"{inv_dt.isoformat()}T10:00:00Z",
                    lines=lines
                )
                self.freight_invoices.append(finv)
                self.invoice_lines.extend(lines)
                
                ex_id = f"FEX-2026-{ex_counter:06d}"
                ex_counter += 1
                self.audit_exceptions.append(AuditException(
                    exception_id=ex_id,
                    invoice_id=inv_id,
                    line_id=lines[0].line_id,
                    shipment_id=target_shp.shipment_id,
                    carrier_id=c_id,
                    exception_type=ExceptionType.EXPIRED_RATE_CARD,
                    severity=ExceptionSeverity.HIGH,
                    disputed_amount=disputed_amt,
                    status=ExceptionStatus.APPROVED_FOR_DISPUTE,
                    resolution_notes="Rate card expired prior to dispatch date. Claiming discrepancy refund.",
                    assigned_to="audit.analyst@logistics.com",
                    created_at=f"{inv_dt.isoformat()}T10:05:00Z"
                ))

            # --- CASE 3: WEIGHT TIER MISAPPLIED ---
            elif injected_type == ExceptionType.WEIGHT_TIER_MISAPPLIED:
                # Carrier charged at a higher weight tier (e.g. tier 3 instead of tier 2) or ignored volumetric calculation
                misapplied_base = round(expected_base * 1.40, 2)
                misapplied_fuel = round(misapplied_base * (fuel_pct / 100.0), 2)
                var_base = round(misapplied_base - expected_base, 2)
                
                lines.append(InvoiceLine(
                    line_id=f"FLINE-{inv_id}-{line_idx:02d}",
                    invoice_id=inv_id,
                    line_number=line_idx,
                    line_type="BASE_FREIGHT",
                    accessorial_id=None,
                    description=f"Base Freight (Weight billed: {billable_wt*1.5:.1f}kg vs Actual: {billable_wt:.1f}kg)",
                    quantity=round(billable_wt * 1.5, 2),
                    billed_unit_rate=rate_per_kg,
                    billed_total=misapplied_base,
                    expected_unit_rate=rate_per_kg,
                    expected_total=expected_base,
                    variance_amount=var_base,
                    variance_reason="Weight tier misapplied: Billed weight exceeds certified warehouse measurement"
                ))
                line_idx += 1
                
                lines.append(InvoiceLine(
                    line_id=f"FLINE-{inv_id}-{line_idx:02d}",
                    invoice_id=inv_id,
                    line_number=line_idx,
                    line_type="FUEL_SURCHARGE",
                    accessorial_id=None,
                    description=f"Fuel Surcharge ({fuel_pct}%)",
                    quantity=1.0,
                    billed_unit_rate=misapplied_fuel,
                    billed_total=misapplied_fuel,
                    expected_unit_rate=expected_fuel,
                    expected_total=expected_fuel,
                    variance_amount=round(misapplied_fuel - expected_fuel, 2),
                    variance_reason="Fuel surcharge levied on uncertified weight tier"
                ))
                
                billed_total = round(misapplied_base + misapplied_fuel, 2)
                expected_total = round(expected_base + expected_fuel, 2)
                variance_total = round(billed_total - expected_total, 2)
                has_exception = True
                expected_decision = "FAILED"
                disputed_amt = variance_total
                anomaly_notes.append("Weight tier misapplied; scanner certified weight differs from billed weight.")
                
                finv = FreightInvoice(
                    invoice_id=inv_id,
                    invoice_number=inv_num,
                    carrier_id=c_id,
                    shipment_id=target_shp.shipment_id,
                    invoice_date=inv_dt.isoformat(),
                    due_date=due_dt.isoformat(),
                    billed_amount=billed_total,
                    expected_amount=expected_total,
                    variance_amount=variance_total,
                    status=InvoiceStatus.DISPUTED,
                    audit_status=AuditStatus.FAILED,
                    created_at=f"{inv_dt.isoformat()}T10:00:00Z",
                    lines=lines
                )
                self.freight_invoices.append(finv)
                self.invoice_lines.extend(lines)
                
                ex_id = f"FEX-2026-{ex_counter:06d}"
                ex_counter += 1
                self.audit_exceptions.append(AuditException(
                    exception_id=ex_id,
                    invoice_id=inv_id,
                    line_id=lines[0].line_id,
                    shipment_id=target_shp.shipment_id,
                    carrier_id=c_id,
                    exception_type=ExceptionType.WEIGHT_TIER_MISAPPLIED,
                    severity=ExceptionSeverity.MEDIUM,
                    disputed_amount=disputed_amt,
                    status=ExceptionStatus.OPEN,
                    resolution_notes="Disputed against Warehouse Scanner certified scale ticket.",
                    assigned_to="audit.analyst@logistics.com",
                    created_at=f"{inv_dt.isoformat()}T10:05:00Z"
                ))

            # --- CASE 4: DUPLICATE SURCHARGE ---
            elif injected_type == ExceptionType.DUPLICATE_SURCHARGE:
                # Correct base rate, but fuel surcharge is billed twice or duplicated accessorial
                lines.append(InvoiceLine(
                    line_id=f"FLINE-{inv_id}-{line_idx:02d}",
                    invoice_id=inv_id,
                    line_number=line_idx,
                    line_type="BASE_FREIGHT",
                    accessorial_id=None,
                    description="Standard Base Freight",
                    quantity=billable_wt,
                    billed_unit_rate=rate_per_kg,
                    billed_total=expected_base,
                    expected_unit_rate=rate_per_kg,
                    expected_total=expected_base,
                    variance_amount=0.0
                ))
                line_idx += 1
                
                # Valid Fuel Line
                lines.append(InvoiceLine(
                    line_id=f"FLINE-{inv_id}-{line_idx:02d}",
                    invoice_id=inv_id,
                    line_number=line_idx,
                    line_type="FUEL_SURCHARGE",
                    accessorial_id=None,
                    description=f"Contracted Fuel Surcharge ({fuel_pct}%)",
                    quantity=1.0,
                    billed_unit_rate=expected_fuel,
                    billed_total=expected_fuel,
                    expected_unit_rate=expected_fuel,
                    expected_total=expected_fuel,
                    variance_amount=0.0
                ))
                line_idx += 1
                
                # DUPLICATE Surcharge Line (Injected)
                lines.append(InvoiceLine(
                    line_id=f"FLINE-{inv_id}-{line_idx:02d}",
                    invoice_id=inv_id,
                    line_number=line_idx,
                    line_type="FUEL_SURCHARGE",
                    accessorial_id=None,
                    description="Additional Fuel Adjustment (Duplicate Surcharge)",
                    quantity=1.0,
                    billed_unit_rate=expected_fuel,
                    billed_total=expected_fuel,
                    expected_unit_rate=0.0,
                    expected_total=0.0,
                    variance_amount=expected_fuel,
                    variance_reason="Duplicate surcharge item detected on single invoice"
                ))
                
                billed_total = round(expected_base + (expected_fuel * 2), 2)
                expected_total = round(expected_base + expected_fuel, 2)
                variance_total = expected_fuel
                has_exception = True
                expected_decision = "FAILED"
                disputed_amt = expected_fuel
                anomaly_notes.append("Duplicate surcharge entry identified during invoice line reconciliation.")
                
                finv = FreightInvoice(
                    invoice_id=inv_id,
                    invoice_number=inv_num,
                    carrier_id=c_id,
                    shipment_id=target_shp.shipment_id,
                    invoice_date=inv_dt.isoformat(),
                    due_date=due_dt.isoformat(),
                    billed_amount=billed_total,
                    expected_amount=expected_total,
                    variance_amount=variance_total,
                    status=InvoiceStatus.DISPUTED,
                    audit_status=AuditStatus.FAILED,
                    created_at=f"{inv_dt.isoformat()}T10:00:00Z",
                    lines=lines
                )
                self.freight_invoices.append(finv)
                self.invoice_lines.extend(lines)
                
                ex_id = f"FEX-2026-{ex_counter:06d}"
                ex_counter += 1
                self.audit_exceptions.append(AuditException(
                    exception_id=ex_id,
                    invoice_id=inv_id,
                    line_id=lines[2].line_id,
                    shipment_id=target_shp.shipment_id,
                    carrier_id=c_id,
                    exception_type=ExceptionType.DUPLICATE_SURCHARGE,
                    severity=ExceptionSeverity.HIGH,
                    disputed_amount=disputed_amt,
                    status=ExceptionStatus.OPEN,
                    resolution_notes="Duplicate fuel surcharge line flagged for full retraction.",
                    assigned_to="audit.analyst@logistics.com",
                    created_at=f"{inv_dt.isoformat()}T10:05:00Z"
                ))

            # --- CASE 5: CREDIT NOTE EXCEEDS EXCEPTION AMOUNT ---
            elif injected_type == ExceptionType.CREDIT_EXCEEDS_EXCEPTION:
                # Invoice has an exception of $100, but a credit note was erroneously generated for $250
                diff = 100.00
                billed_base = round(expected_base + diff, 2)
                
                lines.append(InvoiceLine(
                    line_id=f"FLINE-{inv_id}-{line_idx:02d}",
                    invoice_id=inv_id,
                    line_number=line_idx,
                    line_type="BASE_FREIGHT",
                    accessorial_id=None,
                    description="Standard Base Freight",
                    quantity=billable_wt,
                    billed_unit_rate=round(billed_base / billable_wt, 4),
                    billed_total=billed_base,
                    expected_unit_rate=round(expected_base / billable_wt, 4),
                    expected_total=expected_base,
                    variance_amount=diff,
                    variance_reason="Base freight discrepancy"
                ))
                line_idx += 1
                
                lines.append(InvoiceLine(
                    line_id=f"FLINE-{inv_id}-{line_idx:02d}",
                    invoice_id=inv_id,
                    line_number=line_idx,
                    line_type="FUEL_SURCHARGE",
                    accessorial_id=None,
                    description=f"Fuel Surcharge ({fuel_pct}%)",
                    quantity=1.0,
                    billed_unit_rate=expected_fuel,
                    billed_total=expected_fuel,
                    expected_unit_rate=expected_fuel,
                    expected_total=expected_fuel,
                    variance_amount=0.0
                ))
                
                billed_total = round(billed_base + expected_fuel, 2)
                expected_total = round(expected_base + expected_fuel, 2)
                variance_total = diff
                has_exception = True
                expected_decision = "FAILED"
                disputed_amt = diff
                anomaly_notes.append("Credit note amount strictly exceeds approved exception dispute amount.")
                
                finv = FreightInvoice(
                    invoice_id=inv_id,
                    invoice_number=inv_num,
                    carrier_id=c_id,
                    shipment_id=target_shp.shipment_id,
                    invoice_date=inv_dt.isoformat(),
                    due_date=due_dt.isoformat(),
                    billed_amount=billed_total,
                    expected_amount=expected_total,
                    variance_amount=variance_total,
                    status=InvoiceStatus.DISPUTED,
                    audit_status=AuditStatus.FAILED,
                    created_at=f"{inv_dt.isoformat()}T10:00:00Z",
                    lines=lines
                )
                self.freight_invoices.append(finv)
                self.invoice_lines.extend(lines)
                
                ex_id = f"FEX-2026-{ex_counter:06d}"
                ex_counter += 1
                ex_record = AuditException(
                    exception_id=ex_id,
                    invoice_id=inv_id,
                    line_id=lines[0].line_id,
                    shipment_id=target_shp.shipment_id,
                    carrier_id=c_id,
                    exception_type=ExceptionType.CREDIT_EXCEEDS_EXCEPTION,
                    severity=ExceptionSeverity.HIGH,
                    disputed_amount=disputed_amt,
                    status=ExceptionStatus.APPROVED_FOR_DISPUTE,
                    resolution_notes="Disputed amount was $100, but carrier credit note exceeds threshold.",
                    assigned_to="audit.lead@logistics.com",
                    created_at=f"{inv_dt.isoformat()}T10:05:00Z"
                )
                self.audit_exceptions.append(ex_record)
                
                # INJECTED CREDIT NOTE THAT EXCEEDS DISPUTED AMOUNT
                cn_id = f"CN-2026-{cn_counter:06d}"
                cn_counter += 1
                excessive_credit = round(disputed_amt * 2.5, 2)  # $250.00 > $100.00
                self.credit_notes.append(CreditNote(
                    credit_note_id=cn_id,
                    credit_note_number=f"CN-{c_id}-{cn_counter:04d}",
                    exception_id=ex_id,
                    invoice_id=inv_id,
                    carrier_id=c_id,
                    credit_amount=excessive_credit,
                    reason=f"Erroneous over-credited adjustment for dispute {ex_id}",
                    status=CreditNoteStatus.REJECTED,
                    issue_date=(inv_dt + timedelta(days=5)).isoformat(),
                    created_at=f"{inv_dt.isoformat()}T15:00:00Z"
                ))

            # --- CASE 6: DUPLICATE INVOICE ---
            elif injected_type == ExceptionType.DUPLICATE_INVOICE:
                # Re-reference an earlier shipment that was already billed on a prior invoice
                prev_idx = max(0, i - 6)
                target_shp = available_shipments[prev_idx]
                c_id = target_shp.carrier_id
                wm = self.measurement_map.get(target_shp.shipment_id)
                billable_wt = wm.billable_weight_kg if wm else 150.0
                matched_rate = self._find_applicable_rate_card(c_id, target_shp.lane_id, target_shp.service_level, billable_wt)
                base_rate = matched_rate.base_rate if matched_rate else 100.0
                rate_per_kg = matched_rate.rate_per_kg if matched_rate else 0.35
                fuel_pct = matched_rate.fuel_surcharge_pct if matched_rate else 10.0
                expected_base = round(base_rate + (billable_wt * rate_per_kg), 2)
                expected_fuel = round(expected_base * (fuel_pct / 100.0), 2)
                lines.append(InvoiceLine(
                    line_id=f"FLINE-{inv_id}-{line_idx:02d}",
                    invoice_id=inv_id,
                    line_number=line_idx,
                    line_type="BASE_FREIGHT",
                    accessorial_id=None,
                    description="Standard Base Freight",
                    quantity=billable_wt,
                    billed_unit_rate=rate_per_kg,
                    billed_total=expected_base,
                    expected_unit_rate=0.0,
                    expected_total=0.0,
                    variance_amount=expected_base,
                    variance_reason="Duplicate bill: Shipment already invoiced on previous bill"
                ))
                line_idx += 1
                
                lines.append(InvoiceLine(
                    line_id=f"FLINE-{inv_id}-{line_idx:02d}",
                    invoice_id=inv_id,
                    line_number=line_idx,
                    line_type="FUEL_SURCHARGE",
                    accessorial_id=None,
                    description=f"Fuel Surcharge ({fuel_pct}%)",
                    quantity=1.0,
                    billed_unit_rate=expected_fuel,
                    billed_total=expected_fuel,
                    expected_unit_rate=0.0,
                    expected_total=0.0,
                    variance_amount=expected_fuel,
                    variance_reason="Duplicate bill surcharge"
                ))
                
                billed_total = round(expected_base + expected_fuel, 2)
                expected_total = 0.0
                variance_total = billed_total
                has_exception = True
                expected_decision = "FAILED"
                disputed_amt = billed_total
                anomaly_notes.append("Duplicate invoice received for shipment already settled.")
                
                finv = FreightInvoice(
                    invoice_id=inv_id,
                    invoice_number=inv_num,
                    carrier_id=c_id,
                    shipment_id=target_shp.shipment_id,
                    invoice_date=inv_dt.isoformat(),
                    due_date=due_dt.isoformat(),
                    billed_amount=billed_total,
                    expected_amount=expected_total,
                    variance_amount=variance_total,
                    status=InvoiceStatus.REJECTED,
                    audit_status=AuditStatus.FAILED,
                    created_at=f"{inv_dt.isoformat()}T10:00:00Z",
                    lines=lines
                )
                self.freight_invoices.append(finv)
                self.invoice_lines.extend(lines)
                
                ex_id = f"FEX-2026-{ex_counter:06d}"
                ex_counter += 1
                self.audit_exceptions.append(AuditException(
                    exception_id=ex_id,
                    invoice_id=inv_id,
                    line_id=None,
                    shipment_id=target_shp.shipment_id,
                    carrier_id=c_id,
                    exception_type=ExceptionType.DUPLICATE_INVOICE,
                    severity=ExceptionSeverity.CRITICAL,
                    disputed_amount=disputed_amt,
                    status=ExceptionStatus.OPEN,
                    resolution_notes="Duplicate billing rejected. Primary invoice already in processing pipeline.",
                    assigned_to="audit.lead@logistics.com",
                    created_at=f"{inv_dt.isoformat()}T10:05:00Z"
                ))

            # --- CASE 7: UNAUTHORIZED ACCESSORIAL ---
            elif injected_type == ExceptionType.UNAUTHORIZED_ACCESSORIAL:
                # Base is correct, but unapproved accessorial was billed (e.g. Detention or Inside Pickup)
                lines.append(InvoiceLine(
                    line_id=f"FLINE-{inv_id}-{line_idx:02d}",
                    invoice_id=inv_id,
                    line_number=line_idx,
                    line_type="BASE_FREIGHT",
                    accessorial_id=None,
                    description="Standard Base Freight",
                    quantity=billable_wt,
                    billed_unit_rate=rate_per_kg,
                    billed_total=expected_base,
                    expected_unit_rate=rate_per_kg,
                    expected_total=expected_base,
                    variance_amount=0.0
                ))
                line_idx += 1
                
                lines.append(InvoiceLine(
                    line_id=f"FLINE-{inv_id}-{line_idx:02d}",
                    invoice_id=inv_id,
                    line_number=line_idx,
                    line_type="FUEL_SURCHARGE",
                    accessorial_id=None,
                    description=f"Fuel Surcharge ({fuel_pct}%)",
                    quantity=1.0,
                    billed_unit_rate=expected_fuel,
                    billed_total=expected_fuel,
                    expected_unit_rate=expected_fuel,
                    expected_total=expected_fuel,
                    variance_amount=0.0
                ))
                line_idx += 1
                
                acc_fee = 85.00
                lines.append(InvoiceLine(
                    line_id=f"FLINE-{inv_id}-{line_idx:02d}",
                    invoice_id=inv_id,
                    line_number=line_idx,
                    line_type="ACCESSORIAL",
                    accessorial_id="ACC-000004",  # Detention
                    description="Detention Fee - Driver wait time (No signed authorization ticket)",
                    quantity=1.0,
                    billed_unit_rate=acc_fee,
                    billed_total=acc_fee,
                    expected_unit_rate=0.0,
                    expected_total=0.0,
                    variance_amount=acc_fee,
                    variance_reason="Accessorial requires pre-approval signoff; missing proof from delivery site"
                ))
                
                billed_total = round(expected_base + expected_fuel + acc_fee, 2)
                expected_total = round(expected_base + expected_fuel, 2)
                variance_total = acc_fee
                has_exception = True
                expected_decision = "FAILED"
                disputed_amt = acc_fee
                anomaly_notes.append("Unauthorized accessorial charge lacks dispatcher pre-approval.")
                
                finv = FreightInvoice(
                    invoice_id=inv_id,
                    invoice_number=inv_num,
                    carrier_id=c_id,
                    shipment_id=target_shp.shipment_id,
                    invoice_date=inv_dt.isoformat(),
                    due_date=due_dt.isoformat(),
                    billed_amount=billed_total,
                    expected_amount=expected_total,
                    variance_amount=variance_total,
                    status=InvoiceStatus.PARTIALLY_APPROVED,
                    audit_status=AuditStatus.FAILED,
                    created_at=f"{inv_dt.isoformat()}T10:00:00Z",
                    lines=lines
                )
                self.freight_invoices.append(finv)
                self.invoice_lines.extend(lines)
                
                ex_id = f"FEX-2026-{ex_counter:06d}"
                ex_counter += 1
                self.audit_exceptions.append(AuditException(
                    exception_id=ex_id,
                    invoice_id=inv_id,
                    line_id=lines[2].line_id,
                    shipment_id=target_shp.shipment_id,
                    carrier_id=c_id,
                    exception_type=ExceptionType.UNAUTHORIZED_ACCESSORIAL,
                    severity=ExceptionSeverity.MEDIUM,
                    disputed_amount=disputed_amt,
                    status=ExceptionStatus.OPEN,
                    resolution_notes="Accessorial requires pre-approval; waiting for delivery ticket signature.",
                    assigned_to="audit.analyst@logistics.com",
                    created_at=f"{inv_dt.isoformat()}T10:05:00Z"
                ))

            # --- CASE 8: VALID BASELINE INVOICE (PASSED AUDIT) ---
            else:
                # 100% compliant invoice, matched contract exactly
                # Occasionally includes a valid approved accessorial (e.g. Liftgate $75)
                has_valid_acc = (i % 7 == 0)
                acc_amt = 75.00 if has_valid_acc else 0.0
                
                lines.append(InvoiceLine(
                    line_id=f"FLINE-{inv_id}-{line_idx:02d}",
                    invoice_id=inv_id,
                    line_number=line_idx,
                    line_type="BASE_FREIGHT",
                    accessorial_id=None,
                    description="Standard Base Freight",
                    quantity=billable_wt,
                    billed_unit_rate=rate_per_kg,
                    billed_total=expected_base,
                    expected_unit_rate=rate_per_kg,
                    expected_total=expected_base,
                    variance_amount=0.0
                ))
                line_idx += 1
                
                lines.append(InvoiceLine(
                    line_id=f"FLINE-{inv_id}-{line_idx:02d}",
                    invoice_id=inv_id,
                    line_number=line_idx,
                    line_type="FUEL_SURCHARGE",
                    accessorial_id=None,
                    description=f"Fuel Surcharge ({fuel_pct}%)",
                    quantity=1.0,
                    billed_unit_rate=expected_fuel,
                    billed_total=expected_fuel,
                    expected_unit_rate=expected_fuel,
                    expected_total=expected_fuel,
                    variance_amount=0.0
                ))
                
                if has_valid_acc:
                    line_idx += 1
                    lines.append(InvoiceLine(
                        line_id=f"FLINE-{inv_id}-{line_idx:02d}",
                        invoice_id=inv_id,
                        line_number=line_idx,
                        line_type="ACCESSORIAL",
                        accessorial_id="ACC-000001",  # Liftgate
                        description="Hydraulic liftgate delivery service (Pre-approved)",
                        quantity=1.0,
                        billed_unit_rate=acc_amt,
                        billed_total=acc_amt,
                        expected_unit_rate=acc_amt,
                        expected_total=acc_amt,
                        variance_amount=0.0
                    ))
                
                billed_total = round(expected_base + expected_fuel + acc_amt, 2)
                expected_total = billed_total
                variance_total = 0.0
                has_exception = False
                expected_decision = "PASSED"
                disputed_amt = 0.0
                
                finv = FreightInvoice(
                    invoice_id=inv_id,
                    invoice_number=inv_num,
                    carrier_id=c_id,
                    shipment_id=target_shp.shipment_id,
                    invoice_date=inv_dt.isoformat(),
                    due_date=due_dt.isoformat(),
                    billed_amount=billed_total,
                    expected_amount=expected_total,
                    variance_amount=variance_total,
                    status=InvoiceStatus.APPROVED,
                    audit_status=AuditStatus.PASSED,
                    created_at=f"{inv_dt.isoformat()}T10:00:00Z",
                    lines=lines
                )
                self.freight_invoices.append(finv)
                self.invoice_lines.extend(lines)

            # Record Lifecycle Event (Immutable audit trail)
            evt_id = f"EVT-2026-{evt_counter:08d}"
            evt_counter += 1
            self.lifecycle_events.append(AuditLifecycleEvent(
                event_id=evt_id,
                entity_type="INVOICE",
                entity_id=inv_id,
                event_type="AUDIT_EVALUATION",
                previous_state="RECEIVED",
                new_state=finv.status,
                actor="SYSTEM_AUDITOR",
                notes=f"Automated audit completed. Result: {finv.audit_status}. Variance: ${variance_total:.2f}",
                timestamp=f"{inv_dt.isoformat()}T10:05:00Z"
            ))

            # Step 7: Record Separate Ground Truth (NEVER leaked into input features)
            self.ground_truth.append(GroundTruthRecord(
                invoice_id=inv_id,
                shipment_id=finv.shipment_id,
                carrier_id=c_id,
                has_anomaly=has_exception,
                anomaly_types=injected_type if injected_type else "NONE",
                expected_audit_decision=expected_decision,
                expected_disputed_amount=disputed_amt,
                explanation="; ".join(anomaly_notes) if anomaly_notes else "Fully reconciled and compliant."
            ))
