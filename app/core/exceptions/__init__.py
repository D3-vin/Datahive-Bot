from app.core.exceptions.base import (
    APIError,
    APIErrorType,
    ServerError,
    ProxyForbidden,
    RateLimitExceeded,
    SessionBlocked,
    ServerTimeout,
    EmailValidationFailed,
    CaptchaSolvingFailed,
    NoAvailableProxies,
    ComputingImageFailed,
    DiscordConnectError
)

__all__ = [
    'APIError',
    'APIErrorType',
    'ServerError',
    'ProxyForbidden',
    'RateLimitExceeded',
    'SessionBlocked',
    'ServerTimeout',
    'EmailValidationFailed',
    'CaptchaSolvingFailed',
    'NoAvailableProxies',
    'ComputingImageFailed',
    'DiscordConnectError'
]


