from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import CreateView, UpdateView, DetailView, ListView
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.core.paginator import Paginator

from .models import Review, ReviewResponse, ReviewFlag, WriterRatingSummary
from .moderation import ReviewModerationService, ReviewAnalyticsService
from ..accounts.decorators import writer_required, customer_required, admin_required, client_required
from ..orders.models import Order


@method_decorator([login_required, customer_required], name='dispatch')
class CreateReviewView(CreateView):
    """Create a review for completed order"""
    model = Review
    fields = [
        'rating', 'comment', 'communication_rating',
        'timeliness_rating', 'quality_rating', 'adherence_rating'
    ]
    template_name = 'reviews/create.html'
    
    def dispatch(self, request, *args, **kwargs):
        self.order = get_object_or_404(Order, id=self.kwargs['order_id'])
        
        # Check permissions
        if self.order.customer != request.user:
            raise PermissionDenied("You can only review your own orders")
        
        if self.order.status != 'completed':
            raise PermissionDenied("You can only review completed orders")
        
        # Check if review already exists
        if Review.objects.filter(order=self.order, customer=request.user).exists():
            messages.warning(request, "You have already reviewed this order.")
            return redirect('orders:order_detail', pk=self.order.id)
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Customize form widgets
        for field_name in ['rating', 'communication_rating', 'timeliness_rating', 
                          'quality_rating', 'adherence_rating']:
            form.fields[field_name].widget.attrs.update({
                'min': 1,
                'max': 5,
                'class': 'rating-input'
            })
        return form
    
    def form_valid(self, form):
        try:
            with transaction.atomic():
                review = form.save(commit=False)
                review.order = self.order
                review.customer = self.request.user
                review.writer = self.order.writer
                review.ip_address = self.request.META.get('REMOTE_ADDR')
                review.save()
            
            messages.success(self.request, 'Thank you for your review!')
            return redirect('orders:order_detail', pk=self.order.id)
            
        except Exception as e:
            messages.error(self.request, f'Error submitting review: {str(e)}')
            return self.form_invalid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['order'] = self.order
        return context
    
    def get_success_url(self):
        return reverse_lazy('orders:order_detail', kwargs={'pk': self.order.id})


@method_decorator([login_required, writer_required], name='dispatch')
class CreateReviewResponseView(CreateView):
    """Create response to a review"""
    model = ReviewResponse
    fields = ['response_text']
    template_name = 'reviews/create_response.html'
    
    def dispatch(self, request, *args, **kwargs):
        self.review = get_object_or_404(Review, id=self.kwargs['review_id'])
        
        # Check permissions
        if self.review.writer != request.user:
            raise PermissionDenied("You can only respond to your own reviews")
        
        # Check if response already exists
        if hasattr(self.review, 'response'):
            messages.warning(request, "You have already responded to this review.")
            return redirect('reviews:view', pk=self.review.id)
        
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        try:
            with transaction.atomic():
                response = form.save(commit=False)
                response.review = self.review
                response.writer = self.request.user
                response.save()
            
            messages.success(self.request, 'Response submitted for moderation.')
            return redirect('reviews:view', pk=self.review.id)
            
        except Exception as e:
            messages.error(self.request, f'Error submitting response: {str(e)}')
            return self.form_invalid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['review'] = self.review
        return context
    
    def get_success_url(self):
        return reverse_lazy('reviews:view', kwargs={'pk': self.review.id})


@method_decorator(login_required, name='dispatch')
class ReviewDetailView(DetailView):
    """View a review"""
    model = Review
    template_name = 'reviews/detail.html'
    context_object_name = 'review'
    
    def get_queryset(self):
        return Review.objects.select_related(
            'order', 'customer', 'writer'
        ).prefetch_related('response')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Check if user can flag this review
        context['can_flag'] = (
            self.request.user != self.object.customer and
            not ReviewFlag.objects.filter(
                review=self.object,
                reporter=self.request.user
            ).exists()
        )
        
        # Check if user can mark as helpful
        # (Implementation would require a HelpfulVote model)
        
        return context


@method_decorator([login_required, writer_required], name='dispatch')
class WriterReviewsView(ListView):
    """View all reviews for a writer"""
    model = Review
    template_name = 'reviews/writer_reviews.html'
    context_object_name = 'reviews'
    paginate_by = 20
    
    def get_queryset(self):
        return Review.objects.filter(
            writer=self.request.user,
            is_approved=True,
            is_active=True
        ).select_related('order', 'customer').order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get rating summary
        summary, created = WriterRatingSummary.objects.get_or_create(
            writer=self.request.user
        )
        if created:
            summary.update_summary()
        
        context['rating_summary'] = summary
        
        # Get recent statistics
        context['recent_stats'] = ReviewAnalyticsService.get_review_statistics('30d')
        
        return context

@method_decorator([login_required, customer_required], name='dispatch')
class SelectOrderForReviewView(ListView):
    """View to select which completed order to review"""
    template_name = 'reviews/select_order.html'
    context_object_name = 'completed_orders'
    
    def get_queryset(self):
        # Get completed orders that haven't been reviewed yet
        from ..orders.models import Order
        
        return Order.objects.filter(
            customer=self.request.user,
            status='completed'
        ).exclude(
            review__isnull=False  # Exclude orders that already have reviews
        ).order_by('-completed_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_orders'] = self.get_queryset().count()
        return context
    
@login_required
@require_http_methods(['POST'])
def flag_review(request, review_id):
    """Flag a review for moderation"""
    try:
        review = get_object_or_404(Review, id=review_id)
        
        # Check if user already flagged this review
        if ReviewFlag.objects.filter(review=review, reporter=request.user).exists():
            return JsonResponse({
                'success': False,
                'error': 'You have already flagged this review'
            })
        
        # Create flag
        flag = ReviewFlag.objects.create(
            review=review,
            reporter=request.user,
            reason=request.POST.get('reason', 'other'),
            description=request.POST.get('description', '')
        )
        
        # Increment report count on review
        review.increment_report()
        
        # Auto-flag if multiple reports
        flag_count = ReviewFlag.objects.filter(
            review=review,
            is_resolved=False
        ).count()
        
        if flag_count >= 3:
            review.flag(f"Auto-flagged: {flag_count} user reports")
        
        return JsonResponse({
            'success': True,
            'message': 'Review flagged successfully'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@method_decorator([login_required, admin_required], name='dispatch')
class ModerationQueueView(ListView):
    """Admin view for moderating reviews"""
    model = Review
    template_name = 'reviews/admin/moderation_queue.html'
    context_object_name = 'reviews'
    paginate_by = 50
    
    def get_queryset(self):
        return ReviewModerationService.get_reviews_needing_moderation()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Statistics
        context['total_pending'] = Review.objects.filter(
            is_approved=False, is_flagged=False
        ).count()
        context['total_flagged'] = Review.objects.filter(
            is_flagged=True
        ).count()
        
        return context


@login_required
@admin_required
@require_http_methods(['POST'])
def moderate_review(request, review_id, action):
    """Moderate a single review"""
    try:
        review = get_object_or_404(Review, id=review_id)
        
        if action == 'approve':
            review.approve(request.user)
            ReviewModerationService.update_writer_ratings(review.writer)
            message = 'Review approved successfully'
            
        elif action == 'flag':
            review.flag(request.POST.get('reason', 'Flagged by admin'))
            message = 'Review flagged successfully'
            
        elif action == 'reject':
            review.is_active = False
            review.save()
            message = 'Review rejected successfully'
            
        else:
            return JsonResponse({
                'success': False,
                'error': 'Invalid action'
            })
        
        return JsonResponse({
            'success': True,
            'message': message
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@admin_required
def review_analytics(request):
    """Review analytics dashboard"""
    time_period = request.GET.get('period', '30d')
    
    stats = ReviewAnalyticsService.get_review_statistics(time_period)
    
    # Get top writers by rating
    top_writers = WriterRatingSummary.objects.filter(
        total_reviews__gte=5
    ).order_by('-average_rating')[:10]
    
    # Get recent flagged reviews
    recent_flags = ReviewFlag.objects.filter(
        is_resolved=False
    ).select_related('review', 'reporter').order_by('-created_at')[:10]
    
    context = {
        'stats': stats,
        'time_period': time_period,
        'top_writers': top_writers,
        'recent_flags': recent_flags,
    }
    
    return render(request, 'reviews/admin/analytics.html', context)


@login_required
@writer_required
def writer_performance_report(request):
    """Generate writer performance report"""
    from datetime import datetime, timedelta
    
    # Default to last 30 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    report = ReviewAnalyticsService.get_writer_performance_report(
        writer_id=request.user.id,
        start_date=start_date,
        end_date=end_date
    )
    
    return render(request, 'reviews/writer_performance.html', {'report': report}) 