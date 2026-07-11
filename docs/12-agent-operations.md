# 에이전트 기반 운영 진단 절차

이 문서는 NAS에서 직접 명령을 여러 번 실행하지 않고, Codex/main-agent가 원격 진단을 주도할 수 있게 하기 위한 운영 절차다.

## 원칙

- 비밀번호와 `.env` 실값은 채팅에 쓰지 않는다.
- SSH 접속 정보는 로컬 `~/.ssh/config` 또는 안전한 키 기반 인증으로 관리한다.
- 에이전트는 `docker compose down -v`, DB 볼륨 삭제, 영상 파일 삭제 같은 파괴적 명령을 실행하지 않는다.
- 원격 진단은 기본적으로 읽기 전용 명령을 사용한다.

## 사용자가 한 번만 준비할 것

관리 PC 또는 Codex가 실행되는 환경에서 NAS SSH 별칭을 준비한다.

```sshconfig
Host onedu-nas
  HostName 192.168.0.97
  User your-nas-user
  IdentityFile ~/.ssh/onedu_nas_ed25519
```

접속 확인:

```bash
ssh onedu-nas "hostname && docker --version"
```

Docker 권한 확인:

```bash
ssh onedu-nas "cd /volume1/wbinstitute/docker/onedu/app && docker compose -p onedu ps"
```

만약 `/var/run/docker.sock` permission denied가 나오면 다음 방식으로 실행한다.

```bash
ssh onedu-nas "cd /volume1/wbinstitute/docker/onedu/app && sudo docker compose -p onedu ps"
```

이 경우 이후 원격 래퍼에는 `ONEDU_DOCKER_COMPOSE="sudo docker compose"`를 붙인다.

이후에는 다음처럼 실행할 수 있다.

```bash
ONEDU_SSH_TARGET=onedu-nas sh deploy/remote-compose.sh status
```

## 원격 운영 래퍼

`deploy/remote-compose.sh`는 NAS의 `/volume1/wbinstitute/docker/onedu/app`에서 `docker compose -p onedu` 명령을 안전하게 실행하는 래퍼다.

기본값:

```text
ONEDU_APP_DIR=/volume1/wbinstitute/docker/onedu/app
ONEDU_COMPOSE_PROJECT=onedu
ONEDU_BASE_URL=http://127.0.0.1:8080
ONEDU_HTTP_HOST=192.168.0.97
```

Docker socket 권한이 없는 NAS 계정에서는 다음을 추가한다.

```bash
ONEDU_DOCKER_COMPOSE="sudo docker compose"
```

## NAS에 진단 스크립트 반영

NAS의 프로젝트 폴더에 아직 `deploy/diagnose-video.sh`가 없다면 관리 PC에서 복사한다.

```powershell
cd J:\project\onedu
scp .\deploy\diagnose-video.sh onedu-nas:/volume1/wbinstitute/docker/onedu/app/deploy/diagnose-video.sh
```

권한 문제로 복사가 실패하면 NAS에 접속해 폴더 소유권 또는 쓰기 권한을 확인한다.

```bash
ssh onedu-nas
ls -ld /volume1/wbinstitute/docker/onedu/app/deploy
```

필요하면 실행 시 덮어쓴다.

```bash
ONEDU_SSH_TARGET=onedu-nas \
ONEDU_APP_DIR=/volume1/wbinstitute/docker/onedu/app \
sh deploy/remote-compose.sh status
```

## 자주 쓰는 명령

컨테이너 상태:

```bash
ONEDU_SSH_TARGET=onedu-nas sh deploy/remote-compose.sh status
```

Docker socket 권한이 없을 때:

```bash
ONEDU_SSH_TARGET=onedu-nas ONEDU_DOCKER_COMPOSE="sudo docker compose" sh deploy/remote-compose.sh status
```

Django check:

```bash
ONEDU_SSH_TARGET=onedu-nas sh deploy/remote-compose.sh check
```

전체 테스트:

```bash
ONEDU_SSH_TARGET=onedu-nas sh deploy/remote-compose.sh test
```

운영 보안 체크:

```bash
ONEDU_SSH_TARGET=onedu-nas sh deploy/remote-compose.sh deploy-check
```

Compose 설정 검증:

```bash
ONEDU_SSH_TARGET=onedu-nas sh deploy/remote-compose.sh compose-config
```

최근 로그:

```bash
ONEDU_SSH_TARGET=onedu-nas sh deploy/remote-compose.sh logs
```

실시간 로그:

```bash
ONEDU_SSH_TARGET=onedu-nas sh deploy/remote-compose.sh tail
```

영상 전체 진단:

```bash
ONEDU_SSH_TARGET=onedu-nas sh deploy/remote-compose.sh diagnose-video
```

특정 차시와 수강생 기준 영상 진단:

```bash
ONEDU_SSH_TARGET=onedu-nas sh deploy/remote-compose.sh diagnose-video 1 student01
```

특정 영상 URL 헤더만 빠르게 확인:

```bash
ONEDU_SSH_TARGET=onedu-nas sh deploy/remote-compose.sh video-headers 1 student01
```

## 서브에이전트 분담 방식

main-agent는 전체 판단과 최종 수정만 담당한다. 서브에이전트는 조사 결과를 보고하고 같은 파일을 동시에 수정하지 않는다.

### video-diagnosis-agent

담당:

- `deploy/remote-compose.sh diagnose-video`
- Lesson DB 상태
- Enrollment 상태
- 실제 파일 존재 여부
- web/nginx 로그

보고:

- 영상 파일 DB 등록 여부
- private media 실제 파일 존재 여부
- 수강 권한 문제 여부
- `/lessons/<id>/watch/`, `/lessons/<id>/video/` 상태코드

### backend-media-agent

담당 파일:

- `lessons/models.py`
- `lessons/views.py`
- `lessons/urls.py`
- `lessons/storage.py`
- `core/services/access.py`
- `templates/lessons/detail.html`
- `static/js/video_progress.js`

보고:

- Django 권한 검증이 지나치게 엄격한지
- `X-Accel-Redirect` 헤더가 올바른지
- video source URL이 보호 URL인지
- 필요한 최소 수정안

### nginx-protected-media-agent

담당 파일:

- `deploy/nginx/default.conf`
- `docker-compose.yml`

보고:

- `/protected-media/` internal location 존재 여부
- alias와 볼륨 경로 일치 여부
- nginx 컨테이너에서 private media 파일 읽기 가능 여부
- Range request를 Nginx가 처리할 수 있는 구조인지

### ui-video-player-agent

담당 파일:

- `templates/lessons/detail.html`
- `static/js/video_progress.js`
- `static/css/app.css`

보고:

- HTML5 video 태그 렌더링 상태
- source URL 상태
- 워터마크 overlay 문제 여부
- 브라우저 Network에서 확인해야 할 상태코드

## main-agent 의사결정 순서

1. `status`, `check`, `logs` 실행
2. `diagnose-video` 실행
3. 특정 `LESSON_ID`, `USERNAME`이 있으면 focused 진단 실행
4. 원인을 다음 중 하나로 분류
   - DB에 영상 파일 없음
   - 실제 private media 파일 없음
   - Enrollment 권한/기간 문제
   - Django video view 문제
   - X-Accel-Redirect 경로 문제
   - Nginx alias/볼륨 문제
   - 브라우저/파일 코덱 문제
5. 수정 파일 후보를 사용자에게 보고
6. 최소 수정
7. `check`, `test`, `compose-config`, `video-headers`, 로그 확인

## 사용자가 직접 해야 하는 일

가능하면 이것만 하면 된다.

- SSH 키 또는 SSH 별칭 준비
- 관리자/수강생 테스트 계정 정보 제공
- 문제가 나는 `LESSON_ID`와 수강생 `USERNAME` 제공
- 브라우저 Network 상태코드가 필요한 경우 화면에서 확인

나머지 코드 수정, 테스트, 로그 해석, 원인 분류는 main-agent가 담당한다.
