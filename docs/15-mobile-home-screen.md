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
