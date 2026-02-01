from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'blog'

# API Router
api_router = DefaultRouter()
api_router.register(r'posts', views.BlogPostViewSet, basename='post')
api_router.register(r'categories', views.BlogCategoryViewSet, basename='category')
api_router.register(r'comments', views.BlogCommentViewSet, basename='comment')

urlpatterns = [
    # Public views
    path('', views.BlogHomeView.as_view(), name='home'),
    path('category/<slug:slug>/', views.CategoryDetailView.as_view(), name='category_detail'),
    path('post/<slug:slug>/', views.BlogPostDetailView.as_view(), name='post_detail'),
    path('search/', views.BlogSearchView.as_view(), name='search'),
    path('tags/<slug:tag>/', views.TagListView.as_view(), name='tag_list'),
    path('archive/<int:year>/<int:month>/', views.MonthlyArchiveView.as_view(), name='monthly_archive'),
    
    # Subscription views
    path('subscribe/', views.SubscribeView.as_view(), name='subscribe'),
    path('unsubscribe/<uuid:token>/', views.UnsubscribeView.as_view(), name='unsubscribe'),
    
    # Comment views
    path('post/<slug:slug>/comment/', views.CreateCommentView.as_view(), name='create_comment'),
    path('comment/<uuid:pk>/vote/', views.CommentVoteView.as_view(), name='comment_vote'),
    
    # SEO views
    path('sitemap.xml', views.BlogSitemapView.as_view(), name='sitemap'),
    path('robots.txt', views.RobotsTextView.as_view(), name='robots'),
    
    # API views
    path('api/', include(api_router.urls)),
    path('api/seo-analyze/', views.SEOAnalyzeView.as_view(), name='seo_analyze'),
    
    # Admin/author views (protected)
    path('dashboard/', views.AuthorDashboardView.as_view(), name='author_dashboard'),
    path('create/', views.CreateBlogPostView.as_view(), name='create_post'),
    path('edit/<slug:slug>/', views.EditBlogPostView.as_view(), name='edit_post'),
    path('preview/<slug:slug>/', views.PostPreviewView.as_view(), name='post_preview'),
    path('stats/<slug:slug>/', views.PostStatsView.as_view(), name='post_stats'),
]