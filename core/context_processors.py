from urllib.parse import urljoin

from django.conf import settings
from django.templatetags.static import static


def onedu_settings(request):
    site_url = settings.PUBLIC_SITE_URL or request.build_absolute_uri('/')
    return {
        'onedu_deposit_notice': settings.ONEDU_DEPOSIT_NOTICE,
        'onedu_share_url': urljoin(site_url, request.path),
        'onedu_share_image_url': urljoin(site_url, static('img/withbrain-logo.png')),
    }
