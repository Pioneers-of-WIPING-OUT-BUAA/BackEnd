import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-secret-never-use-in-production")

from .settings import *  # noqa: E402,F403

OPENROUTER_API_KEY = "test-only-api-key"
COS_SECRET_ID = "test-only-id"
COS_SECRET_KEY = "test-only-key"
COS_BUCKET_NAME = "test-bucket-123"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
