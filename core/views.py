import random

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from courses.models import Course


def home(request):
    public_courses = Course.objects.filter(is_public=True)
    public_course_ids = list(public_courses.values_list('id', flat=True))
    selected_ids = random.sample(public_course_ids, min(2, len(public_course_ids)))
    selected_courses = {
        course.pk: course
        for course in public_courses.filter(pk__in=selected_ids).prefetch_related('lessons')
    }
    courses = [selected_courses[course_id] for course_id in selected_ids if course_id in selected_courses]
    featured_course = courses[0] if courses else None
    return render(
        request,
        'core/home.html',
        {
            'featured_course': featured_course,
            'courses': courses,
            'course_count': len(public_course_ids),
            'lesson_count': sum(course.lesson_count for course in courses),
        },
    )


def privacy_policy(request):
    return render(request, 'core/privacy_policy.html')


@staff_member_required
def ui_preview(request):
    return render(request, 'core/ui_preview.html')
