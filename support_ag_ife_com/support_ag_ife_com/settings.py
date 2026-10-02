from decouple import config
from pathlib import Path
import os


BASE_DIR = Path(__file__).resolve().parent.parent


SECRET_KEY = config("DJANGO_KEY")
DEBUG = config("DEBUG", cast=bool)

ALLOWED_HOSTS = ['support.ag-ife.com', '10.1.0.150', '127.0.0.1']
CSRF_TRUSTED_ORIGINS = ['https://support.ag-ife.com']

# Доверять Nginx что соединение HTTPS
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Редирект на HTTPS делает Nginx, не Django
SECURE_SSL_REDIRECT = False

# Куки сессии только по HTTPS
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

# CSRF куки только по HTTPS
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = 'Lax'


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'support.apps.SupportConfig',
    'statistic.apps.StatisticConfig',
    'daily_schedule.apps.DailyScheduleConfig',
    'aeroflot.apps.AeroflotConfig',
    'russia.apps.RussiaConfig',
    'knowledge_check.apps.KnowledgeCheckConfig',
    'anonimaeroflot.apps.AnonimaeroflotConfig',
    'anonimrussia.apps.AnonimrussiaConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'support.middleware.AdminAccessMiddleware',  # Блокировка /admin/ по роли
]

ROOT_URLCONF = 'support_ag_ife_com.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'support_ag_ife_com' / 'templates'
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'support.context_processors.get_menu', # Мое меню-сайдбар
                'support.context_processors.get_svg_user', # Мое user-меню
            ],
        },
    },
]

WSGI_APPLICATION = 'support_ag_ife_com.wsgi.application'




DATABASES = {
    'default': {
        'ENGINE':   'django.db.backends.postgresql',
        'NAME':     config('DB_NAME'),
        'USER':     config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST':     config('DB_HOST', default='localhost'),
        'PORT':     config('DB_PORT', default='5432'),
    }
}



AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]




LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


STATIC_URL = 'static/' # Стоит по дефолту
STATIC_ROOT = BASE_DIR / 'staticfiles'  # Для продакшена




LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{asctime} [{levelname}] {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'app.log',
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
    },
    'loggers': {
        'statistic': {
            'handlers': ['console', 'file'],
            'level': config('LOG_LEVEL', default='INFO'),
            'propagate': False,
        },
        'daily_schedule': {
            'handlers': ['console', 'file'],
            'level': config('LOG_LEVEL', default='INFO'),
            'propagate': False,
        },
        'aeroflot': {
            'handlers': ['console', 'file'],
            'level': config('LOG_LEVEL', default='INFO'),
            'propagate': False,
        },
        'russia': {
            'handlers': ['console', 'file'],
            'level': config('LOG_LEVEL', default='INFO'),
            'propagate': False,
        },
        'knowledge_check': {
            'handlers': ['console', 'file'],
            'level': config('LOG_LEVEL', default='INFO'),
            'propagate': False,
        },

    },
}

LOGIN_URL = 'login'

MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Email настройки
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('HOST_MAIL')
EMAIL_PORT = config('MAIL_PORT', cast=int)
EMAIL_USE_TLS = config('USE_TLS', cast=bool)
EMAIL_HOST_USER = config('HOST_USER')
EMAIL_HOST_PASSWORD = config('HOST_PASSWORD')
DEFAULT_FROM_EMAIL = config('HOST_USER')