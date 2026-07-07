from django.urls import path

from . import views

app_name = 'enrollments'

urlpatterns = [
    path('', views.classroom, name='classroom'),
    path('<int:course_id>/', views.classroom_course_detail, name='course_detail'),
]
