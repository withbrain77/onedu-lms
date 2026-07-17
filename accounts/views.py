from smtplib import SMTPException
from urllib.parse import urlparse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import (
    LoginView,
    PasswordChangeDoneView,
    PasswordChangeView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.core.mail import BadHeaderError
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, FormView, UpdateView

from .forms import (
    AccountWithdrawalRequestForm,
    BootstrapAuthenticationForm,
    BootstrapPasswordChangeForm,
    BootstrapPasswordResetForm,
    BootstrapSetPasswordForm,
    StudentSignUpForm,
    StudentProfileForm,
    UsernameLookupForm,
)
from .models import AccessLog, AccountWithdrawalRequest, User
from .services import record_access_log


REMEMBER_USERNAME_COOKIE = 'onedu_remembered_username'
REMEMBER_USERNAME_MAX_AGE = 60 * 60 * 24 * 180


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

    def get_initial(self):
        initial = super().get_initial()
        remembered_username = self.request.COOKIES.get(REMEMBER_USERNAME_COOKIE, '').strip()
        if remembered_username:
            initial['username'] = remembered_username
            initial['remember_username'] = True
        return initial

    def get_success_url(self):
        user = self.request.user
        if user.is_staff or getattr(user, 'role', None) == User.Role.ADMIN:
            return reverse('admin:index')
        return reverse('enrollments:classroom')

    def form_valid(self, form):
        response = super().form_valid(form)
        record_access_log(self.request, AccessLog.EventType.LOGIN_SUCCESS)
        if form.cleaned_data.get('remember_username'):
            response.set_cookie(
                REMEMBER_USERNAME_COOKIE,
                form.cleaned_data.get('username', '').strip(),
                max_age=REMEMBER_USERNAME_MAX_AGE,
                secure=self.request.is_secure(),
                httponly=True,
                samesite='Lax',
            )
        else:
            response.delete_cookie(REMEMBER_USERNAME_COOKIE, samesite='Lax')
        return response


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    form_class = StudentProfileForm
    template_name = 'accounts/profile.html'
    success_url = reverse_lazy('accounts:profile')

    def get_object(self, queryset=None):
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_withdrawal_request'] = (
            AccountWithdrawalRequest.objects
            .filter(
                user=self.request.user,
                status__in=[
                    AccountWithdrawalRequest.Status.REQUESTED,
                    AccountWithdrawalRequest.Status.PROCESSING,
                ],
            )
            .order_by('-requested_at')
            .first()
        )
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, '내 정보가 저장되었습니다.')
        return response


class AccountWithdrawalRequestView(LoginRequiredMixin, FormView):
    form_class = AccountWithdrawalRequestForm
    template_name = 'accounts/withdrawal_request.html'
    success_url = reverse_lazy('accounts:profile')

    def get_active_request(self):
        return (
            AccountWithdrawalRequest.objects
            .filter(
                user=self.request.user,
                status__in=[
                    AccountWithdrawalRequest.Status.REQUESTED,
                    AccountWithdrawalRequest.Status.PROCESSING,
                ],
            )
            .order_by('-requested_at')
            .first()
        )

    def dispatch(self, request, *args, **kwargs):
        self.active_request = self.get_active_request() if request.user.is_authenticated else None
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_withdrawal_request'] = self.active_request
        return context

    def form_valid(self, form):
        if self.active_request:
            messages.info(self.request, '이미 처리 대기 중인 계정 탈퇴 요청이 있습니다.')
            return redirect('accounts:profile')

        AccountWithdrawalRequest.objects.create(
            user=self.request.user,
            reason=form.cleaned_data.get('reason', '').strip(),
        )
        messages.success(self.request, '계정 탈퇴 요청이 접수되었습니다. 운영자가 확인 후 처리합니다.')
        return redirect(self.get_success_url())


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

    def get_password_reset_options(self):
        options = {
            'use_https': self.request.is_secure(),
            'token_generator': self.token_generator,
            'from_email': self.from_email,
            'email_template_name': self.email_template_name,
            'subject_template_name': self.subject_template_name,
            'request': self.request,
            'html_email_template_name': self.html_email_template_name,
            'extra_email_context': self.extra_email_context,
        }

        if settings.PUBLIC_SITE_URL:
            public_url = urlparse(settings.PUBLIC_SITE_URL)
            if public_url.scheme and public_url.netloc:
                options['domain_override'] = public_url.netloc
                options['use_https'] = public_url.scheme == 'https'

        return options

    def form_valid(self, form):
        try:
            form.save(**self.get_password_reset_options())
            return HttpResponseRedirect(self.get_success_url())
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


class LMSPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    form_class = BootstrapPasswordChangeForm
    template_name = 'accounts/password_change_form.html'
    success_url = reverse_lazy('accounts:password_change_done')


class LMSPasswordChangeDoneView(LoginRequiredMixin, PasswordChangeDoneView):
    template_name = 'accounts/password_change_done.html'


@login_required
@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, '로그아웃되었습니다.')
    return redirect('courses:list')
