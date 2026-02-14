from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import View
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .models import Comment
from .forms import CommentForm
from media_portfolio.media.models import MediaItem


class AddCommentView(View):
    """
    View for adding a comment to a media item
    """
    
    def post(self, request, media_id):
        media_item = get_object_or_404(MediaItem, id=media_id, is_published=True)
        
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.media_item = media_item
            
            # Set parent if this is a reply
            parent_id = request.POST.get('parent_id')
            if parent_id:
                try:
                    comment.parent = Comment.objects.get(id=parent_id)
                except Comment.DoesNotExist:
                    pass
            
            # Capture IP and user agent
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                comment.ip_address = x_forwarded_for.split(',')[0]
            else:
                comment.ip_address = request.META.get('REMOTE_ADDR')
            
            comment.user_agent = request.META.get('HTTP_USER_AGENT', '')
            
            comment.save()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Comment submitted successfully and awaiting moderation.',
                    'comment': {
                        'name': comment.name,
                        'content': comment.content,
                        'created_at': comment.created_at.strftime('%B %d, %Y'),
                    }
                })
            else:
                messages.success(request, 'Your comment has been submitted and is awaiting moderation.')
                return redirect('media:detail', slug=media_item.slug)
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
                return redirect('media:detail', slug=media_item.slug)


class LoadCommentsView(View):
    """
    View for loading comments via AJAX
    """
    
    def get(self, request, media_id):
        media_item = get_object_or_404(MediaItem, id=media_id)
        
        # Get approved comments
        comments = Comment.objects.filter(
            media_item=media_item,
            is_approved=True,
            parent=None
        ).prefetch_related('replies')
        
        # Paginate if needed
        page = int(request.GET.get('page', 1))
        per_page = 10
        start = (page - 1) * per_page
        end = start + per_page
        
        comments_page = comments[start:end]
        has_next = comments.count() > end
        
        # Render comments HTML
        from django.template.loader import render_to_string
        html = render_to_string('comments/comment_list_items.html', {
            'comments': comments_page
        })
        
        return JsonResponse({
            'success': True,
            'html': html,
            'has_next': has_next,
            'next_page': page + 1 if has_next else None
        })


class ModerateCommentView(View):
    """
    View for comment moderation (admin only)
    """
    
    def post(self, request, comment_id):
        if not request.user.is_staff:
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        
        comment = get_object_or_404(Comment, id=comment_id)
        action = request.POST.get('action')
        
        if action == 'approve':
            comment.is_approved = True
            comment.save()
            return JsonResponse({'success': True, 'message': 'Comment approved'})
        
        elif action == 'reject':
            comment.is_approved = False
            comment.save()
            return JsonResponse({'success': True, 'message': 'Comment rejected'})
        
        elif action == 'spam':
            comment.is_spam = True
            comment.is_approved = False
            comment.save()
            return JsonResponse({'success': True, 'message': 'Comment marked as spam'})
        
        elif action == 'feature':
            comment.is_featured = True
            comment.save()
            return JsonResponse({'success': True, 'message': 'Comment featured'})
        
        return JsonResponse({'error': 'Invalid action'}, status=400)