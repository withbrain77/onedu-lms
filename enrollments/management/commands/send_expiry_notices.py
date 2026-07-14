from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from enrollments.models import Enrollment
from enrollments.notifications import notify_enrollment_expiry_7d


class Command(BaseCommand):
    help = 'Send one-time enrollment expiry notice emails for enrollments ending in 7 days.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print matching enrollments without sending emails or updating records.',
        )
        parser.add_argument(
            '--date',
            help='Override the local date used for matching, in YYYY-MM-DD format.',
        )

    def handle(self, *args, **options):
        today = self._resolve_today(options.get('date'))
        target_date = today + timedelta(days=7)
        dry_run = options['dry_run']

        enrollments = (
            Enrollment.objects
            .select_related('user', 'course')
            .filter(
                status=Enrollment.Status.APPROVED,
                is_completed=False,
                end_date=target_date,
                expiry_notice_7d_sent_at__isnull=True,
            )
            .order_by('end_date', 'pk')
        )

        matched = enrollments.count()
        sent = 0
        skipped = 0

        for enrollment in enrollments.iterator():
            label = f'{enrollment.pk} {enrollment.user.username} {enrollment.course.title}'
            if dry_run:
                self.stdout.write(f'[dry-run] {label}')
                continue

            if notify_enrollment_expiry_7d(enrollment):
                enrollment.expiry_notice_7d_sent_at = timezone.now()
                enrollment.save(update_fields=['expiry_notice_7d_sent_at', 'updated_at'])
                sent += 1
                self.stdout.write(self.style.SUCCESS(f'[sent] {label}'))
            else:
                skipped += 1
                self.stdout.write(self.style.WARNING(f'[skipped] {label}'))

        self.stdout.write(
            f'today={today} target_end_date={target_date} matched={matched} sent={sent} skipped={skipped} dry_run={dry_run}'
        )

    def _resolve_today(self, date_value):
        if not date_value:
            return timezone.localdate()
        try:
            return datetime.strptime(date_value, '%Y-%m-%d').date()
        except ValueError as exc:
            raise CommandError('--date must be in YYYY-MM-DD format.') from exc
