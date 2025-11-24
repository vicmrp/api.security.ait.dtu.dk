from .settings import *


CAS_SERVER_URL = 'https://auth.dtu.dk/dtu/' # no multifactor




CSRF_COOKIE_DOMAIN = 'api.security.ait.dtu.dk'

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 3600  # This sets the duration for one hour, adjust as needed.
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = False