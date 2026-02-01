# apps/wallet/apps.py
from django.apps import AppConfig

class WalletConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.wallet'  # <--- This MUST be the full path
    verbose_name = 'Wallet Management'