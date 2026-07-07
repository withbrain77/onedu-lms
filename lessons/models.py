from django.db import models
from django.urls import reverse


class Lesson(models.Model):
    course = models.ForeignKey(
        'courses.Course',
        verbose_name='강의',
        on_delete=models.CASCADE,
        related_name='lessons',
    )
    title = models.CharField('차시명', max_length=200)
    description = models.TextField('차시 설명', blank=True)
    video_file = models.FileField('영상 파일', upload_to='lesson_videos/', blank=True)
    order = models.PositiveIntegerField('순서', default=1)
    duration_seconds = models.PositiveIntegerField('영상 길이(초)', default=0)
    is_public = models.BooleanField('공개 여부', default=True)
    created_at = models.DateTimeField('생성일', auto_now_add=True)
    updated_at = models.DateTimeField('수정일', auto_now=True)

    class Meta:
        verbose_name = '차시'
        verbose_name_plural = '차시'
        ordering = ['course', 'order', 'id']
        constraints = [
            models.UniqueConstraint(fields=['course', 'order'], name='unique_lesson_order_per_course'),
        ]

    def __str__(self):
        return f'{self.course.title} - {self.order}. {self.title}'

    def get_absolute_url(self):
        return reverse('lessons:detail', kwargs={'pk': self.pk})

    def get_video_url(self):
        return reverse('lessons:video', kwargs={'pk': self.pk})
