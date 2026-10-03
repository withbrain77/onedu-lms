from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from enrollments.models import Enrollment, ReEnrollmentRequest
from .models import RevenueRecord


@receiver(post_save, sender=Enrollment)
def prepare_enrollment_revenue(sender, instance, raw=False, **kwargs):
    if raw or instance.payment_status != Enrollment.PaymentStatus.CONFIRMED or not instance.course.is_paid:
        return
    # Read persisted fields: save(update_fields=...) may leave other instance fields unsaved.
    saved = Enrollment.objects.get(pk=instance.pk)
    if saved.payment_status == Enrollment.PaymentStatus.CONFIRMED:
        RevenueRecord.objects.get_or_create(enrollment=saved, defaults={
            'course_id': saved.course_id,
            'received_on': timezone.localdate(saved.payment_confirmed_at) if saved.payment_confirmed_at else None,
        })


@receiver(post_save, sender=ReEnrollmentRequest)
def prepare_renewal_revenue(sender, instance, raw=False, **kwargs):
    if raw or not instance.course.is_paid:
        return
    saved = ReEnrollmentRequest.objects.get(pk=instance.pk)
    if saved.status == ReEnrollmentRequest.Status.APPROVED and saved.price_krw != 0:
        # Approval is not evidence of actual payment date or amount.
        RevenueRecord.objects.get_or_create(renewal=saved, defaults={'course_id': saved.course_id})
