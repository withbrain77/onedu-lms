from django.conf import settings
from django.db import models


class ServerWarningAcknowledgement(models.Model):
    warning_key = models.CharField('경고 키', max_length=120)
    message_hash = models.CharField('메시지 해시', max_length=64)
    message = models.TextField('확인한 메시지', blank=True)
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='확인 관리자',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='server_warning_acknowledgements',
    )
    acknowledged_at = models.DateTimeField('확인 일시', auto_now_add=True)

    class Meta:
        verbose_name = '서버 경고 확인'
        verbose_name_plural = '서버 경고 확인'
        unique_together = ('warning_key', 'message_hash')
        ordering = ['-acknowledged_at']
        indexes = [
            models.Index(fields=['warning_key', 'message_hash']),
            models.Index(fields=['-acknowledged_at']),
        ]

    def __str__(self):
        return f'{self.warning_key} / {self.acknowledged_at:%Y-%m-%d %H:%M}'
