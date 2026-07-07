from django.urls import path

from . import views

app_name = 'courses'

urlpatterns = [
    path('', views.course_list, name='list'),
    path('<str:slug>/', views.course_detail, name='detail'),
    path('<str:slug>/apply/', views.apply_course, name='apply'),
]
