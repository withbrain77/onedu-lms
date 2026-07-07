# Onedu Approval LMS

이 저장소는 결제 기능이 없는 승인형 업무용 온라인 강의 사이트를 위한 설계 작업 공간이다.
현재 단계에서는 코드를 작성하지 않고, Django 기반 MVP를 구현하기 위한 아키텍처와 작업 계획을 먼저 정리한다.

## 목표

- 수강생이 직접 결제하지 않는 승인형 LMS를 구축한다.
- 수강 신청 후 관리자가 승인하거나 계정을 열어주는 방식으로 운영한다.
- 회사 내 Synology NAS에서 Docker Compose로 배포한다.
- Django template와 Bootstrap 5를 기반으로 빠르게 운영 가능한 MVP를 만든다.
- 기능만 동작하는 화면이 아니라 실제 업무에 사용할 수 있는 UI/UX 품질을 확보한다.

## 우선 기술 스택

- Backend: Django
- Database: PostgreSQL
- Web server: Nginx
- App server: Gunicorn
- Frontend: Django template
- UI framework: Bootstrap 5
- Optional interaction: HTMX 또는 Vanilla JavaScript
- Deployment: Docker Compose on Synology NAS

## 설계 문서

- [전체 아키텍처](docs/01-architecture.md)
- [DB 모델 설계](docs/02-db-model.md)
- [화면 목록과 URL 구조](docs/03-screens-and-urls.md)
- [UI/UX 설계안](docs/04-ui-ux.md)
- [개발 단계별 체크리스트](docs/05-development-plan.md)
- [서브에이전트 사용 판단과 작업 지시문](docs/06-subagents.md)
- [MVP 구현 계획과 추후 확장 기능](docs/07-mvp-and-roadmap.md)

## 구현 원칙

- 초기 MVP는 Django Admin과 Django template를 적극 활용한다.
- React 또는 Next.js는 초기 범위에서 제외한다.
- 수강 권한, 수강 기간, 영상 접근 권한 검증은 공통 서비스로 분리한다.
- 영상 파일은 public media URL로 직접 노출하지 않는다.
- 수강생 화면은 모바일 반응형을 필수로 한다.
- 관리자 화면은 데스크톱 업무 효율을 우선한다.
- Bootstrap 5 기반으로 버튼, 카드, 폼, 테이블, 배지 스타일을 통일한다.

## 추천 진행 순서

1. 설계 문서를 기준으로 화면과 데이터 구조를 확정한다.
2. 메인 에이전트가 Django 기본 프로젝트 구조를 생성한다.
3. 백엔드 모델, 권한 서비스, Django Admin을 구현한다.
4. 수강생 화면과 관리자 보조 화면을 Bootstrap 5 기반으로 구현한다.
5. 영상 권한 제공 구조와 워터마크를 구현한다.
6. Docker Compose와 Synology NAS 배포 구성을 추가한다.
7. QA와 보안 점검 후 통합 리팩터링을 진행한다.
