import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-secret-never-use-in-production")

from .settings import *  # noqa: E402,F403

OPENROUTER_API_KEY = "test-only-api-key"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
