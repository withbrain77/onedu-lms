from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect, render

from courses.models import Course


def home(request):
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('admin:index')
        return redirect('enrollments:classroom')

    courses = list(
        Course.objects
        .filter(is_public=True)
        .prefetch_related('lessons')
        .order_by('title')[:3]
    )
    featured_course = courses[0] if courses else None
    return render(
        request,
        'core/home.html',
        {
            'featured_course': featured_course,
            'courses': courses,
            'course_count': len(courses),
            'lesson_count': sum(course.lesson_count for course in courses),
        },
    )


@staff_member_required
def ui_preview(request):
    return render(request, 'core/ui_preview.html')
