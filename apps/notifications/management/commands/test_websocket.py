# apps/notifications/management/commands/test_websocket.py
import asyncio
import json
import logging
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings

logger = logging.getLogger(__name__)
User = get_user_model()


class Command(BaseCommand):
    help = 'Test WebSocket notifications connection'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--user-email',
            type=str,
            required=True,
            help='Email of user to test notifications for'
        )
        parser.add_argument(
            '--send-test',
            action='store_true',
            help='Send a test notification'
        )
        parser.add_argument(
            '--count',
            type=int,
            default=5,
            help='Number of test notifications to send'
        )
        parser.add_argument(
            '--simulate-only',
            action='store_true',
            help='Only simulate without actual WebSocket connection'
        )
    
    def handle(self, *args, **options):
        user_email = options['user_email']
        send_test = options['send_test']
        count = options['count']
        simulate_only = options['simulate_only']
        
        try:
            user = User.objects.get(email=user_email)
            
            self.stdout.write(f"Testing notifications for user: {user_email}")
            self.stdout.write(f"User ID: {user.id}")
            
            if send_test:
                if simulate_only:
                    self.simulate_test(user, count)
                else:
                    # Run async test
                    try:
                        asyncio.run(self.run_test_async(user, count))
                    except ImportError:
                        self.stdout.write(self.style.WARNING(
                            "WebSocket client not available. Install with: pip install websockets"
                        ))
                        self.stdout.write("Running simulation instead...")
                        self.simulate_test(user, count)
            else:
                self.stdout.write("Use --send-test to send test notifications")
        
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"User {user_email} not found"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))
    
    def simulate_test(self, user, count):
        """Simulate WebSocket test without actual connection."""
        self.stdout.write(self.style.WARNING("SIMULATION MODE - No actual WebSocket connection"))
        
        from apps.notifications.websocket_utils import WebSocketNotificationService
        from django.utils import timezone
        
        for i in range(count):
            test_data = {
                'id': f'test-notification-{i}',
                'title': f'Test Notification {i+1}',
                'message': f'This is a simulated test notification #{i+1}',
                'category': 'system',
                'notification_type': 'info',
                'priority': 2,
                'action_url': '/notifications/',
                'action_text': 'View',
                'context_data': {'test': True, 'iteration': i+1},
                'timestamp': timezone.now().isoformat(),
                'unread_count': i + 1
            }
            
            # Try to send via WebSocket (will work if Channels is running)
            try:
                WebSocketNotificationService.send_notification_to_user(
                    user_id=str(user.id),
                    notification_data=test_data
                )
                self.stdout.write(self.style.SUCCESS(
                    f"Simulated notification {i+1} sent via WebSocket utils"
                ))
            except Exception as e:
                self.stdout.write(self.style.WARNING(
                    f"Could not send WebSocket notification {i+1}: {e}"
                ))
            
            # Also test other notification types
            if i % 4 == 0:
                # Test order update
                order_data = {
                    'order_id': f'#TEST{i:03d}',
                    'order_title': f'Test Order {i}',
                    'status': 'in_progress',
                    'old_status': 'assigned',
                    'message': f'Order #{i:03d} status updated',
                    'action_url': f'/orders/#TEST{i:03d}'
                }
                WebSocketNotificationService.send_order_update(
                    user_id=str(user.id),
                    order_data=order_data
                )
                self.stdout.write(f"  Sent order update: {order_data['order_id']}")
            
            elif i % 4 == 1:
                # Test new message
                message_data = {
                    'message_id': f'test-message-{i}',
                    'conversation_id': f'test-conv-{i}',
                    'order_id': f'#TEST{i:03d}',
                    'sender_id': 'system',
                    'sender_name': 'Test System',
                    'preview': f'Test message preview #{i}',
                    'action_url': f'/orders/#TEST{i:03d}/messages'
                }
                WebSocketNotificationService.send_new_message(
                    user_id=str(user.id),
                    message_data=message_data
                )
                self.stdout.write(f"  Sent new message notification")
            
            elif i % 4 == 2:
                # Test payment update
                payment_data = {
                    'payment_id': f'test-payment-{i}',
                    'order_id': f'#TEST{i:03d}',
                    'status': 'completed',
                    'amount': '100.00',
                    'currency': 'USD',
                    'message': f'Payment of $100.00 completed',
                    'action_url': f'/payments/test-payment-{i}'
                }
                WebSocketNotificationService.send_payment_update(
                    user_id=str(user.id),
                    payment_data=payment_data
                )
                self.stdout.write(f"  Sent payment update")
            
            # Update unread count
            WebSocketNotificationService.update_unread_count(
                user_id=str(user.id),
                count=i + 1
            )
            self.stdout.write(f"  Updated unread count: {i + 1}")
            
            # Small delay between simulations
            import time
            time.sleep(0.5)
        
        self.stdout.write(self.style.SUCCESS(f"Simulated {count} test notifications"))
    
    async def run_test_async(self, user, count):
        """Run actual async WebSocket test."""
        try:
            import websockets
        except ImportError:
            raise ImportError(
                "WebSocket client library not installed. "
                "Install with: pip install websockets"
            )
        
        # For JWT authentication, we would need a token
        # Since this is a test command, we'll simulate the connection
        # In production, you would get a JWT token for the user
        
        self.stdout.write(self.style.WARNING(
            "Note: Actual WebSocket connection requires JWT authentication.\n"
            "This simulation uses the WebSocket utility methods instead."
        ))
        
        # Fall back to simulation
        self.simulate_test(user, count)