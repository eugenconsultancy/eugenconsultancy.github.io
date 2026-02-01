"""
Search and filter views for orders.
"""
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, TemplateView
from django.db.models import Q
from django.utils import timezone
from django.http import JsonResponse
import csv
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View

from apps.orders.models import Order
from apps.orders.forms import OrderFilterForm, OrderSearchForm


class OrderSearchView(LoginRequiredMixin, ListView):
    """View for searching orders."""
    model = Order
    template_name = 'orders/search.html'
    context_object_name = 'orders'
    paginate_by = 20
    
    def get_queryset(self):
        """Return search results based on query parameters."""
        user = self.request.user
        form = OrderSearchForm(self.request.GET)
        
        if not form.is_valid():
            return Order.objects.none()
        
        search_field = form.cleaned_data['search_field']
        search_query = form.cleaned_data['search_query']
        exact_match = form.cleaned_data['exact_match']
        case_sensitive = form.cleaned_data['case_sensitive']
        
        # Base queryset based on user role
        if user.is_staff:
            queryset = Order.objects.all()
        elif user.is_client:
            queryset = Order.objects.filter(client=user)
        elif user.is_writer:
            queryset = Order.objects.filter(writer=user)
        else:
            return Order.objects.none()
        
        # Apply search filters
        if search_query:
            if exact_match:
                if case_sensitive:
                    filter_kwargs = {f'{search_field}__exact': search_query}
                else:
                    filter_kwargs = {f'{search_field}__iexact': search_query}
            else:
                if case_sensitive:
                    filter_kwargs = {f'{search_field}__contains': search_query}
                else:
                    filter_kwargs = {f'{search_field}__icontains': search_query}
            
            # Special handling for email searches
            if search_field in ['client_email', 'writer_email']:
                if search_field == 'client_email':
                    queryset = queryset.filter(client__email__icontains=search_query)
                else:
                    queryset = queryset.filter(writer__email__icontains=search_query)
            else:
                queryset = queryset.filter(**filter_kwargs)
        
        return queryset.select_related('client', 'writer').order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        """Add search form to context."""
        context = super().get_context_data(**kwargs)
        context['search_form'] = OrderSearchForm(self.request.GET)
        context['search_query'] = self.request.GET.get('search_query', '')
        context['total_results'] = self.get_queryset().count()
        return context


class OrderFilterView(LoginRequiredMixin, TemplateView):
    """View for filtering orders."""
    template_name = 'orders/filter.html'
    
    def get_context_data(self, **kwargs):
        """Add filter options to context."""
        context = super().get_context_data(**kwargs)
        context['filter_form'] = OrderFilterForm(self.request.GET)
        
        # Get filter counts
        user = self.request.user
        
        if user.is_staff:
            base_queryset = Order.objects.all()
        elif user.is_client:
            base_queryset = Order.objects.filter(client=user)
        elif user.is_writer:
            base_queryset = Order.objects.filter(writer=user)
        else:
            base_queryset = Order.objects.none()
        
        # Get counts by state
        state_counts = {}
        for state_code, state_name in Order.STATE_CHOICES:
            state_counts[state_code] = base_queryset.filter(state=state_code).count()
        
        # Get counts by academic level
        level_counts = {}
        for level_code, level_name in Order.AcademicLevel.choices:
            level_counts[level_code] = base_queryset.filter(academic_level=level_code).count()
        
        # Get counts by urgency
        urgency_counts = {}
        for urgency_code, urgency_name in Order.UrgencyLevel.choices:
            urgency_counts[urgency_code] = base_queryset.filter(urgency=urgency_code).count()
        
        context.update({
            'state_counts': state_counts,
            'level_counts': level_counts,
            'urgency_counts': urgency_counts,
            'total_orders': base_queryset.count(),
        })
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle filter form submission."""
        form = OrderFilterForm(request.POST)
        if form.is_valid():
            # Build URL with filter parameters
            params = []
            
            if form.cleaned_data.get('state'):
                params.append(f'state={form.cleaned_data["state"]}')
            
            if form.cleaned_data.get('academic_level'):
                params.append(f'academic_level={form.cleaned_data["academic_level"]}')
            
            if form.cleaned_data.get('date_from'):
                params.append(f'date_from={form.cleaned_data["date_from"]}')
            
            if form.cleaned_data.get('date_to'):
                params.append(f'date_to={form.cleaned_data["date_to"]}')
            
            if form.cleaned_data.get('search'):
                params.append(f'search={form.cleaned_data["search"]}')
            
            if params:
                return redirect(f'{reverse("orders:list")}?{"&".join(params)}')
        
        return self.get(request, *args, **kwargs)


class ExportOrdersView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Export orders to CSV."""
    
    def test_func(self):
        return self.request.user.is_staff
    
    def get(self, request, *args, **kwargs):
        """Export orders as CSV."""
        # Get filter parameters
        state = request.GET.get('state')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        
        # Build queryset
        queryset = Order.objects.all().select_related('client', 'writer')
        
        if state:
            queryset = queryset.filter(state=state)
        
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="orders_export.csv"'
        
        writer = csv.writer(response)
        
        # Write header
        writer.writerow([
            'Order Number', 'Title', 'Client Email', 'Writer Email',
            'Status', 'Academic Level', 'Subject', 'Pages', 'Words',
            'Price', 'Writer Payment', 'Platform Fee',
            'Deadline', 'Created At', 'Completed At'
        ])
        
        # Write data
        for order in queryset:
            writer.writerow([
                order.order_number,
                order.title,
                order.client.email if order.client else '',
                order.writer.email if order.writer else '',
                order.get_state_display(),
                order.get_academic_level_display(),
                order.subject,
                order.pages,
                order.words,
                str(order.price),
                str(order.writer_payment),
                str(order.platform_fee),
                order.deadline.strftime('%Y-%m-%d %H:%M:%S') if order.deadline else '',
                order.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                order.completed_at.strftime('%Y-%m-%d %H:%M:%S') if order.completed_at else ''
            ])
        
        return response