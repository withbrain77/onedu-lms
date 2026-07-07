from django.shortcuts import redirect


def home(request):
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('admin:index')
        return redirect('enrollments:classroom')
    return redirect('courses:list')
