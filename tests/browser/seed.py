import json
from datetime import timedelta

from django.contrib import admin
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from accounts.models import User, AccessLog
from courses.models import Course
from lessons.models import Lesson, LessonAttachment, LessonAttachmentDownload
from enrollments.models import Enrollment, ReEnrollmentRequest
from core.models import Notice
from quizzes.models import Quiz, Question, AnswerChoice
from progress.models import WatchProgress


def seed(root):
    staff, _ = User.objects.get_or_create(username='browseradmin', defaults={'is_staff': True, 'is_superuser': True})
    student, _ = User.objects.get_or_create(username='browserstudent', defaults={
        'name': '모바일 긴 이름 점검 수강생', 'email': 'mobile.long.name.for.layout@example.invalid'})
    for user in (staff, student):
        user.set_password('Browser-only-2026!')
        user.save()
    course, _ = Course.objects.get_or_create(slug='browser-layout', defaults={
        'title': '뇌과학과 학습 관리 심화 세미나 및 실무 적용 과정 2026 — 긴 제목 점검'})
    Course.objects.get_or_create(slug='browser-paid', defaults={
        'title': '입금 안내 확인 과정', 'pricing_type': 'paid', 'price_krw': 30000})
    lesson, _ = Lesson.objects.get_or_create(course=course, order=1, defaults={
        'title': '뇌과학 교육 프로그램의 실무 적용과 긴 차시 제목 화면 점검', 'duration_seconds': 600})
    today = timezone.localdate()
    enrollment, _ = Enrollment.objects.update_or_create(user=student, course=course, defaults={
        'status': 'approved', 'start_date': today - timedelta(days=1), 'end_date': today + timedelta(days=7)})
    WatchProgress.objects.get_or_create(user=student, enrollment=enrollment, lesson=lesson)
    expired, _ = Course.objects.get_or_create(slug='browser-expired', defaults={'title': '기간 만료 과정'})
    old, _ = Enrollment.objects.update_or_create(user=student, course=expired, defaults={
        'status': 'approved', 'start_date': today-timedelta(days=40), 'end_date': today-timedelta(days=10)})
    ReEnrollmentRequest.objects.get_or_create(enrollment=old, user=student, course=expired, status='pending')
    AccessLog.objects.get_or_create(user=student, event_type='login_success', ip_address='2001:db8:1234:5678:abcd:1234:5678:9012', defaults={
        'is_suspicious': True, 'device_summary': 'Android Phone / Chrome'})
    attachment, _ = LessonAttachment.objects.get_or_create(lesson=lesson, title='긴 제목 교육 자료 — 실무 적용 사례 PDF 교재', defaults={'file': 'lesson_attachments/layout.pdf'})
    LessonAttachmentDownload.objects.get_or_create(user=student, attachment=attachment, defaults={
        'lesson': lesson, 'course': course, 'attachment_title': attachment.title})
    notice, _ = Notice.objects.get_or_create(title='모바일 화면 점검용 긴 공지 제목', defaults={
        'content': 'https://example.invalid/materials/VeryLongResourceIdentifierForResponsiveLayoutTesting2026'})
    quiz, _ = Quiz.objects.get_or_create(course=course, title='긴 시험 제목 학습 내용 확인 평가')
    question, _ = Question.objects.get_or_create(quiz=quiz, order=1, defaults={
        'type': 'multiple_choice', 'text': '학습 내용을 확인하고 올바른 보기를 선택하세요. ' * 5})
    AnswerChoice.objects.get_or_create(question=question, order=1, defaults={'text': '긴 시험 보기 화면 확인 ' * 8, 'is_correct': True})
    routes = {
        'public': ['/', '/courses/', course.get_absolute_url(), '/notices/', reverse('notice_detail', args=[notice.pk]),
                   '/privacy/', '/install/', '/accounts/login/', '/accounts/signup/', '/accounts/find-username/',
                   '/accounts/password-reset/', '/certificates/verify/', '/admin/login/'],
        'student': ['/', '/classroom/', '/classroom/?status=ended', f'/classroom/{course.pk}/',
                    '/accounts/profile/', '/accounts/password-change/', '/accounts/withdrawal-request/',
                    lesson.get_absolute_url(), reverse('quizzes:take', args=[quiz.pk])],
        'admin': ['/admin/', '/admin/ops/mobile/', '/admin/password_change/'],
    }
    request = RequestFactory().get('/admin/')
    request.user = staff
    for model, model_admin in admin.site._registry.items():
        prefix = f'admin:{model._meta.app_label}_{model._meta.model_name}'
        routes['admin'].append(reverse(prefix + '_changelist'))
        if model_admin.has_add_permission(request):
            routes['admin'].append(reverse(prefix + '_add'))
        obj = model.objects.first()
        if obj:
            routes['admin'].append(reverse(prefix + '_change', args=[obj.pk]))
    (root / '.browser-tests/routes.json').write_text(json.dumps(routes), encoding='utf-8')
