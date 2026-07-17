from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'admin', '관리자'
        STUDENT = 'student', '수강생'

    name = models.CharField('이름', max_length=100, blank=True)
    phone = models.CharField('연락처', max_length=30, blank=True)
    role = models.CharField(
        '역할',
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
    )

    @property
    def display_name(self):
        return self.name or self.get_full_name() or self.username

    @property
    def is_lms_admin(self):
        return self.role == self.Role.ADMIN or self.is_staff

    @property
    def is_student(self):
        return self.role == self.Role.STUDENT and not self.is_staff


class AccessLog(models.Model):
    class EventType(models.TextChoices):
        LOGIN_SUCCESS = 'login_success', '로그인 성공'
        LESSON_VIEW = 'lesson_view', '차시 화면 진입'
        VIDEO_ACCESS = 'video_access', '영상 접근'
        HLS_PLAYLIST = 'hls_playlist', 'HLS 재생 시작'
        ATTACHMENT_DOWNLOAD = 'attachment_download', '학습 자료 다운로드'

    user = models.ForeignKey(
        User,
        verbose_name='사용자',
        on_delete=models.CASCADE,
        related_name='access_logs',
    )
    event_type = models.CharField('기록 유형', max_length=30, choices=EventType.choices)
    ip_address = models.GenericIPAddressField('IP 주소', blank=True, null=True)
    user_agent = models.TextField('브라우저 원문', blank=True)
    device_summary = models.CharField('기기 정보', max_length=160, blank=True)
    session_key = models.CharField('세션 키', max_length=40, blank=True, db_index=True)
    path = models.CharField('요청 경로', max_length=500, blank=True)
    course_id_value = models.PositiveBigIntegerField('강의 ID', blank=True, null=True)
    course_title = models.CharField('강의명', max_length=200, blank=True)
    lesson_id_value = models.PositiveBigIntegerField('차시 ID', blank=True, null=True)
    lesson_title = models.CharField('차시명', max_length=200, blank=True)
    is_suspicious = models.BooleanField('주의 필요', default=False, db_index=True)
    suspicious_reason = models.CharField('주의 사유', max_length=255, blank=True)
    created_at = models.DateTimeField('기록일시', auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = '접속 보안 로그'
        verbose_name_plural = '접속 보안 로그'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['event_type', '-created_at']),
            models.Index(fields=['ip_address', '-created_at']),
            models.Index(fields=['is_suspicious', '-created_at']),
        ]

    def __str__(self):
        created = timezone.localtime(self.created_at).strftime('%Y-%m-%d %H:%M')
        return f'{self.user} / {self.get_event_type_display()} / {created}'


class AccountWithdrawalRequest(models.Model):
    class Status(models.TextChoices):
        REQUESTED = 'requested', '요청 접수'
        PROCESSING = 'processing', '처리 중'
        COMPLETED = 'completed', '처리 완료'
        CANCELED = 'canceled', '요청 취소'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='사용자',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='withdrawal_requests',
    )
    status = models.CharField('상태', max_length=20, choices=Status.choices, default=Status.REQUESTED, db_index=True)
    reason = models.TextField('요청 사유', blank=True)
    username_snapshot = models.CharField('아이디', max_length=150, blank=True)
    name_snapshot = models.CharField('이름', max_length=100, blank=True)
    email_snapshot = models.EmailField('이메일', blank=True)
    phone_snapshot = models.CharField('연락처', max_length=30, blank=True)
    requested_at = models.DateTimeField('요청일시', auto_now_add=True, db_index=True)
    processed_at = models.DateTimeField('처리일시', null=True, blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='처리 관리자',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_withdrawal_requests',
    )
    admin_note = models.TextField('관리자 메모', blank=True)

    class Meta:
        verbose_name = '계정 탈퇴 요청'
        verbose_name_plural = '계정 탈퇴 요청'
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['status', '-requested_at']),
            models.Index(fields=['user', '-requested_at']),
        ]

    def __str__(self):
        user_label = self.name_snapshot or self.username_snapshot or '알 수 없음'
        return f'{user_label} / {self.get_status_display()}'

    @property
    def is_active_request(self):
        return self.status in (self.Status.REQUESTED, self.Status.PROCESSING)

    def save(self, *args, **kwargs):
        if self.user_id:
            self.username_snapshot = self.username_snapshot or self.user.username
            self.name_snapshot = self.name_snapshot or self.user.display_name
            self.email_snapshot = self.email_snapshot or self.user.email
            self.phone_snapshot = self.phone_snapshot or self.user.phone
        if self.status in (self.Status.COMPLETED, self.Status.CANCELED) and self.processed_at is None:
            self.processed_at = timezone.now()
        super().save(*args, **kwargs)
