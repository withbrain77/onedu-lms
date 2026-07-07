# 화면 목록과 URL 구조

## 1. URL 설계 원칙

- 수강생 화면과 관리자 보조 화면을 URL 레벨에서 분리한다.
- 수강생의 개인 학습 공간은 `/classroom/` 아래에 둔다.
- 관리자 보조 화면은 `/dashboard/` 아래에 둔다.
- Django Admin은 `/admin/`으로 유지하되 운영 보조 화면과 역할을 분리한다.
- 영상 파일은 직접 media URL이 아니라 권한 검사 URL을 통해 제공한다.

## 2. 인증 흐름

| 상황 | 이동 |
| --- | --- |
| 수강생 로그인 성공 | `/classroom/` |
| 관리자 로그인 성공 | `/dashboard/` |
| 비로그인 상태에서 보호 페이지 접근 | `/accounts/login/?next=...` |
| 승인되지 않은 강의 접근 | 안내 화면 또는 403 |
| 수강 기간 전/후 영상 접근 | 접근 불가 안내 화면 |

## 3. 수강생 화면 목록

| 화면 | URL | 목적 |
| --- | --- | --- |
| 회원가입 | `/accounts/signup/` | 수강생 계정 생성 |
| 로그인 | `/accounts/login/` | 로그인 |
| 로그아웃 | `/accounts/logout/` | 로그아웃 |
| 내 정보 수정 | `/accounts/profile/` | 이름, 연락처 등 수정 |
| 강의 목록 | `/courses/` | 공개 강의 탐색 |
| 강의 상세 | `/courses/<slug>/` | 강의 설명 확인 |
| 수강 신청 | `/courses/<slug>/apply/` | 강의 수강 신청 |
| 내 강의실 | `/classroom/` | 승인, 대기, 종료 강의 확인 |
| 내 강의 상세 | `/classroom/<course_id>/` | 차시 목록, 진도, 시험, 수료 확인 |
| 영상 시청 | `/lessons/<lesson_id>/watch/` | 영상 재생과 진도 저장 |
| 진도 저장 API | `/progress/lessons/<lesson_id>/save/` | 비동기 진도 저장 |
| 시험 응시 | `/quizzes/<quiz_id>/take/` | 문제 풀이 |
| 시험 결과 | `/quizzes/attempts/<attempt_id>/` | 점수와 합격 여부 확인 |
| 수료증 목록 | `/certificates/` | 발급된 수료증 확인 |
| 수료증 다운로드 | `/certificates/<certificate_id>/download/` | PDF 다운로드 |
| 재수강 신청 | `/reenrollments/<course_id>/request/` | 만료 강의 재수강 요청 |

## 4. 관리자 화면 목록

| 화면 | URL | 목적 |
| --- | --- | --- |
| Django Admin | `/admin/` | 모델 CRUD, 기본 운영 |
| 관리자 대시보드 | `/dashboard/` | 핵심 지표 요약 |
| 수강 신청 관리 | `/dashboard/enrollments/` | 승인, 반려, 검색, 필터 |
| 수강 신청 상세 | `/dashboard/enrollments/<id>/` | 신청 내용과 처리 |
| 수강생 목록 | `/dashboard/students/` | 수강생 검색 |
| 수강생 상세 | `/dashboard/students/<id>/` | 수강 이력, 진도, 시험, 수료 |
| 강의 관리 | `/dashboard/courses/` | 강의 운영 상태 확인 |
| 강의 운영 상세 | `/dashboard/courses/<id>/` | 차시, 영상 업로드 상태 |
| 진도 현황 | `/dashboard/progress/` | 수강생별, 강의별 진도 확인 |
| 시험 결과 | `/dashboard/quiz-attempts/` | 시험 결과 확인 |
| 수료증 관리 | `/dashboard/certificates/` | 발급, 취소, 다운로드 확인 |
| 재수강 신청 관리 | `/dashboard/reenrollments/` | 재수강 승인, 반려 |
| 공지 관리 | `/dashboard/notices/` | 공지 작성과 게시 |

## 5. 앱별 URL 구조

### accounts

```text
/accounts/signup/
/accounts/login/
/accounts/logout/
/accounts/profile/
/accounts/password-reset/
```

비밀번호 재설정은 MVP에서 관리자 초기화 중심으로 처리하고, 이메일 기반 재설정은 후속 기능으로 둘 수 있다.

### courses

```text
/courses/
/courses/<slug>/
/courses/<slug>/apply/
```

### classroom

```text
/classroom/
/classroom/<course_id>/
```

`classroom`은 앱 이름보다 화면 영역에 가까우므로 `enrollments` 또는 `courses` view로 구현할 수 있다.

### lessons

```text
/lessons/<lesson_id>/watch/
/videos/<video_id>/stream/
```

`/videos/<video_id>/stream/`은 video 파일 자체가 아니라 권한 검사 endpoint이다.

### progress

```text
/progress/lessons/<lesson_id>/save/
```

POST 요청만 허용한다. CSRF 보호를 유지한다.

### quizzes

```text
/quizzes/<quiz_id>/take/
/quizzes/attempts/<attempt_id>/
```

### certificates

```text
/certificates/
/certificates/<certificate_id>/download/
```

### reenrollments

```text
/reenrollments/<course_id>/request/
```

실제 앱은 `enrollments`에 포함해도 된다.

### dashboard

```text
/dashboard/
/dashboard/enrollments/
/dashboard/enrollments/<id>/
/dashboard/students/
/dashboard/students/<id>/
/dashboard/courses/
/dashboard/courses/<id>/
/dashboard/progress/
/dashboard/quiz-attempts/
/dashboard/certificates/
/dashboard/reenrollments/
/dashboard/notices/
```

## 6. 수강생 UX 흐름

```text
회원가입
  -> 로그인
  -> 내 강의실
  -> 공개 강의 목록
  -> 수강 신청
  -> 승인 대기
  -> 관리자 승인
  -> 내 강의실에서 승인 강의 확인
  -> 강의 상세
  -> 영상 시청
  -> 진도 저장
  -> 시험 응시
  -> 점수 확인
  -> 수료 조건 충족
  -> 수료증 다운로드
  -> 필요 시 재수강 신청
```

## 7. 관리자 UX 흐름

```text
관리자 로그인
  -> 대시보드에서 승인 대기와 운영 지표 확인
  -> 수강 신청 관리
  -> 신청 검색과 필터
  -> 시작일/종료일 입력
  -> 승인 또는 반려
  -> 수강생 상세에서 진도와 시험 결과 확인
  -> 수료 조건 충족자 수료증 발급
  -> 재수강 신청 승인 또는 반려
```

## 8. 접근 차단 화면

다음 상황에는 빈 403 화면 대신 이유와 다음 행동을 보여준다.

| 상황 | 안내 | 다음 행동 |
| --- | --- | --- |
| 로그인 필요 | 로그인이 필요합니다 | 로그인 |
| 승인 전 | 아직 승인되지 않은 강의입니다 | 내 강의실 |
| 시작일 전 | 수강 시작일 이후 이용 가능합니다 | 내 강의실 |
| 종료 후 | 수강 기간이 종료되었습니다 | 재수강 신청 |
| 타 사용자 데이터 | 접근 권한이 없습니다 | 내 강의실 |
| 수료증 없음 | 발급된 수료증이 없습니다 | 강의 상세 |
