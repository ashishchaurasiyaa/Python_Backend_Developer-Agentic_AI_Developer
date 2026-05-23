"""
Service Layer for Challan Management.
=====================================

THIS IS THE KEY FILE IN THIS PROJECT.

The Service Layer pattern places a THIN layer of application logic between
the views (presentation) and the repositories (data access).  It is the
single place where business rules, validations, and multi-step workflows
live.

WHY THIS MATTERS AT YOUNGMAN
-----------------------------
In the real Youngman ERP, ChallanService.php is a 53 KB file with a
12-step createChallan() method.  It handles:
  1. Validate order exists and is approved
  2. Check inventory availability
  3. Generate sequential challan number (DC-000001 / PC-000001)
  4. Create challan header record
  5. Create challan line items
  6. Create initial stage log entry
  7. Update order status
  8. Reserve inventory
  9. Trigger notification to logistics team
 10. Create freight entry
 11. Generate PDF
 12. Return challan details

All of that is business logic that does NOT belong in a view or a model.
The Service Layer is the right home for it.

PRINCIPLES
----------
- Views are THIN: they parse HTTP, call the service, return HTTP.
- Models are THIN: they define structure, not workflow.
- Services are FAT: they contain business rules and orchestration.
- Repositories handle data access: the service never touches the ORM.
- Dependency Injection: the service takes a repository in __init__,
  making it trivially testable with mocks.
"""

from decimal import Decimal
from django.db import transaction

from .models import Challan, ChallanItem, ChallanStageLog
from .repositories import (
    ChallanRepository,
    ChallanItemRepository,
    ChallanStageLogRepository,
)


class ChallanServiceError(Exception):
    """Custom exception for service-layer business rule violations."""
    pass


class ChallanService:
    """
    Orchestrates all Challan business logic.

    This class is the HEART of the Service Layer pattern.  Every business
    rule, every validation, every multi-step workflow lives here -- NOT
    in views, NOT in models.

    Usage:
        service = ChallanService()          # default repositories
        service = ChallanService(repo=mock) # injected for testing
    """

    # ------------------------------------------------------------------
    # Stage flow: defines the ONLY valid stage transitions.
    # A Delivery challan goes through all stages.
    # A Pickup challan goes through the same stages in reverse context.
    # ------------------------------------------------------------------
    STAGE_FLOW = {
        'PLANNING_DONE': 'GENERATED_CHALLAN',
        'GENERATED_CHALLAN': 'VEHICLE_EXIT',
        'VEHICLE_EXIT': 'ARRIVAL_AT_SITE',
        'ARRIVAL_AT_SITE': 'INSTALLATION_DONE',
        'INSTALLATION_DONE': 'SITE_EXIT',
        'SITE_EXIT': 'ARRIVAL_AT_BRANCH',
    }

    REQUIRED_FIELDS = [
        'challan_type',
        'challan_movement_type',
        'order_id',
        'pickup_location',
        'delivery_location',
    ]

    def __init__(self, repository=None, item_repository=None,
                 stage_log_repository=None):
        """
        Dependency Injection: accept repositories from outside.
        Falls back to real implementations for production use.
        """
        self.repository = repository or ChallanRepository()
        self.item_repository = item_repository or ChallanItemRepository()
        self.stage_log_repository = (
            stage_log_repository or ChallanStageLogRepository()
        )

    # ==================================================================
    # CREATE CHALLAN -- the multi-step workflow
    # ==================================================================
    @transaction.atomic
    def create_challan(self, data):
        """
        Create a new Challan with full business validation.

        Steps (mirrors the real Youngman 12-step flow, simplified):
          1. Validate required fields
          2. Generate sequential challan number
          3. Set initial stage
          4. Create challan via repository
          5. Create initial stage log entry
          6. Return the created challan

        Args:
            data (dict): Challan field values from the API request.

        Returns:
            Challan: The newly created challan instance.

        Raises:
            ChallanServiceError: If validation fails.
        """
        # Step 1: Validate required fields
        self._validate_required_fields(data)

        # Step 2: Validate challan_type
        challan_type = data.get('challan_type')
        if challan_type not in ('Delivery', 'Pickup'):
            raise ChallanServiceError(
                f"Invalid challan_type: '{challan_type}'. "
                f"Must be 'Delivery' or 'Pickup'."
            )

        # Step 3: Validate movement type
        valid_movements = ('delivery', 'pickup', 'inter_branch', 'sales')
        movement = data.get('challan_movement_type')
        if movement not in valid_movements:
            raise ChallanServiceError(
                f"Invalid movement type: '{movement}'. "
                f"Must be one of {valid_movements}."
            )

        # Step 4: Generate challan number
        challan_no = self._generate_challan_number(challan_type)

        # Step 5: Prepare challan data
        challan_data = {
            'challan_no': challan_no,
            'challan_type': challan_type,
            'challan_movement_type': movement,
            'order_id': data['order_id'],
            'pickup_location': data['pickup_location'],
            'delivery_location': data['delivery_location'],
            'dispatch_date': data.get('dispatch_date'),
            'freight_amount': Decimal(str(data.get('freight_amount', '0.00'))),
            'is_authorized': '0',           # Always starts Under Review
            'current_stage': 'PLANNING_DONE',  # Always starts here
        }

        # Step 6: Create via repository
        challan = self.repository.create(challan_data)

        # Step 7: Create initial stage log
        self.stage_log_repository.create({
            'challan_id': challan.pk,
            'from_stage': 'NEW',
            'to_stage': 'PLANNING_DONE',
            'changed_by': data.get('created_by', 'system'),
            'remarks': 'Challan created',
        })

        return challan

    # ==================================================================
    # AUTHORIZE CHALLAN
    # ==================================================================
    @transaction.atomic
    def authorize_challan(self, challan_id, action, remarks=''):
        """
        Authorize or reject a challan.

        Business Rules:
          - Only challans with is_authorized='0' (Under Review) can be processed.
          - action='approve' sets is_authorized='1'
          - action='reject' sets is_authorized='-1'

        Args:
            challan_id (int): The challan PK.
            action (str): 'approve' or 'reject'.
            remarks (str): Optional remarks.

        Returns:
            Challan: The updated challan.

        Raises:
            ChallanServiceError: If challan not found or business rule violated.
        """
        challan = self.repository.find(challan_id)
        if not challan:
            raise ChallanServiceError(
                f"Challan with id {challan_id} not found."
            )

        if challan.is_authorized != '0':
            status_map = {'1': 'Authorized', '-1': 'Rejected'}
            current = status_map.get(challan.is_authorized, 'Unknown')
            raise ChallanServiceError(
                f"Challan {challan.challan_no} is already '{current}'. "
                f"Only 'Under Review' challans can be authorized/rejected."
            )

        if action not in ('approve', 'reject'):
            raise ChallanServiceError(
                f"Invalid action: '{action}'. Must be 'approve' or 'reject'."
            )

        new_status = '1' if action == 'approve' else '-1'
        challan = self.repository.update(challan_id, {
            'is_authorized': new_status,
        })

        # Log the authorization event
        self.stage_log_repository.create({
            'challan_id': challan_id,
            'from_stage': challan.current_stage,
            'to_stage': challan.current_stage,  # Stage doesn't change
            'changed_by': 'authorizer',
            'remarks': f"Authorization: {action}. {remarks}".strip(),
        })

        return challan

    # ==================================================================
    # ADVANCE STAGE
    # ==================================================================
    @transaction.atomic
    def advance_stage(self, challan_id, changed_by=None, remarks=''):
        """
        Move a challan to the next stage in the lifecycle.

        Business Rules:
          - Challan must be authorized (is_authorized='1') to advance.
          - Current stage must have a valid next stage in STAGE_FLOW.
          - ARRIVAL_AT_BRANCH is the final stage -- cannot advance further.

        Args:
            challan_id (int): The challan PK.
            changed_by (str): Who triggered the transition.
            remarks (str): Optional remarks.

        Returns:
            Challan: The updated challan.

        Raises:
            ChallanServiceError: If transition is invalid.
        """
        challan = self.repository.find(challan_id)
        if not challan:
            raise ChallanServiceError(
                f"Challan with id {challan_id} not found."
            )

        # Business rule: must be authorized first
        if challan.is_authorized != '1':
            raise ChallanServiceError(
                f"Challan {challan.challan_no} is not authorized. "
                f"Cannot advance stage until authorized."
            )

        current_stage = challan.current_stage
        next_stage = self.STAGE_FLOW.get(current_stage)

        if not next_stage:
            raise ChallanServiceError(
                f"Challan {challan.challan_no} is at '{current_stage}' "
                f"which is a terminal stage. Cannot advance further."
            )

        # Perform the transition
        challan = self.repository.update(challan_id, {
            'current_stage': next_stage,
        })

        # Log the stage transition
        self.stage_log_repository.create({
            'challan_id': challan_id,
            'from_stage': current_stage,
            'to_stage': next_stage,
            'changed_by': changed_by or 'system',
            'remarks': remarks,
        })

        return challan

    # ==================================================================
    # ADD ITEMS
    # ==================================================================
    def add_items(self, challan_id, items_data):
        """
        Add line items to a challan.

        Args:
            challan_id (int): The challan PK.
            items_data (list[dict]): List of item dicts with keys:
                item_code, item_name, quantity.

        Returns:
            list[ChallanItem]: The created items.

        Raises:
            ChallanServiceError: If challan not found or items invalid.
        """
        challan = self.repository.find(challan_id)
        if not challan:
            raise ChallanServiceError(
                f"Challan with id {challan_id} not found."
            )

        if not items_data or not isinstance(items_data, list):
            raise ChallanServiceError("Items data must be a non-empty list.")

        # Validate each item
        for idx, item in enumerate(items_data):
            if not item.get('item_code'):
                raise ChallanServiceError(
                    f"Item at index {idx} missing 'item_code'."
                )
            if not item.get('item_name'):
                raise ChallanServiceError(
                    f"Item at index {idx} missing 'item_name'."
                )
            if not item.get('quantity') or int(item['quantity']) <= 0:
                raise ChallanServiceError(
                    f"Item at index {idx} must have a positive 'quantity'."
                )

        # Prepare items for bulk creation
        prepared_items = [
            {
                'challan_id': challan_id,
                'item_code': item['item_code'],
                'item_name': item['item_name'],
                'quantity': int(item['quantity']),
                'ok_quantity': int(item.get('ok_quantity', 0)),
                'damaged_quantity': int(item.get('damaged_quantity', 0)),
                'missing_quantity': int(item.get('missing_quantity', 0)),
            }
            for item in items_data
        ]

        return self.item_repository.bulk_create(prepared_items)

    # ==================================================================
    # CLOSE CHALLAN
    # ==================================================================
    @transaction.atomic
    def close_challan(self, challan_id):
        """
        Mark a challan as CLOSED (final stage after ARRIVAL_AT_BRANCH).

        Business Rules:
          - Only challans at ARRIVAL_AT_BRANCH can be closed.
          - Must be authorized.

        Args:
            challan_id (int): The challan PK.

        Returns:
            Challan: The closed challan.
        """
        challan = self.repository.find(challan_id)
        if not challan:
            raise ChallanServiceError(
                f"Challan with id {challan_id} not found."
            )

        if challan.is_authorized != '1':
            raise ChallanServiceError(
                f"Challan {challan.challan_no} is not authorized. "
                f"Cannot close."
            )

        if challan.current_stage != 'ARRIVAL_AT_BRANCH':
            raise ChallanServiceError(
                f"Challan {challan.challan_no} is at '{challan.current_stage}'. "
                f"Only challans at 'ARRIVAL_AT_BRANCH' can be closed."
            )

        challan = self.repository.update(challan_id, {
            'current_stage': 'CLOSED',
        })

        self.stage_log_repository.create({
            'challan_id': challan_id,
            'from_stage': 'ARRIVAL_AT_BRANCH',
            'to_stage': 'CLOSED',
            'changed_by': 'system',
            'remarks': 'Challan closed.',
        })

        return challan

    # ==================================================================
    # GET CHALLAN SUMMARY
    # ==================================================================
    def get_challan_summary(self, challan_id):
        """
        Return a comprehensive summary of a challan including items and
        full stage history.

        Args:
            challan_id (int): The challan PK.

        Returns:
            dict: Challan data with nested items and stage_logs.

        Raises:
            ChallanServiceError: If challan not found.
        """
        challan = self.repository.find(challan_id)
        if not challan:
            raise ChallanServiceError(
                f"Challan with id {challan_id} not found."
            )

        items = self.item_repository.get_by_challan(challan_id)
        stage_logs = self.stage_log_repository.get_by_challan(challan_id)

        return {
            'challan': challan,
            'items': items,
            'stage_logs': stage_logs,
        }

    # ==================================================================
    # PRIVATE HELPERS
    # ==================================================================
    def _validate_required_fields(self, data):
        """Ensure all required fields are present and non-empty."""
        missing = [
            field for field in self.REQUIRED_FIELDS
            if not data.get(field)
        ]
        if missing:
            raise ChallanServiceError(
                f"Missing required fields: {', '.join(missing)}"
            )

    def _generate_challan_number(self, challan_type):
        """
        Generate a sequential challan number.

        Format:
          - Delivery challans: DC-000001, DC-000002, ...
          - Pickup challans:   PC-000001, PC-000002, ...

        Uses the total count of challans of that type + 1.
        """
        prefix = 'DC' if challan_type == 'Delivery' else 'PC'
        existing_count = Challan.objects.filter(
            challan_type=challan_type
        ).count()
        next_number = existing_count + 1
        return f"{prefix}-{next_number:06d}"
