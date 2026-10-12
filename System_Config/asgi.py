"""
ASGI config for System_Config project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "System_Config.settings")

application = get_asgi_application()

# Only server processes import this module, so management commands and tests never start it.
from Main.services.alert_scheduler import start_alert_scheduler  # noqa: E402

start_alert_scheduler()
