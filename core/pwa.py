from django.http import JsonResponse
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.http import require_safe


@require_safe
def manifest(request):
    response = JsonResponse({
        'id': reverse('home'),
        'name': '위드브레인연구소 아카데미',
        'short_name': '위드브레인',
        'description': '위드브레인연구소의 교육 영상과 학습 자료를 내 강의실에서 이어보세요.',
        'lang': 'ko',
        'start_url': reverse('enrollments:classroom'),
        'scope': reverse('home'),
        'display': 'standalone',
        'background_color': '#ffffff',
        'theme_color': '#087f7b',
        'icons': [
            {'src': static('img/pwa/withbrain-192.png'), 'sizes': '192x192', 'type': 'image/png', 'purpose': 'any'},
            {'src': static('img/pwa/withbrain-512.png'), 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any maskable'},
        ],
    }, json_dumps_params={'ensure_ascii': False}, content_type='application/manifest+json')
    response['Cache-Control'] = 'public, max-age=3600'
    return response
