from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.contrib.admin import SimpleListFilter
from django.db.models import Q, Count, Avg
from django.utils import timezone
from datetime import timedelta
import csv
from django.http import HttpResponse

from .models import Review, ReviewResponse, ReviewFlag, WriterRatingSummary
from .moderation import ReviewModerationService


class RatingFilter(SimpleListFilter):
    """Filter reviews by rating"""
    title = 'Rating'
    parameter_name = 'rating'
    
    def lookups(self, request, model_admin):
        return [
            ('5', '5 Stars'),
            ('4', '4 Stars'),
            ('3', '3 Stars'),
            ('2', '2 Stars'),
            ('1', '1 Stars'),
            ('negative', 'Negative (1-2)'),
            ('positive', 'Positive (4-5)'),
        ]
    
    def queryset(self, request, queryset):
        if self.value() == '5':
            return queryset.filter(rating=5)
        elif self.value() == '4':
            return queryset.filter(rating=4)
        elif self.value() == '3':
            return queryset.filter(rating=3)
        elif self.value() == '2':
            return queryset.filter(rating=2)
        elif self.value() == '1':
            return queryset.filter(rating=1)
        elif self.value() == 'negative':
            return queryset.filter(rating__lte=2)
        elif self.value() == 'positive':
            return queryset.filter(rating__gte=4)
        return queryset


class ModerationStatusFilter(SimpleListFilter):
    """Filter reviews by moderation status"""
    title = 'Moderation Status'
    parameter_name = 'moderation_status'
    
    def lookups(self, request, model_admin):
        return [
            ('needs_moderation', 'Needs Moderation'),
            ('approved', 'Approved'),
            ('flagged', 'Flagged'),
            ('unapproved', 'Not Approved'),
        ]
    
    def queryset(self, request, queryset):
        if self.value() == 'needs_moderation':
            return queryset.filter(is_approved=False, is_flagged=False)
        elif self.value() == 'approved':
            return queryset.filter(is_approved=True, is_flagged=False)
        elif self.value() == 'flagged':
            return queryset.filter(is_flagged=True)
        elif self.value() == 'unapproved':
            return queryset.filter(is_approved=False)
        return queryset


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = [
        'review_id', 'order_link', 'customer_email', 'writer_email',
        'rating_stars', 'is_approved_display', 'is_flagged_display',
        'created_at', 'display_actions'
    ]
    list_filter = [
        RatingFilter, ModerationStatusFilter, 'is_verified',
        ('created_at', admin.DateFieldListFilter)
    ]
    search_fields = [
        'order__order_number', 'customer__email', 'writer__email',
        'comment'
    ]
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'moderated_at',
        'helpful_count', 'report_count', 'ip_address',
        'average_quality_score'
    ]
    fieldsets = (
        ('Review Details', {
            'fields': (
                'order', 'customer', 'writer', 'rating', 'comment',
                'communication_rating', 'timeliness_rating',
                'quality_rating', 'adherence_rating'
            )
        }),
        ('Moderation', {
            'fields': (
                'is_approved', 'is_flagged', 'flagged_reason',
                'moderated_by', 'moderated_at'
            )
        }),
        ('Metadata', {
            'fields': (
                'is_verified', 'is_edited', 'edit_reason',
                'helpful_count', 'report_count', 'ip_address',
                'average_quality_score'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    actions = [
        'approve_selected', 'flag_selected', 'reject_selected',
        'export_reviews_csv', 'bulk_moderate'
    ]
    
    def review_id(self, obj):
        return str(obj.id)[:8]
    review_id.short_description = 'ID'
    
    def order_link(self, obj):
        url = reverse('admin:orders_order_change', args=[obj.order.id])
        return format_html(
            '<a href="{}">Order #{}</a>',
            url, obj.order.order_number
        )
    order_link.short_description = 'Order'
    order_link.admin_order_field = 'order__order_number'
    
    def customer_email(self, obj):
        return obj.customer.email
    customer_email.short_description = 'Customer'
    customer_email.admin_order_field = 'customer__email'
    
    def writer_email(self, obj):
        url = reverse('admin:accounts_user_change', args=[obj.writer.id])
        return format_html(
            '<a href="{}">{}</a>',
            url, obj.writer.email
        )
    writer_email.short_description = 'Writer'
    writer_email.admin_order_field = 'writer__email'
    
    def rating_stars(self, obj):
        stars = '★' * obj.rating + '☆' * (5 - obj.rating)
        color = {
            1: '#ff6b6b',
            2: '#ffa726',
            3: '#ffd54f',
            4: '#9ccc65',
            5: '#66bb6a',
        }.get(obj.rating, '#666')
        return format_html(
            '<span style="color: {}; font-size: 1.2em;">{}</span>',
            color, stars
        )
    rating_stars.short_description = 'Rating'
    
    def is_approved_display(self, obj):
        if obj.is_approved:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Approved</span>'
            )
        return format_html(
            '<span style="color: orange;">Pending</span>'
        )
    is_approved_display.short_description = 'Approved'
    
    def is_flagged_display(self, obj):
        if obj.is_flagged:
            return format_html(
                '<span style="color: red; font-weight: bold;">⚠ Flagged</span>'
            )
        return '-'
    is_flagged_display.short_description = 'Flagged'
    
    def display_actions(self, obj):
        """Admin action buttons"""
        buttons = []
        if not obj.is_approved:
            buttons.append(
                f'<a href="approve/{obj.id}/" class="button" style="background-color: #4CAF50; color: white; padding: 5px 10px; text-decoration: none;">Approve</a>'
            )
        if not obj.is_flagged:
            buttons.append(
                f'<a href="flag/{obj.id}/" class="button" style="background-color: #ff9800; color: white; padding: 5px 10px; text-decoration: none;">Flag</a>'
            )
        return format_html(' '.join(buttons))
    display_actions.short_description = 'Actions'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'order', 'customer', 'writer'
        )
    
    def approve_selected(self, request, queryset):
        """Approve selected reviews"""
        ReviewModerationService.moderate_review_batch(
            [r.id for r in queryset],
            'approve',
            request.user
        )
        self.message_user(
            request,
            f'{queryset.count()} reviews approved.'
        )
    approve_selected.short_description = "Approve selected reviews"
    
    def flag_selected(self, request, queryset):
        """Flag selected reviews"""
        ReviewModerationService.moderate_review_batch(
            [r.id for r in queryset],
            'flag',
            request.user,
            "Flagged via admin bulk action"
        )
        self.message_user(
            request,
            f'{queryset.count()} reviews flagged.'
        )
    flag_selected.short_description = "Flag selected reviews"
    
    def export_reviews_csv(self, request, queryset):
        """Export reviews to CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="reviews_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Review ID', 'Order Number', 'Customer Email', 'Writer Email',
            'Rating', 'Comment', 'Communication', 'Timeliness', 'Quality',
            'Adherence', 'Is Approved', 'Is Flagged', 'Created Date'
        ])
        
        for review in queryset:
            writer.writerow([
                str(review.id),
                review.order.order_number,
                review.customer.email,
                review.writer.email,
                review.rating,
                review.comment[:200] if review.comment else '',
                review.communication_rating or '',
                review.timeliness_rating or '',
                review.quality_rating or '',
                review.adherence_rating or '',
                review.is_approved,
                review.is_flagged,
                review.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        
        return response
    export_reviews_csv.short_description = "Export selected reviews to CSV"


@admin.register(ReviewResponse)
class ReviewResponseAdmin(admin.ModelAdmin):
    list_display = [
        'response_id', 'review_link', 'writer_email',
        'response_preview', 'is_approved', 'created_at'
    ]
    list_filter = ['is_approved', ('created_at', admin.DateFieldListFilter)]
    search_fields = ['review__id', 'writer__email', 'response_text']
    readonly_fields = ['created_at', 'updated_at']
    
    def response_id(self, obj):
        return str(obj.id)[:8]
    response_id.short_description = 'ID'
    
    def review_link(self, obj):
        url = reverse('admin:reviews_review_change', args=[obj.review.id])
        return format_html('<a href="{}">Review {}</a>', url, str(obj.review.id)[:8])
    review_link.short_description = 'Review'
    
    def writer_email(self, obj):
        return obj.writer.email
    writer_email.short_description = 'Writer'
    
    def response_preview(self, obj):
        return obj.response_text[:100] + '...' if len(obj.response_text) > 100 else obj.response_text
    response_preview.short_description = 'Response'


@admin.register(ReviewFlag)
class ReviewFlagAdmin(admin.ModelAdmin):
    list_display = [
        'flag_id', 'review_link', 'reporter_email', 'reason_display',
        'is_resolved', 'created_at', 'resolved_at'
    ]
    list_filter = [
        'reason', 'is_resolved', ('created_at', admin.DateFieldListFilter)
    ]
    search_fields = [
        'review__id', 'reporter__email', 'description'
    ]
    readonly_fields = ['created_at', 'resolved_at']
    
    def flag_id(self, obj):
        return str(obj.id)[:8]
    flag_id.short_description = 'ID'
    
    def review_link(self, obj):
        url = reverse('admin:reviews_review_change', args=[obj.review.id])
        return format_html('<a href="{}">Review {}</a>', url, str(obj.review.id)[:8])
    review_link.short_description = 'Review'
    
    def reporter_email(self, obj):
        return obj.reporter.email
    reporter_email.short_description = 'Reporter'
    
    def reason_display(self, obj):
        return obj.get_reason_display()
    reason_display.short_description = 'Reason'


@admin.register(WriterRatingSummary)
class WriterRatingSummaryAdmin(admin.ModelAdmin):
    list_display = [
        'writer_email', 'average_rating_display', 'total_reviews',
        'positive_percentage', 'last_review', 'calculated_at'
    ]
    search_fields = ['writer__email']
    readonly_fields = [
        'average_rating', 'total_reviews', 'rating_5', 'rating_4',
        'rating_3', 'rating_2', 'rating_1', 'avg_communication',
        'avg_timeliness', 'avg_quality', 'avg_adherence',
        'positive_review_percentage', 'last_review_at', 'calculated_at'
    ]
    actions = ['update_summaries']
    
    def writer_email(self, obj):
        url = reverse('admin:accounts_user_change', args=[obj.writer.id])
        return format_html('<a href="{}">{}</a>', url, obj.writer.email)
    writer_email.short_description = 'Writer'
    
    def average_rating_display(self, obj):
        stars_full = int(obj.average_rating)
        stars_half = 1 if obj.average_rating - stars_full >= 0.5 else 0
        stars_empty = 5 - stars_full - stars_half
        
        stars = '★' * stars_full + '½' * stars_half + '☆' * stars_empty
        color = {
            1: '#ff6b6b',
            2: '#ffa726',
            3: '#ffd54f',
            4: '#9ccc65',
            5: '#66bb6a',
        }.get(stars_full, '#666')
        
        return format_html(
            '<span style="color: {}; font-size: 1.2em;">{} {:.2f}</span>',
            color, stars, obj.average_rating
        )
    average_rating_display.short_description = 'Avg Rating'
    
    def positive_percentage(self, obj):
        return format_html('{:.1f}%', obj.positive_review_percentage)
    positive_percentage.short_description = 'Positive %'
    
    def last_review(self, obj):
        if obj.last_review_at:
            return obj.last_review_at.strftime('%Y-%m-%d')
        return 'Never'
    last_review.short_description = 'Last Review'
    
    def update_summaries(self, request, queryset):
        """Update selected rating summaries"""
        for summary in queryset:
            summary.update_summary()
        self.message_user(
            request,
            f'{queryset.count()} rating summaries updated.'
        )
    update_summaries.short_description = "Update selected summaries"