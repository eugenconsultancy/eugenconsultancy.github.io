from .assignment_service import AssignmentService
from .delivery_service import DeliveryService
from .dispute_trigger import DisputeService

# apps/orders/services/__init__.py
class OrderService:
    """Dummy OrderService for migration."""
    pass

class AssignmentService:
    pass

class DeliveryService:
    pass

class DisputeService:
    pass

__all__ = ['OrderService', 'AssignmentService', 'DeliveryService', 'DisputeService']