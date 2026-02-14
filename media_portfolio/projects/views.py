from django.shortcuts import render, get_object_or_404, redirect  # Added redirect here
from django.views.generic import ListView, DetailView, View
from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib import messages
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import json

from .models import Project, ProjectLike, ProjectComment
from .forms import ProjectCommentForm, ProjectFilterForm
from media_portfolio.categories.models import Category


class ProjectListView(ListView):
    """
    View for listing all projects with filtering
    """
    model = Project
    template_name = 'projects/project_list.html'
    context_object_name = 'projects'
    paginate_by = 9

    def get_queryset(self):
        queryset = Project.objects.filter(is_published=True)
        
        # Apply filters
        form = ProjectFilterForm(self.request.GET)
        if form.is_valid():
            difficulty = form.cleaned_data.get('difficulty')
            category_id = form.cleaned_data.get('category')
            search = form.cleaned_data.get('search')
            featured_only = form.cleaned_data.get('featured_only')
            sort = form.cleaned_data.get('sort')

            if difficulty:
                queryset = queryset.filter(difficulty_level=difficulty)
            
            if category_id:
                queryset = queryset.filter(categories__id=category_id)
            
            if search:
                queryset = queryset.filter(
                    Q(title__icontains=search) |
                    Q(short_summary__icontains=search) |
                    Q(description__icontains=search) |
                    Q(tags__icontains=search)
                )
            
            if featured_only:
                queryset = queryset.filter(is_featured=True)
            
            if sort:
                queryset = queryset.order_by(sort)
            else:
                queryset = queryset.order_by('-is_featured', '-published_date')
        
        # Annotate with like count
        queryset = queryset.annotate(like_count=Count('likes'))
        
        return queryset.prefetch_related('categories')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = ProjectFilterForm(self.request.GET or None)
        context['categories'] = Category.objects.filter(
            is_active=True
        ).annotate(
            project_count=Count('projects')
        )
        context['difficulty_counts'] = {
            level: Project.objects.filter(
                is_published=True,
                difficulty_level=level
            ).count()
            for level, _ in Project.DIFFICULTY_LEVELS
        }
        context['featured_projects'] = Project.objects.filter(
            is_published=True,
            is_featured=True
        )[:3]
        return context


class FeaturedProjectsView(ListView):
    """
    View for featured projects
    """
    model = Project
    template_name = 'projects/featured_projects.html'
    context_object_name = 'projects'
    paginate_by = 12

    def get_queryset(self):
        return Project.objects.filter(
            is_published=True,
            is_featured=True
        ).annotate(
            like_count=Count('likes')
        ).order_by('-performance_score', '-published_date')


class ProjectsByDifficultyView(ListView):
    """
    View for projects filtered by difficulty level
    """
    model = Project
    template_name = 'projects/project_list.html'
    context_object_name = 'projects'
    paginate_by = 12

    def get_queryset(self):
        level = self.kwargs.get('level')
        return Project.objects.filter(
            is_published=True,
            difficulty_level=level
        ).annotate(
            like_count=Count('likes')
        ).order_by('-is_featured', '-published_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_difficulty'] = self.kwargs.get('level')
        context['difficulty_display'] = dict(Project.DIFFICULTY_LEVELS).get(
            self.kwargs.get('level'), 'Projects'
        )
        return context


class ProjectDetailView(DetailView):
    """
    View for displaying a single project
    """
    model = Project
    template_name = 'projects/project_detail.html'
    context_object_name = 'project'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        return Project.objects.filter(is_published=True)

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        
        # Increment view count
        if not request.session.get(f'viewed_project_{self.object.id}'):
            self.object.increment_view_count()
            request.session[f'viewed_project_{self.object.id}'] = True
        
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.object
        
        # Get like count and check if user liked
        context['like_count'] = project.likes.count()
        session_key = self.request.session.session_key
        if session_key:
            context['user_liked'] = project.likes.filter(session_key=session_key).exists()
        else:
            context['user_liked'] = False
        
        # Get approved comments
        context['comments'] = project.comments.filter(
            is_approved=True,
            parent=None
        ).prefetch_related('replies')[:10]
        
        # Comment form
        context['comment_form'] = ProjectCommentForm()
        
        # Related projects (same categories)
        category_ids = project.categories.values_list('id', flat=True)
        related = Project.objects.filter(
            is_published=True,
            categories__in=category_ids
        ).exclude(
            id=project.id
        ).annotate(
            like_count=Count('likes')
        ).distinct()[:4]
        context['related_projects'] = related
        
        # Next/Previous navigation
        context['next_project'] = Project.objects.filter(
            is_published=True,
            published_date__gt=project.published_date
        ).order_by('published_date').first()
        
        context['prev_project'] = Project.objects.filter(
            is_published=True,
            published_date__lt=project.published_date
        ).order_by('-published_date').first()
        
        return context


class LikeProjectView(View):
    """
    View for liking/unliking a project (AJAX)
    """
    
    def post(self, request, slug):
        project = get_object_or_404(Project, slug=slug, is_published=True)
        
        # Get or create session key
        if not request.session.session_key:
            request.session.save()
        session_key = request.session.session_key
        
        # Check if already liked
        like, created = ProjectLike.objects.get_or_create(
            project=project,
            session_key=session_key,
            defaults={
                'ip_address': self.get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', '')[:255]
            }
        )
        
        if not created:
            # Unlike
            like.delete()
            liked = False
            message = 'Project unliked'
        else:
            liked = True
            message = 'Project liked'
        
        # Get updated count
        like_count = project.likes.count()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'liked': liked,
                'like_count': like_count,
                'message': message
            })
        
        messages.success(request, message)
        return redirect('projects:detail', slug=project.slug)
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')


class AddCommentView(View):
    """
    View for adding comments to projects
    """
    
    def post(self, request, slug):
        project = get_object_or_404(Project, slug=slug, is_published=True)
        
        form = ProjectCommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.project = project
            
            # Set parent if this is a reply
            parent_id = request.POST.get('parent_id')
            if parent_id:
                try:
                    comment.parent = ProjectComment.objects.get(id=parent_id)
                except ProjectComment.DoesNotExist:
                    pass
            
            # Capture IP and user agent
            comment.ip_address = self.get_client_ip(request)
            comment.user_agent = request.META.get('HTTP_USER_AGENT', '')[:255]
            
            comment.save()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Comment submitted and awaiting moderation.',
                    'comment': {
                        'name': comment.name,
                        'content': comment.content,
                        'created_at': comment.created_at.strftime('%B %d, %Y'),
                    }
                })
            else:
                messages.success(request, 'Your comment has been submitted and is awaiting moderation.')
                return redirect('projects:detail', slug=project.slug)
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'errors': form.errors
                }, status=400)
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
                return redirect('projects:detail', slug=project.slug)
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')


class LoadCommentsView(View):
    """
    View for loading more comments via AJAX
    """
    
    def get(self, request, slug):
        project = get_object_or_404(Project, slug=slug, is_published=True)
        
        # Get approved comments
        comments = project.comments.filter(
            is_approved=True,
            parent=None
        ).prefetch_related('replies')
        
        # Paginate
        page = int(request.GET.get('page', 1))
        per_page = 10
        start = (page - 1) * per_page
        end = start + per_page
        
        comments_page = comments[start:end]
        has_next = comments.count() > end
        
        # Render comments HTML
        from django.template.loader import render_to_string
        html = render_to_string('projects/comment_list_items.html', {
            'comments': comments_page
        })
        
        return JsonResponse({
            'success': True,
            'html': html,
            'has_next': has_next,
            'next_page': page + 1 if has_next else None
        })