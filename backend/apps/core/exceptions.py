from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class BusinessRuleError(Exception):
    """A broken business rule. The API returns 400 {"code": ..., "detail": ...}."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def exception_handler(exc, context):
    if isinstance(exc, BusinessRuleError):
        return Response({"code": exc.code, "detail": exc.message},
                        status=status.HTTP_400_BAD_REQUEST)
    return drf_exception_handler(exc, context)
