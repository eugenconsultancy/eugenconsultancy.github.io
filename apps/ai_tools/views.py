from django.shortcuts import render, redirect
from django.views import View
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
import json
from .models import AIToolUsageLog as AIToolUsage, GrammarCheckRequest, CitationRequest, OutlineRequest

from .services import (
    OutlineHelperService, 
    GrammarCheckerService, 
    CitationFormatterService
)
from .services.limit_service import AILimitService
from .models import AIToolConfiguration, AIToolTemplate, CitationStyle
from .serializers import (
    OutlineRequestSerializer, 
    GrammarCheckSerializer,
    CitationFormatSerializer,
    BatchCitationSerializer
)


class AIBaseView(LoginRequiredMixin):
    """Base view for AI tools with common functionality"""
    
    def dispatch(self, request, *args, **kwargs):
        # Check if AI tools are enabled globally
        if not self._are_ai_tools_enabled():
            messages.error(
                request,
                "AI tools are currently disabled. Please try again later."
            )
            return redirect('dashboard')
        
        return super().dispatch(request, *args, **kwargs)
    
    def _are_ai_tools_enabled(self) -> bool:
        """Check if AI tools are enabled globally"""
        # This could be controlled by a feature flag or configuration
        return True
    
    def _check_tool_access(self, request, tool_type: str) -> tuple:
        """Check if user can access a specific tool"""
        can_use, reason, limits = AILimitService.can_user_use_tool(
            request.user, 
            tool_type
        )
        
        if not can_use:
            return False, reason
        
        return True, ""
    
    def _get_user_limits(self, request) -> dict:
        """Get user's AI tool limits"""
        return AILimitService.get_user_limits(request.user)


class AIDashboardView(AIBaseView, TemplateView):
    """Dashboard for AI tools"""
    
    template_name = 'ai_tools/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get user limits
        context['user_limits'] = self._get_user_limits(self.request)
        
        # Get available tools
        context['available_tools'] = AIToolConfiguration.objects.filter(
            is_enabled=True
        ).values('tool_type', 'daily_limit_per_user')
        
        # Get templates for outline helper
        context['templates'] = AIToolTemplate.objects.filter(
            is_active=True
        ).values('template_type', 'name', 'academic_level').distinct()
        
        # Get citation styles
        context['citation_styles'] = CitationStyle.objects.filter(
            is_active=True
        ).values('abbreviation', 'name')
        
        return context


class OutlineHelperView(AIBaseView, View):
    """View for outline helper tool"""
    
    def get(self, request):
        """Render outline helper form"""
        
        # Check access
        can_use, reason = self._check_tool_access(request, 'outline_helper')
        if not can_use:
            messages.error(request, reason)
            return redirect('ai_tools:dashboard')
        
        # Get templates
        templates = AIToolTemplate.objects.filter(is_active=True)
        
        context = {
            'templates': templates,
            'user_limits': self._get_user_limits(request),
        }
        
        return render(request, 'ai_tools/outline_helper.html', context)
    
    @method_decorator(csrf_exempt)
    def post(self, request):
        """Generate outline"""
        
        # Check access
        can_use, reason = self._check_tool_access(request, 'outline_helper')
        if not can_use:
            return JsonResponse({
                'error': reason,
                'success': False
            }, status=403)
        
        # Parse request data
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'error': 'Invalid JSON data',
                'success': False
            }, status=400)
        
        # Validate data
        serializer = OutlineRequestSerializer(data=data)
        if not serializer.is_valid():
            return JsonResponse({
                'error': serializer.errors,
                'success': False
            }, status=400)
        
        # Generate outline
        service = OutlineHelperService()
        
        try:
            result = service.generate_outline(
                topic=serializer.validated_data['topic'],
                template_type=serializer.validated_data.get('template_type', 'essay'),
                academic_level=serializer.validated_data.get('academic_level', 'undergraduate'),
                word_count_target=serializer.validated_data.get('word_count_target', 1500),
                user=request.user,
                session_id=request.session.session_key
            )
            
            # Record usage
            AILimitService.record_tool_usage(request.user, 'outline_helper')
            
            return JsonResponse({
                'success': True,
                'result': result,
                'limits': self._get_user_limits(request),
            })
        
        except Exception as e:
            return JsonResponse({
                'error': f'Error generating outline: {str(e)}',
                'success': False
            }, status=500)


class GrammarCheckerView(AIBaseView, View):
    """View for grammar checker tool"""
    
    def get(self, request):
        """Render grammar checker form"""
        
        # Check access
        can_use, reason = self._check_tool_access(request, 'grammar_checker')
        if not can_use:
            messages.error(request, reason)
            return redirect('ai_tools:dashboard')
        
        context = {
            'user_limits': self._get_user_limits(request),
        }
        
        return render(request, 'ai_tools/grammar_checker.html', context)
    
    @method_decorator(csrf_exempt)
    def post(self, request):
        """Check grammar"""
        
        # Check access
        can_use, reason = self._check_tool_access(request, 'grammar_checker')
        if not can_use:
            return JsonResponse({
                'error': reason,
                'success': False
            }, status=403)
        
        # Parse request data
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'error': 'Invalid JSON data',
                'success': False
            }, status=400)
        
        # Validate data
        serializer = GrammarCheckSerializer(data=data)
        if not serializer.is_valid():
            return JsonResponse({
                'error': serializer.errors,
                'success': False
            }, status=400)
        
        # Check grammar
        service = GrammarCheckerService()
        
        try:
            result = service.check_text(
                text=serializer.validated_data['text'],
                check_type=serializer.validated_data.get('check_type', 'all'),
                academic_level=serializer.validated_data.get('academic_level', 'undergraduate'),
                user=request.user,
                session_id=request.session.session_key
            )
            
            # Record usage
            AILimitService.record_tool_usage(request.user, 'grammar_checker')
            
            return JsonResponse({
                'success': True,
                'result': result,
                'limits': self._get_user_limits(request),
            })
        
        except Exception as e:
            return JsonResponse({
                'error': f'Error checking grammar: {str(e)}',
                'success': False
            }, status=500)


class CitationFormatterView(AIBaseView, View):
    """View for citation formatter tool"""
    
    def get(self, request):
        """Render citation formatter form"""
        
        # Check access
        can_use, reason = self._check_tool_access(request, 'citation_formatter')
        if not can_use:
            messages.error(request, reason)
            return redirect('ai_tools:dashboard')
        
        # Get citation styles
        styles = CitationStyle.objects.filter(is_active=True)
        
        context = {
            'styles': styles,
            'publication_types': [
                ('book', 'Book'),
                ('journal', 'Journal Article'),
                ('website', 'Website'),
                ('conference', 'Conference Paper'),
                ('thesis', 'Thesis/Dissertation'),
                ('report', 'Report'),
                ('newspaper', 'Newspaper Article'),
                ('chapter', 'Book Chapter'),
            ],
            'user_limits': self._get_user_limits(request),
        }
        
        return render(request, 'ai_tools/citation_formatter.html', context)
    
    @method_decorator(csrf_exempt)
    def post(self, request):
        """Format citation"""
        
        # Check access
        can_use, reason = self._check_tool_access(request, 'citation_formatter')
        if not can_use:
            return JsonResponse({
                'error': reason,
                'success': False
            }, status=403)
        
        # Parse request data
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'error': 'Invalid JSON data',
                'success': False
            }, status=400)
        
        # Check if batch request
        is_batch = data.get('batch', False)
        
        if is_batch:
            serializer = BatchCitationSerializer(data=data)
        else:
            serializer = CitationFormatSerializer(data=data)
        
        if not serializer.is_valid():
            return JsonResponse({
                'error': serializer.errors,
                'success': False
            }, status=400)
        
        # Format citation(s)
        service = CitationFormatterService()
        
        try:
            if is_batch:
                result = service.batch_format_citations(
                    citations_list=serializer.validated_data['citations'],
                    style=serializer.validated_data.get('style', 'apa'),
                    output_format=serializer.validated_data.get('output_format', 'text'),
                    sort_by=serializer.validated_data.get('sort_by', 'author'),
                    user=request.user,
                    session_id=request.session.session_key
                )
            else:
                result = service.format_citation(
                    citation_data=serializer.validated_data['citation_data'],
                    style=serializer.validated_data.get('style', 'apa'),
                    output_format=serializer.validated_data.get('output_format', 'text'),
                    user=request.user,
                    session_id=request.session.session_key
                )
            
            # Record usage
            AILimitService.record_tool_usage(request.user, 'citation_formatter')
            
            return JsonResponse({
                'success': True,
                'result': result,
                'limits': self._get_user_limits(request),
            })
        
        except Exception as e:
            return JsonResponse({
                'error': f'Error formatting citation: {str(e)}',
                'success': False
            }, status=500)


class UserLimitsView(AIBaseView, APIView):
    """API view for user limits"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get user's AI tool limits"""
        
        limits = AILimitService.get_user_limits(request.user)
        
        return Response({
            'success': True,
            'limits': limits,
        })


class UsageHistoryView(AIBaseView, APIView):
    """API view for user's AI tool usage history"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get user's usage history"""
        
        from .models import AIToolUsageLog
        from django.db.models import Count
        from django.utils import timezone
        
        # Get parameters
        days = int(request.GET.get('days', 7))
        tool_type = request.GET.get('tool_type', None)
        
        # Calculate date range
        end_date = timezone.now()
        start_date = end_date - timezone.timedelta(days=days)
        
        # Build query
        queryset = AIToolUsageLog.objects.filter(
            user=request.user,
            created_at__gte=start_date,
            created_at__lte=end_date
        )
        
        if tool_type:
            queryset = queryset.filter(tool_type=tool_type)
        
        # Get usage by date
        usage_by_date = queryset.extra(
            select={'date': 'DATE(created_at)'}
        ).values('date').annotate(
            count=Count('id')
        ).order_by('date')
        
        # Get recent uses
        recent_uses = queryset.select_related('reviewed_by').order_by('-created_at')[:10]
        
        # Serialize recent uses
        recent_uses_data = []
        for usage in recent_uses:
            recent_uses_data.append({
                'id': str(usage.id),
                'tool_type': usage.get_tool_type_display(),
                'created_at': usage.created_at.isoformat(),
                'input_preview': usage.input_text[:100] + '...' if len(usage.input_text) > 100 else usage.input_text,
                'is_reviewed': usage.is_reviewed,
                'reviewed_by': usage.reviewed_by.get_full_name() if usage.reviewed_by else None,
                'reviewed_at': usage.reviewed_at.isoformat() if usage.reviewed_at else None,
            })
        
        return Response({
            'success': True,
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
                'days': days,
            },
            'usage_by_date': list(usage_by_date),
            'recent_uses': recent_uses_data,
            'total_uses': queryset.count(),
        })


class AIToolsAPIView(APIView):
    """REST API for AI tools"""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request, tool_name):
        """Handle AI tool API requests"""
        
        # Map tool names to services
        service_map = {
            'outline': OutlineHelperService,
            'grammar': GrammarCheckerService,
            'citation': CitationFormatterService,
        }
        
        if tool_name not in service_map:
            return Response({
                'error': f'Tool {tool_name} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check access
        can_use, reason, limits = AILimitService.can_user_use_tool(
            request.user, 
            self._get_tool_type(tool_name)
        )
        
        if not can_use:
            return Response({
                'error': reason,
                'limits': limits
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Process request based on tool
        try:
            result = self._process_tool_request(
                tool_name, 
                service_map[tool_name], 
                request
            )
            
            # Record usage
            AILimitService.record_tool_usage(
                request.user, 
                self._get_tool_type(tool_name)
            )
            
            return Response({
                'success': True,
                'result': result,
                'limits': AILimitService.get_user_limits(request.user),
            })
        
        except Exception as e:
            return Response({
                'error': str(e),
                'success': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _get_tool_type(self, tool_name: str) -> str:
        """Convert API tool name to tool type"""
        
        tool_map = {
            'outline': 'outline_helper',
            'grammar': 'grammar_checker',
            'citation': 'citation_formatter',
        }
        
        return tool_map.get(tool_name, tool_name)
    
    def _process_tool_request(self, tool_name: str, service_class, request):
        """Process tool-specific request"""
        
        service = service_class()
        
        if tool_name == 'outline':
            serializer = OutlineRequestSerializer(data=request.data)
            if not serializer.is_valid():
                raise ValueError(serializer.errors)
            
            return service.generate_outline(
                topic=serializer.validated_data['topic'],
                template_type=serializer.validated_data.get('template_type', 'essay'),
                academic_level=serializer.validated_data.get('academic_level', 'undergraduate'),
                word_count_target=serializer.validated_data.get('word_count_target', 1500),
                user=request.user,
                session_id=request.session.session_key if hasattr(request, 'session') else ''
            )
        
        elif tool_name == 'grammar':
            serializer = GrammarCheckSerializer(data=request.data)
            if not serializer.is_valid():
                raise ValueError(serializer.errors)
            
            return service.check_text(
                text=serializer.validated_data['text'],
                check_type=serializer.validated_data.get('check_type', 'all'),
                academic_level=serializer.validated_data.get('academic_level', 'undergraduate'),
                user=request.user,
                session_id=request.session.session_key if hasattr(request, 'session') else ''
            )
        
        elif tool_name == 'citation':
            is_batch = request.data.get('batch', False)
            
            if is_batch:
                serializer = BatchCitationSerializer(data=request.data)
                if not serializer.is_valid():
                    raise ValueError(serializer.errors)
                
                return service.batch_format_citations(
                    citations_list=serializer.validated_data['citations'],
                    style=serializer.validated_data.get('style', 'apa'),
                    output_format=serializer.validated_data.get('output_format', 'text'),
                    sort_by=serializer.validated_data.get('sort_by', 'author'),
                    user=request.user,
                    session_id=request.session.session_key if hasattr(request, 'session') else ''
                )
            else:
                serializer = CitationFormatSerializer(data=request.data)
                if not serializer.is_valid():
                    raise ValueError(serializer.errors)
                
                return service.format_citation(
                    citation_data=serializer.validated_data['citation_data'],
                    style=serializer.validated_data.get('style', 'apa'),
                    output_format=serializer.validated_data.get('output_format', 'text'),
                    user=request.user,
                    session_id=request.session.session_key if hasattr(request, 'session') else ''
                )
        
        raise ValueError(f'Unknown tool: {tool_name}')