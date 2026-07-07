from django.urls import path

from . import views

app_name = 'certificates'

urlpatterns = [
    path('verify/', views.verify_certificate, name='verify'),
    path('<int:pk>/download/', views.download_certificate, name='download'),
]
