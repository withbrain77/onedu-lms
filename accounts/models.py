from django.contrib.auth.models import AbstractUser
from django.db import models


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
