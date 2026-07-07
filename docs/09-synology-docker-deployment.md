# Synology NAS Docker Compose 배포 가이드

## 구성 개요

운영 구성은 다음 컨테이너 3개를 기준으로 한다.

- `web`: Django + Gunicorn
- `db`: PostgreSQL
- `nginx`: reverse proxy, static/media 서빙, protected private media 서빙

```text
Browser
  -> Synology Reverse Proxy 또는 Nginx
  -> Django web
  -> PostgreSQL

영상 요청:
Browser -> /lessons/<id>/video/ -> Django 권한 확인
        -> X-Accel-Redirect: /protected-media/...
        -> Nginx internal location에서 private_media 파일 전송
```

## NAS 폴더 구조 예시

Synology File Station 또는 SSH에서 다음처럼 폴더를 준비한다.

```text
/volume1/docker/onedu/
  app/                 # Git checkout 또는 프로젝트 파일
  data/
    postgres/
    static/
    media/
    private_media/
  backups/
    db/
    media/
    private_media/
```

`.env`에서는 다음 값들을 NAS 실제 경로로 바꿀 수 있다.

```env
ONEDU_DB_DIR=/volume1/docker/onedu/data/postgres
ONEDU_STATIC_DIR=/volume1/docker/onedu/data/static
ONEDU_MEDIA_DIR=/volume1/docker/onedu/data/media
ONEDU_PRIVATE_MEDIA_DIR=/volume1/docker/onedu/data/private_media
```

## 환경변수 준비

1. `.env.example`을 참고해 `.env`를 만든다.
2. `.env`는 Git에 커밋하지 않는다.
3. 운영 필수 값:

```env
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=충분히-긴-랜덤-문자열
DJANGO_ALLOWED_HOSTS=lms.example.com,nas.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://lms.example.com
POSTGRES_PASSWORD=충분히-긴-랜덤-비밀번호
USE_X_ACCEL_REDIRECT=True
```

## HTTPS 적용 방식

권장 방식은 Synology Reverse Proxy에서 HTTPS 인증서를 적용하고, 내부적으로 `nginx:80`으로 전달하는 것이다.

Synology Reverse Proxy 예시:

- Source: `https://lms.example.com:443`
- Destination: `http://127.0.0.1:8080`
- WebSocket은 현재 필요 없음
- `X-Forwarded-Proto: https` 헤더가 전달되어야 한다.

이 경우 `.env`에는 다음을 권장한다.

```env
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_SESSION_COOKIE_SECURE=True
DJANGO_CSRF_COOKIE_SECURE=True
```

HSTS는 도메인과 인증서 운영이 안정화된 뒤 켠다.

```env
DJANGO_SECURE_HSTS_SECONDS=31536000
DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=True
DJANGO_SECURE_HSTS_PRELOAD=False
```

## 실행 절차

```bash
cd /volume1/docker/onedu/app
cp .env.example .env
vi .env
docker compose config
docker compose build
docker compose up -d
docker compose logs -f web
```

`web` 컨테이너는 시작 시 기본적으로 다음을 수행한다.

- DB 연결 대기
- `python manage.py migrate --noinput`
- `python manage.py collectstatic --noinput`
- Gunicorn 실행

필요하면 `.env`에서 끌 수 있다.

```env
DJANGO_RUN_MIGRATIONS=0
DJANGO_COLLECTSTATIC=0
```

## 운영 확인

```bash
docker compose ps
docker compose logs --tail=100 web
docker compose logs --tail=100 nginx
docker compose exec web python manage.py check --deploy
```

브라우저에서 확인할 URL:

- `/courses/`
- `/accounts/login/`
- `/certificates/verify/`
- 관리자: `/admin/`

## 한글 PDF 폰트

Dockerfile은 `fonts-nanum`을 설치한다. 기본 설정은 다음이다.

```env
CERTIFICATE_FONT_PATH=/usr/share/fonts/truetype/nanum/NanumGothic.ttf
```

다른 폰트를 쓰려면 컨테이너에 폰트 파일을 넣고 해당 경로를 지정한다.

## 운영 전 체크리스트

- `DJANGO_DEBUG=False`
- `DJANGO_SECRET_KEY` 교체
- `DJANGO_ALLOWED_HOSTS` 실제 도메인만 설정
- `DJANGO_CSRF_TRUSTED_ORIGINS`에 HTTPS 도메인 설정
- PostgreSQL 비밀번호 교체
- NAS `data/`, `backups/` 폴더 권한 확인
- 영상 업로드/재생 테스트
- 수료증 PDF 한글 출력 테스트
- 수료증 검증 페이지 테스트
- DB와 media/private_media 백업 테스트
