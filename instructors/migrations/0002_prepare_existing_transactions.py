from django.db import migrations
from django.utils import timezone


def prepare_existing(apps, schema_editor):
    Enrollment = apps.get_model('enrollments', 'Enrollment')
    Renewal = apps.get_model('enrollments', 'ReEnrollmentRequest')
    Revenue = apps.get_model('instructors', 'RevenueRecord')
    db = schema_editor.connection.alias
    for enrollment in Enrollment.objects.using(db).filter(payment_status='confirmed', course__pricing_type='paid').iterator():
        Revenue.objects.using(db).get_or_create(enrollment_id=enrollment.pk, defaults={
            'course_id': enrollment.course_id,
            'received_on': timezone.localdate(enrollment.payment_confirmed_at) if enrollment.payment_confirmed_at else None,
            'note': '도입 전 거래: 실제 입금액과 당시 정산 기준을 확인해 주세요.',
        })
    for renewal in Renewal.objects.using(db).filter(status='approved', course__pricing_type='paid').exclude(price_krw=0).iterator():
        Revenue.objects.using(db).get_or_create(renewal_id=renewal.pk, defaults={
            'course_id': renewal.course_id,
            'note': '도입 전 재수강: 승인만으로 입금액·입금일을 추정하지 않습니다. 실제 내역을 확인해 주세요.',
        })


class Migration(migrations.Migration):
    dependencies = [('instructors', '0001_initial'), ('accounts', '0004_user_is_instructor')]
    operations = [migrations.RunPython(prepare_existing, migrations.RunPython.noop)]
