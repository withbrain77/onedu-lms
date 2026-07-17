import random

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from courses.models import Course
from .models import Notice


def _published_notices():
    return Notice.objects.filter(
        is_published=True,
        published_at__lte=timezone.now(),
    ).filter(Q(course__isnull=True) | Q(course__is_public=True))


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
            'notices': _published_notices().filter(course__isnull=True)[:3],
            'course_count': len(public_course_ids),
            'lesson_count': sum(course.lesson_count for course in courses),
        },
    )


def notice_list(request):
    notices = _published_notices().select_related('course')
    return render(request, 'core/notice_list.html', {'notices': notices})


def notice_detail(request, notice_id):
    notice = get_object_or_404(
        _published_notices().select_related('course'),
        pk=notice_id,
    )
    return render(request, 'core/notice_detail.html', {'notice': notice})


def privacy_policy(request):
    return render(request, 'core/privacy_policy.html')


@staff_member_required
def ui_preview(request):
    return render(request, 'core/ui_preview.html')
