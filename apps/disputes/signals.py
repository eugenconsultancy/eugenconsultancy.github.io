from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Dispute

@receiver(post_save, sender=Dispute)
def handle_dispute_creation(sender, instance, created, **kwargs):
    if created:
        # Logic to lock the order or notify the writer
        order = instance.order
        order.status = 'DISPUTED'
        order.save()