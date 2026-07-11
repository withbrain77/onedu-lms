# HLS 스트리밍 운영 메모

대용량 강의 영상은 MP4 원본을 바로 재생하지 않고 HLS로 변환해 재생하는 것을 권장한다. HLS가 준비된 차시는 수강생 화면에서 HLS를 우선 사용하고, 준비되지 않은 차시는 기존 MP4 보호 URL로 재생한다.

## 기본 흐름

1. NAS에 원본 영상을 업로드한다.
2. Django admin에서 차시의 `서버 영상 파일 연결`로 원본 MP4를 연결한다.
3. 차시 수정 화면에서 `HLS 변환 요청` 버튼을 누르거나, 차시 목록에서 admin action으로 `선택한 차시 HLS 변환 요청`을 실행한다.
4. Django가 `HLS 변환 작업`을 생성하고 Redis 작업 큐에 등록한다.
5. `worker` 컨테이너가 큐에서 작업을 가져와 ffmpeg로 HLS를 생성한다.
6. 변환이 끝나면 차시의 `HLS 준비 완료`와 `HLS 재생 목록 경로`가 자동 설정된다.
7. 수강생은 차시 화면에서 HLS 스트리밍으로 영상을 본다.

## 관리자 화면 사용법

차시 수정 화면:

- `HLS 변환 요청`: 기존 HLS 결과가 없을 때 기본 변환을 요청한다.
- `HLS 재변환`: 기존 HLS 결과를 덮어쓰고 다시 만든다.
- `H.264/AAC 재변환`: 기존 HLS 결과를 덮어쓰고 브라우저 호환성이 좋은 H.264/AAC로 다시 인코딩한다. 시간이 오래 걸린다.

차시 목록 화면:

- 여러 차시를 선택한 뒤 `선택한 차시 HLS 변환 요청` action을 실행할 수 있다.
- 여러 차시를 선택한 뒤 `선택한 차시 HLS 재변환 요청(기존 결과 덮어쓰기)` action을 실행할 수 있다.

작업 상태 확인:

- Django admin의 `HLS 변환 작업` 메뉴에서 `대기 중`, `변환 중`, `완료`, `실패` 상태를 확인한다.
- 차시 목록의 `최근 변환 작업` 컬럼에서도 마지막 작업 상태를 볼 수 있다.
- 실패한 작업은 `오류 메시지`를 확인한 뒤 원본 파일 경로, 파일 권한, 디스크 용량, ffmpeg 로그를 점검한다.

## 작업 큐 컨테이너

Docker Compose에는 다음 컨테이너가 추가된다.

```text
redis  = 변환 작업 대기열 저장
worker = HLS 변환 전담 작업자
```

운영 기본값:

```env
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1
CELERY_VIDEO_QUEUE=video
CELERY_WORKER_CONCURRENCY=1
```

`CELERY_WORKER_CONCURRENCY=1`은 NAS에서 한 번에 하나의 대용량 영상만 변환하게 하려는 안전한 기본값이다. CPU/디스크 여유가 충분할 때만 늘린다.

## 수동 변환 명령

관리자 화면 변환이 기본 방식이다. 아래 명령은 장애 대응이나 운영자가 직접 재처리해야 할 때만 사용한다.

```bash
sudo /usr/local/bin/docker compose -p onedu exec web python manage.py convert_lesson_hls <LESSON_ID>
```

기존 변환 결과를 덮어쓸 때:

```bash
sudo /usr/local/bin/docker compose -p onedu exec web python manage.py convert_lesson_hls <LESSON_ID> --force
```

브라우저 호환성 문제가 있거나 원본 코덱이 HLS에 적합하지 않을 때:

```bash
sudo /usr/local/bin/docker compose -p onedu exec web python manage.py convert_lesson_hls <LESSON_ID> --force --transcode
```

기본 변환은 빠른 처리를 위해 원본 코덱을 복사한다. `--transcode`는 H.264/AAC로 재인코딩하므로 시간이 오래 걸리지만 호환성은 더 좋다.

## 저장 위치

원본 영상:

```text
private_media/lesson_videos/
```

HLS 변환 결과:

```text
private_media/lesson_hls/lesson-<LESSON_ID>/index.m3u8
private_media/lesson_hls/lesson-<LESSON_ID>/segment_00000.ts
```

## 보안 구조

- 수강생은 직접 `private_media` 경로에 접근하지 않는다.
- HLS playlist와 segment 요청도 로그인, 수강 승인, 수강 기간 검증을 통과해야 한다.
- 운영 환경에서는 Django가 권한 확인 후 `X-Accel-Redirect`를 반환하고, Nginx가 internal 경로에서 파일을 전송한다.
- HLS도 완전한 복제 방지는 아니므로 워터마크와 접근 제어를 함께 사용한다.

## 운영 주의사항

- 30GB 원본은 변환 시간이 길 수 있다.
- 변환 중에는 NAS CPU 사용량이 높아질 수 있으므로 사용자가 적은 시간에 실행한다.
- 작업 큐 방식에서도 ffmpeg는 NAS 자원을 많이 쓰므로 `worker` 동시 실행 수를 신중히 조절한다.
- 변환 작업이 시작되지 않으면 `redis`와 `worker` 컨테이너가 실행 중인지 확인한다.
- 변환 작업이 실패하면 Django admin의 `HLS 변환 작업`에서 오류 메시지를 먼저 확인한다.
- HLS 변환 결과도 저장 공간을 차지하므로 `private_media` 백업/용량 관리를 같이 한다.
- 모바일 재생 안정성이 중요하면 `--transcode`로 H.264/AAC를 사용하는 것이 안전하다.
