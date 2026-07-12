from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from courses.models import Course


def home(request):
    public_courses = Course.objects.filter(is_public=True).prefetch_related('lessons')
    courses = list(
        public_courses
        .order_by('-created_at', '-id')[:2]
    )
    featured_course = courses[0] if courses else None
    return render(
        request,
        'core/home.html',
        {
            'featured_course': featured_course,
            'courses': courses,
            'course_count': public_courses.count(),
            'lesson_count': sum(course.lesson_count for course in courses),
        },
    )


@staff_member_required
def ui_preview(request):
    return render(request, 'core/ui_preview.html')
