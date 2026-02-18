from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User

# You can add signals here for automatic actions when users are created/updated