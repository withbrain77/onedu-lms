from django import forms

from .models import ReEnrollmentRequest


class ReEnrollmentRequestForm(forms.ModelForm):
    class Meta:
        model = ReEnrollmentRequest
        fields = ('reason',)
        labels = {
            'reason': '재수강 신청 사유',
        }
        widgets = {
            'reason': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 4,
                    'placeholder': '재수강이 필요한 이유를 간단히 입력하세요.',
                }
            ),
        }

    def clean_reason(self):
        reason = self.cleaned_data['reason'].strip()
        if len(reason) < 5:
            raise forms.ValidationError('신청 사유를 5자 이상 입력해 주세요.')
        return reason
