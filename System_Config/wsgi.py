"""
WSGI config for System_Config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "System_Config.settings")

application = get_wsgi_application()

# Only server processes import this module, so management commands and tests never start it.
from Main.services.alert_scheduler import start_alert_scheduler  # noqa: E402

start_alert_scheduler()
