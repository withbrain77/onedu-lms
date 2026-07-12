from datetime import timedelta

from django.core import mail
from django.test import override_settings
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from courses.models import Course
from enrollments.models import Enrollment
from lessons.models import Lesson


class MVPFlowViewTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.student = User.objects.create_user(
            username='student',
            password='pass12345',
            name='테스트 수강생',
        )
        self.course = Course.objects.create(
            title='업무 보안 기본 교육',
            description='업무에 필요한 기본 보안 강의입니다.',
            is_public=True,
            pricing_type=Course.PricingType.PAID,
            price_krw=30000,
        )
        self.lesson = Lesson.objects.create(
            course=self.course,
            title='1차시 보안 기본',
            order=1,
            is_public=True,
        )

    def login_student(self):
        self.client.force_login(self.student)

    def test_anonymous_course_detail_is_visible_without_login(self):
        self.course.thumbnail = 'course_thumbnails/test-thumb.png'
        self.course.save(update_fields=['thumbnail'])

        response = self.client.get(self.course.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.course.title)
        self.assertContains(response, 'course-detail-intro')
        self.assertContains(response, 'course-detail-thumb')
        self.assertContains(response, 'course_thumbnails/test-thumb.png')
        self.assertContains(response, '세미나 안내')
        self.assertContains(response, reverse('accounts:login'))

    def test_paid_course_detail_shows_deposit_notice_to_logged_in_student(self):
        self.login_student()

        response = self.client.get(self.course.get_absolute_url())

        self.assertContains(response, '입금 안내')
        self.assertContains(response, '국민은행')
        self.assertContains(response, '700101-01-323177')
        self.assertContains(response, '표진호(위드브레인)')
        self.assertContains(response, '수강생 이름과 동일하게 입력해 주세요.')

    def test_course_detail_shows_short_share_link(self):
        short_path = reverse('course_short_link', kwargs={'course_id': self.course.pk})

        response = self.client.get(self.course.get_absolute_url())

        self.assertContains(response, '강의 주소 공유하기')
        self.assertContains(response, short_path)
        self.assertContains(response, 'data-course-share-url="http://testserver')
        self.assertContains(response, 'course_share.js')

    def test_short_course_link_redirects_to_course_detail(self):
        short_path = reverse('course_short_link', kwargs={'course_id': self.course.pk})

        response = self.client.get(short_path)

        self.assertRedirects(response, self.course.get_absolute_url(), fetch_redirect_response=False)

    def test_short_course_link_ignores_private_courses(self):
        private_course = Course.objects.create(
            title='비공개 강의',
            description='비공개 강의입니다.',
            is_public=False,
        )

        response = self.client.get(reverse('course_short_link', kwargs={'course_id': private_course.pk}))

        self.assertEqual(response.status_code, 404)

    def test_anonymous_classroom_redirects_to_login(self):
        response = self.client.get(reverse('enrollments:classroom'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response['Location'])

    def test_logged_in_student_can_view_course_list(self):
        self.login_student()
        response = self.client.get(reverse('courses:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.course.title)
        self.assertContains(response, '이용료')
        self.assertContains(response, '30,000원')
        self.assertContains(response, '운영자 확인 후 승인')
        self.assertContains(response, '수강 신청')

    def test_course_list_classroom_cta_is_visible_for_students(self):
        self.login_student()

        response = self.client.get(reverse('courses:list'))

        self.assertContains(response, 'page-header-cta')
        self.assertContains(response, reverse('enrollments:classroom'))
        self.assertContains(response, '내 강의실')

    def test_student_can_apply_and_waiting_state_is_visible(self):
        self.login_student()
        response = self.client.post(reverse('courses:apply', kwargs={'slug': self.course.slug}))
        self.assertRedirects(response, reverse('enrollments:classroom'))

        enrollment = Enrollment.objects.get(user=self.student, course=self.course)
        self.assertEqual(enrollment.status, Enrollment.Status.REQUESTED)

        classroom = self.client.get(reverse('enrollments:classroom'))
        self.assertContains(classroom, '신청 대기')
        self.assertContains(classroom, '관리자 승인 대기')
        self.assertContains(classroom, '입금 안내')
        self.assertContains(classroom, '국민은행')
        self.assertContains(classroom, '700101-01-323177')

        course_list = self.client.get(reverse('courses:list'))
        self.assertContains(course_list, self.course.get_absolute_url())
        self.assertContains(course_list, '상세 보기')
        self.assertContains(course_list, '승인 대기 중')

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        ONEDU_NOTIFY_ENROLLMENT_REQUEST=True,
        ONEDU_ADMIN_NOTIFICATION_EMAILS=['admin@example.com'],
        PUBLIC_SITE_URL='https://onedu.withbrain.kr',
    )
    def test_paid_course_application_sends_admin_notification_email(self):
        self.login_student()

        self.client.post(reverse('courses:apply', kwargs={'slug': self.course.slug}))

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ['admin@example.com'])
        self.assertIn('[ONEDU]', message.subject)
        self.assertIn(self.course.title, message.body)
        self.assertIn(self.student.username, message.body)
        self.assertIn('https://onedu.withbrain.kr/admin/enrollments/enrollment/', message.body)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        ONEDU_NOTIFY_ENROLLMENT_REQUEST=True,
        ONEDU_ADMIN_NOTIFICATION_EMAILS=[],
        EMAIL_HOST_USER='operator@example.com',
    )
    def test_paid_course_application_can_use_smtp_account_as_admin_notification_recipient(self):
        self.login_student()

        self.client.post(reverse('courses:apply', kwargs={'slug': self.course.slug}))

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['operator@example.com'])

    def test_free_course_application_is_auto_approved(self):
        free_course = Course.objects.create(
            title='무료 공개 강의',
            description='무료로 볼 수 있는 강의입니다.',
            is_public=True,
            pricing_type=Course.PricingType.FREE,
            price_krw=0,
            default_enrollment_days=14,
        )
        free_lesson = Lesson.objects.create(
            course=free_course,
            title='무료 1차시',
            order=1,
            is_public=True,
        )
        self.login_student()

        response = self.client.post(reverse('courses:apply', kwargs={'slug': free_course.slug}))

        enrollment = Enrollment.objects.get(user=self.student, course=free_course)
        self.assertEqual(enrollment.status, Enrollment.Status.APPROVED)
        self.assertEqual(enrollment.start_date, self.today)
        self.assertEqual(enrollment.end_date, self.today + timedelta(days=14))
        self.assertRedirects(response, reverse('enrollments:course_detail', kwargs={'course_id': free_course.pk}))

        lesson_response = self.client.get(free_lesson.get_absolute_url())
        self.assertEqual(lesson_response.status_code, 200)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        ONEDU_NOTIFY_ENROLLMENT_REQUEST=True,
        ONEDU_ADMIN_NOTIFICATION_EMAILS=['admin@example.com'],
    )
    def test_free_course_application_does_not_send_admin_notification_email(self):
        free_course = Course.objects.create(
            title='Free Notification Course',
            description='Free course should not notify admins.',
            is_public=True,
            pricing_type=Course.PricingType.FREE,
            price_krw=0,
            default_enrollment_days=14,
        )
        self.login_student()

        self.client.post(reverse('courses:apply', kwargs={'slug': free_course.slug}))

        self.assertEqual(len(mail.outbox), 0)

    def test_free_course_price_and_policy_are_visible(self):
        free_course = Course.objects.create(
            title='무료 영상 과정',
            description='무료 영상입니다.',
            is_public=True,
            pricing_type=Course.PricingType.FREE,
            price_krw=0,
            default_enrollment_days=30,
        )
        self.login_student()

        list_response = self.client.get(reverse('courses:list'))
        detail_response = self.client.get(free_course.get_absolute_url())

        self.assertContains(list_response, '무료')
        self.assertContains(list_response, '신청 즉시 수강 가능')
        self.assertContains(detail_response, '무료 프로그램입니다.')
        self.assertContains(detail_response, '무료 수강 신청')
        self.assertNotContains(detail_response, '700101-01-323177')

    def test_requested_enrollment_cannot_access_lesson(self):
        Enrollment.objects.create(user=self.student, course=self.course)
        self.login_student()
        response = self.client.get(self.lesson.get_absolute_url())
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, '관리자 승인 대기 중입니다.', status_code=403)

    def test_approved_enrollment_can_access_lesson(self):
        Enrollment.objects.create(
            user=self.student,
            course=self.course,
            status=Enrollment.Status.APPROVED,
            start_date=self.today - timedelta(days=1),
            end_date=self.today + timedelta(days=7),
        )
        self.login_student()
        response = self.client.get(self.lesson.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'lessons/detail.html')

    def test_future_start_date_cannot_access_classroom_course(self):
        Enrollment.objects.create(
            user=self.student,
            course=self.course,
            status=Enrollment.Status.APPROVED,
            start_date=self.today + timedelta(days=1),
            end_date=self.today + timedelta(days=7),
        )
        self.login_student()
        response = self.client.get(reverse('enrollments:course_detail', kwargs={'course_id': self.course.pk}))
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, '아직 수강 시작일 전입니다.', status_code=403)

    def test_expired_enrollment_cannot_access_classroom_course(self):
        Enrollment.objects.create(
            user=self.student,
            course=self.course,
            status=Enrollment.Status.APPROVED,
            start_date=self.today - timedelta(days=7),
            end_date=self.today - timedelta(days=1),
        )
        self.login_student()
        response = self.client.get(reverse('enrollments:course_detail', kwargs={'course_id': self.course.pk}))
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, '수강 기간이 종료되었습니다.', status_code=403)
