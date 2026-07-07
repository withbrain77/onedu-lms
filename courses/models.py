from django.db import models
from django.conf import settings
from django.urls import reverse
from django.utils.text import slugify


class Course(models.Model):
    title = models.CharField('강의명', max_length=200)
    slug = models.SlugField('URL 슬러그', max_length=220, unique=True, blank=True, allow_unicode=True)
    description = models.TextField('강의 설명', blank=True)
    thumbnail = models.FileField('썸네일', upload_to='course_thumbnails/', blank=True)
    is_public = models.BooleanField('공개 여부', default=True)
    required_progress_percent = models.PositiveSmallIntegerField('수료 진도 기준(%)', default=90)
    require_quiz_pass = models.BooleanField('시험 합격 필요', default=True)
    certificate_enabled = models.BooleanField('수료증 발급 사용', default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='생성자',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_courses',
    )
    created_at = models.DateTimeField('생성일', auto_now_add=True)
    updated_at = models.DateTimeField('수정일', auto_now=True)

    class Meta:
        verbose_name = '강의'
        verbose_name_plural = '강의'
        ordering = ['title']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title, allow_unicode=True) or 'course'
            candidate = base_slug
            index = 2
            while Course.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f'{base_slug}-{index}'
                index += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('courses:detail', kwargs={'slug': self.slug})

    @property
    def lesson_count(self):
        return self.lessons.filter(is_public=True).count()
