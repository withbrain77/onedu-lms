from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()


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

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.STUDENT
        if commit:
            user.save()
        return user
