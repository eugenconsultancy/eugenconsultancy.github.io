from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count, F
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.core.cache import cache
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
import json
# apps/blog/views.py

from django.db import models

from .models import BlogCategory, BlogPost, BlogComment, SEOAuditLog, BlogSubscription
from .forms import BlogPostForm, BlogCommentForm, SubscriptionForm, BlogSearchForm
from .serializers import (
    BlogPostSerializer, BlogCategorySerializer, 
    BlogCommentSerializer, SEOAnalyzeSerializer
)
from .seo import SEOAnalyzer, SEOSitemapGenerator, OpenGraphGenerator
from .permissions import IsAuthorOrReadOnly, IsStaffOrReadOnly


# ================ Public Views ================

class BlogHomeView(ListView):
    """Homepage showing latest blog posts"""
    model = BlogPost
    template_name = 'blog/home.html'
    context_object_name = 'posts'
    paginate_by = 10

    def get_queryset(self):
        # Return a CLEAN, unsliced queryset for the paginator to use
        return BlogPost.objects.filter(
            status=BlogPost.PostStatus.PUBLISHED,
            published_at__lte=timezone.now()
        ).select_related('author', 'category').prefetch_related('tags').order_by('-published_at')

    def get_context_data(self, **kwargs):
        # 1. Get the standard context (this includes 'posts' and 'page_obj')
        context = super().get_context_data(**kwargs)
        
        # 2. Extract featured posts from the queryset (top 3 overall)
        # We do this separately so it doesn't interfere with the pagination of 'posts'
        all_published = self.get_queryset()
        context['featured_posts'] = all_published[:3]
        
        # 3. Sidebar data
        context['categories'] = BlogCategory.objects.filter(is_active=True).annotate(
            post_count=Count('posts')
        ).order_by('-post_count')[:10]
        
        context['popular_posts'] = all_published.order_by('-view_count')[:5]
        context['search_form'] = BlogSearchForm()
        
        return context
    

class BlogPostDetailView(DetailView):
    """Detail view for a blog post"""
    model = BlogPost
    template_name = 'blog/post_detail.html'
    context_object_name = 'post'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    
    def get_queryset(self):
        return BlogPost.objects.select_related('author', 'category').prefetch_related('tags')
    
    def get_object(self, queryset=None):
        """Get the post object and increment view count"""
        obj = super().get_object(queryset)
        
        # Check if user has already viewed this post in this session
        session_key = f'viewed_post_{obj.id}'
        if not self.request.session.get(session_key, False):
            obj.increment_view_count()
            self.request.session[session_key] = True
        
        return obj
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        post = self.object
        
        # Get approved comments
        context['comments'] = BlogComment.objects.filter(
            post=post,
            status=BlogComment.CommentStatus.APPROVED
        ).select_related('user').order_by('-created_at')
        
        # Comment form
        context['comment_form'] = BlogCommentForm()
        
        # Related posts
        context['related_posts'] = BlogPost.objects.filter(
            category=post.category,
            status=BlogPost.PostStatus.PUBLISHED,
            published_at__lte=timezone.now()
        ).exclude(id=post.id).order_by('-published_at')[:3]
        
        # Generate Open Graph and Twitter Card data
        context['og_tags'] = OpenGraphGenerator.generate_for_post(post)
        context['twitter_card'] = OpenGraphGenerator.generate_twitter_card(post)
        
        # SEO structured data
        context['structured_data'] = post.structured_data or self._generate_structured_data(post)
        
        return context
    
    def _generate_structured_data(self, post):
        """Generate JSON-LD structured data for the post"""
        from django.contrib.sites.models import Site
        
        current_site = Site.objects.get_current()
        base_url = f"https://{current_site.domain}"
        
        structured_data = {
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "headline": post.title,
            "description": post.excerpt,
            "image": post.featured_image.url if post.featured_image else f"{base_url}/static/img/og-default.jpg",
            "author": {
                "@type": "Person",
                "name": post.author.get_full_name() if post.author else "EBWriting Team"
            },
            "publisher": {
                "@type": "Organization",
                "name": "EBWriting",
                "logo": {
                    "@type": "ImageObject",
                    "url": f"{base_url}/static/img/logo.png"
                }
            },
            "datePublished": post.published_at.isoformat() if post.published_at else None,
            "dateModified": post.updated_at.isoformat(),
            "mainEntityOfPage": {
                "@type": "WebPage",
                "@id": f"{base_url}{post.get_absolute_url()}"
            },
            "wordCount": post.word_count,
            "timeRequired": f"PT{post.reading_time_minutes}M"
        }
        
        if post.category:
            structured_data["articleSection"] = post.category.name
        
        return json.dumps(structured_data, default=str)


class CategoryDetailView(ListView):
    """View posts by category"""
    template_name = 'blog/category_detail.html'
    context_object_name = 'posts'
    paginate_by = 10
    
    def get_queryset(self):
        self.category = get_object_or_404(
            BlogCategory, 
            slug=self.kwargs['slug'],
            is_active=True
        )
        
        return BlogPost.objects.filter(
            category=self.category,
            status=BlogPost.PostStatus.PUBLISHED,
            published_at__lte=timezone.now()
        ).select_related('author').prefetch_related('tags').order_by('-published_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category'] = self.category
        
        # Get popular posts in this category
        context['popular_posts'] = BlogPost.objects.filter(
            category=self.category,
            status=BlogPost.PostStatus.PUBLISHED,
            published_at__lte=timezone.now()
        ).order_by('-view_count')[:5]
        
        return context


class TagListView(ListView):
    """View posts by tag"""
    template_name = 'blog/tag_list.html'
    context_object_name = 'posts'
    paginate_by = 10
    
    def get_queryset(self):
        self.tag = self.kwargs['tag']
        
        return BlogPost.objects.filter(
            tags__name=self.tag,
            status=BlogPost.PostStatus.PUBLISHED,
            published_at__lte=timezone.now()
        ).select_related('author', 'category').prefetch_related('tags').order_by('-published_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tag'] = self.tag
        return context


class BlogSearchView(ListView):
    """Search blog posts"""
    template_name = 'blog/search_results.html'
    context_object_name = 'posts'
    paginate_by = 10
    
    def get_queryset(self):
        form = BlogSearchForm(self.request.GET or None)
        
        if form.is_valid():
            query = form.cleaned_data['q']
            
            # Search in title, content, excerpt, and author name
            return BlogPost.objects.filter(
                Q(title__icontains=query) |
                Q(content__icontains=query) |
                Q(excerpt__icontains=query) |
                Q(author__first_name__icontains=query) |
                Q(author__last_name__icontains=query) |
                Q(tags__name__icontains=query),
                status=BlogPost.PostStatus.PUBLISHED,
                published_at__lte=timezone.now()
            ).select_related('author', 'category').prefetch_related('tags').distinct().order_by('-published_at')
        
        return BlogPost.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = BlogSearchForm(self.request.GET or None)
        context['search_query'] = self.request.GET.get('q', '')
        return context


class MonthlyArchiveView(ListView):
    """Monthly archive of posts"""
    template_name = 'blog/monthly_archive.html'
    context_object_name = 'posts'
    paginate_by = 10
    
    def get_queryset(self):
        year = self.kwargs['year']
        month = self.kwargs['month']
        
        return BlogPost.objects.filter(
            published_at__year=year,
            published_at__month=month,
            status=BlogPost.PostStatus.PUBLISHED,
            published_at__lte=timezone.now()
        ).select_related('author', 'category').prefetch_related('tags').order_by('-published_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['archive_date'] = f"{self.kwargs['year']}-{self.kwargs['month']:02d}"
        return context


class CreateCommentView(LoginRequiredMixin, CreateView):
    """Create a new comment on a blog post"""
    form_class = BlogCommentForm
    template_name = 'blog/includes/comment_form.html'
    
    def form_valid(self, form):
        post = get_object_or_404(
            BlogPost, 
            slug=self.kwargs['slug'],
            status=BlogPost.PostStatus.PUBLISHED
        )
        
        comment = form.save(commit=False)
        comment.post = post
        comment.user = self.request.user
        comment.ip_address = self.get_client_ip()
        comment.user_agent = self.request.META.get('HTTP_USER_AGENT', '')
        
        # Auto-approve comments from staff
        if self.request.user.is_staff:
            comment.status = BlogComment.CommentStatus.APPROVED
        else:
            comment.status = BlogComment.CommentStatus.PENDING
        
        comment.save()
        
        messages.success(
            self.request,
            'Your comment has been submitted and is awaiting moderation.'
        )
        
        return redirect('blog:post_detail', slug=post.slug)
    
    def get_client_ip(self):
        """Get client IP address"""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip


class CommentVoteView(LoginRequiredMixin, View):
    """Upvote or downvote a comment"""
    def post(self, request, pk):
        comment = get_object_or_404(
            BlogComment, 
            pk=pk,
            status=BlogComment.CommentStatus.APPROVED
        )
        
        vote_type = request.POST.get('vote_type')
        session_key = f'voted_comment_{comment.id}'
        
        # Check if user already voted
        if request.session.get(session_key):
            return JsonResponse({'error': 'Already voted'}, status=400)
        
        if vote_type == 'up':
            comment.upvotes = F('upvotes') + 1
        elif vote_type == 'down':
            comment.downvotes = F('downvotes') + 1
        else:
            return JsonResponse({'error': 'Invalid vote type'}, status=400)
        
        comment.save()
        comment.refresh_from_db()
        
        # Mark as voted in session
        request.session[session_key] = True
        
        return JsonResponse({
            'upvotes': comment.upvotes,
            'downvotes': comment.downvotes
        })


class SubscribeView(CreateView):
    """Subscribe to blog updates"""
    form_class = SubscriptionForm
    template_name = 'blog/subscribe.html'
    
    def form_valid(self, form):
        subscription = form.save(commit=False)
        subscription.ip_address = self.get_client_ip()
        
        # Check if already subscribed
        existing = BlogSubscription.objects.filter(
            email=subscription.email,
            is_active=True
        ).first()
        
        if existing:
            messages.info(
                self.request,
                'You are already subscribed to our newsletter.'
            )
            return redirect('blog:home')
        
        subscription.save()
        
        # Send confirmation email
        self.send_confirmation_email(subscription)
        
        messages.success(
            self.request,
            'Thank you for subscribing! Please check your email to confirm.'
        )
        
        return redirect('blog:home')
    
    def get_client_ip(self):
        """Get client IP address"""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip
    
    def send_confirmation_email(self, subscription):
        """Send subscription confirmation email"""
        from django.core.mail import send_mail
        from django.template.loader import render_to_string
        
        subject = 'Confirm your subscription to EBWriting Blog'
        message = render_to_string('emails/blog_subscription_confirm.html', {
            'subscription': subscription
        })
        
        send_mail(
            subject,
            '',
            'noreply@ebwriting.com',
            [subscription.email],
            html_message=message,
            fail_silently=False,
        )


class UnsubscribeView(View):
    """Unsubscribe from blog updates"""
    def get(self, request, token):
        subscription = get_object_or_404(
            BlogSubscription,
            subscription_token=token,
            is_active=True
        )
        
        subscription.unsubscribe()
        
        messages.success(
            request,
            'You have been unsubscribed from our newsletter.'
        )
        
        return redirect('blog:home')


# ================ SEO Views ================

class BlogSitemapView(View):
    """Generate sitemap.xml"""
    def get(self, request):
        posts = BlogPost.objects.filter(
            status=BlogPost.PostStatus.PUBLISHED,
            published_at__lte=timezone.now()
        )
        
        sitemap_xml = SEOSitemapGenerator.generate_blog_sitemap(posts)
        
        return HttpResponse(sitemap_xml, content_type='application/xml')


class RobotsTextView(View):
    """Generate robots.txt"""
    def get(self, request):
        robots_txt = SEOSitemapGenerator.generate_robots_txt()
        return HttpResponse(robots_txt, content_type='text/plain')


# ================ Author/Admin Views ================

class AuthorDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Dashboard for authors to manage their posts"""
    template_name = 'blog/author_dashboard.html'
    
    def test_func(self):
        return self.request.user.is_staff
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get user's posts
        posts = BlogPost.objects.filter(author=user).order_by('-created_at')
        
        # Pagination
        paginator = Paginator(posts, 10)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Stats
        total_posts = posts.count()
        published_posts = posts.filter(status=BlogPost.PostStatus.PUBLISHED).count()
        total_views = posts.aggregate(total_views=models.Sum('view_count'))['total_views'] or 0
        
        context.update({
            'page_obj': page_obj,
            'total_posts': total_posts,
            'published_posts': published_posts,
            'total_views': total_views,
        })
        
        return context


class CreateBlogPostView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Create a new blog post"""
    form_class = BlogPostForm
    template_name = 'blog/create_post.html'
    
    def test_func(self):
        return self.request.user.is_staff
    
    def form_valid(self, form):
        post = form.save(commit=False)
        post.author = self.request.user
        
        # Set initial status based on user permissions
        if self.request.user.has_perm('blog.can_publish_post'):
            post.status = BlogPost.PostStatus.UNDER_REVIEW
        else:
            post.status = BlogPost.PostStatus.DRAFT
        
        post.save()
        form.save_m2m()  # Save tags
        
        # Run initial SEO audit
        self.run_seo_audit(post)
        
        messages.success(
            self.request,
            'Blog post created successfully!'
        )
        
        return redirect('blog:author_dashboard')
    
    def run_seo_audit(self, post):
        """Run SEO audit on new post"""
        analyzer = SEOAnalyzer(post.content, post.title, post.meta_description)
        recommendations = analyzer.generate_recommendations()
        
        SEOAuditLog.objects.create(
            post=post,
            audit_type='post_created',
            readability_score=analyzer.calculate_readability(),
            issues_found=recommendations,
            performed_by=self.request.user
        )
        
        # Update post with recommendations
        if recommendations:
            messages.info(
                self.request,
                f'SEO recommendations: {len(recommendations)} suggestions for improvement.'
            )


class EditBlogPostView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Edit an existing blog post"""
    model = BlogPost
    form_class = BlogPostForm
    template_name = 'blog/edit_post.html'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    
    def test_func(self):
        post = self.get_object()
        return (
            self.request.user.is_staff and 
            (self.request.user == post.author or 
             self.request.user.has_perm('blog.can_review_post'))
        )
    
    def form_valid(self, form):
        post = form.save()
        
        # Run SEO audit on update
        self.run_seo_audit(post)
        
        messages.success(
            self.request,
            'Blog post updated successfully!'
        )
        
        return redirect('blog:author_dashboard')
    
    def run_seo_audit(self, post):
        """Run SEO audit on updated post"""
        analyzer = SEOAnalyzer(post.content, post.title, post.meta_description)
        recommendations = analyzer.generate_recommendations()
        
        SEOAuditLog.objects.create(
            post=post,
            audit_type='post_updated',
            readability_score=analyzer.calculate_readability(),
            issues_found=recommendations,
            performed_by=self.request.user
        )


class PostPreviewView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Preview a post before publishing"""
    model = BlogPost
    template_name = 'blog/post_preview.html'
    context_object_name = 'post'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    
    def test_func(self):
        post = self.get_object()
        return (
            self.request.user.is_staff and 
            (self.request.user == post.author or 
             self.request.user.has_perm('blog.can_review_post'))
        )


class PostStatsView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View statistics for a post"""
    model = BlogPost
    template_name = 'blog/post_stats.html'
    context_object_name = 'post'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    
    def test_func(self):
        post = self.get_object()
        return (
            self.request.user.is_staff and 
            (self.request.user == post.author or 
             self.request.user.has_perm('blog.can_review_post'))
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        post = self.object
        
        # Get SEO audits for this post
        context['seo_audits'] = SEOAuditLog.objects.filter(
            post=post
        ).order_by('-created_at')[:10]
        
        # Get comment stats
        context['comment_stats'] = {
            'total': BlogComment.objects.filter(post=post).count(),
            'approved': BlogComment.objects.filter(
                post=post, 
                status=BlogComment.CommentStatus.APPROVED
            ).count(),
            'pending': BlogComment.objects.filter(
                post=post, 
                status=BlogComment.CommentStatus.PENDING
            ).count(),
        }
        
        return context


# ================ API Views ================

class BlogPostViewSet(viewsets.ModelViewSet):
    """API endpoint for blog posts"""
    queryset = BlogPost.objects.filter(
        status=BlogPost.PostStatus.PUBLISHED,
        published_at__lte=timezone.now()
    ).select_related('author', 'category').prefetch_related('tags')
    
    serializer_class = BlogPostSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by category
        category_slug = self.request.query_params.get('category')
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)
        
        # Filter by tag
        tag = self.request.query_params.get('tag')
        if tag:
            queryset = queryset.filter(tags__name=tag)
        
        # Filter by author
        author_id = self.request.query_params.get('author')
        if author_id:
            queryset = queryset.filter(author_id=author_id)
        
        # Search
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(content__icontains=search) |
                Q(excerpt__icontains=search)
            )
        
        return queryset.order_by('-published_at')
    
    @action(detail=True, methods=['post'])
    def increment_view(self, request, pk=None):
        """Increment view count"""
        post = self.get_object()
        post.increment_view_count()
        return Response({'view_count': post.view_count})
    
    @action(detail=True, methods=['get'])
    def seo_analysis(self, request, pk=None):
        """Get SEO analysis for the post"""
        post = self.get_object()
        analyzer = SEOAnalyzer(post.content, post.title, post.meta_description)
        
        analysis = {
            'readability_score': analyzer.calculate_readability(),
            'keyword_density': analyzer.analyze_keyword_density(),
            'heading_structure': analyzer.check_heading_structure(),
            'meta_analysis': analyzer.analyze_meta_tags(),
            'recommendations': analyzer.generate_recommendations()
        }
        
        return Response(analysis)


class BlogCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for blog categories"""
    queryset = BlogCategory.objects.filter(is_active=True)
    serializer_class = BlogCategorySerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'slug'


class BlogCommentViewSet(viewsets.ModelViewSet):
    """API endpoint for blog comments"""
    queryset = BlogComment.objects.filter(
        status=BlogComment.CommentStatus.APPROVED
    ).select_related('user', 'post')
    
    serializer_class = BlogCommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by post
        post_slug = self.request.query_params.get('post')
        if post_slug:
            queryset = queryset.filter(post__slug=post_slug)
        
        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer):
        # Auto-approve comments from staff
        if self.request.user.is_staff:
            status = BlogComment.CommentStatus.APPROVED
        else:
            status = BlogComment.CommentStatus.PENDING
        
        serializer.save(
            user=self.request.user,
            status=status,
            ip_address=self.get_client_ip()
        )
    
    @action(detail=True, methods=['post'])
    def vote(self, request, pk=None):
        """Upvote or downvote a comment"""
        comment = self.get_object()
        vote_type = request.data.get('vote_type')
        
        if vote_type == 'up':
            comment.upvotes = F('upvotes') + 1
        elif vote_type == 'down':
            comment.downvotes = F('downvotes') + 1
        else:
            return Response(
                {'error': 'Invalid vote type'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        comment.save()
        comment.refresh_from_db()
        
        return Response({
            'upvotes': comment.upvotes,
            'downvotes': comment.downvotes
        })
    
    def get_client_ip(self):
        """Get client IP address"""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip


class SEOAnalyzeView(APIView):
    """API endpoint for SEO analysis"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = SEOAnalyzeSerializer(data=request.data)
        
        if serializer.is_valid():
            analyzer = SEOAnalyzer(
                serializer.validated_data['content'],
                serializer.validated_data.get('title', ''),
                serializer.validated_data.get('meta_description', '')
            )
            
            analysis = {
                'readability_score': analyzer.calculate_readability(),
                'keyword_density': analyzer.analyze_keyword_density(),
                'heading_structure': analyzer.check_heading_structure(),
                'meta_analysis': analyzer.analyze_meta_tags(),
                'recommendations': analyzer.generate_recommendations()
            }
            
            return Response(analysis)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)