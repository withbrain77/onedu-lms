from django.urls import path

from .views import (
    LMSLoginView,
    LMSPasswordResetCompleteView,
    LMSPasswordResetConfirmView,
    LMSPasswordResetDoneView,
    LMSPasswordResetView,
    SignUpView,
    UsernameLookupView,
    logout_view,
)

app_name = 'accounts'

urlpatterns = [
    path('signup/', SignUpView.as_view(), name='signup'),
    path('login/', LMSLoginView.as_view(), name='login'),
    path('find-username/', UsernameLookupView.as_view(), name='find_username'),
    path('password-reset/', LMSPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', LMSPasswordResetDoneView.as_view(), name='password_reset_done'),
    path(
        'reset/<uidb64>/<token>/',
        LMSPasswordResetConfirmView.as_view(),
        name='password_reset_confirm',
    ),
    path('reset/done/', LMSPasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('logout/', logout_view, name='logout'),
]
