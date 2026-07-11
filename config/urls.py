from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from core.views import home, ui_preview

urlpatterns = [
    path('', home, name='home'),
    path('ui-preview/', ui_preview, name='ui_preview'),
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('courses/', include('courses.urls')),
    path('classroom/', include('enrollments.urls')),
    path('lessons/', include('lessons.urls')),
    path('progress/', include('progress.urls')),
    path('quizzes/', include('quizzes.urls')),
    path('certificates/', include('certificates.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
