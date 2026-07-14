# ONEDU LMS Project Memory

이 문서는 다음 작업 세션에서 프로젝트 맥락을 빠르게 이어받기 위한 요약이다. 비밀번호, 앱 비밀번호, 비밀키 같은 민감정보는 저장하지 않는다.

## 프로젝트 목적

- 위드브레인연구소가 운영하는 승인형 온라인 교육 사이트다.
- 교육 영상, 세미나 영상, 강의 영상을 제한적으로 제공하고 수강 신청, 승인, 시청 진도, 시험, 수료, 수료증, 재수강 흐름을 관리한다.
- 결제 기능은 탑재하지 않고, 유료 과정은 입금 확인 후 관리자가 승인하는 방식이다.
- 무료 과정은 신청 즉시 자동 승인되어 바로 수강 가능하다.

## 운영 주소와 저장소

- 운영 도메인: `https://onedu.withbrain.kr`
- 내부 접속: `http://192.168.0.97:8080`
- 관리자: `https://onedu.withbrain.kr/admin/`
- 로컬 프로젝트 경로: `J:\project\onedu`
- NAS 프로젝트 경로: `/volume1/wbinstitute/docker/onedu/app`
- Docker Compose 프로젝트명: `onedu`
- GitHub 저장소: `https://github.com/withbrain77/onedu-lms.git`
- 기본 브랜치: `master`

## 기술 스택

- Django template 기반 LMS
- Bootstrap 5 기반 반응형 UI
- PostgreSQL, Redis, Celery, Nginx, Docker Compose
- Synology NAS Container Manager 환경에서 운영
- 영상은 private media + 권한 확인 view + 운영 시 X-Accel-Redirect 구조
- HLS 변환은 Celery worker 큐 기반

## 주요 구현 상태

- 회원가입, 로그인, 로그아웃
- 아이디 기억하기
- 아이디 찾기
- 이메일 기반 비밀번호 재설정
- 로그인 사용자의 내 정보 수정
- 로그인 사용자의 비밀번호 변경
- 강의 목록, 강의 상세, 내 강의실
- 유료/무료 이용료 정책
- 유료 과정 입금 안내
- 수강 신청 및 신청 취소
- 무료 과정 자동 승인
- 관리자 승인 후 수강 접근
- 수강 시작일/종료일 접근 제한
- 영상 업로드 및 NAS 서버 파일 연결
- HTML5/HLS 영상 플레이어
- 영상 진도 저장
- 동적 워터마크
- 학습 자료 다운로드
- PDF 학습 자료 워터마크
- 시험/문제/응시/자동 채점
- 수료 조건 판정
- 수료증 PDF 다운로드
- 수료증 검증 페이지
- 재수강 신청 및 관리자 승인
- 관리자 운영 대시보드
- 수강 신청 관리자 이메일 알림
- 수강 승인 수강생 이메일 알림
- 수강 종료 7일 전 수강생 이메일 알림

## 이메일 알림 정책

- 유료 수강 신청 접수 시 관리자에게 승인 요청 메일을 보낸다.
- 관리자가 수강 신청을 승인하면 수강생에게 승인 안내 메일을 보낸다.
- 수강 종료일이 7일 남은 승인 수강생에게 만료 예정 안내 메일을 보낸다.
- 수료 완료자는 7일 전 만료 알림 대상에서 제외한다.
- 7일 전 만료 알림은 `expiry_notice_7d_sent_at`에 기록되어 중복 발송되지 않는다.
- 관련 환경변수:
  - `ONEDU_NOTIFY_ENROLLMENT_REQUEST`
  - `ONEDU_NOTIFY_ENROLLMENT_APPROVAL`
  - `ONEDU_NOTIFY_ENROLLMENT_EXPIRY_7D`
  - `ONEDU_ADMIN_NOTIFICATION_EMAIL`
  - `ONEDU_ADMIN_NOTIFICATION_EMAILS`

## 자동 작업

- HLS 변환은 Celery worker가 처리한다.
- 수강 만료 7일 전 알림은 Celery beat가 매일 자동 실행한다.
- 기본 실행 시간은 한국 시간 오전 9시다.
- 관련 환경변수:
  - `CELERY_TASK_DEFAULT_QUEUE=default`
  - `CELERY_VIDEO_QUEUE=video`
  - `CELERY_EXPIRY_NOTICE_HOUR=9`
  - `CELERY_EXPIRY_NOTICE_MINUTE=0`

수동 확인:

```bash
docker compose -p onedu exec -T web python manage.py send_expiry_notices --dry-run
```

수동 발송:

```bash
docker compose -p onedu exec -T web python manage.py send_expiry_notices
```

## 영상 저장 위치

운영 기준 권장 업로드 위치:

```text
/volume1/wbinstitute/docker/onedu/app/data/private_media/lesson_videos/
```

주의:

- 원본 MP4와 HLS 변환본 위치는 다르다.
- HLS 변환 후에도 원본 삭제는 신중하게 진행한다.
- 원본 삭제 전에는 관리자 화면에서 해당 차시가 HLS 준비 완료인지 확인한다.

## 운영 명령

배포:

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\onedu-remote.ps1 deploy
```

상태 확인:

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\onedu-remote.ps1 status
```

worker 로그:

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\onedu-remote.ps1 logs-worker
```

HLS 상태:

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\onedu-remote.ps1 hls-status
```

## 디자인 방향

- 전체 톤은 화이트, 딥 틸, 다크 네이비 중심의 업무용 교육 포털 스타일이다.
- 메인 페이지는 위드브레인연구소 교육/세미나 영상 아카이브의 목적을 드러내는 구조다.
- 학생 화면은 모바일 반응형을 우선 유지한다.
- 관리자 화면은 데스크톱 업무 환경을 우선한다.
- UI 수정 시 기본 브라우저 스타일처럼 보이지 않게 Bootstrap 5와 기존 `static/css/app.css` 패턴을 따른다.

## 수강료 표현

- 사이트 문구는 `참가비`보다 `이용료`를 사용한다.
- 무료 과정은 `무료`로 표시하고, 신청 즉시 수강 가능하다.
- 유료 과정은 온라인 결제 없이 입금 확인 후 관리자 승인으로 운영한다.
- 현재 입금 안내:
  - 은행: 국민은행
  - 계좌번호: 700101-01-323177
  - 예금주: 표진호(위드브레인)
  - 입금자명: 수강생 이름과 동일하게 입력

## 최근 주요 커밋

- `816ab69` Add enrollment expiry reminder emails
- `6ce3ac3` Normalize classroom status badge size
- `033bda8` Send enrollment approval emails to students
- `4e2a0c3` Add account profile and password change pages
- `4b6d584` Add remember username option to login

## 주의사항

- `.env`, DB, media, private_media, staticfiles, 가상환경은 Git에 포함하지 않는다.
- 비밀번호, 앱 비밀번호, SMTP 비밀번호, Django secret key는 문서에 저장하지 않는다.
- 운영 DB 볼륨 삭제 금지.
- `docker compose down -v` 금지.
- 영상 파일 삭제 금지.
- NAS 작업은 가능한 한 `deploy/onedu-remote.ps1`와 `onedu-ops` 자동화를 사용한다.
- 기능 변경 후에는 테스트, 커밋, 배포, 외부 URL 확인까지 진행하는 흐름을 유지한다.

## 다음 세션 시작 시 확인 순서

1. `git status --short --branch`
2. `git log --oneline -5`
3. `docs/14-project-memory.md` 확인
4. 필요한 경우 `powershell -ExecutionPolicy Bypass -File .\deploy\onedu-remote.ps1 status`
5. 변경 작업 후 `python manage.py check`
6. 영향 범위에 따라 `python manage.py test`
7. 커밋 및 `git push`
8. 운영 반영이 필요하면 `deploy/onedu-remote.ps1 deploy`
