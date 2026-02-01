from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.contrib import messages
from import_export.admin import ImportExportModelAdmin
from import_export import resources
from django.db.models import Count, Q

from .models import (
    AIToolUsageLog, AIToolConfiguration, 
    AIToolTemplate, CitationStyle,
    WritingFeedback, UserAILimits
)


class AIToolUsageLogResource(resources.ModelResource):
    class Meta:
        model = AIToolUsageLog
        exclude = ('id',)
        export_order = ('user', 'tool_type', 'created_at', 'is_reviewed')


@admin.register(AIToolUsageLog)
class AIToolUsageLogAdmin(ImportExportModelAdmin):
    """Admin for AI tool usage logs"""
    
    resource_class = AIToolUsageLogResource
    
    list_display = (
        'user_display', 
        'tool_type_display', 
        'input_preview', 
        'created_at', 
        'is_reviewed_badge',
        'has_disclaimer_badge',
        'display_actions'
    )
    
    list_filter = (
        'tool_type', 
        'is_reviewed', 
        'has_disclaimer',
        'created_at',
        ('user', admin.RelatedOnlyFieldListFilter)
    )
    
    search_fields = (
        'user__email', 
        'user__first_name', 
        'user__last_name',
        'input_text', 
        'output_text',
        'session_id'
    )
    
    readonly_fields = (
        'id', 'created_at', 'updated_at', 
        'ip_address', 'user_agent', 'session_id',
        'input_preview_field', 'output_preview_field',
        'parameters_display'
    )
    
    fieldsets = (
        ('Usage Information', {
            'fields': ('user', 'tool_type', 'session_id')
        }),
        ('Content', {
            'fields': ('input_preview_field', 'output_preview_field')
        }),
        ('Parameters', {
            'fields': ('parameters_display',),
            'classes': ('collapse',)
        }),
        ('Compliance', {
            'fields': ('has_disclaimer', 'is_reviewed', 'reviewed_by', 'reviewed_at')
        }),
        ('Technical Information', {
            'fields': ('ip_address', 'user_agent'),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_reviewed', 'mark_as_unreviewed', 'export_selected_json']
    
    def user_display(self, obj):
        if obj.user:
            url = reverse('admin:accounts_user_change', args=[obj.user.id])
            return format_html('<a href="{}">{}</a>', url, obj.user.get_full_name())
        return "Anonymous"
    user_display.short_description = 'User'
    
    def tool_type_display(self, obj):
        return obj.get_tool_type_display()
    tool_type_display.short_description = 'Tool'
    
    def input_preview(self, obj):
        preview = obj.input_text[:50] + '...' if len(obj.input_text) > 50 else obj.input_text
        return format_html('<span title="{}">{}</span>', obj.input_text, preview)
    input_preview.short_description = 'Input'
    
    def input_preview_field(self, obj):
        return format_html(
            '<div style="max-height: 200px; overflow-y: auto; padding: 10px; background: #f5f5f5; border: 1px solid #ddd; border-radius: 4px; font-family: monospace; white-space: pre-wrap;">{}</div>',
            obj.input_text
        )
    input_preview_field.short_description = 'Input Text'
    
    def output_preview_field(self, obj):
        return format_html(
            '<div style="max-height: 200px; overflow-y: auto; padding: 10px; background: #f5f5f5; border: 1px solid #ddd; border-radius: 4px; font-family: monospace; white-space: pre-wrap;">{}</div>',
            obj.output_text
        )
    output_preview_field.short_description = 'Output Text'
    
    def parameters_display(self, obj):
        import json
        try:
            params = json.dumps(obj.parameters, indent=2, default=str)
        except:
            params = str(obj.parameters)
        
        return format_html(
            '<div style="max-height: 200px; overflow-y: auto; padding: 10px; background: #f5f5f5; border: 1px solid #ddd; border-radius: 4px; font-family: monospace; white-space: pre-wrap;">{}</div>',
            params
        )
    parameters_display.short_description = 'Parameters'
    
    def is_reviewed_badge(self, obj):
        if obj.is_reviewed:
            color = 'green'
            text = 'Reviewed'
        else:
            color = 'orange'
            text = 'Pending'
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 12px;">{}</span>',
            color, text
        )
    is_reviewed_badge.short_description = 'Review Status'
    
    def has_disclaimer_badge(self, obj):
        if obj.has_disclaimer:
            color = 'green'
            text = '✓'
        else:
            color = 'red'
            text = '✗'
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 12px;">{}</span>',
            color, text
        )
    has_disclaimer_badge.short_description = 'Disclaimer'
    
    def display_actions(self, obj):
        review_url = reverse('admin:ai_tools_aitoolusagelog_review', args=[obj.id])
        return format_html(
            '<a href="{}" class="button" style="padding: 3px 8px; font-size: 12px;">Review</a>',
            review_url
        )
    display_actions.short_description = 'Actions'
    
    def mark_as_reviewed(self, request, queryset):
        """Mark selected logs as reviewed"""
        updated = queryset.update(
            is_reviewed=True,
            reviewed_by=request.user,
            reviewed_at=timezone.now()
        )
        self.message_user(
            request,
            f"Marked {updated} usage log(s) as reviewed.",
            messages.SUCCESS
        )
    mark_as_reviewed.short_description = "Mark as reviewed"
    
    def mark_as_unreviewed(self, request, queryset):
        """Mark selected logs as unreviewed"""
        updated = queryset.update(
            is_reviewed=False,
            reviewed_by=None,
            reviewed_at=None
        )
        self.message_user(
            request,
            f"Marked {updated} usage log(s) as pending review.",
            messages.WARNING
        )
    mark_as_unreviewed.short_description = "Mark as unreviewed"
    
    def export_selected_json(self, request, queryset):
        """Export selected logs as JSON"""
        import json
        from django.http import HttpResponse
        
        data = []
        for log in queryset:
            data.append({
                'id': str(log.id),
                'user': log.user.get_full_name() if log.user else 'Anonymous',
                'tool_type': log.get_tool_type_display(),
                'input_text': log.input_text,
                'output_text': log.output_text,
                'created_at': log.created_at.isoformat(),
                'is_reviewed': log.is_reviewed,
                'has_disclaimer': log.has_disclaimer,
            })
        
        response = HttpResponse(
            json.dumps(data, indent=2, default=str),
            content_type='application/json'
        )
        response['Content-Disposition'] = 'attachment; filename="ai_usage_logs.json"'
        
        return response
    export_selected_json.short_description = "Export as JSON"
    
    def get_urls(self):
        """Add custom URLs for review"""
        from django.urls import path
        
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:object_id>/review/',
                self.admin_site.admin_view(self.review_view),
                name='ai_tools_aitoolusagelog_review'
            ),
        ]
        return custom_urls + urls
    
    def review_view(self, request, object_id):
        """View for reviewing AI tool usage"""
        from django.shortcuts import render, get_object_or_404
        
        log = get_object_or_404(AIToolUsageLog, id=object_id)
        
        context = {
            'log': log,
            'opts': self.model._meta,
            'title': f'Review AI Tool Usage: {log.get_tool_type_display()}',
        }
        
        return render(request, 'admin/ai_tools/review_usage.html', context)


@admin.register(AIToolConfiguration)
class AIToolConfigurationAdmin(admin.ModelAdmin):
    """Admin for AI tool configurations"""
    
    list_display = (
        'tool_type_display', 
        'is_enabled_badge', 
        'daily_limit_per_user',
        'require_review_badge',
        'last_modified'
    )
    
    list_filter = ('is_enabled', 'require_review')
    readonly_fields = ('last_modified', 'modified_by')
    
    fieldsets = (
        ('Basic Settings', {
            'fields': ('tool_type', 'is_enabled', 'maintenance_message')
        }),
        ('Usage Limits', {
            'fields': ('daily_limit_per_user', 'max_input_length', 'max_output_length')
        }),
        ('AI Parameters', {
            'fields': ('temperature', 'max_tokens'),
            'classes': ('collapse',)
        }),
        ('Safety Controls', {
            'fields': ('content_filter_enabled', 'plagiarism_check_enabled', 'require_review')
        }),
        ('Audit Information', {
            'fields': ('last_modified', 'modified_by'),
            'classes': ('collapse',)
        }),
    )
    
    def tool_type_display(self, obj):
        return obj.get_tool_type_display()
    tool_type_display.short_description = 'Tool'
    
    def is_enabled_badge(self, obj):
        if obj.is_enabled:
            color = 'green'
            text = 'Enabled'
        else:
            color = 'red'
            text = 'Disabled'
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 12px;">{}</span>',
            color, text
        )
    is_enabled_badge.short_description = 'Status'
    
    def require_review_badge(self, obj):
        if obj.require_review:
            color = 'orange'
            text = 'Review Required'
        else:
            color = 'blue'
            text = 'Auto-approved'
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 12px;">{}</span>',
            color, text
        )
    require_review_badge.short_description = 'Review'
    
    def save_model(self, request, obj, form, change):
        obj.modified_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(AIToolTemplate)
class AIToolTemplateAdmin(admin.ModelAdmin):
    """Admin for AI tool templates"""
    
    list_display = (
        'name', 
        'template_type_display', 
        'academic_level_display',
        'section_count',
        'is_active_badge'
    )
    
    list_filter = ('template_type', 'academic_level', 'is_active')
    search_fields = ('name', 'guidelines', 'common_mistakes')
    readonly_fields = ('created_at', 'updated_at')
    # REMOVED: filter_horizontal = ('recommended_sources',)  # This was causing the error
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'template_type', 'academic_level', 'is_active')
        }),
        ('Structure', {
            'fields': ('sections', 'word_count_range')
        }),
        ('Guidance', {
            'fields': ('guidelines', 'common_mistakes', 'recommended_sources')
        }),
        ('Examples', {
            'fields': ('example_outline', 'example_thesis'),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def template_type_display(self, obj):
        return obj.get_template_type_display()
    template_type_display.short_description = 'Type'
    
    def academic_level_display(self, obj):
        level_map = {
            'high_school': 'High School',
            'undergraduate': 'Undergraduate',
            'graduate': 'Graduate',
            'phd': 'PhD',
        }
        return level_map.get(obj.academic_level, obj.academic_level)
    academic_level_display.short_description = 'Level'
    
    def section_count(self, obj):
        return len(obj.sections)
    section_count.short_description = 'Sections'
    
    def is_active_badge(self, obj):
        if obj.is_active:
            color = 'green'
            text = 'Active'
        else:
            color = 'gray'
            text = 'Inactive'
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 12px;">{}</span>',
            color, text
        )
    is_active_badge.short_description = 'Status'


@admin.register(CitationStyle)
class CitationStyleAdmin(admin.ModelAdmin):
    """Admin for citation styles"""
    
    list_display = ('name', 'abbreviation', 'is_active_badge', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'abbreviation', 'description')
    readonly_fields = ('created_at', 'rules_preview')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'abbreviation', 'description', 'is_active')
        }),
        ('Examples', {
            'fields': ('book_example', 'journal_example', 'website_example')
        }),
        ('Rules', {
            'fields': ('rules_preview',),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def rules_preview(self, obj):
        import json
        try:
            rules = json.dumps(obj.rules, indent=2, default=str)
        except:
            rules = str(obj.rules)
        
        return format_html(
            '<div style="max-height: 300px; overflow-y: auto; padding: 10px; background: #f5f5f5; border: 1px solid #ddd; border-radius: 4px; font-family: monospace; white-space: pre-wrap;">{}</div>',
            rules
        )
    rules_preview.short_description = 'Rules (JSON)'
    
    def is_active_badge(self, obj):
        if obj.is_active:
            color = 'green'
            text = 'Active'
        else:
            color = 'gray'
            text = 'Inactive'
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 12px;">{}</span>',
            color, text
        )
    is_active_badge.short_description = 'Status'


@admin.register(WritingFeedback)
class WritingFeedbackAdmin(admin.ModelAdmin):
    """Admin for writing feedback"""
    
    list_display = (
        'user_display', 
        'feedback_type_display', 
        'score_badge',
        'word_count',
        'created_at'
    )
    
    list_filter = ('feedback_type', 'created_at')
    search_fields = ('user__email', 'original_text', 'suggestions')
    readonly_fields = (
        'id', 'created_at', 'original_preview', 
        'corrected_preview', 'issues_list', 'suggestions_display'
    )
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'feedback_type', 'score', 'confidence')
        }),
        ('Text Analysis', {
            'fields': ('original_preview', 'corrected_preview', 'word_count', 'reading_time')
        }),
        ('Feedback Details', {
            'fields': ('issues_list', 'suggestions_display')
        }),
        ('Audit Information', {
            'fields': ('id', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def user_display(self, obj):
        if obj.user:
            url = reverse('admin:accounts_user_change', args=[obj.user.id])
            return format_html('<a href="{}">{}</a>', url, obj.user.get_full_name())
        return "Unknown"
    user_display.short_description = 'User'
    
    def feedback_type_display(self, obj):
        return obj.get_feedback_type_display()
    feedback_type_display.short_description = 'Type'
    
    def score_badge(self, obj):
        if obj.score is None:
            return "N/A"
        
        if obj.score >= 8:
            color = 'green'
        elif obj.score >= 6:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 12px;">{}/10</span>',
            color, obj.score
        )
    score_badge.short_description = 'Score'
    
    def original_preview(self, obj):
        return format_html(
            '<div style="max-height: 200px; overflow-y: auto; padding: 10px; background: #f5f5f5; border: 1px solid #ddd; border-radius: 4px; white-space: pre-wrap;">{}</div>',
            obj.original_text
        )
    original_preview.short_description = 'Original Text'
    
    def corrected_preview(self, obj):
        if not obj.corrected_text:
            return "No corrected text"
        
        return format_html(
            '<div style="max-height: 200px; overflow-y: auto; padding: 10px; background: #f5f5f5; border: 1px solid #ddd; border-radius: 4px; white-space: pre-wrap;">{}</div>',
            obj.corrected_text
        )
    corrected_preview.short_description = 'Corrected Text'
    
    def issues_list(self, obj):
        issues_html = '<ul>'
        for issue in obj.issues_found[:10]:  # Limit to 10 issues
            issues_html += f'<li>{issue}</li>'
        issues_html += '</ul>'
        
        if len(obj.issues_found) > 10:
            issues_html += f'<p>... and {len(obj.issues_found) - 10} more issues</p>'
        
        return format_html(issues_html)
    issues_list.short_description = 'Issues Found'
    
    def suggestions_display(self, obj):
        return format_html(
            '<div style="max-height: 200px; overflow-y: auto; padding: 10px; background: #f5f5f5; border: 1px solid #ddd; border-radius: 4px; white-space: pre-wrap;">{}</div>',
            obj.suggestions
        )
    suggestions_display.short_description = 'Suggestions'


@admin.register(UserAILimits)
class UserAILimitsAdmin(admin.ModelAdmin):
    """Admin for user AI limits"""
    
    list_display = (
        'user_display', 
        'total_uses', 
        'is_restricted_badge',
        'daily_usage_summary',
        'last_reset_date'
    )
    
    list_filter = ('is_restricted', 'last_reset_date')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    readonly_fields = (
        'created_at', 'updated_at', 'last_reset_date',
        'usage_summary', 'restriction_details'
    )
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'is_restricted', 'restriction_details')
        }),
        ('Daily Usage Counts', {
            'fields': (
                'outline_helper_used_today',
                'grammar_checker_used_today',
                'citation_formatter_used_today',
                'paraphrasing_tool_used_today',
                'thesis_generator_used_today',
            )
        }),
        ('Summary', {
            'fields': ('total_uses', 'usage_summary', 'last_reset_date')
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['reset_daily_counts', 'restrict_users', 'unrestrict_users']
    
    def user_display(self, obj):
        if obj.user:
            url = reverse('admin:accounts_user_change', args=[obj.user.id])
            return format_html('<a href="{}">{}</a>', url, obj.user.get_full_name())
        return "Unknown"
    user_display.short_description = 'User'
    
    def is_restricted_badge(self, obj):
        if obj.is_restricted:
            color = 'red'
            text = 'Restricted'
            if obj.restricted_until:
                text += f' until {obj.restricted_until.strftime("%Y-%m-%d")}'
        else:
            color = 'green'
            text = 'Active'
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 12px;">{}</span>',
            color, text
        )
    is_restricted_badge.short_description = 'Status'
    
    def daily_usage_summary(self, obj):
        tools = [
            ('Outline', obj.outline_helper_used_today),
            ('Grammar', obj.grammar_checker_used_today),
            ('Citation', obj.citation_formatter_used_today),
            ('Paraphrase', obj.paraphrasing_tool_used_today),
            ('Thesis', obj.thesis_generator_used_today),
        ]
        
        active_tools = [f"{name}:{count}" for name, count in tools if count > 0]
        
        if not active_tools:
            return "No usage today"
        
        return ", ".join(active_tools[:3]) + ("..." if len(active_tools) > 3 else "")
    daily_usage_summary.short_description = 'Today\'s Usage'
    
    def usage_summary(self, obj):
        """Display usage summary"""
        from apps.ai_tools.services.limit_service import AILimitService
        
        limits = AILimitService.get_user_limits(obj.user)
        
        html = '<div style="max-height: 200px; overflow-y: auto;">'
        html += '<table style="width: 100%; border-collapse: collapse;">'
        html += '<tr style="background: #f5f5f5;"><th>Tool</th><th>Used Today</th><th>Daily Limit</th><th>Remaining</th></tr>'
        
        if 'tools' in limits:
            for tool_type, tool_info in limits['tools'].items():
                html += f'''
                <tr>
                    <td>{tool_info['name']}</td>
                    <td>{tool_info['daily_used']}</td>
                    <td>{tool_info['daily_limit']}</td>
                    <td>{tool_info['remaining']}</td>
                </tr>
                '''
        
        html += '</table>'
        html += f'<p><strong>Total Uses:</strong> {obj.total_uses}</p>'
        html += '</div>'
        
        return format_html(html)
    usage_summary.short_description = 'Usage Summary'
    
    def restriction_details(self, obj):
        if not obj.is_restricted:
            return "User is not restricted"
        
        html = f'<p><strong>Reason:</strong> {obj.restriction_reason}</p>'
        
        if obj.restricted_until:
            from django.utils import timezone
            now = timezone.now()
            
            if obj.restricted_until > now:
                remaining = obj.restricted_until - now
                html += f'<p><strong>Restricted until:</strong> {obj.restricted_until.strftime("%Y-%m-%d %H:%M")}</p>'
                html += f'<p><strong>Time remaining:</strong> {remaining.days} days, {remaining.seconds // 3600} hours</p>'
            else:
                html += '<p><strong>Restriction expired</strong></p>'
        
        return format_html(html)
    restriction_details.short_description = 'Restriction Details'
    
    def reset_daily_counts(self, request, queryset):
        """Reset daily usage counts for selected users"""
        for user_limit in queryset:
            user_limit.outline_helper_used_today = 0
            user_limit.grammar_checker_used_today = 0
            user_limit.citation_formatter_used_today = 0
            user_limit.paraphrasing_tool_used_today = 0
            user_limit.thesis_generator_used_today = 0
            user_limit.last_reset_date = timezone.now().date()
            user_limit.save()
        
        self.message_user(
            request,
            f"Reset daily counts for {queryset.count()} user(s).",
            messages.SUCCESS
        )
    reset_daily_counts.short_description = "Reset daily usage counts"
    
    def restrict_users(self, request, queryset):
        """Restrict selected users from using AI tools"""
        from apps.ai_tools.services.limit_service import AILimitService
        
        count = 0
        for user_limit in queryset:
            if AILimitService.restrict_user(
                user_limit.user,
                reason="Admin action",
                duration_hours=24,
                admin_user=request.user
            ):
                count += 1
        
        self.message_user(
            request,
            f"Restricted {count} user(s) from using AI tools.",
            messages.SUCCESS
        )
    restrict_users.short_description = "Restrict from AI tools"
    
    def unrestrict_users(self, request, queryset):
        """Unrestrict selected users"""
        from apps.ai_tools.services.limit_service import AILimitService
        
        count = 0
        for user_limit in queryset:
            if AILimitService.unrestrict_user(user_limit.user, request.user):
                count += 1
        
        self.message_user(
            request,
            f"Unrestricted {count} user(s).",
            messages.SUCCESS
        )
    unrestrict_users.short_description = "Remove restrictions"


class AIAnalyticsDashboard(admin.AdminSite):
    """Custom admin site for AI analytics"""
    
    site_header = "AI Tools Analytics"
    site_title = "AI Tools Analytics"
    index_title = "Analytics Dashboard"


ai_analytics_site = AIAnalyticsDashboard(name='ai_analytics')


class AIAnalyticsView(admin.ModelAdmin):
    """View for AI tools analytics"""
    
    def has_module_permission(self, request):
        return request.user.is_staff
    
    def has_view_permission(self, request, obj=None):
        return request.user.is_staff
    
    def changelist_view(self, request, extra_context=None):
        from apps.ai_tools.services.limit_service import AILimitService
        from django.db.models import Count
        from django.utils import timezone
        
        # Get usage statistics
        daily_stats = AILimitService.get_usage_statistics('day')
        weekly_stats = AILimitService.get_usage_statistics('week')
        
        # Get top users
        from .models import AIToolUsageLog
        top_users = AIToolUsageLog.objects.filter(
            created_at__gte=timezone.now() - timezone.timedelta(days=7)
        ).values('user__email', 'user__first_name', 'user__last_name').annotate(
            usage_count=Count('id')
        ).order_by('-usage_count')[:10]
        
        # Get tool popularity
        tool_popularity = AIToolUsageLog.objects.filter(
            created_at__gte=timezone.now() - timezone.timedelta(days=30)
        ).values('tool_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        context = {
            **self.admin_site.each_context(request),
            'title': 'AI Tools Analytics Dashboard',
            'daily_stats': daily_stats,
            'weekly_stats': weekly_stats,
            'top_users': list(top_users),
            'tool_popularity': list(tool_popularity),
            'opts': self.model._meta,
        }
        
        return self.render(request, 'admin/ai_tools/analytics_dashboard.html', context)


# Register analytics view
ai_analytics_site.register(AIToolUsageLog, AIAnalyticsView)