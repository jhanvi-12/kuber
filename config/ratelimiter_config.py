"""Configuration constants for API rate limiting."""

# For general authenticated requests (per second window).
RATE_LIMITER_SECONDS = 60
RATE_LIMITER_TIME = 60

# For unauthenticated requests.
UNAUTH_RATE_LIMIT_TIMES = 5
UNAUTH_RATE_LIMIT_SECONDS = 60

# Login attempt limits.
LOGIN_MAX_ATTEMPTS_PER_DAY = 5
LOGIN_BLOCK_SECONDS = 86400
