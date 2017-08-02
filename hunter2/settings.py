from .utils import load_or_create_secret_key
import environ
import logging

# Load the current environment profile
root = environ.Path(__file__) - 2
env = environ.Env()

# Default settings which should be overridden by environment variables
DEBUG         = env.bool      ('H2_DEBUG',         default=False)
LOG_LEVEL     = env.str       ('H2_LOG_LEVEL',     default='WARNING')
LANGUAGE_CODE = env.str       ('H2_LANGUAGE_CODE', default='en-gb')
TIME_ZONE     = env.str       ('H2_TIME_ZONE',     default='Europe/London')
ALLOWED_HOSTS = env.list      ('H2_ALLOWED_HOSTS', default=['*'])
INTERNAL_IPS  = env.list      ('H2_INTERNAL_IPS',  default=['127.0.0.1'])
EMAIL_CONFIG  = env.email_url ('H2_EMAIL_URL',     default='smtp://localhost:25')
DATABASES = {
    'default': env.db('H2_DATABASE_URL', default="postgres://postgres:postgres@db:5432/postgres")
}
CACHES = {
    'default': env.cache_url('H2_CACHE_URL', default="dummycache://" )
}
USE_SILK = DEBUG and env.bool('H2_SILK', default=False)

if USE_SILK:
    try:
        import silk  # noqa: F401
    except ImportError:
        logging.error("Silk profiling enabled but not available. Check REQUIREMENTS_VERSION is set to development at build time.")
        USE_SILK = False

# Generate a secret key and store it the first time it is accessed
SECRET_KEY = load_or_create_secret_key("/config/secrets.ini")

# Load the email configuration
vars().update(EMAIL_CONFIG)

BASE_DIR = root()

# Application definition
ACCOUNT_ACTIVATION_DAYS = 7

ACCOUNT_AUTHENTICATED_LOGIN_REDIRECTS = False

ACCOUNT_EMAIL_REQUIRED = True

ACCOUNT_EMAIL_VERIFICATION = 'none'

AUTHENTICATION_BACKENDS = (
    'allauth.account.auth_backends.AuthenticationBackend',
    'django.contrib.auth.backends.ModelBackend',
    'lazysignup.backends.LazySignupBackend',
    'rules.permissions.ObjectPermissionBackend',
)

DATABASES['default']['ATOMIC_REQUESTS'] = True

DEBUG_TOOLBAR_PATCH_SETTINGS = False

INSTALLED_APPS = (
    'dal',
    'dal_select2',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.sites',
    'django.contrib.staticfiles',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.openid',
    'debug_toolbar',
    'lazysignup',
    'nested_admin',
    'rules.apps.AutodiscoverRulesConfig',
    'sortedm2m',
    'subdomains',
    'events',
    'teams',
    'hunts',
    'hunter2',
)
if USE_SILK:
    INSTALLED_APPS = INSTALLED_APPS + ('silk',)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        '': {
            'handlers': ['console'],
            'level': LOG_LEVEL,
        },
        'django.db': {
        },
    },
}

LOGIN_REDIRECT_URL = '/'

LOGIN_URL = '/accounts/login/'

MEDIA_ROOT = '/uploads/'

MEDIA_URL = '/media/'

MIDDLEWARE = (
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.http.ConditionalGetMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'subdomains.middleware.SubdomainURLRoutingMiddleware',
    'django.middleware.common.CommonMiddleware',
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'events.middleware.EventMiddleware',
    'teams.middleware.TeamMiddleware',
)
if USE_SILK:
    MIDDLEWARE = ('silk.middleware.SilkyMiddleware',) + MIDDLEWARE

ROOT_URLCONF = 'hunter2.urls'

SOCIALACCOUNT_AUTO_SIGNUP = False

SOCIALACCOUNT_PROVIDERS = {
    'openid': {
        'SERVERS': [{
            'id': 'steam',
            'name': 'Steam',
            'openid_url': 'http://steamcommunity.com/openid',
        }]
    }
}

STATIC_ROOT = '/static/'

STATIC_URL = '/static/'

STATICFILES_DIRS = (
    'hunter2/static',
    'hunts/static',
)

SECURE_BROWSER_XSS_FILTER = True

SECURE_CONTENT_TYPE_NOSNIFF = True

SITE_ID = 1

SUBDOMAIN_URLCONFS = {
    'admin': 'hunter2.urls.admin',
    'www': 'hunter2.urls.www',
}

TEMPLATES = [
    {
        'APP_DIRS': True,
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            'hunter2/templates',
        ],
        'OPTIONS': {
            'context_processors': [
                'django.contrib.auth.context_processors.auth',
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.template.context_processors.static',
                'django.contrib.messages.context_processors.messages',
                'teams.context_processors.event_team',
                'hunts.context_processors.announcements',
            ],
        },
    },
]

TEST_RUNNER = 'hunter2.tests.TestRunner'

USE_I18N = True

USE_L10N = True

USE_TZ = True

WSGI_APPLICATION = 'hunter2.wsgi.application'

X_FRAME_OPTIONS = 'DENY'

if USE_SILK:
    SILKY_PYTHON_PROFILER = True
    SILKY_PYTHON_PROFILER_BINARY = True
    # Well, the following path is rubbish but I cba doing it properly for now
    SILKY_PYTHON_PROFILER_RESULT_PATH = '/uploads/events/'
