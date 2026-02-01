# apps/blog/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.contrib import messages
from import_export.admin import ImportExportModelAdmin
from import_export import resources
from .models import BlogCategory, BlogPost, BlogComment, SEOAuditLog, BlogSubscription


class BlogCategoryResource(resources.ModelResource):
    class Meta:
        model = BlogCategory
        import_id_fields = ('slug',)
        fields = ('name', 'slug', 'description', 'meta_title', 'meta_description', 'is_active')


@admin.register(BlogCategory)
class BlogCategoryAdmin(ImportExportModelAdmin):
    """Admin for blog categories"""
    resource_class = BlogCategoryResource
    list_display = ('name', 'slug', 'post_count', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'description', 'is_active')
        }),
        ('SEO Information', {
            'fields': ('meta_title', 'meta_description'),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def post_count(self, obj):
        return obj.posts.count()
    post_count.short_description = 'Posts'


class BlogPostResource(resources.ModelResource):
    class Meta:
        model = BlogPost
        import_id_fields = ('slug',)
        exclude = ('id', 'structured_data', 'view_count', 'share_count')
        export_order = ('title', 'slug', 'status', 'published_at', 'author')


@admin.register(BlogPost)
class BlogPostAdmin(ImportExportModelAdmin):
    """Admin for blog posts"""
    resource_class = BlogPostResource
    
    list_display = (
        'title', 
        'author_display', 
        'category', 
        'status_badge', 
        'published_at', 
        'view_count', 
        'word_count',
        'seo_actions'
    )
    
    list_filter = (
        'status', 
        'category', 
        'published_at', 
        'created_at',
        ('author', admin.RelatedOnlyFieldListFilter)
    )
    
    search_fields = ('title', 'content', 'excerpt', 'author__email', 'author__first_name', 'author__last_name')
    readonly_fields = (
        'id', 'word_count', 'reading_time_minutes', 'view_count', 'share_count',
        'created_at', 'updated_at', 'published_at', 'reviewed_at', 'reviewed_by',
        'seo_preview'
    )
    
    prepopulated_fields = {'slug': ('title',)}
    
    # FIXED OPTION 1: Remove autocomplete_fields if User model is not registered
    # OR FIXED OPTION 2: Only use autocomplete_fields for models that are registered
    # Let's remove autocomplete_fields for now since User might not be registered
    # autocomplete_fields = ('author', 'category', 'reviewed_by')
    
    # FIXED: If tags field has a custom relationship, remove from filter_horizontal
    # filter_horizontal = ('tags',)  # Comment this out if causing issues
    
    fieldsets = (
        ('Content', {
            'fields': ('title', 'slug', 'excerpt', 'content', 'featured_image')
        }),
        ('Metadata', {
            'fields': ('author', 'category', 'status', 'tags', 'canonical_url')
        }),
        ('SEO Information', {
            'fields': ('meta_title', 'meta_description', 'meta_keywords', 'seo_preview'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('reading_time_minutes', 'word_count', 'view_count', 'share_count'),
            'classes': ('collapse',)
        }),
        ('Publication', {
            'fields': ('published_at', 'reviewed_by', 'reviewed_at'),
            'classes': ('collapse',)
        }),
        ('Advanced', {
            'fields': ('structured_data', 'id'),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_posts', 'reject_posts', 'run_seo_audit', 'export_as_json']
    
    def author_display(self, obj):
        if obj.author:
            url = reverse('admin:accounts_user_change', args=[obj.author.id])
            return format_html('<a href="{}">{}</a>', url, obj.author.get_full_name())
        return "No Author"
    author_display.short_description = 'Author'
    
    def status_badge(self, obj):
        colors = {
            'draft': 'gray',
            'under_review': 'orange',
            'published': 'green',
            'archived': 'red'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 12px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def seo_preview(self, obj):
        """Display SEO preview"""
        from .seo import SEOAnalyzer
        
        if not obj.content or not obj.title:
            return "Add content to see SEO preview"
        
        analyzer = SEOAnalyzer(obj.content, obj.title, obj.meta_description)
        
        preview_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px;">
            <div style="border: 1px solid #ddd; padding: 15px; margin-bottom: 15px;">
                <h3 style="margin-top: 0; color: #1a0dab; font-size: 18px; margin-bottom: 5px;">
                    {obj.title}
                </h3>
                <div style="color: #006621; font-size: 14px; margin-bottom: 5px;">
                    https://ebwriting.com{obj.get_absolute_url()}
                </div>
                <div style="color: #545454; font-size: 14px;">
                    {obj.meta_description or obj.excerpt[:160]}
                </div>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                <div style="background: #f8f9fa; padding: 10px; border-radius: 4px;">
                    <strong>Readability:</strong><br>
                    {analyzer.calculate_readability()}/100
                </div>
                <div style="background: #f8f9fa; padding: 10px; border-radius: 4px;">
                    <strong>Word Count:</strong><br>
                    {obj.word_count} words
                </div>
            </div>
        </div>
        """
        return format_html(preview_html)
    seo_preview.short_description = 'SEO Preview'
    
    def seo_actions(self, obj):
        """SEO action buttons"""
        audit_url = reverse('admin:blog_blogpost_seo_audit', args=[obj.id])
        return format_html(
            '<a href="{}" class="button" style="background: #4CAF50; color: white; padding: 5px 10px; border-radius: 3px; text-decoration: none;">SEO Audit</a>',
            audit_url
        )
    seo_actions.short_description = 'SEO Actions'
    
    def approve_posts(self, request, queryset):
        """Approve selected posts"""
        updated = queryset.filter(status='under_review').update(
            status='published',
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
            published_at=timezone.now()
        )
        self.message_user(
            request, 
            f"Approved and published {updated} post(s).",
            messages.SUCCESS
        )
    approve_posts.short_description = "Approve and publish selected posts"
    
    def reject_posts(self, request, queryset):
        """Reject selected posts"""
        updated = queryset.filter(status='under_review').update(
            status='draft',
            reviewed_by=request.user,
            reviewed_at=timezone.now()
        )
        self.message_user(
            request,
            f"Rejected {updated} post(s). They have been moved to draft.",
            messages.WARNING
        )
    reject_posts.short_description = "Reject selected posts"
    
    def run_seo_audit(self, request, queryset):
        """Run SEO audit on selected posts"""
        from .seo import SEOAnalyzer
        
        for post in queryset:
            analyzer = SEOAnalyzer(post.content, post.title, post.meta_description)
            recommendations = analyzer.generate_recommendations()
            
            # Create audit log
            SEOAuditLog.objects.create(
                post=post,
                audit_type='seo_check',
                readability_score=analyzer.calculate_readability(),
                issues_found=recommendations,
                performed_by=request.user
            )
        
        self.message_user(
            request,
            f"SEO audit completed for {queryset.count()} post(s).",
            messages.SUCCESS
        )
    run_seo_audit.short_description = "Run SEO audit"
    
    def export_as_json(self, request, queryset):
        """Export selected posts as JSON"""
        import json
        from django.http import HttpResponse
        from django.core import serializers
        
        data = serializers.serialize('json', queryset)
        response = HttpResponse(data, content_type='application/json')
        response['Content-Disposition'] = 'attachment; filename="blog_posts.json"'
        return response
    export_as_json.short_description = "Export as JSON"
    
    def get_urls(self):
        """Add custom URLs for SEO audit"""
        from django.urls import path
        
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:object_id>/seo-audit/',
                self.admin_site.admin_view(self.seo_audit_view),
                name='blog_blogpost_seo_audit'
            ),
        ]
        return custom_urls + urls
    
    def seo_audit_view(self, request, object_id):
        """View for detailed SEO audit"""
        from django.shortcuts import render, get_object_or_404
        from .seo import SEOAnalyzer
        
        post = get_object_or_404(BlogPost, id=object_id)
        analyzer = SEOAnalyzer(post.content, post.title, post.meta_description)
        
        context = {
            'post': post,
            'readability_score': analyzer.calculate_readability(),
            'keyword_analysis': analyzer.analyze_keyword_density(),
            'heading_structure': analyzer.check_heading_structure(),
            'meta_analysis': analyzer.analyze_meta_tags(),
            'recommendations': analyzer.generate_recommendations(),
            'opts': self.model._meta,
            'title': f'SEO Audit: {post.title}'
        }
        
        return render(request, 'admin/blog/seo_audit.html', context)


@admin.register(BlogComment)
class BlogCommentAdmin(admin.ModelAdmin):
    """Admin for blog comments"""
    list_display = (
        'truncated_content', 
        'post_link', 
        'display_name', 
        'status_badge', 
        'created_at', 
        'reviewed_by'
    )
    
    list_filter = ('status', 'created_at', 'post')
    search_fields = ('content', 'guest_name', 'guest_email', 'post__title')
    readonly_fields = ('id', 'ip_address', 'user_agent', 'created_at', 'updated_at')
    actions = ['approve_comments', 'reject_comments', 'mark_as_spam']
    
    fieldsets = (
        ('Comment Content', {
            'fields': ('content', 'post', 'user', 'guest_name', 'guest_email', 'parent_comment')
        }),
        ('Moderation', {
            'fields': ('status', 'reviewed_by', 'reviewed_at')
        }),
        ('Technical Information', {
            'fields': ('ip_address', 'user_agent', 'upvotes', 'downvotes'),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def truncated_content(self, obj):
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    truncated_content.short_description = 'Content'
    
    def post_link(self, obj):
        url = reverse('admin:blog_blogpost_change', args=[obj.post.id])
        return format_html('<a href="{}">{}</a>', url, obj.post.title[:50])
    post_link.short_description = 'Post'
    
    def status_badge(self, obj):
        colors = {
            'pending': 'orange',
            'approved': 'green',
            'rejected': 'red',
            'spam': 'gray'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 12px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def approve_comments(self, request, queryset):
        """Approve selected comments"""
        for comment in queryset:
            comment.approve(request.user)
        self.message_user(
            request,
            f"Approved {queryset.count()} comment(s).",
            messages.SUCCESS
        )
    approve_comments.short_description = "Approve selected comments"
    
    def reject_comments(self, request, queryset):
        """Reject selected comments"""
        for comment in queryset:
            comment.reject(request.user)
        self.message_user(
            request,
            f"Rejected {queryset.count()} comment(s).",
            messages.WARNING
        )
    reject_comments.short_description = "Reject selected comments"
    
    def mark_as_spam(self, request, queryset):
        """Mark comments as spam"""
        updated = queryset.update(status='spam')
        self.message_user(
            request,
            f"Marked {updated} comment(s) as spam.",
            messages.ERROR
        )
    mark_as_spam.short_description = "Mark as spam"


@admin.register(SEOAuditLog)
class SEOAuditLogAdmin(admin.ModelAdmin):
    """Admin for SEO audit logs"""
    list_display = ('post', 'audit_type', 'readability_score', 'performed_by', 'created_at')
    list_filter = ('audit_type', 'created_at')
    search_fields = ('post__title', 'performed_by__email', 'issues_found')
    readonly_fields = ('id', 'created_at', 'all_fields')
    
    def all_fields(self, obj):
        """Display all fields in a readable format"""
        fields = []
        for field in obj._meta.fields:
            if field.name not in ['id']:
                value = getattr(obj, field.name)
                if isinstance(value, (list, dict)):
                    import json
                    value = json.dumps(value, indent=2, default=str)
                fields.append(f"<strong>{field.verbose_name}:</strong> {value}<br>")
        
        return format_html(''.join(fields))
    all_fields.short_description = 'All Data'


@admin.register(BlogSubscription)
class BlogSubscriptionAdmin(admin.ModelAdmin):
    """Admin for blog subscriptions"""
    list_display = ('email', 'is_active', 'subscribed_at', 'unsubscribed_at', 'receive_new_posts')
    list_filter = ('is_active', 'receive_new_posts', 'receive_weekly_digest', 'subscribed_at')
    search_fields = ('email', 'ip_address')
    readonly_fields = ('subscription_token', 'subscribed_at', 'ip_address')
    actions = ['export_emails', 'send_test_newsletter']
    
    fieldsets = (
        ('Subscription Details', {
            'fields': ('email', 'is_active', 'subscription_token', 'ip_address')
        }),
        ('Preferences', {
            'fields': ('receive_new_posts', 'receive_weekly_digest', 'categories')
        }),
        ('Dates', {
            'fields': ('subscribed_at', 'unsubscribed_at'),
            'classes': ('collapse',)
        }),
    )
    
    def export_emails(self, request, queryset):
        """Export selected emails to CSV"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="subscribers.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Email', 'Active', 'Subscribed At', 'Preferences'])
        
        for subscription in queryset:
            preferences = []
            if subscription.receive_new_posts:
                preferences.append('New Posts')
            if subscription.receive_weekly_digest:
                preferences.append('Weekly Digest')
            
            writer.writerow([
                subscription.email,
                'Yes' if subscription.is_active else 'No',
                subscription.subscribed_at.strftime('%Y-%m-%d %H:%M'),
                ', '.join(preferences)
            ])
        
        return response
    export_emails.short_description = "Export emails to CSV"
    
    def send_test_newsletter(self, request, queryset):
        """Send test newsletter to selected emails"""
        from django.core.mail import send_mail
        
        for subscription in queryset:
            send_mail(
                'Test Newsletter - EBWriting Blog',
                'This is a test newsletter from EBWriting Blog.',
                'noreply@ebwriting.com',
                [subscription.email],
                fail_silently=False,
            )
        
        self.message_user(
            request,
            f"Test newsletter sent to {queryset.count()} subscriber(s).",
            messages.SUCCESS
        )
    send_test_newsletter.short_description = "Send test newsletter"