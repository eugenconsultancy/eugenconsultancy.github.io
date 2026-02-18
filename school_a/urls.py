from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('accounts.urls')),
    path('students/', include('students.urls')),
    path('teachers/', include('teachers.urls')),
    path('marks/', include('marks.urls')),
    path('payments/', include('payments.urls')),  # Added payments URLs
    path('messages/', include('school_messages.urls')),  # Keep URL as /messages/ but include school_messages.urls
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)