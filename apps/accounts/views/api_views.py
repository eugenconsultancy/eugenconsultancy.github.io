from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import View
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json

from apps.accounts.forms import ProfileUpdateForm, DocumentUploadForm
from apps.accounts.services import DocumentService


class UpdateProfileAPIView(LoginRequiredMixin, View):
    """API view for updating user profile via AJAX."""
    
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def post(self, request):
        """Handle profile update."""
        try:
            data = json.loads(request.body)
            form = ProfileUpdateForm(data, instance=request.user)
            
            if form.is_valid():
                form.save()
                return JsonResponse({
                    'success': True,
                    'message': 'Profile updated successfully.',
                    'user': {
                        'first_name': request.user.first_name,
                        'last_name': request.user.last_name,
                        'email': request.user.email,
                    }
                })
            else:
                return JsonResponse({
                    'success': False,
                    'errors': form.errors,
                }, status=400)
                
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data.',
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e),
            }, status=500)


class UploadDocumentAPIView(LoginRequiredMixin, View):
    """API view for uploading documents via AJAX."""
    
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def post(self, request):
        """Handle document upload."""
        try:
            form = DocumentUploadForm(request.POST, request.FILES)
            
            if form.is_valid():
                document = DocumentService.upload_document(
                    user=request.user,
                    document_type=form.cleaned_data['document_type'],
                    file_obj=form.cleaned_data['document'],
                    description=form.cleaned_data.get('description', '')
                )
                
                return JsonResponse({
                    'success': True,
                    'message': 'Document uploaded successfully.',
                    'document': {
                        'id': document.id,
                        'type': document.get_document_type_display(),
                        'status': document.get_status_display(),
                        'uploaded_at': document.created_at.isoformat(),
                        'file_size': document.file_size,
                    }
                })
            else:
                return JsonResponse({
                    'success': False,
                    'errors': form.errors,
                }, status=400)
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e),
            }, status=500)


class CheckUsernameView(View):
    """API view for checking username availability."""
    
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get(self, request):
        """Check if username is available."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        username = request.GET.get('username', '').strip().lower()
        
        if not username:
            return JsonResponse({
                'available': False,
                'message': 'Username is required.',
            })
        
        # Check if username is taken
        exists = User.objects.filter(username=username).exists()
        
        return JsonResponse({
            'available': not exists,
            'message': 'Username is available.' if not exists else 'Username is already taken.',
        })