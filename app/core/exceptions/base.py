from enum import Enum


class APIErrorType(Enum):
    """API error types for Datahive"""
    POLICY_NOT_ACCEPTED = "You are not allowed to do measurement as you're not accepted the privacy policy"
    LOGGED_OUT = 'You have been loged out!'
    ACCOUNT_BANNED = 'Your account has been suspended until further notice for violating our terms of service. It will go into further review'
    EMAIL_ALREADY_EXISTS = 'Email already exist!!'
    NOT_PARTICIPATED_IN_RAFFLE_SEASON = 'You have not participated in the current raffle season'
    KYC_ALREADY_APPLIED = 'KYC is already applied'
    CLIENT_UPGRADE_REQUIRED = 'Client upgrade is required'


class APIError(Exception):
    def __init__(self, error: str, response_data: dict | str = None):
        self.error = error
        self.response_data = response_data
        self.error_type = self._get_error_type()
        super().__init__(error)
    
    def _get_error_type(self) -> APIErrorType | None:
        """Determine error type based on message"""
        return next(
            (error_type for error_type in APIErrorType if error_type.value == self.error_message),
            None
        )
    
    @property
    def error_message(self) -> str:
        if isinstance(self.response_data, dict):
            if 'error' in self.response_data:
                return self.response_data.get('error') or self.error
        return self.error
    
    def __str__(self) -> str:
        return self.error


class ServerError(Exception):
    pass


class ProxyForbidden(Exception):
    pass


class RateLimitExceeded(Exception):
    def __init__(self, reset_time: int = 60):
        self.reset_time = reset_time
        super().__init__(f'Rate limit exceeded. Try again in {reset_time} seconds.')
    
    def __str__(self) -> str:
        return f'Rate limit exceeded. Try again in {self.reset_time} seconds.'


class SessionBlocked(Exception):
    pass


class ServerTimeout(Exception):
    pass


class EmailValidationFailed(Exception):
    """Raised when the email validation failed"""
    pass


class CaptchaSolvingFailed(Exception):
    """Raised when the captcha solving failed"""
    pass


class NoAvailableProxies(Exception):
    """Raised when there are no available proxies"""
    pass


class ComputingImageFailed(Exception):
    """Raised when the computing image failed"""
    pass


class DiscordConnectError(Exception):
    """Raised when there is an error with Discord connection"""
    pass

