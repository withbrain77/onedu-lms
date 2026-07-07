from dataclasses import dataclass
from typing import Optional

from django.utils import timezone

from enrollments.models import Enrollment


@dataclass
class AccessResult:
    allowed: bool
    code: str
    message: str
    enrollment: Optional[Enrollment] = None


def get_latest_enrollment(user, course):
    if not getattr(user, 'is_authenticated', False):
        return None
    return (
        Enrollment.objects
        .filter(user=user, course=course)
        .select_related('course', 'user')
        .order_by('-created_at')
        .first()
    )


def can_access_course(user, course, today=None):
    if not getattr(user, 'is_authenticated', False):
        return AccessResult(False, 'login_required', '로그인이 필요합니다.')

    if user.is_staff:
        return AccessResult(True, 'admin_preview', '관리자 미리보기 접근입니다.')

    enrollment = get_latest_enrollment(user, course)
    if enrollment is None:
        return AccessResult(False, 'not_applied', '수강 신청 후 관리자 승인이 필요합니다.')

    if enrollment.status == Enrollment.Status.REQUESTED:
        return AccessResult(False, 'waiting_approval', '관리자 승인 대기 중입니다.', enrollment)

    if enrollment.status == Enrollment.Status.REJECTED:
        return AccessResult(False, 'rejected', '수강 신청이 반려되었습니다.', enrollment)

    if enrollment.status == Enrollment.Status.CANCELLED:
        return AccessResult(False, 'cancelled', '취소된 수강 신청입니다.', enrollment)

    if enrollment.status != Enrollment.Status.APPROVED:
        return AccessResult(False, 'not_approved', '승인된 수강 신청이 없습니다.', enrollment)

    if not enrollment.start_date or not enrollment.end_date:
        return AccessResult(False, 'period_missing', '수강 기간이 아직 설정되지 않았습니다.', enrollment)

    today = today or timezone.localdate()
    if today < enrollment.start_date:
        return AccessResult(False, 'not_started', '아직 수강 시작일 전입니다.', enrollment)

    if today > enrollment.end_date:
        return AccessResult(False, 'ended', '수강 기간이 종료되었습니다.', enrollment)

    return AccessResult(True, 'allowed', '접근 가능합니다.', enrollment)


def can_access_lesson(user, lesson, today=None):
    return can_access_course(user, lesson.course, today=today)
