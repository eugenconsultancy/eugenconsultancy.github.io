# apps/documents/management/commands/generate_documents.py
from django.core.management.base import BaseCommand
from django.utils import timezone
import logging

from apps.documents.services import PDFGenerationService
from apps.orders.models import Order

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Generate missing documents for orders'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--order-id',
            type=str,
            help='Generate documents for specific order ID'
        )
        parser.add_argument(
            '--document-type',
            type=str,
            choices=['invoice', 'summary', 'delivery', 'certificate', 'all'],
            default='all',
            help='Type of document to generate'
        )
        parser.add_argument(
            '--status',
            type=str,
            choices=['paid', 'delivered', 'completed', 'all'],
            default='all',
            help='Generate for orders with specific status'
        )
    
    def handle(self, *args, **options):
        order_id = options['order_id']
        doc_type = options['document_type']
        status = options['status']
        
        # Build queryset
        if order_id:
            orders = Order.objects.filter(order_id=order_id)
            if not orders.exists():
                self.stdout.write(self.style.ERROR(f"Order {order_id} not found"))
                return
        else:
            orders = Order.objects.all()
            
            if status != 'all':
                status_map = {
                    'paid': 'paid',
                    'delivered': 'delivered',
                    'completed': 'completed'
                }
                orders = orders.filter(status=status_map[status])
        
        self.stdout.write(f"Processing {orders.count()} orders...")
        
        generated_count = 0
        error_count = 0
        
        for order in orders:
            try:
                documents_generated = []
                
                # Generate invoices for paid orders
                if doc_type in ['invoice', 'all'] and order.status in ['paid', 'assigned', 'in_progress', 'delivered', 'completed']:
                    invoice = PDFGenerationService.generate_invoice(order)
                    if invoice:
                        documents_generated.append('invoice')
                
                # Generate order summaries
                if doc_type in ['summary', 'all']:
                    summary = PDFGenerationService.generate_order_summary(order)
                    if summary:
                        documents_generated.append('summary')
                
                # Generate delivery covers for delivered orders
                if doc_type in ['delivery', 'all'] and order.status in ['delivered', 'completed']:
                    delivery_cover = PDFGenerationService.generate_delivery_cover(order)
                    if delivery_cover:
                        documents_generated.append('delivery_cover')
                
                # Generate completion certificates for completed orders
                if doc_type in ['certificate', 'all'] and order.status == 'completed':
                    certificate = PDFGenerationService.generate_completion_certificate(order)
                    if certificate:
                        documents_generated.append('completion_certificate')
                
                if documents_generated:
                    generated_count += 1
                    self.stdout.write(self.style.SUCCESS(
                        f"Order #{order.order_id}: Generated {', '.join(documents_generated)}"
                    ))
                else:
                    self.stdout.write(
                        f"Order #{order.order_id}: No documents generated (status: {order.status})"
                    )
                    
            except Exception as e:
                error_count += 1
                self.stdout.write(self.style.ERROR(
                    f"Order #{order.order_id}: Error generating documents - {e}"
                ))
                logger.error(f"Error generating documents for order {order.order_id}: {e}")
        
        self.stdout.write("\n" + "="*50)
        self.stdout.write(self.style.SUCCESS(
            f"Generation complete: {generated_count} orders processed, "
            f"{error_count} errors"
        ))
        logger.info(
            f"Document generation command completed: "
            f"{generated_count} orders processed, {error_count} errors"
        )