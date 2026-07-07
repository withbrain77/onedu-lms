from django.urls import path

from . import views

app_name = 'certificates'

urlpatterns = [
    path('<int:pk>/download/', views.download_certificate, name='download'),
]
