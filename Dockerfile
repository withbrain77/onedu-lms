FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-nanum curl ffmpeg gosu \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 10001 onedu \
    && useradd --system --uid 10001 --gid onedu --home-dir /app --shell /usr/sbin/nologin onedu

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/
COPY deploy/entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh \
    && mkdir -p /vol/web/static /vol/web/media /vol/web/private_media /vol/web/private_media/lesson_hls /vol/web/logs \
    && chown -R onedu:onedu /app /vol/web

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
