"""
ASGI config for the project.

Exposes the ASGI callable as a module-level variable named ``application``.
Kept alongside wsgi.py so both deployment styles (gunicorn, uvicorn) work.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")

application = get_asgi_application()
