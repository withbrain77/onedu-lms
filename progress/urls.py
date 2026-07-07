from django.urls import path

from . import views

app_name = 'progress'

urlpatterns = [
    path('lessons/<int:lesson_id>/save/', views.save_lesson_progress, name='save_lesson'),
]
