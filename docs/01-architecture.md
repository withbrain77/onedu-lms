# 전체 아키텍처 문서

## 1. 설계 목표

이 프로젝트는 결제 기능이 없는 승인형 LMS이다. 수강생은 강의를 직접 구매하지 않고, 수강 신청을 제출한다. 관리자는 신청을 승인하거나 반려하고, 승인 시 수강 시작일과 종료일을 지정한다.

핵심 목표는 다음과 같다.

- Django 기반으로 빠르게 MVP를 만든다.
- Django template와 Bootstrap 5로 실제 운영 가능한 화면 품질을 확보한다.
- Synology NAS의 Docker Compose 환경에서 운영 가능하게 설계한다.
- 로그인, 수강 승인, 수강 기간, 사용자 소유권 검증을 강하게 적용한다.
- 영상 파일의 직접 URL 노출을 최소화한다.
- 수강생 정보 기반 동적 워터마크를 영상 위에 표시한다.

## 2. 권장 기술 스택

| 영역 | 선택 | 이유 |
| --- | --- | --- |
| Backend | Django | 인증, Admin, ORM, 템플릿, 파일 처리에 강함 |
| Database | PostgreSQL | 운영 안정성, 관계형 데이터 모델에 적합 |
| Frontend | Django template | MVP 속도와 유지보수성 우선 |
| UI | Bootstrap 5 | 업무용 UI를 빠르게 통일 가능 |
| Interaction | Vanilla JS, 필요 시 HTMX | 진도 저장, 모달, 부분 갱신에 충분 |
| App server | Gunicorn | Django 운영 배포 표준 |
| Web server | Nginx | reverse proxy, static serving, private video serving |
| Deployment | Docker Compose | Synology NAS 운영에 적합 |

React 또는 Next.js는 초기 MVP 범위에서 제외한다. 현재 요구사항은 복잡한 SPA보다 권한, 운영, 영상 접근 제어, 관리자 업무 화면이 중요하다.

## 3. 런타임 구조

```text
User Browser
  -> HTTPS endpoint
    -> Nginx reverse proxy
      -> Django app container
        -> PostgreSQL container
        -> public media volume
        -> private video volume
```

권장 컨테이너 구성:

```text
nginx
django
postgres
```

볼륨 구성:

```text
static_volume        # collectstatic 결과
public_media_volume  # 썸네일, 공개 첨부 파일
private_media_volume # 강의 영상 원본, 수료증 등 권한 필요 파일
postgres_data        # DB 데이터
backup_volume        # DB dump와 백업 산출물
```

## 4. Django 앱 구조

```text
config/
  settings/
    base.py
    local.py
    production.py
  urls.py
  wsgi.py

core/
  services/
    access.py
    completion.py
    certificates.py
  utils/
  templatetags/

accounts/
courses/
lessons/
enrollments/
progress/
quizzes/
certificates/
notices/
dashboard/

templates/
  base.html
  partials/
  accounts/
  courses/
  classroom/
  lessons/
  quizzes/
  certificates/
  dashboard/

static/
  css/app.css
  js/app.js
  js/video_player.js
```

앱별 책임:

| 앱 | 책임 |
| --- | --- |
| accounts | 사용자, 역할, 회원가입, 로그인, 프로필 |
| courses | 강의, 강의 목록, 강의 상세 |
| lessons | 차시, 영상 자산, 영상 순서, 영상 공개 여부 |
| enrollments | 수강 신청, 승인, 반려, 수강 기간, 재수강 |
| progress | 영상 시청 이력, 진도율, 완료 여부 |
| quizzes | 시험, 문제, 선택지, 응시 결과 |
| certificates | 수료증 발급, 다운로드 권한 |
| notices | 공지사항 |
| dashboard | 관리자 보조 화면 |
| core | 공통 권한 검사, 수료 판정, 유틸리티 |

## 5. 권한과 접근 제어

권한 검사는 view 내부에 흩어두지 않고 `core/services/access.py`에 모은다.

필수 검사:

- 로그인 여부
- 사용자 역할: 관리자 또는 수강생
- 수강 신청 승인 여부
- 수강 시작일 도달 여부
- 수강 종료일 경과 여부
- 요청한 사용자와 데이터 소유자 일치 여부
- 수료증 다운로드 권한
- 영상 스트림 접근 권한

권장 서비스 함수:

```text
get_active_enrollment(user, course)
can_access_course(user, course)
can_access_lesson(user, lesson)
can_watch_video(user, lesson)
can_submit_quiz(user, quiz)
can_download_certificate(user, certificate)
```

## 6. 영상 파일 제공 구조

영상 파일은 public media URL로 직접 제공하지 않는다.

권장 방식:

```text
/lessons/<lesson_id>/watch/
  -> Django가 페이지 렌더링

/videos/<video_id>/stream/
  -> Django가 로그인, 승인, 수강 기간, 차시 권한 검사
  -> 통과 시 Nginx X-Accel-Redirect로 private path 제공
```

Nginx 내부 위치 예시:

```text
/protected-media/
```

이 위치는 `internal`로 설정하여 외부 URL 직접 접근을 막는다. Django만 내부 경로를 응답 헤더로 전달할 수 있게 한다.

## 7. 워터마크 구조

워터마크는 영상 파일에 직접 입히는 방식이 아니라 플레이어 UI 위에 동적으로 표시한다.

구조:

```text
video-player-shell
  video
  watermark-layer
  player-actions
```

요구사항:

- 사용자 이름과 아이디 일부를 표시한다.
- 반투명으로 표시한다.
- 일정 시간마다 위치가 바뀐다.
- 모바일에서도 영상 영역을 벗어나지 않는다.
- 전체화면 시에도 보인다.

중요한 구현 기준:

- 브라우저 기본 video fullscreen을 그대로 쓰면 overlay가 빠질 수 있다.
- 자체 전체화면 버튼을 제공하고 `video-player-shell.requestFullscreen()`을 호출한다.
- 워터마크는 wrapper 내부 absolute overlay로 둔다.

## 8. 운영 환경 설정

운영 설정은 환경변수 기반으로 분리한다.

필수 환경변수:

```text
DJANGO_SECRET_KEY
DJANGO_DEBUG
DJANGO_ALLOWED_HOSTS
DJANGO_CSRF_TRUSTED_ORIGINS
DATABASE_URL 또는 POSTGRES_* 변수
STATIC_ROOT
MEDIA_ROOT
PRIVATE_MEDIA_ROOT
TIME_ZONE
```

운영 기본값:

- `DEBUG=False`
- `ALLOWED_HOSTS` 명시
- `CSRF_TRUSTED_ORIGINS` 명시
- HTTPS 사용
- 관리자 URL 접근 제한 검토
- 보안 쿠키 옵션 적용

## 9. Synology NAS 배포 고려사항

NAS 절대경로는 코드에 고정하지 않는다. Compose 환경변수로 주입한다.

예시:

```text
NAS_APP_ROOT=/volume1/docker/onedu
NAS_VIDEO_ROOT=/volume1/media/onedu/videos
NAS_BACKUP_ROOT=/volume1/backups/onedu
```

HTTPS 선택지:

| 방식 | 장점 | 단점 | 추천 |
| --- | --- | --- | --- |
| Synology Reverse Proxy | 인증서 관리가 쉬움, DSM UI 활용 가능 | Nginx 세부 제어가 분리됨 | 일반 운영에 추천 |
| 컨테이너 Nginx 직접 HTTPS | 앱 단위 설정이 명확함 | 인증서 갱신 운영 부담 | 고급 운영 시 선택 |

초기 운영은 Synology Reverse Proxy에서 HTTPS를 처리하고, 컨테이너 Nginx는 내부 HTTP reverse proxy와 static/private media 처리를 담당하는 구성이 적합하다.

## 10. 백업 구조

백업 대상:

- PostgreSQL dump
- private video files
- public media files
- certificate files
- `.env`는 별도 안전 저장, 저장소에는 커밋 금지

권장 정책:

- DB: 매일 dump
- 영상 파일: NAS 공유 폴더 스냅샷 또는 Hyper Backup
- 백업 보관: 일간 7개, 주간 4개, 월간 6개 등 운영 정책화
- 복구 리허설: 최소 월 1회
