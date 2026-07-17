from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from core.admin_views import acknowledge_server_warning, mobile_operations, server_logs, server_operations
from core.views import home, notice_detail, notice_list, privacy_policy, ui_preview
from courses.views import short_course_redirect

admin.site.index_template = 'admin/onedu_index.html'

urlpatterns = [
    path('', home, name='home'),
    path('notices/', notice_list, name='notice_list'),
    path('notices/<int:notice_id>/', notice_detail, name='notice_detail'),
    path('privacy/', privacy_policy, name='privacy_policy'),
    path('c/<int:course_id>/', short_course_redirect, name='course_short_link'),
    path('ui-preview/', ui_preview, name='ui_preview'),
    path('admin/ops/mobile/', mobile_operations, name='admin_mobile_ops'),
    path('admin/ops/server/', server_operations, name='admin_server_ops'),
    path('admin/ops/logs/', server_logs, name='admin_server_logs'),
    path('admin/ops/server/warnings/ack/', acknowledge_server_warning, name='admin_server_warning_ack'),
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
