from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView

from .forms import BootstrapAuthenticationForm, StudentSignUpForm
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


@login_required
@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, '로그아웃되었습니다.')
    return redirect('courses:list')
