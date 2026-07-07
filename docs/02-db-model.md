# DB 모델 설계

## 1. 모델 개요

승인형 LMS의 핵심 모델은 다음과 같다.

```text
User
Course
Lesson
VideoAsset
Enrollment
WatchProgress
Quiz
Question
AnswerChoice
QuizAttempt
QuizAttemptAnswer
Certificate
ReEnrollmentRequest
Notice
```

## 2. User

사용자 모델은 Django custom user를 권장한다. 프로젝트 초기에 적용해야 나중에 변경 비용이 낮다.

주요 필드:

```text
username
email
name
phone
role: admin, student
is_active
is_staff
last_login
date_joined
```

권장 사항:

- 관리자 권한은 `is_staff`와 `role=admin`을 함께 고려한다.
- 수강생 개인정보는 필요한 최소 필드만 저장한다.
- 주민등록번호 같은 고위험 개인정보는 저장하지 않는다.

## 3. Course

강의 단위 모델이다.

주요 필드:

```text
title
slug
description
thumbnail
is_public
created_by
created_at
updated_at
```

관계:

```text
Course 1:N Lesson
Course 1:N Enrollment
Course 1:N Quiz
Course 1:N Notice
```

## 4. Lesson

강의 안의 차시 모델이다.

주요 필드:

```text
course
title
description
order
duration_seconds
is_public
created_at
updated_at
```

제약:

```text
unique(course, order)
```

관리자 요구사항:

- 영상 순서 변경
- 영상 공개/비공개 처리
- 차시별 영상 업로드 상태 확인

## 5. VideoAsset

차시에 연결되는 영상 파일 모델이다.

주요 필드:

```text
lesson
file
original_filename
storage_path
size_bytes
content_type
duration_seconds
is_active
uploaded_by
uploaded_at
```

권장 사항:

- 실제 영상 파일은 private media storage에 저장한다.
- public URL을 template에 직접 노출하지 않는다.
- 파일 교체 이력을 남기고 싶다면 `VideoAsset`을 누적 저장하고 `is_active`로 현재 파일을 구분한다.

## 6. Enrollment

수강 신청과 승인 상태를 관리한다.

상태:

```text
requested
approved
rejected
expired
cancelled
```

주요 필드:

```text
user
course
status
start_date
end_date
approved_by
approved_at
rejected_reason
created_at
updated_at
```

권장 속성:

```text
is_approved
is_active_period
is_currently_accessible
days_remaining
```

주의:

- 활성 승인 수강은 사용자와 강의 기준으로 중복되지 않게 한다.
- 재수강 이력을 보존해야 하므로 과거 Enrollment를 삭제하지 않는다.

## 7. WatchProgress

차시별 시청 진도를 저장한다.

주요 필드:

```text
user
enrollment
lesson
last_position_seconds
duration_seconds
progress_percent
is_completed
completed_at
last_watched_at
created_at
updated_at
```

제약:

```text
unique(enrollment, lesson)
```

완료 기준 예시:

```text
progress_percent >= 90
```

완료 기준은 운영 정책에 따라 90%, 95%, 100% 중 하나로 확정한다.

## 8. Quiz

강의별 시험이다.

주요 필드:

```text
course
title
description
pass_score
is_active
created_at
updated_at
```

권장 사항:

- MVP에서는 강의당 활성 시험 1개를 기본으로 한다.
- 추후 여러 시험을 허용할 수 있게 모델은 1:N 구조로 둔다.

## 9. Question

시험 문제 모델이다.

문제 유형:

```text
multiple_choice
short_answer
```

주요 필드:

```text
quiz
type
text
order
points
correct_text_answer
explanation
```

주의:

- 객관식은 `AnswerChoice`를 사용한다.
- 주관식 자동 채점은 MVP에서 단순 문자열 비교로 시작할 수 있다.
- 운영 요구에 따라 주관식 수동 채점 여부를 추후 결정한다.

## 10. AnswerChoice

객관식 선택지 모델이다.

주요 필드:

```text
question
text
is_correct
order
```

제약:

```text
unique(question, order)
```

## 11. QuizAttempt

시험 응시 결과이다.

주요 필드:

```text
quiz
user
enrollment
score
max_score
passed
submitted_at
created_at
```

관계:

```text
QuizAttempt 1:N QuizAttemptAnswer
```

권장 사항:

- 재응시 허용 여부를 정책으로 분리한다.
- MVP에서는 최신 응시 결과 또는 최고 점수를 수료 판정에 사용할지 정해야 한다.

## 12. QuizAttemptAnswer

응시자가 제출한 답안이다.

주요 필드:

```text
attempt
question
selected_choice
text_answer
is_correct
earned_points
```

## 13. Certificate

수료증 모델이다.

주요 필드:

```text
user
course
enrollment
certificate_no
pdf_file
issued_at
revoked_at
issued_by
```

제약:

```text
unique(enrollment)
unique(certificate_no)
```

권한:

- 본인 수료증만 다운로드 가능하다.
- 관리자는 수료증 발급, 재발급, 취소를 할 수 있다.

## 14. ReEnrollmentRequest

수강 기간 만료 후 재수강 신청을 관리한다.

상태:

```text
requested
approved
rejected
cancelled
```

주요 필드:

```text
user
course
previous_enrollment
status
reason
reviewed_by
reviewed_at
rejected_reason
created_at
updated_at
```

## 15. Notice

공지사항 모델이다.

대상:

```text
all
students
course
```

주요 필드:

```text
title
body
target
course
is_published
published_at
created_by
created_at
updated_at
```

## 16. 수료 판정 모델

수료 조건은 `core/services/completion.py`에서 관리한다.

기본 조건:

```text
모든 필수 차시 완료
활성 시험 합격
수강 기간 내 수료
```

권장 함수:

```text
get_course_progress(enrollment)
has_completed_required_lessons(enrollment)
has_passed_required_quiz(enrollment)
can_issue_certificate(enrollment)
issue_certificate(enrollment)
```

## 17. 권한 검증 서비스

권한 검증은 모델 property만으로 끝내지 않고 서비스 함수로 모은다.

```text
core/services/access.py
```

권장 함수:

```text
get_active_enrollment(user, course)
can_view_course(user, course)
can_apply_course(user, course)
can_access_classroom(user, course)
can_access_lesson(user, lesson)
can_stream_video(user, video_asset)
can_view_progress(user, enrollment)
can_take_quiz(user, quiz)
can_download_certificate(user, certificate)
```

이 함수들은 view, admin action, dashboard에서 동일하게 사용한다.
