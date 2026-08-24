import os
from pathlib import Path

import django

from System_Config.database import build_database_config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True, parents=True)


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
ENVIRONMENT = os.getenv("SYSTEMA_ENV", "development").strip().lower()
IS_PRODUCTION = ENVIRONMENT == "production"

# Production must provide its own secret. The fallback is intentionally local-only.
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-systema-local-development-only")
if IS_PRODUCTION and (SECRET_KEY.startswith("django-insecure-") or len(SECRET_KEY) < 50):
    raise RuntimeError("DJANGO_SECRET_KEY must be set to a strong value in production")

# python manage.py collectstatic 本番環境に更新内容を反映させるために必要
# python manage.py collectstatic --clear 設定リセット
DEBUG = os.getenv("DJANGO_DEBUG", "false").strip().lower() in {"1", "true", "yes", "on"}
if IS_PRODUCTION and DEBUG:
    raise RuntimeError("DJANGO_DEBUG must be false in production")

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if host.strip()
]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

SECURE_SSL_REDIRECT = IS_PRODUCTION
SESSION_COOKIE_SECURE = IS_PRODUCTION
CSRF_COOKIE_SECURE = IS_PRODUCTION
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = int(os.getenv("DJANGO_SESSION_COOKIE_AGE", "28800"))
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SECURE_HSTS_SECONDS = 31536000 if IS_PRODUCTION else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = IS_PRODUCTION
SECURE_HSTS_PRELOAD = IS_PRODUCTION
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

EXTERNAL_SEARCH_KEYWORD_MAX_LENGTH = int(os.getenv("EXTERNAL_SEARCH_KEYWORD_MAX_LENGTH", "100"))
EXTERNAL_SEARCH_RATE_LIMIT = int(os.getenv("EXTERNAL_SEARCH_RATE_LIMIT", "30"))
EXTERNAL_SEARCH_RATE_WINDOW_SECONDS = int(os.getenv("EXTERNAL_SEARCH_RATE_WINDOW_SECONDS", "60"))
EXTERNAL_SEARCH_TRUST_X_FORWARDED_FOR = os.getenv(
    "EXTERNAL_SEARCH_TRUST_X_FORWARDED_FOR", "false"
).strip().lower() in {"1", "true", "yes", "on"}

AUTH_LOGIN_ACCOUNT_MAX_FAILURES = int(os.getenv("AUTH_LOGIN_ACCOUNT_MAX_FAILURES", "5"))
AUTH_LOGIN_IP_MAX_FAILURES = int(os.getenv("AUTH_LOGIN_IP_MAX_FAILURES", "30"))
AUTH_LOGIN_WINDOW_SECONDS = int(os.getenv("AUTH_LOGIN_WINDOW_SECONDS", "900"))
AUTH_LOGIN_LOCK_BASE_SECONDS = int(os.getenv("AUTH_LOGIN_LOCK_BASE_SECONDS", "60"))
AUTH_MAX_LOCK_SECONDS = int(os.getenv("AUTH_MAX_LOCK_SECONDS", "3600"))
AUTH_SIGNUP_MAX_ATTEMPTS = int(os.getenv("AUTH_SIGNUP_MAX_ATTEMPTS", "5"))
AUTH_ADMIN_SETUP_MAX_ATTEMPTS = int(os.getenv("AUTH_ADMIN_SETUP_MAX_ATTEMPTS", "5"))
AUTH_REGISTRATION_WINDOW_SECONDS = int(
    os.getenv("AUTH_REGISTRATION_WINDOW_SECONDS", "3600")
)
AUTH_RATE_LIMIT_TRUST_X_FORWARDED_FOR = os.getenv(
    "AUTH_RATE_LIMIT_TRUST_X_FORWARDED_FOR", "false"
).strip().lower() in {"1", "true", "yes", "on"}
ADMIN_SETUP_ENABLED = not IS_PRODUCTION and os.getenv(
    "ADMIN_SETUP_ENABLED", "true"
).strip().lower() in {"1", "true", "yes", "on"}

if os.getenv("DJANGO_BEHIND_HTTPS_PROXY", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

TEST_RUNNER = "django.test.runner.DiscoverRunner"

# Application definition
INSTALLED_APPS = [
    "Main.apps.TaskleConfig",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "Main.middleware.error_logging_middleware.ErrorLoggingMiddleware",
]

if django.VERSION >= (6, 0):
    from django.utils.csp import CSP

    MIDDLEWARE.insert(-1, "django.middleware.csp.ContentSecurityPolicyMiddleware")
    SECURE_CSP = {
        "default-src": [CSP.SELF],
        "script-src": [
            CSP.SELF,
            CSP.UNSAFE_INLINE,
            "https://cdn.jsdelivr.net",
            "https://code.jquery.com",
            "https://d3js.org",
        ],
        "style-src": [
            CSP.SELF,
            CSP.UNSAFE_INLINE,
            "https://cdn.jsdelivr.net",
            "https://fonts.googleapis.com",
        ],
        "font-src": [
            CSP.SELF,
            "data:",
            "https://cdn.jsdelivr.net",
            "https://fonts.gstatic.com",
        ],
        "img-src": [CSP.SELF, "data:", "https:"],
        "connect-src": [CSP.SELF],
        "object-src": [CSP.NONE],
        "base-uri": [CSP.SELF],
        "frame-ancestors": [CSP.NONE],
        "form-action": [CSP.SELF],
    }

ROOT_URLCONF = "System_Config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "System_Config.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = build_database_config(BASE_DIR, os.environ)

# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = "ja"

TIME_ZONE = "Asia/Tokyo"

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    BASE_DIR / "Main/static",
]

if DEBUG:
    STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
else:
    # STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "index"
LOGOUT_REDIRECT_URL = "index"
# loggingの設定
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": str(LOG_DIR / "search.log"),
            "formatter": "verbose",
            "encoding": "utf-8",
        },
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "error_file": {
            "level": "ERROR",
            "class": "logging.FileHandler",
            "filename": str(LOG_DIR / "error.log"),
            "formatter": "verbose",
        },
        "server_file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": str(LOG_DIR / "server.log"),
            "formatter": "verbose",
        },
    },
    "loggers": {
        "": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "search_logger": {
            "handlers": ["file", "console"],
            "level": "INFO",
            "propagate": False,
        },
        "error_logger": {
            "handlers": ["error_file", "console"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.server": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "server_logger": {
            "handlers": ["server_file", "console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

HANDLER404 = "Main.views.Error.custom_404"
HANDLER500 = "Main.views.Error.custom_500"
HANDLER400 = "Main.views.Error.custom_400"
HANDLER415 = "Main.views.Error.custom_415"
