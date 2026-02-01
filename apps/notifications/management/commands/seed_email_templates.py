# apps/notifications/management/commands/seed_email_templates.py
from django.core.management.base import BaseCommand
from apps.notifications.models import EmailTemplate
import json


class Command(BaseCommand):
    help = 'Seed initial email templates'
    
    def handle(self, *args, **options):
        templates = [
            {
                'name': 'welcome_email',
                'template_type': 'system',
                'subject': 'Welcome to EBWriting - Your Academic Partner!',
                'body_template': '''<!DOCTYPE html>
<html>
<head><title>Welcome to EBWriting</title></head>
<body style="font-family: Arial, sans-serif; line-height: 1.6;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background-color: #3498db; color: white; padding: 30px; text-align: center;">
            <h1>Welcome to EBWriting!</h1>
        </div>
        <div style="padding: 30px; background-color: #f8f9fa;">
            <h2>Hello {{user_name}},</h2>
            <p>Thank you for joining EBWriting - your trusted academic writing partner.</p>
            <p>We're excited to have you on board. With EBWriting, you can:</p>
            <ul>
                <li>Order high-quality academic papers</li>
                <li>Track your orders in real-time</li>
                <li>Communicate securely with writers</li>
                <li>Request revisions if needed</li>
                <li>Enjoy secure payment processing</li>
            </ul>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{{site_url}}/dashboard" style="background-color: #3498db; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px;">
                    Go to Your Dashboard
                </a>
            </div>
            <p>If you have any questions, feel free to contact our support team at {{support_email}}.</p>
            <p>Best regards,<br>The EBWriting Team</p>
        </div>
        <div style="text-align: center; padding: 20px; color: #7f8c8d; font-size: 12px;">
            <p>&copy; {{current_year}} EBWriting. All rights reserved.</p>
        </div>
    </div>
</body>
</html>''',
                'plain_text_template': '''Welcome to EBWriting!

Hello {{user_name}},

Thank you for joining EBWriting - your trusted academic writing partner.

We're excited to have you on board. With EBWriting, you can:
- Order high-quality academic papers
- Track your orders in real-time
- Communicate securely with writers
- Request revisions if needed
- Enjoy secure payment processing

Get started: {{site_url}}/dashboard

If you have any questions, feel free to contact our support team at {{support_email}}.

Best regards,
The EBWriting Team

© {{current_year}} EBWriting. All rights reserved.''',
                'placeholders': json.dumps([
                    {
                        'name': 'user_name',
                        'description': 'Full name of the user',
                        'required': True
                    },
                    {
                        'name': 'site_url',
                        'description': 'Base URL of the website',
                        'required': True
                    },
                    {
                        'name': 'support_email',
                        'description': 'Support email address',
                        'required': True
                    },
                    {
                        'name': 'current_year',
                        'description': 'Current year',
                        'required': True
                    }
                ])
            },
            {
                'name': 'order_confirmation',
                'template_type': 'order_update',
                'subject': 'Order Confirmation - Order #{{order_id}}',
                'body_template': '''<!DOCTYPE html>
<html>
<head><title>Order Confirmation</title></head>
<body style="font-family: Arial, sans-serif; line-height: 1.6;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background-color: #27ae60; color: white; padding: 30px; text-align: center;">
            <h1>Order Confirmed!</h1>
            <p style="font-size: 18px;">Order #{{order_id}} - {{order_title}}</p>
        </div>
        <div style="padding: 30px; background-color: #f8f9fa;">
            <h2>Hello {{user_name}},</h2>
            <p>Your order has been confirmed and is now being processed.</p>
            
            <div style="background-color: white; padding: 20px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #27ae60;">
                <h3>Order Details</h3>
                <p><strong>Order ID:</strong> #{{order_id}}</p>
                <p><strong>Title:</strong> {{order_title}}</p>
                <p><strong>Deadline:</strong> {{deadline}}</p>
                <p><strong>Amount Paid:</strong> {{amount}}</p>
            </div>
            
            <p><strong>Next Steps:</strong></p>
            <ol>
                <li>Our team will review your order requirements</li>
                <li>A qualified writer will be assigned to your order</li>
                <li>You'll be notified when the writer starts working</li>
                <li>You can communicate with the writer through our secure messaging system</li>
            </ol>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="{{site_url}}/orders/{{order_id}}" style="background-color: #27ae60; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px;">
                    View Your Order
                </a>
            </div>
            
            <p>If you have any questions about your order, please contact our support team.</p>
            <p>Best regards,<br>The EBWriting Team</p>
        </div>
        <div style="text-align: center; padding: 20px; color: #7f8c8d; font-size: 12px;">
            <p>&copy; {{current_year}} EBWriting. All rights reserved.</p>
        </div>
    </div>
</body>
</html>''',
                'plain_text_template': '''Order Confirmation

Hello {{user_name}},

Your order has been confirmed and is now being processed.

Order Details:
- Order ID: #{{order_id}}
- Title: {{order_title}}
- Deadline: {{deadline}}
- Amount Paid: {{amount}}

Next Steps:
1. Our team will review your order requirements
2. A qualified writer will be assigned to your order
3. You'll be notified when the writer starts working
4. You can communicate with the writer through our secure messaging system

View your order: {{site_url}}/orders/{{order_id}}

If you have any questions about your order, please contact our support team.

Best regards,
The EBWriting Team

© {{current_year}} EBWriting. All rights reserved.''',
                'placeholders': json.dumps([
                    {
                        'name': 'user_name',
                        'description': 'Full name of the user',
                        'required': True
                    },
                    {
                        'name': 'order_id',
                        'description': 'Order ID number',
                        'required': True
                    },
                    {
                        'name': 'order_title',
                        'description': 'Title of the order',
                        'required': True
                    },
                    {
                        'name': 'deadline',
                        'description': 'Order deadline',
                        'required': True
                    },
                    {
                        'name': 'amount',
                        'description': 'Amount paid',
                        'required': True
                    },
                    {
                        'name': 'site_url',
                        'description': 'Base URL of the website',
                        'required': True
                    },
                    {
                        'name': 'current_year',
                        'description': 'Current year',
                        'required': True
                    }
                ])
            },
            {
                'name': 'system_notification',
                'template_type': 'system',
                'subject': '{{notification_title}}',
                'body_template': '''<!DOCTYPE html>
<html>
<head><title>System Notification</title></head>
<body style="font-family: Arial, sans-serif; line-height: 1.6;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background-color: #3498db; color: white; padding: 30px; text-align: center;">
            <h1>EBWriting Notification</h1>
        </div>
        <div style="padding: 30px; background-color: #f8f9fa;">
            <div style="background-color: white; padding: 20px; border-radius: 5px; margin-bottom: 20px; border-left: 4px solid #3498db;">
                <h2 style="margin-top: 0;">{{notification_title}}</h2>
                <p>{{notification_message}}</p>
                {% if action_url %}
                <div style="text-align: center; margin-top: 20px;">
                    <a href="{{site_url}}{{action_url}}" style="background-color: #3498db; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px;">
                        {{action_text|default:"View Details"}}
                    </a>
                </div>
                {% endif %}
            </div>
            
            <p>You received this notification because you have an account with EBWriting.</p>
            
            <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #7f8c8d;">
                <p>Manage your notification preferences in your <a href="{{site_url}}/account/notifications">account settings</a>.</p>
            </div>
        </div>
        <div style="text-align: center; padding: 20px; color: #7f8c8d; font-size: 12px;">
            <p>&copy; {{current_year}} EBWriting. All rights reserved.</p>
        </div>
    </div>
</body>
</html>''',
                'plain_text_template': '''EBWriting Notification

{{notification_title}}

{{notification_message}}

{% if action_url %}
View details: {{site_url}}{{action_url}}
{% endif %}

You received this notification because you have an account with EBWriting.

Manage your notification preferences in your account settings: {{site_url}}/account/notifications

© {{current_year}} EBWriting. All rights reserved.''',
                'placeholders': json.dumps([
                    {
                        'name': 'notification_title',
                        'description': 'Title of the notification',
                        'required': True
                    },
                    {
                        'name': 'notification_message',
                        'description': 'Content of the notification',
                        'required': True
                    },
                    {
                        'name': 'action_url',
                        'description': 'URL for action button',
                        'required': False
                    },
                    {
                        'name': 'action_text',
                        'description': 'Text for action button',
                        'required': False
                    },
                    {
                        'name': 'site_url',
                        'description': 'Base URL of the website',
                        'required': True
                    },
                    {
                        'name': 'current_year',
                        'description': 'Current year',
                        'required': True
                    }
                ])
            },
            {
                'name': 'daily_digest',
                'template_type': 'system',
                'subject': 'Your EBWriting Daily Digest - {{date}}',
                'body_template': '''<!DOCTYPE html>
<html>
<head><title>Daily Digest</title></head>
<body style="font-family: Arial, sans-serif; line-height: 1.6;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background-color: #2c3e50; color: white; padding: 30px; text-align: center;">
            <h1>Your Daily Digest</h1>
            <p style="font-size: 16px;">Summary of your EBWriting activity</p>
        </div>
        <div style="padding: 30px; background-color: #f8f9fa;">
            <div style="text-align: center; color: #7f8c8d; margin-bottom: 30px;">
                <h2 style="margin: 0;">{{date}}</h2>
            </div>
            
            <div style="display: flex; justify-content: space-around; background-color: #ecf0f1; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <div style="text-align: center;">
                    <div style="font-size: 24px; font-weight: bold; color: #2c3e50;">{{notification_count}}</div>
                    <div style="font-size: 12px; color: #7f8c8d;">Notifications</div>
                </div>
                <div style="text-align: center;">
                    <div style="font-size: 24px; font-weight: bold; color: #2c3e50;">1</div>
                    <div style="font-size: 12px; color: #7f8c8d;">Active Orders</div>
                </div>
                <div style="text-align: center;">
                    <div style="font-size: 24px; font-weight: bold; color: #2c3e50;">0</div>
                    <div style="font-size: 12px; color: #7f8c8d;">Messages</div>
                </div>
            </div>
            
            {% if notifications %}
            <h2>Today's Notifications</h2>
            
            {% for notif in notifications %}
            <div style="border-left: 3px solid #3498db; padding: 15px; margin-bottom: 15px; background-color: white; border-radius: 4px;">
                <div style="font-size: 12px; color: #95a5a6; margin-bottom: 5px;">{{notif.time}}</div>
                <div>
                    <h3 style="margin: 0 0 5px 0; font-size: 16px; color: #2c3e50;">{{notif.title}}</h3>
                    <p style="margin: 0; color: #555; font-size: 14px;">{{notif.message}}</p>
                </div>
            </div>
            {% endfor %}
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="{{site_url}}/notifications" style="background-color: #3498db; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; display: inline-block;">
                    View All Notifications
                </a>
            </div>
            {% else %}
            <div style="text-align: center; padding: 40px 20px;">
                <h3>No new notifications today</h3>
                <p>You're all caught up! Check back tomorrow for updates.</p>
            </div>
            {% endif %}
            
            <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd;">
                <h3>Quick Links</h3>
                <p>
                    <a href="{{site_url}}/orders">View Orders</a> | 
                    <a href="{{site_url}}/messages">Check Messages</a> | 
                    <a href="{{site_url}}/account">Account Settings</a>
                </p>
            </div>
        </div>
        <div style="text-align: center; padding: 20px; color: #7f8c8d; font-size: 12px;">
            <p>&copy; {{current_year}} EBWriting. All rights reserved.</p>
            <p>
                <a href="{{site_url}}/notifications/digest/unsubscribe">Unsubscribe from daily digest</a>
            </p>
        </div>
    </div>
</body>
</html>''',
                'plain_text_template': '''Your EBWriting Daily Digest - {{date}}

Hello {{user_name}},

Here's your daily summary of activity on EBWriting.

Today's Statistics:
- Notifications: {{notification_count}}
- Active Orders: 1
- New Messages: 0

{% if notifications %}
Today's Notifications:
{% for notif in notifications %}
{{notif.time}} - {{notif.title}}
{{notif.message}}

{% endfor %}
View all notifications: {{site_url}}/notifications
{% else %}
No new notifications today. You're all caught up!
{% endif %}

Quick Links:
- View Orders: {{site_url}}/orders
- Check Messages: {{site_url}}/messages
- Account Settings: {{site_url}}/account

To unsubscribe from daily digest emails, visit:
{{site_url}}/notifications/digest/unsubscribe

© {{current_year}} EBWriting. All rights reserved.''',
                'placeholders': json.dumps([
                    {
                        'name': 'user_name',
                        'description': 'Full name of the user',
                        'required': True
                    },
                    {
                        'name': 'date',
                        'description': 'Date of the digest',
                        'required': True
                    },
                    {
                        'name': 'notification_count',
                        'description': 'Number of notifications',
                        'required': True
                    },
                    {
                        'name': 'notifications',
                        'description': 'Array of notification objects',
                        'required': False
                    },
                    {
                        'name': 'site_url',
                        'description': 'Base URL of the website',
                        'required': True
                    },
                    {
                        'name': 'current_year',
                        'description': 'Current year',
                        'required': True
                    }
                ])
            }
        ]
        
        created_count = 0
        updated_count = 0
        
        for template_data in templates:
            name = template_data.pop('name')
            
            # Check if template exists
            template, created = EmailTemplate.objects.update_or_create(
                name=name,
                defaults=template_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"Created template: {name}"))
            else:
                updated_count += 1
                template.version += 1
                template.save()
                self.stdout.write(f"Updated template: {name} (v{template.version})")
        
        self.stdout.write(self.style.SUCCESS(
            f"\nSeeding complete: {created_count} created, {updated_count} updated"
        ))