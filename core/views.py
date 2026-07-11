from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect, render


def home(request):
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('admin:index')
        return redirect('enrollments:classroom')
    return redirect('courses:list')


@staff_member_required
def ui_preview(request):
    return render(request, 'core/ui_preview.html')
