from decouple import config
from django.templatetags.static import static
from django.urls import reverse_lazy
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
    'unfold',  # Оформление админки — должно стоять до django.contrib.admin
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
    'project_finance.apps.ProjectFinanceConfig',
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
    'support.middleware.AdminRussianLocaleMiddleware',  # Админка на русском
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
        'project_finance': {
            'handlers': ['console', 'file'],
            'level': config('LOG_LEVEL', default='INFO'),
            'propagate': False,
        },

    },
}

LOGIN_URL = 'login'
# Куда вести после входа через /admin/login/ без ?next= (вход на сайт редиректит сам, см. support/auth.py)
LOGIN_REDIRECT_URL = 'admin:index'

# Переводы, которых нет в пакетах (строки интерфейса django-unfold)
LOCALE_PATHS = [BASE_DIR / 'locale']


# ── Оформление админки (django-unfold) ───────────────────────────────────────

def _admin_link(name):
    return reverse_lazy(f'admin:{name}_changelist')


UNFOLD = {
    'SITE_TITLE':     'Aerogroup',
    'SITE_HEADER':    'Aerogroup',
    'SITE_SUBHEADER': 'Панель администратора',
    'SITE_URL':       '/',
    'SITE_ICON':      lambda request: static('support/images/logo_icon.png'),
    'SITE_FAVICONS': [
        {'rel': 'icon', 'type': 'image/png', 'href': lambda request: static('support/images/logo_icon.png')},
    ],
    'BORDER_RADIUS': '8px',
    # Фирменный голубой сайта (#03a0dc) как основной цвет
    'COLORS': {
        'primary': {
            '50':  '#e6f6fc', '100': '#cdeef9', '200': '#9bdcf3', '300': '#69cbed',
            '400': '#37b9e7', '500': '#03a0dc', '600': '#0384b6', '700': '#02678e',
            '800': '#024b67', '900': '#012f41', '950': '#011f2b',
        },
    },
    'SIDEBAR': {
        'show_search': True,
        'show_all_applications': False,
        'navigation': [
            {
                'title': 'Сотрудники и регистрация пользователей',
                'items': [
                    {'title': 'Сотрудники', 'icon': 'badge',                'link': _admin_link('support_employee')},
                    {'title': 'Отделы',     'icon': 'apartment',            'link': _admin_link('support_department')},
                    {'title': 'Роли',       'icon': 'admin_panel_settings', 'link': _admin_link('support_role')},
                ],
            },
            {
                'title': 'База знаний | Аэрофлот',
                'collapsible': True,
                'items': [
                    {'title': 'Статьи',       'icon': 'article',     'link': _admin_link('aeroflot_bdaeroflotarticle')},
                    {'title': 'Категории',    'icon': 'folder',      'link': _admin_link('aeroflot_bdaeroflotcategory')},
                    {'title': 'Вложения',     'icon': 'attach_file', 'link': _admin_link('aeroflot_bdaeroflotattachment')},
                    {'title': 'Ознакомления', 'icon': 'task_alt',    'link': _admin_link('aeroflot_articleacknowledgement')},
                ],
            },
            {
                'title': 'База знаний | Россия',
                'collapsible': True,
                'items': [
                    {'title': 'Статьи',       'icon': 'article',     'link': _admin_link('russia_bdrussiaarticle')},
                    {'title': 'Категории',    'icon': 'folder',      'link': _admin_link('russia_bdrussiacategory')},
                    {'title': 'Вложения',     'icon': 'attach_file', 'link': _admin_link('russia_bdrussiaattachment')},
                    {'title': 'Ознакомления', 'icon': 'task_alt',    'link': _admin_link('russia_russiaarticleacknowledgement')},
                ],
            },
            {
                'title': 'Проверка знаний',
                'items': [
                    {'title': 'Категории тестирования', 'icon': 'quiz',       'link': _admin_link('knowledge_check_testcategory')},
                    {'title': 'Вопросы',                'icon': 'help',       'link': _admin_link('knowledge_check_question')},
                    {'title': 'Попытки прохождения',    'icon': 'fact_check', 'link': _admin_link('knowledge_check_userattempt')},
                    {'title': 'Разрешения на повтор',   'icon': 'replay',     'link': _admin_link('knowledge_check_retakeproxy')},
                ],
            },
        ],
    },
}

MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
# Файлы MEDIA отдаются только вошедшим (support.views.protected_media).
# MEDIA_X_ACCEL=True — проверку делает Django, а файл отдаёт nginx из internal
# location /protected-media/ (nginx/nginx.conf). По умолчанию включено вне DEBUG.
MEDIA_X_ACCEL        = config('MEDIA_X_ACCEL', default=not DEBUG, cast=bool)
MEDIA_X_ACCEL_PREFIX = '/protected-media/'

# Email настройки
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('HOST_MAIL')
EMAIL_PORT = config('MAIL_PORT', cast=int)
EMAIL_USE_TLS = config('USE_TLS', cast=bool)
EMAIL_HOST_USER = config('HOST_USER')
EMAIL_HOST_PASSWORD = config('HOST_PASSWORD')
DEFAULT_FROM_EMAIL = config('HOST_USER')