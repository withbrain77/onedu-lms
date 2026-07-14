# 운영 배포 전 최종 체크리스트

이 문서는 Synology NAS에 Onedu LMS를 배포하기 직전에 관리자가 순서대로 확인하기 위한 체크리스트다.

## 1. 배포 전 준비물

- [ ] 운영 도메인 준비
  - 예: `lms.example.com`
- [ ] HTTPS 인증서 준비
  - Synology DSM 인증서 또는 외부 인증서
- [ ] Synology Container Manager 설치
- [ ] 프로젝트 파일 준비
  - Git clone 또는 압축 파일 업로드
  - 예: `/volume1/docker/onedu/app`
- [ ] NAS 데이터 폴더 준비
  - `/volume1/docker/onedu/data/postgres`
  - `/volume1/docker/onedu/data/static`
  - `/volume1/docker/onedu/data/media`
  - `/volume1/docker/onedu/data/private_media`
  - `/volume1/docker/onedu/data/redis`
  - `/volume1/docker/onedu/backups`
- [ ] `.env` 파일 준비
  - `.env.example`을 복사해 실제 값으로 수정
- [ ] 한글 PDF 폰트 확인
  - 기본 Docker 이미지: `/usr/share/fonts/truetype/nanum/NanumGothic.ttf`
  - 별도 폰트 사용 시 컨테이너에서 접근 가능한 경로 확인

## 2. `.env` 필수 설정

다음 값은 운영 배포 전에 반드시 확인한다.

```env
DJANGO_DEBUG=False
```

- 운영에서는 반드시 `False`여야 한다.

```env
DJANGO_SECRET_KEY=충분히-긴-랜덤-문자열
```

- 기본 예시값을 그대로 사용하지 않는다.
- 외부에 노출되면 즉시 교체한다.

```env
DJANGO_ALLOWED_HOSTS=lms.example.com,nas.example.com
```

- 실제 접속 도메인만 입력한다.
- 여러 값은 쉼표로 구분한다.

```env
DJANGO_CSRF_TRUSTED_ORIGINS=https://lms.example.com
```

- HTTPS 스킴을 포함한다.
- Synology Reverse Proxy에서 쓰는 실제 외부 URL을 넣는다.

```env
POSTGRES_DB=onedu
POSTGRES_USER=onedu
POSTGRES_PASSWORD=충분히-긴-랜덤-비밀번호
```

- DB 비밀번호는 예시값을 사용하지 않는다.
- DB 컨테이너를 처음 만든 뒤에는 같은 데이터 폴더에서 DB 이름/사용자/비밀번호를 임의 변경하지 않는다.

```env
CERTIFICATE_FONT_PATH=/usr/share/fonts/truetype/nanum/NanumGothic.ttf
```

- 수료증 PDF 한글 깨짐 여부와 직접 연결된다.

```env
USE_X_ACCEL_REDIRECT=True
X_ACCEL_REDIRECT_PREFIX=/protected-media/
```

- 운영에서는 Django가 직접 영상을 전송하지 않고 Nginx internal location을 사용하게 한다.

```env
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1
CELERY_VIDEO_QUEUE=video
CELERY_WORKER_CONCURRENCY=1
```

- HLS 변환 작업 큐 설정이다.
- NAS 부하를 줄이기 위해 worker 동시 실행 수는 기본 `1`을 권장한다.

```env
DJANGO_EMAIL_HOST=smtp.example.com
DJANGO_EMAIL_PORT=587
DJANGO_EMAIL_HOST_USER=no-reply@example.com
DJANGO_EMAIL_HOST_PASSWORD=메일-앱-비밀번호
DJANGO_EMAIL_USE_TLS=True
DJANGO_DEFAULT_FROM_EMAIL=Onedu LMS <no-reply@example.com>
ONEDU_NOTIFY_ENROLLMENT_REQUEST=True
ONEDU_NOTIFY_ENROLLMENT_APPROVAL=True
ONEDU_ADMIN_NOTIFICATION_EMAIL=admin@example.com
```

- 유료 강의 수강 신청이 접수되면 `ONEDU_ADMIN_NOTIFICATION_EMAIL` 주소로 승인요청 메일이 발송된다.
- 관리자가 수강 신청을 승인하면 수강생 이메일 주소로 승인 안내 메일이 발송된다.
- 여러 관리자에게 보내려면 `ONEDU_ADMIN_NOTIFICATION_EMAILS=admin1@example.com,admin2@example.com`처럼 쉼표로 구분한다.
- `ONEDU_ADMIN_NOTIFICATION_EMAIL`을 비워 두면 SMTP 로그인 계정인 `DJANGO_EMAIL_HOST_USER`가 기본 수신자가 된다.
- 무료 강의는 신청 즉시 자동 승인되므로 승인요청 메일을 보내지 않는다.

## 3. 배포 명령 순서

프로젝트 폴더에서 실행한다.

```bash
cd /volume1/docker/onedu/app
cp .env.example .env
vi .env
```

Compose 설정 확인:

```bash
docker compose config
```

이미지 빌드:

```bash
docker compose build
```

서비스 실행:

```bash
docker compose up -d
```

웹 컨테이너 로그 확인:

```bash
docker compose logs -f web
```

HLS 변환 worker 로그 확인:

```bash
docker compose logs -f worker
```

관리자 계정 생성:

```bash
docker compose exec web python manage.py createsuperuser
```

운영 보안 체크:

```bash
docker compose exec web python manage.py check --deploy
```

## 4. 배포 후 기능 확인

### 기본 접속

- [ ] `/courses/` 접속 가능
- [ ] `/accounts/login/` 접속 가능
- [ ] `/admin/` 접속 가능
- [ ] 관리자 계정 로그인 가능

### 관리자 기능

- [ ] 강의 생성 가능
- [ ] 강의 공개/비공개 설정 가능
- [ ] 차시 생성 가능
- [ ] 영상 업로드 가능
- [ ] 차시 수정 화면에서 HLS 변환 요청 가능
- [ ] `HLS 변환 작업` 메뉴에서 대기/진행/완료/실패 상태 확인 가능
- [ ] 시험/문제/보기 생성 가능
- [ ] 수강 신청 목록 확인 가능
- [ ] 수강 승인 및 시작일/종료일 설정 가능
- [ ] 수료증 목록 확인 가능
- [ ] 재수강 신청 목록 확인 가능

### 수강생 흐름

- [ ] 회원가입 가능
- [ ] 로그인 가능
- [ ] 강의 목록 확인 가능
- [ ] 수강 신청 가능
- [ ] 승인 전에는 차시 접근 차단
- [ ] 승인 후 내 강의실에 강의 표시
- [ ] 수강 시작일 전 접근 차단
- [ ] 수강 종료일 후 접근 차단
- [ ] 영상 재생 가능
- [ ] HLS 변환 완료 차시가 HLS로 재생됨
- [ ] 영상 위 워터마크 표시
- [ ] 진도 저장 표시 동작
- [ ] 시험 응시 가능
- [ ] 시험 합격/불합격 표시
- [ ] 수료 조건 충족 시 수료 완료 표시
- [ ] 수료증 다운로드 가능
- [ ] `/certificates/verify/`에서 검증 코드 확인 가능
- [ ] 기간 만료 후 재수강 신청 가능
- [ ] 관리자 재수강 승인 후 다시 접근 가능

## 5. 보안 확인

- [ ] `.env`가 웹으로 노출되지 않음
- [ ] `.env`가 Git에 커밋되지 않음
- [ ] `DJANGO_DEBUG=False`
- [ ] `DJANGO_SECRET_KEY`가 예시값이 아님
- [ ] `DJANGO_ALLOWED_HOSTS`가 실제 도메인으로 제한됨
- [ ] HTTPS 접속 가능
- [ ] HTTP 접속 시 HTTPS로 전환됨
- [ ] `SESSION_COOKIE_SECURE=True`
- [ ] `CSRF_COOKIE_SECURE=True`
- [ ] `/admin/`은 관리자 계정만 접근 가능
- [ ] `private_media` 파일을 직접 URL로 열 수 없음
  - 예: `/protected-media/...` 직접 접근 시 404 또는 403이어야 함
- [ ] 영상 URL은 `/lessons/<id>/video/` 권한 확인을 거쳐야 함
- [ ] PostgreSQL 포트가 외부 인터넷에 노출되지 않음
- [ ] Redis 포트가 외부 인터넷에 노출되지 않음
- [ ] NAS 방화벽과 공유기 포트포워딩 설정 확인

## 6. 백업 확인

### PostgreSQL

- [ ] DB 백업 명령 실행 가능

```bash
docker compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" \
  > /volume1/docker/onedu/backups/db/onedu_$(date +%Y%m%d_%H%M%S).sql
```

- [ ] 백업 파일이 생성됨
- [ ] 백업 파일 용량이 0이 아님
- [ ] Synology 작업 스케줄러 등록 여부 확인

### 파일

- [ ] `media` 백업 가능
- [ ] `private_media` 백업 가능
- [ ] 영상 업로드 후 백업 대상에 포함되는지 확인

```bash
rsync -a --delete /volume1/docker/onedu/data/media/ \
  /volume1/docker/onedu/backups/media/latest/

rsync -a --delete /volume1/docker/onedu/data/private_media/ \
  /volume1/docker/onedu/backups/private_media/latest/
```

### 복구 리허설

- [ ] 테스트 위치에 DB dump 복구 가능
- [ ] `media` 복구 가능
- [ ] `private_media` 복구 가능
- [ ] 복구 후 영상 재생 가능
- [ ] 복구 후 수료증 PDF 생성 가능

## 7. 장애 대응

### 로그 확인

```bash
docker compose logs --tail=200 web
docker compose logs --tail=200 nginx
docker compose logs --tail=200 db
```

실시간 로그:

```bash
docker compose logs -f web
```

### 컨테이너 재시작

```bash
docker compose restart web
docker compose restart nginx
docker compose restart db
```

전체 재시작:

```bash
docker compose down
docker compose up -d
```

### DB 백업 복구

```bash
cat /volume1/docker/onedu/backups/db/onedu_YYYYMMDD_HHMMSS.sql \
  | docker compose exec -T db psql -U "$POSTGRES_USER" "$POSTGRES_DB"
```

복구 전에는 현재 DB를 별도 백업한다.

### 영상 파일 경로 문제

확인할 항목:

- `.env`의 `ONEDU_PRIVATE_MEDIA_DIR`
- 컨테이너 내부 `PRIVATE_MEDIA_ROOT`
- Nginx `location /protected-media/` alias
- 파일 권한
- 영상 파일이 실제로 `private_media/lesson_videos/` 아래 있는지

컨테이너에서 확인:

```bash
docker compose exec web ls -al /vol/web/private_media
docker compose exec nginx ls -al /vol/web/private_media
```

### 수료증 한글 폰트 문제

증상:

- PDF에서 한글이 깨짐
- PDF 생성 중 폰트 오류 발생

확인:

```bash
docker compose exec web ls -al /usr/share/fonts/truetype/nanum/NanumGothic.ttf
```

`.env`의 `CERTIFICATE_FONT_PATH`를 실제 존재하는 폰트 경로로 수정한 뒤 재시작한다.

```bash
docker compose restart web
```

## 8. 운영 전 남은 리스크

- [ ] 대용량 영상 업로드/재생 부하 테스트 필요
- [ ] 여러 수강생 동시 재생 테스트 필요
- [ ] 모바일 실제 기기 테스트 필요
  - iPhone Safari
  - Android Chrome
  - 390px 전후 화면
- [ ] 전체화면 워터마크가 실제 모바일 브라우저에서 유지되는지 확인 필요
- [ ] 진도 조작 방지 고도화 필요
  - 현재 진도 저장 API는 권한은 확인하지만 클라이언트 제출 값을 기반으로 한다.
- [ ] 관리자 대시보드 개선 필요
  - 승인 대기, 재수강 신청, 수료자 현황을 한 화면에서 보는 기능은 아직 없다.
- [ ] 주관식 자동/관리자 채점 정책 확정 필요
- [ ] HLS/DRM은 별도 보안 단계에서 검토 필요

## 최종 배포 승인 기준

아래 항목이 모두 충족되면 1차 운영 배포를 진행할 수 있다.

- [ ] `docker compose config` 통과
- [ ] `docker compose build` 통과
- [ ] `docker compose up -d` 후 모든 컨테이너 healthy 또는 running
- [ ] `python manage.py check --deploy` 주요 경고 없음
- [ ] 관리자 계정 생성 완료
- [ ] 영상 업로드와 재생 확인
- [ ] 수료증 PDF 한글 확인
- [ ] 수료증 검증 페이지 확인
- [ ] DB/media/private_media 백업 확인
- [ ] 복구 리허설 최소 1회 완료
