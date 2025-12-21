"""Application exceptions."""


class ThinkerAPIError(Exception):
    """Exception raised when the thinker API fails."""

    def __init__(self, message: str, is_quota_error: bool = False):
        self.message = message
        self.is_quota_error = is_quota_error
        super().__init__(message)


class BillingError(Exception):
    """Exception raised when there is a billing or quota-related error."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)
