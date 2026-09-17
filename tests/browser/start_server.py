"""Prepare a disposable database before starting the local browser test server."""
import os
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
os.chdir(root)
sys.path.insert(0, str(root))
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.browser_test_settings'
(root / '.browser-tests').mkdir(exist_ok=True)
import django
django.setup()
from django.core.management import call_command
call_command('migrate', verbosity=0, interactive=False)
from seed import seed
seed(root)
subprocess.run([sys.executable, 'manage.py', 'runserver', '127.0.0.1:8766', '--noreload', '--nothreading'], check=True)
