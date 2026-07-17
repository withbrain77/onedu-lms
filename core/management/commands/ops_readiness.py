from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.utils import OperationalError, ProgrammingError
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from accounts.models import AccessLog
from courses.models import Course
from enrollments.models import EmailDeliveryLog, Enrollment, ReEnrollmentRequest
from lessons.models import HLSConversionJob


class Command(BaseCommand):
    help = 'Check operational readiness signals before or during production operation.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fail-on-warnings',
            action='store_true',
            help='Exit with an error when warnings are found.',
        )

    def handle(self, *args, **options):
        warnings = []
        errors = []
        now = timezone.now()
        day_ago = now - timezone.timedelta(hours=24)

        self._check_database(errors)
        self._check_migrations(warnings)
        self._check_paths(warnings, errors)

        pending_payment_count = self._safe_count(
            Enrollment.objects.filter(
                status=Enrollment.Status.REQUESTED,
                course__pricing_type=Course.PricingType.PAID,
                payment_status=Enrollment.PaymentStatus.PENDING,
            ),
            warnings,
            '입금 확인 대기',
        )
        failed_email_count = self._safe_count(
            EmailDeliveryLog.objects.filter(
                status=EmailDeliveryLog.Status.FAILED,
                created_at__gte=day_ago,
            ),
            warnings,
            '최근 24시간 메일 실패',
        )
        queued_email_count = self._safe_count(
            EmailDeliveryLog.objects.filter(status=EmailDeliveryLog.Status.QUEUED),
            warnings,
            '발송 대기 메일',
        )
        failed_hls_count = self._safe_count(
            HLSConversionJob.objects.filter(status=HLSConversionJob.Status.FAILED),
            warnings,
            'HLS 변환 실패',
        )
        running_hls_count = self._safe_count(
            HLSConversionJob.objects.filter(status=HLSConversionJob.Status.RUNNING),
            warnings,
            'HLS 변환 중',
        )
        suspicious_count = self._safe_count(
            AccessLog.objects.filter(is_suspicious=True, created_at__gte=day_ago),
            warnings,
            '최근 24시간 접속 주의',
        )
        pending_reenrollment_count = self._safe_count(
            ReEnrollmentRequest.objects.filter(status=ReEnrollmentRequest.Status.PENDING),
            warnings,
            '재수강 승인 대기',
        )

        if failed_email_count:
            warnings.append(f'최근 24시간 메일 발송 실패 {failed_email_count}건')
        if queued_email_count:
            warnings.append(f'발송 대기 중인 메일 {queued_email_count}건')
        if failed_hls_count:
            warnings.append(f'HLS 변환 실패 {failed_hls_count}건')
        if suspicious_count:
            warnings.append(f'최근 24시간 접속 주의 기록 {suspicious_count}건')

        self.stdout.write(self.style.MIGRATE_HEADING('ONEDU 운영 점검'))
        self.stdout.write(f'- 입금 확인 대기: {pending_payment_count}건')
        self.stdout.write(f'- 재수강 승인 대기: {pending_reenrollment_count}건')
        self.stdout.write(f'- HLS 변환 중: {running_hls_count}건')
        self.stdout.write(f'- 최근 24시간 메일 실패: {failed_email_count}건')
        self.stdout.write(f'- 최근 24시간 접속 주의: {suspicious_count}건')

        if errors:
            for item in errors:
                self.stderr.write(self.style.ERROR(f'ERROR: {item}'))
            raise CommandError('운영 점검에서 오류가 발견되었습니다.')

        if warnings:
            for item in warnings:
                self.stdout.write(self.style.WARNING(f'WARNING: {item}'))
            if options['fail_on_warnings']:
                raise CommandError('운영 점검에서 경고가 발견되었습니다.')
        else:
            self.stdout.write(self.style.SUCCESS('운영 점검 경고가 없습니다.'))

    def _check_database(self, errors):
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                cursor.fetchone()
        except Exception as exc:
            errors.append(f'DB 연결 실패: {type(exc).__name__}: {exc}')

    def _check_migrations(self, warnings):
        try:
            executor = MigrationExecutor(connection)
            targets = executor.loader.graph.leaf_nodes()
            plan = executor.migration_plan(targets)
        except Exception as exc:
            warnings.append(f'마이그레이션 상태 확인 실패: {type(exc).__name__}: {exc}')
            return
        if plan:
            warnings.append(f'미적용 마이그레이션 {len(plan)}개')

    def _check_paths(self, warnings, errors):
        path_items = [
            ('STATIC_ROOT', settings.STATIC_ROOT, False),
            ('MEDIA_ROOT', settings.MEDIA_ROOT, True),
            ('PRIVATE_MEDIA_ROOT', settings.PRIVATE_MEDIA_ROOT, True),
            ('ONEDU_LOG_DIR', getattr(settings, 'ONEDU_LOG_DIR', ''), True),
        ]
        for label, raw_path, should_be_writable in path_items:
            if not raw_path:
                warnings.append(f'{label} 경로가 비어 있습니다.')
                continue
            path = Path(raw_path)
            if not path.exists():
                warnings.append(f'{label} 경로가 없습니다: {path}')
                continue
            if should_be_writable and not self._is_writable(path):
                errors.append(f'{label} 경로에 쓸 수 없습니다: {path}')

    def _is_writable(self, path):
        probe = path / '.onedu-write-test'
        try:
            probe.write_text('ok', encoding='utf-8')
            probe.unlink(missing_ok=True)
            return True
        except Exception:
            return False

    def _safe_count(self, queryset, warnings, label):
        try:
            return queryset.count()
        except (OperationalError, ProgrammingError) as exc:
            warnings.append(f'{label} 조회 실패: {type(exc).__name__}: {exc}')
            return 0
