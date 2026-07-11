from django import template


register = template.Library()


@register.filter
def duration_hms(value):
    try:
        total_seconds = max(int(float(value or 0)), 0)
    except (TypeError, ValueError):
        total_seconds = 0

    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours:
        return f'{hours}시간 {minutes}분 {seconds}초'
    if minutes:
        return f'{minutes}분 {seconds}초'
    return f'{seconds}초'
