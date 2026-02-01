import logging
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Count
from django.conf import settings
from .models import Review, ReviewFlag, WriterRatingSummary
from ..notifications.services import NotificationService
# apps/reviews/moderation.py

from django.db.models import Avg
from .models import ReviewResponse

logger = logging.getLogger(__name__)


class ReviewModerationService:
    """Service for moderating reviews"""
    
    @staticmethod
    def auto_moderate_review(review):
        """Automatically moderate review based on rules"""
        
        # Check for potential spam
        spam_keywords = ['spam', 'casino', 'gambling', 'xxx', 'adult']
        comment_lower = review.comment.lower() if review.comment else ''
        
        # Rule 1: Check for spam keywords
        if any(keyword in comment_lower for keyword in spam_keywords):
            review.flag(f"Auto-flagged: Contains spam keywords")
            review.save()
            return 'flagged'
        
        # Rule 2: Check for excessive caps
        if review.comment and len(review.comment) > 20:
            caps_count = sum(1 for c in review.comment if c.isupper())
            caps_percentage = (caps_count / len(review.comment)) * 100
            if caps_percentage > 70:
                review.flag(f"Auto-flagged: Excessive capitalization ({caps_percentage:.1f}%)")
                review.save()
                return 'flagged'
        
        # Rule 3: Check for duplicate content
        duplicate_check = Review.objects.filter(
            Q(comment__iexact=review.comment) | 
            Q(comment__icontains=review.comment[:50])
        ).exclude(id=review.id)
        
        if duplicate_check.exists():
            review.flag("Auto-flagged: Potential duplicate review")
            review.save()
            return 'flagged'
        
        # If passes all checks, auto-approve positive/neutral reviews
        if review.rating >= 3:
            review.is_approved = True
            review.save()
            
            # Update writer rating summary
            ReviewModerationService.update_writer_ratings(review.writer)
            
            logger.info(f"Auto-approved review {review.id} with rating {review.rating}")
            return 'approved'
        
        # Negative reviews go to manual moderation
        review.is_approved = False
        review.save()
        
        # Notify admins about negative review
        NotificationService.notify_admins(
            subject=f"Negative Review Requires Moderation",
            message=f"Review ID: {review.id} with {review.rating} stars needs moderation.",
            notification_type='review_moderation'
        )
        
        return 'pending'
    
    @staticmethod
    def update_writer_ratings(writer):
        """Update writer's rating summary"""
        try:
            summary, created = WriterRatingSummary.objects.get_or_create(
                writer=writer
            )
            summary.update_summary()
            
            # Check if writer needs restrictions due to low ratings
            if summary.average_rating < 3.0 and summary.total_reviews >= 5:
                ReviewModerationService.apply_low_rating_restrictions(writer, summary)
            
            logger.info(f"Updated rating summary for writer {writer.email}")
            
        except Exception as e:
            logger.error(f"Failed to update writer ratings: {str(e)}")
    
    @staticmethod
    def apply_low_rating_restrictions(writer, summary):
        """Apply restrictions to writers with low ratings"""
        from ..accounts.models import WriterProfile
        
        try:
            profile = WriterProfile.objects.get(user=writer)
            
            if summary.average_rating < 2.5 and summary.total_reviews >= 10:
                # Severe restriction: Suspend account
                profile.is_suspended = True
                profile.suspension_reason = f"Low average rating: {summary.average_rating}"
                profile.save()
                
                NotificationService.notify_user(
                    user=writer,
                    subject="Account Suspended Due to Low Ratings",
                    message=f"Your account has been suspended due to consistently low ratings.",
                    notification_type='account_suspended'
                )
                
                logger.warning(f"Suspended writer {writer.email} for low ratings")
                
            elif summary.average_rating < 3.0 and summary.total_reviews >= 5:
                # Mild restriction: Reduce order assignment priority
                profile.max_concurrent_orders = 1
                profile.order_priority = 'low'
                profile.save()
                
                NotificationService.notify_user(
                    user=writer,
                    subject="Order Priority Reduced Due to Ratings",
                    message=f"Your order assignment priority has been reduced due to low ratings.",
                    notification_type='priority_reduced'
                )
                
                logger.info(f"Reduced priority for writer {writer.email}")
                
        except WriterProfile.DoesNotExist:
            pass
        except Exception as e:
            logger.error(f"Failed to apply low rating restrictions: {str(e)}")
    
    @staticmethod
    def process_flags():
        """Process flagged reviews in batch"""
        from datetime import timedelta
        
        # Get flags that haven't been resolved for 24 hours
        threshold = timezone.now() - timedelta(hours=24)
        unresolved_flags = ReviewFlag.objects.filter(
            is_resolved=False,
            created_at__lte=threshold
        ).select_related('review')
        
        for flag in unresolved_flags:
            # If multiple flags exist for same review
            flag_count = ReviewFlag.objects.filter(
                review=flag.review,
                is_resolved=False
            ).count()
            
            if flag_count >= 3:  # Auto-resolve if 3+ flags
                flag.review.is_active = False
                flag.review.save()
                
                flag.resolve(
                    admin_user=None,  # Auto-resolved
                    notes="Auto-resolved: Multiple user flags"
                )
                
                logger.info(f"Auto-resolved flag {flag.id} for review {flag.review.id}")
    
    @staticmethod
    def get_reviews_needing_moderation():
        """Get reviews that need manual moderation"""
        return Review.objects.filter(
            Q(is_approved=False) & Q(is_flagged=False) |
            Q(is_flagged=True)
        ).select_related('customer', 'writer', 'order').order_by('-created_at')
    
    @staticmethod
    def moderate_review_batch(review_ids, action, moderator, notes=None):
        """Moderate multiple reviews at once"""
        reviews = Review.objects.filter(id__in=review_ids)
        
        with transaction.atomic():
            for review in reviews:
                if action == 'approve':
                    review.approve(moderator)
                    ReviewModerationService.update_writer_ratings(review.writer)
                elif action == 'reject':
                    review.is_active = False
                    review.is_approved = False
                    review.save()
                elif action == 'flag':
                    review.flag(notes or "Flagged by moderator")
                
                review.save()
        
        logger.info(f"Moderator {moderator.email} performed {action} on {len(reviews)} reviews")


class ReviewAnalyticsService:
    """Service for review analytics"""
    
    @staticmethod
    def get_review_statistics(time_period='30d'):
        """Get review statistics for dashboard"""
        from django.db.models import Avg, Count, Q
        from datetime import timedelta
        
        if time_period == '30d':
            date_threshold = timezone.now() - timedelta(days=30)
        elif time_period == '7d':
            date_threshold = timezone.now() - timedelta(days=7)
        else:  # all time
            date_threshold = None
        
        filters = Q(is_approved=True, is_active=True)
        if date_threshold:
            filters &= Q(created_at__gte=date_threshold)
        
        reviews = Review.objects.filter(filters)
        
        stats = reviews.aggregate(
            total=Count('id'),
            avg_rating=Avg('rating'),
            avg_communication=Avg('communication_rating'),
            avg_timeliness=Avg('timeliness_rating'),
            avg_quality=Avg('quality_rating'),
            avg_adherence=Avg('adherence_rating'),
        )
        
        # Rating distribution
        distribution = {
            5: reviews.filter(rating=5).count(),
            4: reviews.filter(rating=4).count(),
            3: reviews.filter(rating=3).count(),
            2: reviews.filter(rating=2).count(),
            1: reviews.filter(rating=1).count(),
        }
        
        return {
            'total_reviews': stats['total'] or 0,
            'average_rating': round(stats['avg_rating'] or 0, 2),
            'rating_distribution': distribution,
            'quality_metrics': {
                'communication': round(stats['avg_communication'] or 0, 2),
                'timeliness': round(stats['avg_timeliness'] or 0, 2),
                'quality': round(stats['avg_quality'] or 0, 2),
                'adherence': round(stats['avg_adherence'] or 0, 2),
            }
        }
    
    @staticmethod
    def get_writer_performance_report(writer_id, start_date=None, end_date=None):
        """Generate performance report for writer"""
        from ..accounts.models import User
        from ..orders.models import Order
        
        writer = User.objects.get(id=writer_id)
        
        # Base filters
        filters = Q(writer=writer, is_approved=True, is_active=True)
        if start_date:
            filters &= Q(created_at__gte=start_date)
        if end_date:
            filters &= Q(created_at__lte=end_date)
        
        reviews = Review.objects.filter(filters)
        
        # Get completed orders in same period
        order_filters = Q(writer=writer, status='completed')
        if start_date:
            order_filters &= Q(completed_at__gte=start_date)
        if end_date:
            order_filters &= Q(completed_at__lte=end_date)
        
        completed_orders = Order.objects.filter(order_filters).count()
        
        # Calculate metrics
        if reviews.exists():
            avg_rating = reviews.aggregate(avg=Avg('rating'))['avg'] or 0
            response_rate = ReviewResponse.objects.filter(
                review__in=reviews
            ).count() / reviews.count() * 100 if reviews.count() > 0 else 0
        else:
            avg_rating = 0
            response_rate = 0
        
        return {
            'writer': writer,
            'period': {
                'start': start_date,
                'end': end_date,
            },
            'metrics': {
                'total_reviews': reviews.count(),
                'completed_orders': completed_orders,
                'review_rate': (reviews.count() / completed_orders * 100) if completed_orders > 0 else 0,
                'average_rating': round(avg_rating, 2),
                'response_rate': round(response_rate, 2),
                'positive_reviews': reviews.filter(rating__gte=4).count(),
                'negative_reviews': reviews.filter(rating__lte=2).count(),
            },
            'recent_reviews': reviews.order_by('-created_at')[:10]
        }