from django.conf import settings


def onedu_settings(request):
    return {
        'onedu_deposit_notice': settings.ONEDU_DEPOSIT_NOTICE,
    }
