# 영상 보호와 워터마크 설계 메모

## 현재 MVP 2.5 구조

MVP 2.5에서는 영상 파일을 템플릿에 직접 노출하지 않는다.

```text
영상 페이지
  /lessons/<lesson_id>/watch/

영상 제공 view
  /lessons/<lesson_id>/video/
```

`/lessons/<lesson_id>/video/`는 다음 조건을 검사한다.

- 로그인 여부
- 차시 공개 여부
- 강의 공개 여부
- 수강 승인 여부
- 수강 시작일/종료일
- 요청 사용자와 수강 데이터의 일치 여부

새로 업로드되는 영상 파일은 `MEDIA_ROOT`가 아니라 `PRIVATE_MEDIA_ROOT` 아래에 저장한다. 개발 환경에서 `/media/`가 열려 있어도 새 영상 파일은 public media 경로에 위치하지 않는다.

## 워터마크

영상 시청 화면에는 HTML overlay 방식의 동적 워터마크를 표시한다.

표시 문구:

```text
수강생 이름 / 사용자 아이디
```

관리자 미리보기:

```text
관리자 미리보기 / 관리자 아이디
```

동작:

- video 위에 absolute overlay로 표시한다.
- `pointer-events: none`을 적용한다.
- opacity는 낮게 유지한다.
- 10~20초 간격으로 위치를 변경한다.
- 전체화면은 video 요소가 아니라 player wrapper에 적용한다.

## 현재 한계

이 방식은 DRM이 아니다. 브라우저에서 재생되는 영상은 화면 녹화나 개발자 도구 분석을 완전히 막을 수 없다.

현재 구조의 목적은 다음이다.

- 승인되지 않은 사용자의 접근 차단
- 수강 기간 외 접근 차단
- 템플릿 내 media URL 직접 노출 최소화
- 화면 녹화 억제를 위한 사용자 식별 워터마크 표시

## 운영 배포 시 권장 보호 방식

운영에서는 Django가 직접 대용량 파일을 전송하지 않는 것이 좋다. Nginx protected media와 `X-Accel-Redirect`를 사용한다.

MVP 6부터 다음 환경변수로 운영 분기를 켤 수 있다.

```env
USE_X_ACCEL_REDIRECT=True
X_ACCEL_REDIRECT_PREFIX=/protected-media/
PRIVATE_MEDIA_ROOT=/vol/web/private_media
```

권장 흐름:

```text
Browser
  -> /lessons/<lesson_id>/video/
  -> Django 권한 검사
  -> X-Accel-Redirect: /protected-media/<internal-path>
  -> Nginx internal location에서 파일 전송
```

Nginx 예시:

```nginx
location /protected-media/ {
    internal;
    alias /vol/web/private_media/;
}
```

Django 응답 예시:

```text
X-Accel-Redirect: /protected-media/lesson_videos/example.mp4
Content-Type: video/mp4
Cache-Control: private, no-store
```

추가 권장 사항:

- 영상 파일은 public `MEDIA_ROOT`와 분리한다.
- `/media/lesson_videos/` 같은 public URL은 만들지 않는다.
- 운영에서는 `DEBUG=False`로 Django static/media serving을 끈다.
- 대용량 영상은 Nginx가 Range request를 처리하게 한다.
- HLS 또는 DRM은 별도 단계에서 검토한다.
