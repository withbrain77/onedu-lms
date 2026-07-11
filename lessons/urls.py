from django.urls import path

from . import views

app_name = 'lessons'

urlpatterns = [
    path('<int:pk>/watch/', views.lesson_detail, name='detail'),
    path('<int:pk>/video/', views.lesson_video, name='video'),
    path('<int:pk>/hls/playlist.m3u8', views.lesson_hls_playlist, name='hls_playlist'),
    path('<int:pk>/hls/<path:filename>', views.lesson_hls_file, name='hls_file'),
    path('<int:pk>/attachments/<int:attachment_id>/download/', views.lesson_attachment_download, name='attachment_download'),
]
