class BaseWeatherError(Exception):
    def __init__(self, message, status_http_code=None, error_code=None):
        self.message = message
        self.status_http_code = status_http_code
        self.error_code = error_code
        super().__init__(self.message, self.status_http_code, self.error_code)


class FatalError(BaseWeatherError):
    pass


class ApiKeyError(FatalError):
    pass


class InvalidRequestBodyError(FatalError):
    pass


class NotFoundLocationError(BaseWeatherError):
    pass
