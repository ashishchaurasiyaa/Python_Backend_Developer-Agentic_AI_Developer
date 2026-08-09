"""
Builder Pattern — SAP document / E-Way Bill payload assembly.
=============================================================

Direct translation of the production `SapDocumentsLinesBuilder.php` and
`EwayBillPayloadBuilder.php` from the Youngman ERP.

THE PROBLEM THIS SOLVES
-----------------------
An E-Way Bill payload has about thirty fields. Roughly six are mandatory,
the rest depend on circumstances: a vehicle number only if transport is by
road, a transporter ID only for a third-party carrier, distance only when
the portal cannot infer it, tax split depending on whether the movement
crosses a state line. Written as a constructor it reads:

    payload = EwayBillPayload(
        'Outward', 2, '27AAA...', 'Y Equipment', 'Bhiwandi', 421302, 27,
        '29BBB...', 'Metro', 'Worli', 400018, 27, None, 'Road', 45, ...
    )

Nobody can review that. Which `None` was the vehicle number? Swap two
adjacent integers and you have silently filed a bill against the wrong
pincode — a real compliance problem, not a style complaint.

TWO BUILDER FLAVOURS LIVE HERE, AND THEY ARE NOT THE SAME THING
---------------------------------------------------------------
1. `PayloadBuilder` — the FLUENT builder. The caller drives it, choosing
   which optional steps to invoke and in whatever order suits them, then
   calls build(). Validation happens once, at build() time, and reports
   *every* problem at once rather than the first.

2. `BaseEwayBillBuilder` — the ABSTRACT builder. Here the STEP SEQUENCE is
   fixed by the base class and SUBCLASSES vary individual steps. A
   Delivery swaps consignor and consignee relative to a Pickup, and
   nothing else differs.

Flavour 2 shades into Template Method, and an interviewer may well push on
that. The honest distinction: Template Method's product is usually a side
effect or a scalar, while a Builder's product is a complex object assembled
piece by piece — and the Builder keeps the partially-built object as state
so construction can be paused, inspected and resumed. Both are true here;
saying so is a better answer than insisting on a clean taxonomy.

`PayloadDirector` is the third piece: it encodes the two or three payload
recipes the business actually uses, so callers stop hand-rolling the same
step sequence in four different places.
"""
from abc import ABC, abstractmethod
from decimal import Decimal


# GST rates. Kept module-level so a rate change is a one-line diff.
CGST_RATE = Decimal('0.09')
SGST_RATE = Decimal('0.09')
IGST_RATE = Decimal('0.18')


class BuilderValidationError(Exception):
    """
    Raised by build() when the assembled payload is incomplete.

    Carries the FULL list of problems, not just the first one — a caller
    fixing a payload wants every missing field in one round trip.
    """

    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__('; '.join(self.errors))


def _money(value):
    """Round to paise, the way the GST portal expects."""
    return Decimal(value).quantize(Decimal('0.01'))


# ----------------------------------------------------------------------
# FLAVOUR 1 — the fluent builder
# ----------------------------------------------------------------------

class PayloadBuilder:
    """
    Fluent, step-by-step builder for a SAP / E-Way Bill payload.

    Every `with_*` method returns self, so calls chain:

        payload = (PayloadBuilder()
                   .for_draft(draft)
                   .with_supply_direction('Outward')
                   .with_consignor_from_company()
                   .with_consignee_from_customer()
                   .with_transport(vehicle_number='MH-04-AB-1234')
                   .with_lines_from_draft()
                   .with_taxes()
                   .build())

    Read that aloud and it says what it does. That readability IS the
    deliverable — everything else the pattern gives you is secondary.
    """

    #: Fields that must be present before build() will succeed.
    REQUIRED_KEYS = [
        'supply_type',
        'transaction_type',
        'gstin_of_consignor',
        'gstin_of_consignee',
        'item_list',
    ]

    def __init__(self):
        self.reset()

    # -- lifecycle ------------------------------------------------------

    def reset(self):
        """
        Clear all accumulated state.

        Called automatically by build(), so one builder instance can safely
        produce several payloads in a loop. Forgetting this is the classic
        Builder bug: the second payload silently inherits the first one's
        line items.
        """
        self._draft = None
        self._payload = {}
        self._items = []
        self._tax_mode = None
        self._steps = []
        return self

    def _record(self, step):
        self._steps.append(step)

    @property
    def steps_applied(self):
        """Which build steps have run so far — useful for debugging."""
        return list(self._steps)

    def peek(self):
        """
        Inspect the partially-built payload WITHOUT finishing it.

        This is the capability that most clearly separates a Builder from
        a plain factory function: the half-built product is addressable.
        """
        snapshot = dict(self._payload)
        snapshot['item_list'] = list(self._items)
        return snapshot

    # -- source ---------------------------------------------------------

    def for_draft(self, draft):
        """Attach the draft that later steps read their defaults from."""
        self._draft = draft
        self._payload['U_ReferenceNo'] = draft.reference_no
        self._payload['doc_date'] = draft.posting_date.isoformat()
        self._record('for_draft')
        return self

    # -- header ---------------------------------------------------------

    def with_supply_direction(self, supply_type=None):
        """
        Outward for a delivery, Inward for a pickup.

        Defaults from the draft's doc_type, but stays overridable — some
        inter-branch movements are filed the other way round.
        """
        if supply_type is None:
            self._require_draft('with_supply_direction')
            supply_type = 'Outward' if self._draft.doc_type == 'delivery' else 'Inward'

        self._payload['supply_type'] = supply_type
        self._payload['transaction_type'] = 2 if supply_type == 'Outward' else 3
        self._record('with_supply_direction')
        return self

    def with_consignor_from_company(self):
        """Company godown is the sender (the delivery case)."""
        self._require_draft('with_consignor_from_company')
        draft = self._draft
        self._payload.update({
            'gstin_of_consignor': draft.from_gstin,
            'name_of_consignor': 'Y Equipment Services PVT. LTD.',
            'address_of_consignor': draft.from_address,
            'pincode_of_consignor': draft.from_pincode,
            'state_of_consignor': draft.from_state_code,
        })
        self._record('with_consignor_from_company')
        return self

    def with_consignee_from_customer(self):
        """Customer site is the receiver (the delivery case)."""
        self._require_draft('with_consignee_from_customer')
        draft = self._draft
        self._payload.update({
            'gstin_of_consignee': draft.to_gstin or 'URP',
            'name_of_consignee': draft.card_name,
            'address_of_consignee': draft.to_address,
            'pincode_of_consignee': draft.to_pincode,
            'state_of_consignee': draft.to_state_code,
        })
        self._record('with_consignee_from_customer')
        return self

    def with_consignor_from_customer(self):
        """Customer site is the sender (the pickup case)."""
        self._require_draft('with_consignor_from_customer')
        draft = self._draft
        self._payload.update({
            'gstin_of_consignor': draft.to_gstin or 'URP',
            'name_of_consignor': draft.card_name,
            'address_of_consignor': draft.to_address,
            'pincode_of_consignor': draft.to_pincode,
            'state_of_consignor': draft.to_state_code,
        })
        self._record('with_consignor_from_customer')
        return self

    def with_consignee_from_company(self):
        """Company godown is the receiver (the pickup case)."""
        self._require_draft('with_consignee_from_company')
        draft = self._draft
        self._payload.update({
            'gstin_of_consignee': draft.from_gstin,
            'name_of_consignee': 'Y Equipment Services PVT. LTD.',
            'address_of_consignee': draft.from_address,
            'pincode_of_consignee': draft.from_pincode,
            'state_of_consignee': draft.from_state_code,
        })
        self._record('with_consignee_from_company')
        return self

    # -- optional steps -------------------------------------------------

    def with_transport(self, vehicle_number=None, transport_mode=None,
                       transporter_id=None, distance_km=None):
        """
        Attach transport details. Every argument falls back to the draft.

        Genuinely optional: a payload filed before a vehicle is assigned
        simply skips this step.
        """
        draft = self._draft
        self._payload.update({
            'vehicle_number': vehicle_number
            or (draft.vehicle_number if draft else '') or '',
            'transport_mode': transport_mode
            or (draft.transport_mode if draft else 'Road') or 'Road',
            'transporter_id': transporter_id
            or (draft.transporter_id if draft else '') or '',
            'distance': distance_km
            if distance_km is not None
            else (draft.distance_km if draft else None),
        })
        self._record('with_transport')
        return self

    def with_comments(self, comments=None):
        """Free-text remarks."""
        if comments is None and self._draft:
            comments = self._draft.comments
        self._payload['comments'] = comments or ''
        self._record('with_comments')
        return self

    def with_warehouses(self, from_warehouse=None, to_warehouse=None):
        """SAP warehouse codes, which the GST portal ignores but SAP needs."""
        draft = self._draft
        self._payload['from_warehouse'] = (
            from_warehouse or (draft.from_warehouse if draft else '') or '')
        self._payload['to_warehouse'] = (
            to_warehouse or (draft.to_warehouse if draft else '') or '')
        self._record('with_warehouses')
        return self

    # -- lines ----------------------------------------------------------

    def with_line(self, item_code, quantity, rate, item_name='',
                  hsn_code='', unit='NOS'):
        """
        Append one line by hand.

        Accumulates rather than replaces, so this can be called in a loop.
        """
        quantity = Decimal(str(quantity))
        rate = Decimal(str(rate))
        self._items.append({
            'product_name': item_name or item_code,
            'item_code': item_code,
            'hsn_code': hsn_code,
            'quantity': float(quantity),
            'unit': unit,
            'rate': float(rate),
            'taxable_amount': float(_money(quantity * rate)),
        })
        self._record('with_line')
        return self

    def with_lines_from_draft(self):
        """Append every line on the attached draft."""
        self._require_draft('with_lines_from_draft')
        for line in self._draft.lines.all():
            self.with_line(
                item_code=line.item_code,
                quantity=line.quantity,
                rate=line.rate,
                item_name=line.item_name,
                hsn_code=line.hsn_code,
                unit=line.unit,
            )
        self._record('with_lines_from_draft')
        return self

    # -- taxes ----------------------------------------------------------

    def with_taxes(self, intra_state=None):
        """
        Compute the GST split over whatever lines exist SO FAR.

        Deliberately order-sensitive, and the validation in build() catches
        the mistake: call this before adding lines and the totals are zero.
        Making it lazy would hide a real modelling question (which lines is
        this bill for?) behind convenience.
        """
        if intra_state is None:
            intra_state = self._draft.is_intra_state if self._draft else False

        taxable = sum(
            (Decimal(str(item['taxable_amount'])) for item in self._items),
            Decimal('0'),
        )

        if intra_state:
            cgst, sgst, igst = (_money(taxable * CGST_RATE),
                                _money(taxable * SGST_RATE),
                                Decimal('0.00'))
        else:
            cgst, sgst, igst = (Decimal('0.00'), Decimal('0.00'),
                                _money(taxable * IGST_RATE))

        self._tax_mode = 'intra' if intra_state else 'inter'
        self._payload.update({
            'tax_mode': self._tax_mode,
            'total_value': float(_money(taxable)),
            'cgst_value': float(cgst),
            'sgst_value': float(sgst),
            'igst_value': float(igst),
            'grand_total': float(_money(taxable + cgst + sgst + igst)),
        })
        self._record('with_taxes')
        return self

    # -- terminal step --------------------------------------------------

    def build(self):
        """
        Validate and return the finished payload, then reset the builder.

        Returns a plain dict. The builder keeps no reference to it, so the
        caller cannot reach back through the builder and mutate a payload
        that has already been filed.
        """
        payload = dict(self._payload)
        payload['item_list'] = list(self._items)

        errors = self._validate(payload)
        if errors:
            raise BuilderValidationError(errors)

        self.reset()
        return payload

    def _validate(self, payload):
        errors = []
        for key in self.REQUIRED_KEYS:
            if not payload.get(key):
                errors.append(f"missing required field '{key}'")

        if payload.get('item_list') and 'total_value' not in payload:
            errors.append(
                'lines were added but with_taxes() never ran, so the payload '
                'has no amounts'
            )

        if payload.get('item_list') and payload.get('total_value') == 0:
            errors.append(
                'total_value is 0 with lines present — with_taxes() probably '
                'ran before the lines were added'
            )

        if payload.get('transport_mode') == 'Road' and \
                'vehicle_number' in payload and not payload['vehicle_number']:
            errors.append('transport mode is Road but no vehicle_number was set')

        return errors

    def _require_draft(self, step):
        if self._draft is None:
            raise BuilderValidationError(
                [f'{step}() needs a draft — call for_draft() first']
            )


# ----------------------------------------------------------------------
# FLAVOUR 2 — the abstract builder, steps fixed, subclasses vary them
# ----------------------------------------------------------------------

class BaseEwayBillBuilder(ABC):
    """
    Abstract builder whose step SEQUENCE is fixed in build().

    Subclasses override only the three steps that genuinely differ between
    a delivery and a pickup. Everything else — transport, items, amounts —
    is shared, so a GST rule change is edited once.
    """

    def __init__(self, draft, params=None):
        self.draft = draft
        self.params = params or {}
        self._payload = {}

    def build(self):
        """The fixed six-step assembly order."""
        self._payload = {}
        self._payload.update(self._get_supply_type())
        self._payload.update(self._get_consignor_details())
        self._payload.update(self._get_consignee_details())
        self._payload.update(self._get_transport_details())
        self._payload['item_list'] = self._get_items()
        self._payload.update(self._get_amounts())
        self._payload['U_ReferenceNo'] = self.draft.reference_no
        return dict(self._payload)

    # -- steps subclasses MUST provide ----------------------------------

    @abstractmethod
    def _get_supply_type(self):
        """Outward/Inward plus the numeric transaction type."""

    @abstractmethod
    def _get_consignor_details(self):
        """Whoever is sending the material in this direction."""

    @abstractmethod
    def _get_consignee_details(self):
        """Whoever is receiving it."""

    # -- steps shared by every subclass ---------------------------------

    def _get_transport_details(self):
        return {
            'transporter_id': self.params.get(
                'transporter_id', self.draft.transporter_id),
            'transport_mode': self.params.get(
                'mode', self.draft.transport_mode or 'Road'),
            'vehicle_number': self.params.get(
                'vehicle_no', self.draft.vehicle_number),
            'distance': self.params.get('distance', self.draft.distance_km),
        }

    def _get_items(self):
        return [
            {
                'product_name': line.item_name or line.item_code,
                'item_code': line.item_code,
                'hsn_code': line.hsn_code,
                'quantity': float(line.quantity),
                'unit': line.unit,
                'taxable_amount': float(_money(line.amount)),
            }
            for line in self.draft.lines.all()
        ]

    def _get_amounts(self):
        total = sum(
            (line.amount for line in self.draft.lines.all()), Decimal('0'))
        total = _money(total)
        intra = self.draft.is_intra_state
        return {
            'total_value': float(total),
            'cgst_value': float(_money(total * CGST_RATE)) if intra else 0.0,
            'sgst_value': float(_money(total * SGST_RATE)) if intra else 0.0,
            'igst_value': 0.0 if intra else float(_money(total * IGST_RATE)),
        }

    def _company_party(self):
        return {
            'gstin': self.draft.from_gstin,
            'name': 'Y Equipment Services PVT. LTD.',
            'address': self.draft.from_address,
            'pincode': self.draft.from_pincode,
            'state': self.draft.from_state_code,
        }

    def _customer_party(self):
        return {
            'gstin': self.draft.to_gstin or 'URP',
            'name': self.draft.card_name,
            'address': self.draft.to_address,
            'pincode': self.draft.to_pincode,
            'state': self.draft.to_state_code,
        }

    @staticmethod
    def _as_consignor(party):
        return {
            'gstin_of_consignor': party['gstin'],
            'name_of_consignor': party['name'],
            'address_of_consignor': party['address'],
            'pincode_of_consignor': party['pincode'],
            'state_of_consignor': party['state'],
        }

    @staticmethod
    def _as_consignee(party):
        return {
            'gstin_of_consignee': party['gstin'],
            'name_of_consignee': party['name'],
            'address_of_consignee': party['address'],
            'pincode_of_consignee': party['pincode'],
            'state_of_consignee': party['state'],
        }


class DeliveryEwayBillBuilder(BaseEwayBillBuilder):
    """Company godown -> customer site."""

    def _get_supply_type(self):
        return {'supply_type': 'Outward', 'transaction_type': 2}

    def _get_consignor_details(self):
        return self._as_consignor(self._company_party())

    def _get_consignee_details(self):
        return self._as_consignee(self._customer_party())


class PickupEwayBillBuilder(BaseEwayBillBuilder):
    """Customer site -> company godown. Only the two parties swap."""

    def _get_supply_type(self):
        return {'supply_type': 'Inward', 'transaction_type': 3}

    def _get_consignor_details(self):
        return self._as_consignor(self._customer_party())

    def _get_consignee_details(self):
        return self._as_consignee(self._company_party())


EWAY_BILL_BUILDERS = {
    'delivery': DeliveryEwayBillBuilder,
    'pickup': PickupEwayBillBuilder,
}


def get_eway_bill_builder(draft, params=None):
    """Pick the direction-specific builder for a draft."""
    builder_class = EWAY_BILL_BUILDERS.get(draft.doc_type)
    if builder_class is None:
        raise ValueError(
            f"No E-Way Bill builder for doc_type '{draft.doc_type}'. "
            f"Known types: {sorted(EWAY_BILL_BUILDERS)}"
        )
    return builder_class(draft, params)


# ----------------------------------------------------------------------
# DIRECTOR — the recipes the business actually uses
# ----------------------------------------------------------------------

class PayloadDirector:
    """
    Knows the standard step sequences so callers do not have to.

    The Builder gives you *freedom* to assemble a payload any way you like.
    The Director gives you back *consistency* for the two or three ways you
    actually want. Both matter: without the builder every recipe would be a
    bespoke function, and without the director every caller re-derives the
    same sequence and one of them gets it subtly wrong.
    """

    def __init__(self, builder=None):
        self.builder = builder or PayloadBuilder()

    def build_delivery(self, draft, **transport):
        """Full outward payload: company -> customer, taxes, transport."""
        return (self.builder.reset()
                .for_draft(draft)
                .with_supply_direction('Outward')
                .with_consignor_from_company()
                .with_consignee_from_customer()
                .with_warehouses()
                .with_transport(**transport)
                .with_comments()
                .with_lines_from_draft()
                .with_taxes()
                .build())

    def build_pickup(self, draft, **transport):
        """Full inward payload: customer -> company, taxes, transport."""
        return (self.builder.reset()
                .for_draft(draft)
                .with_supply_direction('Inward')
                .with_consignor_from_customer()
                .with_consignee_from_company()
                .with_warehouses()
                .with_transport(**transport)
                .with_comments()
                .with_lines_from_draft()
                .with_taxes()
                .build())

    def build_minimal(self, draft):
        """
        Smallest payload that still validates — no transport, no comments.

        Used when a bill must be filed before a vehicle is assigned.
        """
        return (self.builder.reset()
                .for_draft(draft)
                .with_supply_direction()
                .with_consignor_from_company()
                .with_consignee_from_customer()
                .with_lines_from_draft()
                .with_taxes()
                .build())

    def build_for_draft(self, draft, **transport):
        """Pick the recipe from the draft's own direction."""
        if draft.doc_type == 'pickup':
            return self.build_pickup(draft, **transport)
        return self.build_delivery(draft, **transport)


# ----------------------------------------------------------------------
# Persistence helper
# ----------------------------------------------------------------------

def save_payload(draft, payload, builder_used, recipe=''):
    """Record a built payload for audit."""
    from .models import BuiltPayload

    return BuiltPayload.objects.create(
        draft=draft,
        builder_used=builder_used,
        recipe=recipe,
        payload=payload,
        line_count=len(payload.get('item_list', [])),
        taxable_value=Decimal(str(payload.get('total_value', 0))),
        cgst_value=Decimal(str(payload.get('cgst_value', 0))),
        sgst_value=Decimal(str(payload.get('sgst_value', 0))),
        igst_value=Decimal(str(payload.get('igst_value', 0))),
        total_value=Decimal(str(
            payload.get('grand_total',
                        payload.get('total_value', 0)))),
    )
