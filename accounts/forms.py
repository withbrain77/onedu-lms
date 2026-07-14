from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)

from .models import User


class BootstrapFormMixin:
    def apply_bootstrap(self):
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault('class', 'form-check-input')
            else:
                widget.attrs.setdefault('class', 'form-control')


class BootstrapAuthenticationForm(BootstrapFormMixin, AuthenticationForm):
    remember_username = forms.BooleanField(
        label='아이디 기억하기',
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()
        self.fields['username'].label = '아이디'
        self.fields['username'].widget.attrs.setdefault('autocomplete', 'username')
        self.fields['password'].widget.attrs.setdefault('autocomplete', 'current-password')


class StudentSignUpForm(BootstrapFormMixin, UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'name', 'email', 'phone')
        labels = {
            'username': '아이디',
            'name': '이름',
            'email': '이메일',
            'phone': '연락처',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()
        self.fields['email'].required = True
        self.fields['name'].required = True
        self.fields['password1'].label = '비밀번호'
        self.fields['password2'].label = '비밀번호 확인'

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('이미 가입된 이메일 주소입니다. 아이디 찾기 또는 비밀번호 재설정을 이용해 주세요.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.STUDENT
        if commit:
            user.save()
        return user


class StudentProfileForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ('name', 'email', 'phone')
        labels = {
            'name': '이름',
            'email': '이메일',
            'phone': '연락처',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()
        self.fields['name'].required = True
        self.fields['email'].required = True
        self.fields['name'].widget.attrs.setdefault('autocomplete', 'name')
        self.fields['email'].widget.attrs.setdefault('autocomplete', 'email')
        self.fields['phone'].widget.attrs.setdefault('autocomplete', 'tel')

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        queryset = User.objects.filter(email__iexact=email)
        if self.instance and self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        if email and queryset.exists():
            raise forms.ValidationError('이미 다른 계정에서 사용 중인 이메일 주소입니다.')
        return email


class UsernameLookupForm(BootstrapFormMixin, forms.Form):
    name = forms.CharField(label='이름', max_length=100)
    email = forms.EmailField(label='이메일')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()
        self.fields['name'].widget.attrs.setdefault('autocomplete', 'name')
        self.fields['email'].widget.attrs.setdefault('autocomplete', 'email')


class BootstrapPasswordResetForm(BootstrapFormMixin, PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()
        self.fields['email'].label = '가입 이메일'
        self.fields['email'].widget.attrs.setdefault('autocomplete', 'email')


class BootstrapSetPasswordForm(BootstrapFormMixin, SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()
        self.fields['new_password1'].label = '새 비밀번호'
        self.fields['new_password2'].label = '새 비밀번호 확인'


class BootstrapPasswordChangeForm(BootstrapFormMixin, PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()
        self.fields['old_password'].label = '현재 비밀번호'
        self.fields['new_password1'].label = '새 비밀번호'
        self.fields['new_password2'].label = '새 비밀번호 확인'
        self.fields['old_password'].widget.attrs.setdefault('autocomplete', 'current-password')
        self.fields['new_password1'].widget.attrs.setdefault('autocomplete', 'new-password')
        self.fields['new_password2'].widget.attrs.setdefault('autocomplete', 'new-password')
