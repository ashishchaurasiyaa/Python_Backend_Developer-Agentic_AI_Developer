"""
DRF serializers for Challan Management.

Deliberately dumb. In a Service Layer architecture the serializer's job
stops at "is this well-formed JSON of roughly the right shape?" — every
BUSINESS rule (is this movement type legal, can this challan be advanced,
what challan number comes next) belongs to ChallanService, not here.

That split is the thing to point at in an interview: DRF makes it very
tempting to put business logic in serializer.validate() or in a
ModelViewSet, and that is exactly how you end up with rules duplicated
across three endpoints.
"""
from rest_framework import serializers

from .models import Challan, ChallanItem, ChallanStageLog


class ChallanItemSerializer(serializers.ModelSerializer):
    """A line item on a challan."""

    class Meta:
        model = ChallanItem
        fields = [
            'id',
            'challan',
            'item_code',
            'item_name',
            'quantity',
            'ok_quantity',
            'damaged_quantity',
            'missing_quantity',
        ]
        read_only_fields = ['id', 'challan']


class ChallanStageLogSerializer(serializers.ModelSerializer):
    """One row of the stage-transition audit trail."""

    class Meta:
        model = ChallanStageLog
        fields = [
            'id',
            'challan',
            'from_stage',
            'to_stage',
            'changed_by',
            'remarks',
            'changed_at',
        ]
        read_only_fields = fields


class ChallanSerializer(serializers.ModelSerializer):
    """Full challan representation with nested items and stage history."""

    items = ChallanItemSerializer(many=True, read_only=True)
    stage_logs = ChallanStageLogSerializer(many=True, read_only=True)
    authorization_status = serializers.CharField(
        source='get_is_authorized_display', read_only=True)

    class Meta:
        model = Challan
        fields = [
            'id',
            'challan_no',
            'challan_type',
            'challan_movement_type',
            'order_id',
            'pickup_location',
            'delivery_location',
            'dispatch_date',
            'is_authorized',
            'authorization_status',
            'current_stage',
            'freight_amount',
            'created_at',
            'updated_at',
            'items',
            'stage_logs',
        ]
        read_only_fields = fields


class ChallanListSerializer(serializers.ModelSerializer):
    """Lighter representation for list endpoints."""

    class Meta:
        model = Challan
        fields = [
            'id',
            'challan_no',
            'challan_type',
            'challan_movement_type',
            'order_id',
            'pickup_location',
            'delivery_location',
            'dispatch_date',
            'is_authorized',
            'current_stage',
            'freight_amount',
            'created_at',
        ]
        read_only_fields = fields


# ----------------------------------------------------------------------
# Input serializers - shape only, no business rules.
# ----------------------------------------------------------------------

class CreateChallanSerializer(serializers.Serializer):
    """
    Input for POST /api/challans/.

    Note what is NOT here: challan_no (the service generates it),
    is_authorized and current_stage (the service forces the starting
    values). Letting a client set those would let it skip the workflow.
    """

    challan_type = serializers.CharField()
    challan_movement_type = serializers.CharField()
    order_id = serializers.IntegerField()
    pickup_location = serializers.CharField()
    delivery_location = serializers.CharField()
    dispatch_date = serializers.DateField(required=False, allow_null=True)
    freight_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, default='0.00')
    created_by = serializers.CharField(required=False, default='system')


class AuthorizeChallanSerializer(serializers.Serializer):
    """Input for the authorize endpoint."""

    action = serializers.CharField()
    remarks = serializers.CharField(required=False, default='', allow_blank=True)


class AdvanceStageSerializer(serializers.Serializer):
    """Input for the advance-stage endpoint."""

    changed_by = serializers.CharField(required=False, default='system')
    remarks = serializers.CharField(required=False, default='', allow_blank=True)


class AddItemsSerializer(serializers.Serializer):
    """Input for the add-items endpoint — a list of raw item dicts."""

    items = serializers.ListField(child=serializers.DictField(), allow_empty=False)
