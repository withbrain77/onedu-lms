from django import template
from django.urls import reverse

from enrollments.models import Enrollment

register = template.Library()


@register.inclusion_tag('admin/includes/enrollment_notifications.html', takes_context=True)
def enrollment_admin_notifications(context, limit=5):
    request = context.get('request')
    if not request or not request.user.is_staff:
        return {
            'show_enrollment_notifications': False,
        }

    pending_qs = (
        Enrollment.objects
        .filter(status=Enrollment.Status.REQUESTED, course__pricing_type='paid')
        .select_related('user', 'course')
        .order_by('-created_at')
    )
    pending_count = pending_qs.count()
    items = [
        {
            'student_name': enrollment.user.display_name,
            'student_username': enrollment.user.username,
            'course_title': enrollment.course.title,
            'created_at': enrollment.created_at,
            'change_url': reverse('admin:enrollments_enrollment_change', args=[enrollment.pk]),
        }
        for enrollment in pending_qs[:limit]
    ]

    return {
        'show_enrollment_notifications': True,
        'pending_enrollment_count': pending_count,
        'pending_enrollments': items,
        'enrollment_changelist_url': (
            reverse('admin:enrollments_enrollment_changelist') + '?status__exact=requested'
        ),
    }
