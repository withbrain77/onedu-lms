from django.urls import path

from .views import LMSLoginView, SignUpView, logout_view

app_name = 'accounts'

urlpatterns = [
    path('signup/', SignUpView.as_view(), name='signup'),
    path('login/', LMSLoginView.as_view(), name='login'),
    path('logout/', logout_view, name='logout'),
]
