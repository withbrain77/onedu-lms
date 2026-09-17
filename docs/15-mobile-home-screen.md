# 휴대폰 홈 화면 추가

- 정식 설치 이름: 위드브레인연구소 아카데미
- 짧은 이름 / 아이폰 홈 화면 기본 이름: 위드브레인
- 시작 주소: `/classroom/`. 비로그인 상태에서는 로그인 후 내 강의실로 이동합니다.
- 설치 안내: `/install/`. 홈페이지, 내 강의실, 수강 과정 화면에 모바일 배너를 표시합니다.
- 안드로이드 등 지원 브라우저에서는 `beforeinstallprompt`를 사용하고, 미지원 환경에서는 수동 추가 방법을 안내합니다.
- 카카오톡 등 앱 내 브라우저에서는 외부 브라우저 메뉴와 주소 복사를 안내합니다.
- 설치 모드로 실행하면 추가 안내를 숨깁니다. 배너 닫기는 7일간 적용되며 메뉴의 추가 안내는 계속 사용할 수 있습니다.
- 설치와 로그인은 별개입니다. 브라우저에 따라 새 로그인 세션이 필요할 수 있으며, 영상 시청에는 인터넷 연결이 필요합니다.
- 서비스 워커나 오프라인 콘텐츠 저장은 사용하지 않습니다. 기존 영상 접근과 수강기간 확인을 그대로 사용합니다.

## 아이콘 제작

기존 `static/img/withbrain-logo.png`를 참조하여 내장 imagegen 편집으로 글자를 제외한 전구 아이콘을 만들었습니다. 원본은 `static/img/pwa/withbrain-bulb-source.png`에 보관합니다. 플랫폼용 PNG는 여백을 포함해 180, 192, 512px로 내보냈습니다. 로고 디자인 변경 시 이 파일들도 함께 갱신합니다.

사용 프롬프트:

> Edit the supplied WITHBRAIN logo for a mobile home-screen icon. Preserve the exact existing stylized yellow brain/lightbulb symbol and gray bulb base and yellow rays faithfully; extract this existing symbol only, completely remove the black WITHBRAIN wordmark and tagline below it. Do not redraw, simplify, invent or restyle its geometry. Center the complete bulb and rays on a solid pure white square canvas, no border, no shadows, no rounded-corner frame. The complete symbol should fit within the central 68% of the square height to leave safe padding for circular app icon masks. Output a crisp square 1024x1024 PNG. This is an existing brand identity extraction, not a new logo design.

참고: [MDN 설치 조건](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable), [브라우저 설치창](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/How_to/Trigger_install_prompt).

## 모바일 학습 개선 (2026-09-17)

- 홈과 내 강의실 상단에서 최근 접근 가능한 차시와 저장 위치를 보여주고 바로 이어봅니다. 만료·비공개·다른 계정의 진도는 노출하지 않습니다. 과정별 이어보기도 최근 차시로 연결하며, 시청 기록이 없으면 첫 공개 차시로 연결합니다.
- 767px 이하 홈에서는 장식용 영상 패널과 카테고리 소개를 접어 프로그램 목록을 앞당깁니다. 하단에는 홈·내 강의실·내 정보 바로가기를 고정하고 안전 영역 여백을 둡니다.
- 영상 바로 아래에 저장 상태와 다음 차시 버튼을 배치합니다. 차시 목록·학습 자료·학습 진도는 키보드로도 조작 가능한 탭으로 전환합니다. JavaScript를 끄면 모든 내용을 표시합니다.
- 회원가입·내 정보 연락처에 전화 키보드를 사용하고 자동완성을 제공합니다. 비밀번호 입력에는 보기/숨기기 버튼을 제공합니다.
- PDF의 `/view/` 경로는 기존 다운로드와 동일한 권한 확인·개인 워터마크·접근 기록을 적용하고 `inline`으로 응답합니다. PDF 외 파일은 이 경로로 표시하지 않습니다. 브라우저의 PDF 지원에 따라 열리는 방식은 달라질 수 있습니다.

### 진도 저장

재생 중 정기 저장 외에 일시정지·화면 숨김·페이지 이동 때 저장합니다. 실제 재생 위치가 움직인 시간만 집계하며 일시정지·버퍼링·탐색 시간을 제외합니다. 영상 파일은 오프라인으로 저장하지 않습니다.

`progress_sync.js`는 미전송 진도 이벤트를 사용자별 `localStorage` 항목에 보관하고 연결 복구와 다음 페이지 방문 때 재시도합니다. 각 요청은 이벤트 UUID와 수강 ID를 포함합니다. `ProgressSaveReceipt`와 수강 행 잠금으로 재전송 중복 합산을 방지하며, `last_position_recorded_at`으로 지연 요청이 최신 위치를 덮어쓰지 않도록 합니다. 운영 PostgreSQL의 행 잠금을 사용합니다. 기존 클라이언트의 이벤트 ID 없는 요청도 계속 허용합니다.

브라우저가 저장소를 차단하면 해당 페이지의 메모리에서만 재시도하며 화면 유지 안내를 표시합니다. 브라우저 강제 종료 직전 저장, 저장소 삭제, 실제 기기 OS의 백그라운드 종료까지 저장을 보장하지는 않습니다. 진도 이벤트에는 영상 데이터나 인증 토큰을 저장하지 않습니다.

배포에는 `progress/0003` 마이그레이션이 필요합니다. DB 백업 후 적용합니다. 중복 방지 영수증은 임의로 정리하지 않습니다. 정리 기능을 추가하려면 클라이언트 재전송 기한도 함께 정의해야 합니다.

검증: Django 전체 218개 테스트, Chromium의 모바일 크기·데스크톱 화면, 캔버스 스트림 실제 재생/일시정지, 오프라인 재전송·중복 요청·페이지 이동 복구·지연 메타데이터 이어보기, 홈 화면 설치 안내 회귀 확인. iPhone/Android 화면과 사용자 에이전트를 모사했으며 실제 iOS Safari·카카오톡 앱 내 브라우저에서의 기기 테스트는 별도로 필요합니다.

## 학습 복귀와 탐색 개선 (2026-09-17 추가)

- 영상 오류는 진도 저장 상태와 별도로 표시합니다. HLS와 일반 영상의 오류를 감지하면 수강 권한을 다시 확인하고 최대 3회 재연결합니다. 실패가 계속되면 다시 재생 버튼을 제공하며, 복구 시 재생 위치를 유지합니다. 브라우저가 자동 재생을 막으면 사용자 클릭으로 재생합니다.
- `/lessons/<id>/access/`는 로그인 만료(401), 수강 만료 등 접근 제한(403), 비공개/없는 차시(404)를 구분하는 캐시 금지 JSON 응답입니다. 진도 API도 로그인 만료 시 로그인 HTML로 이동하지 않고 401을 반환합니다. 화면에서는 다시 로그인 또는 수강 상태/재수강 확인 링크를 제공합니다.
- 로그인은 Django의 안전한 `next` 검사 후 원래 차시·강의 화면으로 복귀합니다. 외부 사이트로의 리디렉션은 허용하지 않습니다. 복귀한 차시에서 미저장 진도를 다시 전송합니다.
- 끝까지 보고 완료 처리된 최근 차시에는 다음 공개 차시와 처음부터 복습 선택지를 표시합니다. 90% 완료 기준에 도달했어도 아직 영상 끝에 도달하지 않았다면 그대로 이어봅니다. `?replay=1`은 최초 재생 위치만 0으로 설정하고 주소에서 제거하므로 이후 새로고침·재로그인 시 새 진도로 이어볼 수 있습니다. 누적 진도와 수료 상태는 초기화하지 않습니다.
- 내 강의실은 수강 중·승인 대기·종료(필요 시 기타 신청) 탭을 제공하고 선택한 상태만 표시합니다. 강의가 있는 첫 상태가 기본값이며, `status`와 `q` GET 파라미터로 탭·제목 검색을 유지합니다. 공개 강의 목록 검색도 기존 공개·초대·수강 권한 범위 안에서 수행합니다.
- 차시 목록에는 제목 검색과 미완료 필터를 제공합니다. 강의 상세·내 강의실 과정·영상 화면에서 사용하며, 영상 화면에서는 재생을 끊지 않고 목록만 필터링합니다. JavaScript가 없으면 전체 목록을 그대로 표시합니다.
- 수강생 화면의 상단 로고는 기존 전구 이미지를 사용하고 명칭을 위드브레인연구소 아카데미로 통일합니다. 무료 과정 안내는 신청 즉시 이용 가능한 정책으로 맞췄습니다.

추가 검증 명령: `python manage.py test --noinput`, `node --test tests/js/video_recovery.test.cjs`. 로그인 복귀/외부 리디렉션 방지, 접근 상태 구분, 완료 차시 이동, 검색 권한을 Django 테스트로 확인합니다. 재생 복구의 횟수 제한·위치 복원·오프라인 복귀·자동 재생 거절은 독립 JavaScript 테스트로 확인합니다. 브라우저 점검에는 320/390/768/1440px 화면, 실제 로그인 세션 만료 후 차시 복귀와 저장 복구, 탭·검색·필터·복습 흐름을 포함합니다. 추가 DB 마이그레이션은 없습니다.
