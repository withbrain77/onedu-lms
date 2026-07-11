from smtplib import SMTPException

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    LoginView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.core.mail import BadHeaderError
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, FormView

from .forms import (
    BootstrapAuthenticationForm,
    BootstrapPasswordResetForm,
    BootstrapSetPasswordForm,
    StudentSignUpForm,
    UsernameLookupForm,
)
from .models import User


class SignUpView(CreateView):
    form_class = StudentSignUpForm
    template_name = 'accounts/signup.html'
    success_url = reverse_lazy('accounts:login')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, '회원가입이 완료되었습니다. 로그인 후 수강 신청을 진행해 주세요.')
        return response


class LMSLoginView(LoginView):
    authentication_form = BootstrapAuthenticationForm
    template_name = 'accounts/login.html'

    def get_success_url(self):
        user = self.request.user
        if user.is_staff or getattr(user, 'role', None) == User.Role.ADMIN:
            return reverse('admin:index')
        return reverse('enrollments:classroom')


class UsernameLookupView(FormView):
    form_class = UsernameLookupForm
    template_name = 'accounts/find_username.html'

    def form_valid(self, form):
        users = User.objects.filter(
            is_active=True,
            name__iexact=form.cleaned_data['name'].strip(),
            email__iexact=form.cleaned_data['email'].strip(),
        ).order_by('date_joined')
        return render(
            self.request,
            self.template_name,
            {
                'form': form,
                'submitted': True,
                'found_users': users,
            },
        )


class LMSPasswordResetView(PasswordResetView):
    form_class = BootstrapPasswordResetForm
    template_name = 'accounts/password_reset_form.html'
    email_template_name = 'accounts/password_reset_email.txt'
    subject_template_name = 'accounts/password_reset_subject.txt'
    success_url = reverse_lazy('accounts:password_reset_done')

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except (BadHeaderError, OSError, SMTPException):
            messages.error(
                self.request,
                '비밀번호 재설정 메일을 발송하지 못했습니다. 운영자에게 메일 설정 확인을 요청해 주세요.',
            )
            return self.form_invalid(form)


class LMSPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'accounts/password_reset_done.html'


class LMSPasswordResetConfirmView(PasswordResetConfirmView):
    form_class = BootstrapSetPasswordForm
    template_name = 'accounts/password_reset_confirm.html'
    success_url = reverse_lazy('accounts:password_reset_complete')


class LMSPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'accounts/password_reset_complete.html'


@login_required
@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, '로그아웃되었습니다.')
    return redirect('courses:list')
