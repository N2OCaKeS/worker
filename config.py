from os import getenv

TARGET_URLS = getenv("TARGET_URLS", "https://example.com").split(",")
THREADS     = int(getenv("THREADS", "10"))
DURATION    = int(getenv("DURATION", "60"))   # в секундах



TRACK_CODES = [
    100, 101,                 # Informational
    200, 201, 202, 204,       # Success
    301, 302, 304,            # Redirects
    400, 401, 403, 404, 408, 429,  # Client errors
    500, 502, 503, 504        # Server errors
]