import os
import django
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stockdb.settings')

# Otomatik migrate
try:
    django.setup()
    from django.core.management import call_command
    call_command('migrate', interactive=False)
except Exception as e:
    print("Migration error:", e)

application = get_wsgi_application() 