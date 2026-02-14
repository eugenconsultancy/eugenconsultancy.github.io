from django.shortcuts import render, redirect
from django.views.generic import FormView, TemplateView
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from .forms import InquiryForm


class ContactView(FormView):
    """
    View for contact/inquiry form
    """
    template_name = 'inquiries/contact.html'
    form_class = InquiryForm
    success_url = '/inquiries/success/'

    def form_valid(self, form):
        # Save the inquiry
        inquiry = form.save(commit=False)
        
        # Capture IP address
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            inquiry.ip_address = x_forwarded_for.split(',')[0]
        else:
            inquiry.ip_address = self.request.META.get('REMOTE_ADDR')
        
        inquiry.save()
        
        # Send email notification
        self.send_notification_email(inquiry)
        
        # Show success message
        messages.success(self.request, 'Thank you for your message. I will get back to you soon!')
        
        return super().form_valid(form)

    def send_notification_email(self, inquiry):
        """
        Send email notification about new inquiry
        """
        subject = f'New Inquiry: {inquiry.subject}'
        message = f"""
        New inquiry received:
        
        Type: {inquiry.get_inquiry_type_display()}
        Name: {inquiry.name}
        Email: {inquiry.email}
        Phone: {inquiry.phone}
        
        Message:
        {inquiry.message}
        
        View in admin: {settings.BASE_URL}/admin/inquiries/inquiry/{inquiry.id}/
        """
        
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [settings.ADMIN_EMAIL],
                fail_silently=True,
            )
        except:
            pass  # Fail silently in development


class SuccessView(TemplateView):
    """
    View for successful form submission
    """
    template_name = 'inquiries/success.html'