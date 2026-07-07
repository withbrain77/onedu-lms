from django.urls import path

from . import views

app_name = 'lessons'

urlpatterns = [
    path('<int:pk>/watch/', views.lesson_detail, name='detail'),
]
