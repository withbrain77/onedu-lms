# 백업과 복구 절차

## 백업 대상

필수 백업 대상은 다음이다.

- PostgreSQL DB
- `media/`: 공개 업로드 파일, 강의 썸네일 등
- `private_media/`: 강의 영상 파일
- `.env`: 운영 비밀값

주의: `.env`는 Git에 커밋하지 않고, NAS 권한이 제한된 별도 위치에 보관한다.

## PostgreSQL 백업

예시 경로:

```bash
mkdir -p /volume1/docker/onedu/backups/db
docker compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" \
  > /volume1/docker/onedu/backups/db/onedu_$(date +%Y%m%d_%H%M%S).sql
```

Synology 작업 스케줄러에 등록할 때는 `.env` 값을 명시하거나 스크립트 안에서 로드한다.

```bash
cd /volume1/docker/onedu/app
set -a
. ./.env
set +a
docker compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" \
  > /volume1/docker/onedu/backups/db/onedu_$(date +%Y%m%d_%H%M%S).sql
```

## 파일 백업

`media`와 `private_media`는 DB와 같이 시점이 맞아야 가장 안전하다.

```bash
rsync -a --delete /volume1/docker/onedu/data/media/ \
  /volume1/docker/onedu/backups/media/latest/

rsync -a --delete /volume1/docker/onedu/data/private_media/ \
  /volume1/docker/onedu/backups/private_media/latest/
```

영상 파일은 용량이 크므로 NAS 스냅샷, Hyper Backup, 외장 디스크, 원격 NAS 중 하나 이상과 조합하는 것을 권장한다.

## 복구 개요

1. 컨테이너 중지

```bash
docker compose down
```

2. PostgreSQL 데이터 폴더를 새로 준비하거나 기존 데이터를 비운다.
3. 컨테이너를 DB만 먼저 실행한다.

```bash
docker compose up -d db
```

4. DB 복구

```bash
cat /volume1/docker/onedu/backups/db/onedu_YYYYMMDD_HHMMSS.sql \
  | docker compose exec -T db psql -U "$POSTGRES_USER" "$POSTGRES_DB"
```

5. `media`와 `private_media` 복구

```bash
rsync -a /volume1/docker/onedu/backups/media/latest/ \
  /volume1/docker/onedu/data/media/

rsync -a /volume1/docker/onedu/backups/private_media/latest/ \
  /volume1/docker/onedu/data/private_media/
```

6. 전체 서비스 기동

```bash
docker compose up -d
docker compose logs -f web
```

7. 운영 확인

- 관리자 로그인
- 강의 목록 확인
- 영상 재생 확인
- 수료증 다운로드 확인
- 수료증 검증 코드 확인

## 백업 검증

백업은 생성보다 복구 검증이 더 중요하다. 운영 전 최소 한 번은 별도 폴더나 테스트 NAS에서 다음을 확인한다.

- DB dump가 정상 import되는지
- 영상 파일 경로가 유지되는지
- 수료증 PDF가 한글로 생성되는지
- `.env` 없이 복구 절차가 막히지 않는지

## 보관 정책 예시

- 일별 DB 백업: 14일 보관
- 주별 DB 백업: 8주 보관
- 월별 DB 백업: 12개월 보관
- `private_media`: 증분 백업 또는 NAS 스냅샷
- `.env`: 변경 시 수동 백업
