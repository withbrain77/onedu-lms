from django.urls import path

from .views import (
    LMSLoginView,
    LMSPasswordChangeDoneView,
    LMSPasswordChangeView,
    LMSPasswordResetCompleteView,
    LMSPasswordResetConfirmView,
    LMSPasswordResetDoneView,
    LMSPasswordResetView,
    ProfileUpdateView,
    SignUpView,
    UsernameLookupView,
    logout_view,
)

app_name = 'accounts'

urlpatterns = [
    path('signup/', SignUpView.as_view(), name='signup'),
    path('login/', LMSLoginView.as_view(), name='login'),
    path('profile/', ProfileUpdateView.as_view(), name='profile'),
    path('find-username/', UsernameLookupView.as_view(), name='find_username'),
    path('password-change/', LMSPasswordChangeView.as_view(), name='password_change'),
    path('password-change/done/', LMSPasswordChangeDoneView.as_view(), name='password_change_done'),
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
