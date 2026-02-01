from django.urls import path
from . import views

app_name = 'ai_tools'

urlpatterns = [
    # Dashboard
    path('', views.AIDashboardView.as_view(), name='dashboard'),
    
    # Individual tools
    path('outline-helper/', views.OutlineHelperView.as_view(), name='outline_helper'),
    path('grammar-checker/', views.GrammarCheckerView.as_view(), name='grammar_checker'),
    path('citation-formatter/', views.CitationFormatterView.as_view(), name='citation_formatter'),
    
    # API endpoints
    path('api/limits/', views.UserLimitsView.as_view(), name='user_limits'),
    path('api/history/', views.UsageHistoryView.as_view(), name='usage_history'),
    path('api/<str:tool_name>/', views.AIToolsAPIView.as_view(), name='api_tool'),
]