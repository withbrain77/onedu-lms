from django.apps import AppConfig


class InstructorsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'instructors'
    verbose_name = '강사·정산 관리'

    def ready(self):
        from . import signals  # noqa: F401
