# 수강생 이용 가이드 관리

- 내용 원본: `docs/student-guide.json`
- 배포 파일: `static/docs/onedu-student-user-manual.pdf`
- 생성: `python tools/build_student_guide.py`
- 한글 글꼴을 자동으로 찾지 못하면 `--font /path/to/Korean.ttf`를 지정합니다. ReportLab이 설치된 Python 환경이 필요합니다.
- `catalog.png`는 2026-09-21, `classroom.png`는 2026-09-22 템플릿을 사용하는 로컬 화면입니다. 안내용 계정과 예시 강의만 사용했으며 실제 회원 정보는 포함하지 않습니다.

내용이나 UI가 바뀌면 원본과 필요한 화면 예시를 갱신하고 PDF를 다시 생성합니다. 생성 후 각 페이지를 렌더링해 한글, 줄바꿈, 사진 크기, 페이지 넘침을 확인합니다. 홈 및 도움말 페이지의 PDF 링크 버전과 개정일도 함께 갱신합니다.

기존 `docs/ONEDU_LMS_*.docx` 및 `docs/manual_assets` 파일은 이 생성 작업의 입력 또는 출력으로 사용하지 않습니다.
