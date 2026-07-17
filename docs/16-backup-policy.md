# ONEDU Backup Policy

This document describes the current backup behavior for the production LMS.

## Automated Backup Scope

The automated backup intentionally excludes large lesson video files.

Included:

- PostgreSQL database dump
- Public media files under `data/media`
- Private non-video learning materials under `data/private_media`, such as `lesson_attachments`

Excluded:

- Original uploaded lesson videos
- HLS converted video files
- `data/private_media/lesson_videos`
- `data/private_media/lesson_hls`

Reason:

- Video/HLS files are large and should be protected with Synology Hyper Backup, Snapshot Replication, external storage, or a separate NAS/cloud backup policy.
- Database and public media are small enough for daily automated backups on the same NAS.

## Schedule

The default automated backup schedule is daily at `03:20`.

Environment variables:

```env
ONEDU_AUTOMATED_BACKUP_ENABLED=True
ONEDU_BACKUP_HOUR=3
ONEDU_BACKUP_MINUTE=20
ONEDU_BACKUP_RETENTION_DAYS=30
ONEDU_BACKUP_INCLUDE_PUBLIC_MEDIA=True
ONEDU_BACKUP_INCLUDE_PRIVATE_NONVIDEO=True
```

## Storage

Host path:

```text
/volume1/wbinstitute/docker/onedu/app/backups
```

Container path:

```text
/vol/web/backups
```

Expected subfolders:

```text
backups/db/
backups/media/
backups/private_nonvideo/
```

## Retention

The default retention period is 30 days.

Files older than the retention period are deleted automatically by the backup command.

## Manual Check

From the development PC:

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\onedu-remote.ps1 backup-check
```

From the NAS:

```bash
sudo -n /usr/local/sbin/onedu-ops backup-check
```

## Important Limitation

The `.env` file contains secrets and is not automatically copied by the app container.
Keep a separate secure copy of `.env` whenever passwords, domains, mail settings, or security settings change.
