import os
import shutil
import subprocess
import tarfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.utils import timezone


class Command(BaseCommand):
    help = 'Create a non-video backup: database dump and public media archive.'

    def add_arguments(self, parser):
        parser.add_argument('--skip-db', action='store_true', help='Skip database dump.')
        parser.add_argument('--skip-media', action='store_true', help='Skip public media archive.')
        parser.add_argument('--retention-days', type=int, default=None, help='Delete backup files older than this many days.')

    def handle(self, *args, **options):
        backup_root = Path(settings.ONEDU_BACKUP_ROOT)
        retention_days = options['retention_days']
        if retention_days is None:
            retention_days = settings.ONEDU_BACKUP_RETENTION_DAYS

        timestamp = timezone.localtime().strftime('%Y%m%d_%H%M%S')
        backup_root.mkdir(parents=True, exist_ok=True)

        created_files = []
        if not options['skip_db']:
            created_files.append(self._backup_database(backup_root, timestamp))

        if settings.ONEDU_BACKUP_INCLUDE_PUBLIC_MEDIA and not options['skip_media']:
            media_backup = self._backup_public_media(backup_root, timestamp)
            if media_backup:
                created_files.append(media_backup)

        if settings.ONEDU_BACKUP_INCLUDE_PRIVATE_NONVIDEO and not options['skip_media']:
            private_backup = self._backup_private_nonvideo_media(backup_root, timestamp)
            if private_backup:
                created_files.append(private_backup)

        deleted_count = self._prune_old_backups(backup_root, retention_days)

        self.stdout.write(self.style.SUCCESS('Non-video backup complete.'))
        for backup_file in created_files:
            self.stdout.write(f'- {backup_file}')
        self.stdout.write(f'- pruned old files: {deleted_count}')

    def _backup_database(self, backup_root, timestamp):
        db_settings = connections['default'].settings_dict
        engine = db_settings.get('ENGINE', '')
        db_dir = backup_root / 'db'
        db_dir.mkdir(parents=True, exist_ok=True)

        if 'sqlite3' in engine:
            source = Path(db_settings.get('NAME', ''))
            if not source.exists():
                raise CommandError(f'SQLite database file does not exist: {source}')
            target = db_dir / f'onedu_sqlite_{timestamp}.sqlite3'
            shutil.copy2(source, target)
            self._chmod_private(target)
            return target

        if 'postgresql' not in engine:
            raise CommandError(f'Unsupported database engine for backup: {engine}')

        pg_dump = shutil.which('pg_dump')
        if not pg_dump:
            raise CommandError('pg_dump is not installed in this container.')

        target = db_dir / f'onedu_{timestamp}.sql'
        command = [
            pg_dump,
            '--host',
            str(db_settings.get('HOST') or 'localhost'),
            '--port',
            str(db_settings.get('PORT') or 5432),
            '--username',
            str(db_settings.get('USER') or ''),
            '--dbname',
            str(db_settings.get('NAME') or ''),
            '--file',
            str(target),
        ]
        env = os.environ.copy()
        if db_settings.get('PASSWORD'):
            env['PGPASSWORD'] = str(db_settings['PASSWORD'])

        result = subprocess.run(command, env=env, text=True, capture_output=True)
        if result.returncode != 0:
            target.unlink(missing_ok=True)
            message = result.stderr.strip() or result.stdout.strip() or 'pg_dump failed'
            raise CommandError(message)

        self._chmod_private(target)
        return target

    def _backup_public_media(self, backup_root, timestamp):
        source = Path(settings.MEDIA_ROOT)
        if not source.exists():
            self.stdout.write(self.style.WARNING(f'MEDIA_ROOT does not exist, skipped: {source}'))
            return None

        media_dir = backup_root / 'media'
        media_dir.mkdir(parents=True, exist_ok=True)
        target = media_dir / f'onedu_media_{timestamp}.tar.gz'
        with tarfile.open(target, 'w:gz') as archive:
            archive.add(source, arcname='media')
        self._chmod_private(target)
        return target

    def _backup_private_nonvideo_media(self, backup_root, timestamp):
        source = Path(settings.PRIVATE_MEDIA_ROOT)
        if not source.exists():
            self.stdout.write(self.style.WARNING(f'PRIVATE_MEDIA_ROOT does not exist, skipped: {source}'))
            return None

        files = [path for path in source.rglob('*') if path.is_file() and not self._is_video_artifact(source, path)]
        if not files:
            self.stdout.write(self.style.WARNING('No private non-video media files found, skipped.'))
            return None

        private_dir = backup_root / 'private_nonvideo'
        private_dir.mkdir(parents=True, exist_ok=True)
        target = private_dir / f'onedu_private_nonvideo_{timestamp}.tar.gz'
        with tarfile.open(target, 'w:gz') as archive:
            for file_path in files:
                archive.add(file_path, arcname=Path('private_media') / file_path.relative_to(source))
        self._chmod_private(target)
        return target

    def _prune_old_backups(self, backup_root, retention_days):
        if retention_days <= 0:
            return 0
        cutoff = timezone.now().timestamp() - (retention_days * 24 * 60 * 60)
        patterns = (
            'db/onedu_*.sql',
            'db/onedu_sqlite_*.sqlite3',
            'media/onedu_media_*.tar.gz',
            'private_nonvideo/onedu_private_nonvideo_*.tar.gz',
        )
        deleted_count = 0
        for pattern in patterns:
            for backup_file in backup_root.glob(pattern):
                if backup_file.is_file() and backup_file.stat().st_mtime < cutoff:
                    backup_file.unlink()
                    deleted_count += 1
        return deleted_count

    def _chmod_private(self, path):
        try:
            path.chmod(0o600)
        except OSError:
            pass

    def _is_video_artifact(self, root, path):
        relative = path.relative_to(root)
        if relative.parts and relative.parts[0] in {'lesson_videos', 'lesson_hls'}:
            return True
        return path.suffix.lower() in {
            '.mp4',
            '.m4v',
            '.mov',
            '.avi',
            '.mkv',
            '.webm',
            '.ts',
            '.m3u8',
        }
