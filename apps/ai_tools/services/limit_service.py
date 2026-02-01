"""
AI Tool Limit Service
Manages usage limits and restrictions for AI tools
"""
from django.utils import timezone
from django.core.cache import cache
from django.db import transaction

from ..models import AIToolConfiguration, UserAILimits, AIToolUsageLog


class AILimitService:
    """Service for managing AI tool usage limits"""
    
    @staticmethod
    def can_user_use_tool(user, tool_type: str) -> tuple:
        """
        Check if user can use a specific AI tool
        
        Returns:
            tuple: (can_use: bool, reason: str, limits: dict)
        """
        if not user.is_authenticated:
            return False, "Authentication required", {}
        
        # Check if user is restricted
        user_limits, created = UserAILimits.objects.get_or_create(user=user)
        
        if user_limits.is_restricted:
            if user_limits.restricted_until and user_limits.restricted_until > timezone.now():
                return False, f"Restricted until {user_limits.restricted_until}", {}
            elif user_limits.restricted_until:
                # Restriction expired
                user_limits.is_restricted = False
                user_limits.restriction_reason = ''
                user_limits.save()
        
        # Reset daily counts if needed
        user_limits.reset_daily_counts()
        
        # Get tool configuration
        try:
            config = AIToolConfiguration.objects.get(tool_type=tool_type, is_enabled=True)
        except AIToolConfiguration.DoesNotExist:
            return False, "Tool not available", {}
        
        # Check maintenance mode
        if not config.is_enabled:
            return False, config.maintenance_message or "Tool temporarily disabled", {}
        
        # Check daily limit
        daily_usage = getattr(user_limits, f"{tool_type}_used_today", 0)
        if daily_usage >= config.daily_limit_per_user:
            return False, f"Daily limit reached ({config.daily_limit_per_user} uses)", {
                'daily_used': daily_usage,
                'daily_limit': config.daily_limit_per_user,
            }
        
        # Check if review is required
        if config.require_review:
            # Check if user has pending reviews
            pending_reviews = AIToolUsageLog.objects.filter(
                user=user,
                tool_type=tool_type,
                is_reviewed=False
            ).count()
            
            if pending_reviews > 2:  # Limit pending reviews
                return False, "Waiting for admin review of previous uses", {
                    'pending_reviews': pending_reviews,
                }
        
        return True, "", {
            'daily_used': daily_usage,
            'daily_limit': config.daily_limit_per_user,
            'remaining': config.daily_limit_per_user - daily_usage,
        }
    
    @staticmethod
    def record_tool_usage(user, tool_type: str) -> bool:
        """
        Record tool usage and increment counters
        
        Returns:
            bool: Success status
        """
        if not user.is_authenticated:
            return False
        
        with transaction.atomic():
            user_limits, created = UserAILimits.objects.select_for_update().get_or_create(
                user=user
            )
            
            # Reset daily counts if needed
            user_limits.reset_daily_counts()
            
            # Increment usage
            field_map = {
                'outline_helper': 'outline_helper_used_today',
                'grammar_checker': 'grammar_checker_used_today',
                'citation_formatter': 'citation_formatter_used_today',
                'paraphrasing_tool': 'paraphrasing_tool_used_today',
                'thesis_generator': 'thesis_generator_used_today',
            }
            
            if tool_type in field_map:
                current = getattr(user_limits, field_map[tool_type])
                setattr(user_limits, field_map[tool_type], current + 1)
                user_limits.total_uses += 1
                user_limits.save()
                
                # Clear cache for user limits
                cache_key = f"user_ai_limits_{user.id}"
                cache.delete(cache_key)
                
                return True
        
        return False
    
    @staticmethod
    def get_user_limits(user) -> dict:
        """
        Get user's AI tool limits and usage
        
        Returns:
            dict: User limits and usage information
        """
        if not user.is_authenticated:
            return {}
        
        cache_key = f"user_ai_limits_{user.id}"
        cached = cache.get(cache_key)
        
        if cached:
            return cached
        
        user_limits, created = UserAILimits.objects.get_or_create(user=user)
        user_limits.reset_daily_counts()
        
        # Get all tool configurations
        configurations = AIToolConfiguration.objects.filter(is_enabled=True)
        
        limits_info = {
            'is_restricted': user_limits.is_restricted,
            'restriction_reason': user_limits.restriction_reason,
            'restricted_until': user_limits.restricted_until,
            'total_uses': user_limits.total_uses,
            'tools': {},
        }
        
        for config in configurations:
            daily_used = getattr(user_limits, f"{config.tool_type}_used_today", 0)
            remaining = max(0, config.daily_limit_per_user - daily_used)
            
            limits_info['tools'][config.tool_type] = {
                'name': config.get_tool_type_display(),
                'daily_used': daily_used,
                'daily_limit': config.daily_limit_per_user,
                'remaining': remaining,
                'is_enabled': config.is_enabled,
                'require_review': config.require_review,
                'max_input_length': config.max_input_length,
                'max_output_length': config.max_output_length,
            }
        
        # Cache for 5 minutes
        cache.set(cache_key, limits_info, 300)
        
        return limits_info
    
    @staticmethod
    def restrict_user(
        user,
        reason: str,
        duration_hours: int = 24,
        admin_user=None
    ) -> bool:
        """
        Restrict user from using AI tools
        
        Args:
            user: User to restrict
            reason: Reason for restriction
            duration_hours: Duration in hours
            admin_user: Admin applying restriction
        
        Returns:
            bool: Success status
        """
        try:
            user_limits, created = UserAILimits.objects.get_or_create(user=user)
            
            user_limits.is_restricted = True
            user_limits.restriction_reason = reason
            
            if duration_hours > 0:
                from django.utils import timezone
                user_limits.restricted_until = timezone.now() + timezone.timedelta(
                    hours=duration_hours
                )
            else:
                user_limits.restricted_until = None
            
            user_limits.save()
            
            # Log restriction
            from ..models import AIToolUsageLog
            AIToolUsageLog.objects.create(
                user=user,
                tool_type='system',
                input_text='',
                output_text=f'User restricted: {reason}',
                parameters={
                    'action': 'restrict',
                    'admin': admin_user.id if admin_user else None,
                    'duration_hours': duration_hours,
                },
                has_disclaimer=False,
            )
            
            # Clear cache
            cache_key = f"user_ai_limits_{user.id}"
            cache.delete(cache_key)
            
            return True
        except Exception:
            return False
    
    @staticmethod
    def unrestrict_user(user, admin_user=None) -> bool:
        """
        Remove restrictions from user
        
        Returns:
            bool: Success status
        """
        try:
            user_limits = UserAILimits.objects.get(user=user)
            
            user_limits.is_restricted = False
            user_limits.restriction_reason = ''
            user_limits.restricted_until = None
            user_limits.save()
            
            # Log unrestriction
            from ..models import AIToolUsageLog
            AIToolUsageLog.objects.create(
                user=user,
                tool_type='system',
                input_text='',
                output_text='User unrestricted',
                parameters={
                    'action': 'unrestrict',
                    'admin': admin_user.id if admin_user else None,
                },
                has_disclaimer=False,
            )
            
            # Clear cache
            cache_key = f"user_ai_limits_{user.id}"
            cache.delete(cache_key)
            
            return True
        except UserAILimits.DoesNotExist:
            return False
    
    @staticmethod
    def get_usage_statistics(time_period: str = 'day') -> dict:
        """
        Get AI tool usage statistics
        
        Args:
            time_period: 'day', 'week', 'month', 'year'
        
        Returns:
            dict: Usage statistics
        """
        from django.utils import timezone
        from django.db.models import Count, Q
        
        now = timezone.now()
        
        if time_period == 'day':
            start_date = now - timezone.timedelta(days=1)
        elif time_period == 'week':
            start_date = now - timezone.timedelta(days=7)
        elif time_period == 'month':
            start_date = now - timezone.timedelta(days=30)
        elif time_period == 'year':
            start_date = now - timezone.timedelta(days=365)
        else:
            start_date = now - timezone.timedelta(days=1)
        
        # Get usage counts by tool
        usage_by_tool = AIToolUsageLog.objects.filter(
            created_at__gte=start_date
        ).values('tool_type').annotate(
            count=Count('id'),
            unique_users=Count('user', distinct=True)
        ).order_by('-count')
        
        # Get total usage
        total_usage = AIToolUsageLog.objects.filter(
            created_at__gte=start_date
        ).count()
        
        # Get unique users
        unique_users = AIToolUsageLog.objects.filter(
            created_at__gte=start_date
        ).values('user').distinct().count()
        
        # Get users near limits
        user_limits = UserAILimits.objects.all()
        users_near_limit = 0
        
        for user_limit in user_limits:
            # Check each tool
            for tool_type in [
                'outline_helper', 'grammar_checker', 'citation_formatter',
                'paraphrasing_tool', 'thesis_generator'
            ]:
                daily_used = getattr(user_limit, f"{tool_type}_used_today", 0)
                
                try:
                    config = AIToolConfiguration.objects.get(tool_type=tool_type)
                    if daily_used >= config.daily_limit_per_user * 0.8:  # 80% of limit
                        users_near_limit += 1
                        break
                except AIToolConfiguration.DoesNotExist:
                    continue
        
        return {
            'time_period': time_period,
            'start_date': start_date,
            'end_date': now,
            'total_usage': total_usage,
            'unique_users': unique_users,
            'usage_by_tool': list(usage_by_tool),
            'users_near_limit': users_near_limit,
            'total_users_with_limits': user_limits.count(),
        }