from decouple import config

from .base import *

DEBUG = True
SECRET_KEY = config("SECRET_KEY", default="django-insecure-dev-only")
ALLOWED_HOSTS = ["*"]
CORS_ALLOW_ALL_ORIGINS = True
