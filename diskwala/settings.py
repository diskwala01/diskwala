from pathlib import Path
import os
import dj_database_url

# ============================
# BASE
# ============================
BASE_DIR = Path(__file__).resolve().parent.parent
IMAGEKIT_PRIVATE_KEY = os.environ.get(
    "IMAGEKIT_PRIVATE_KEY",
    "private_KzrfZmrVIK/si28ZFtENMdeLpZg="  # ← Yeh temporary dev ke liye daal do
)

# ============================
# SECURITY
# ============================
SECRET_KEY = os.environ.get("SECRET_KEY", "unsafe-secret-key")
SYSTEM_SECRET = os.environ.get("SYSTEM_SECRET", "dev-secret")

DEBUG = os.environ.get("DEBUG", "False") == "True"

ALLOWED_HOSTS = ["*"]

# ============================
# APPLICATIONS
# ============================
INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",

    # Local
    "core",
]

# ============================
# MIDDLEWARE
# ============================
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

# ============================
# URLS / WSGI
# ============================
ROOT_URLCONF = "diskwala.urls"
WSGI_APPLICATION = "diskwala.wsgi.application"

# ============================
# TEMPLATES
# ============================
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

# ============================
# DATABASE (NEON POSTGRES)
# ============================
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    # Render / Production (Postgres)
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            ssl_require=True,
        )
    }
else:
    # Local development (SQLite)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# ============================
# AUTH
# ============================
AUTH_USER_MODEL = "core.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ============================
# INTERNATIONALIZATION
# ============================
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ============================
# STATIC FILES
# ============================
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ============================
# MEDIA FILES
# ============================
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ============================
# DEFAULT PK
# ============================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ============================
# DJANGO REST FRAMEWORK
# ============================
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

# ============================
# CORS / CSRF
# ============================
CORS_ALLOW_ALL_ORIGINS = True

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://localhost:8000",
    "https://127.0.0.1:8000",
]

# ============================
# PRODUCTION HARDENING (OPTIONAL)
# ============================
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
