"""
Repository Layer for Challan Management.

Encapsulates all database access for Challan entities.
The Service Layer depends on this -- never on the ORM directly.

This is the SAME Repository Pattern from project 12, but here it serves
as the DATA ACCESS layer that the Service Layer orchestrates.
"""

from .models import Challan, ChallanItem, ChallanStageLog


class ChallanRepository:
    """
    Repository for Challan CRUD and query operations.

    The Service Layer calls these methods instead of touching the ORM.
    This keeps the service testable (you can mock the repository) and
    keeps data-access concerns out of business logic.
    """

    def __init__(self):
        self.model = Challan

    def all(self):
        """Return all challans with prefetched items for performance."""
        return self.model.objects.prefetch_related('items', 'stage_logs').all()

    def find(self, pk):
        """Find a single challan by primary key, or return None."""
        try:
            return self.model.objects.prefetch_related(
                'items', 'stage_logs'
            ).get(pk=pk)
        except self.model.DoesNotExist:
            return None

    def create(self, data):
        """Create a new Challan from a dictionary of field values."""
        return self.model.objects.create(**data)

    def update(self, pk, data):
        """
        Update a Challan by pk. Returns the updated instance or None.
        """
        try:
            challan = self.model.objects.get(pk=pk)
            for field, value in data.items():
                setattr(challan, field, value)
            challan.save()
            return challan
        except self.model.DoesNotExist:
            return None

    def delete(self, pk):
        """Delete a Challan by pk. Returns True if deleted, False otherwise."""
        try:
            challan = self.model.objects.get(pk=pk)
            challan.delete()
            return True
        except self.model.DoesNotExist:
            return False

    def get_by_order(self, order_id):
        """Get all challans for a specific order."""
        return self.model.objects.filter(order_id=order_id)

    def get_pending_authorization(self):
        """Get all challans that are still Under Review."""
        return self.model.objects.filter(is_authorized='0')

    def get_by_stage(self, stage):
        """Get all challans currently at a specific stage."""
        return self.model.objects.filter(current_stage=stage)

    def count(self):
        """Return total count of challans."""
        return self.model.objects.count()


class ChallanItemRepository:
    """Repository for ChallanItem operations."""

    def __init__(self):
        self.model = ChallanItem

    def create(self, data):
        return self.model.objects.create(**data)

    def bulk_create(self, items_list):
        """Create multiple items at once."""
        objects = [self.model(**item) for item in items_list]
        return self.model.objects.bulk_create(objects)

    def get_by_challan(self, challan_id):
        return self.model.objects.filter(challan_id=challan_id)


class ChallanStageLogRepository:
    """Repository for ChallanStageLog operations."""

    def __init__(self):
        self.model = ChallanStageLog

    def create(self, data):
        return self.model.objects.create(**data)

    def get_by_challan(self, challan_id):
        return self.model.objects.filter(challan_id=challan_id).order_by('changed_at')
