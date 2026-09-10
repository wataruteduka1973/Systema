"""Capture HTTP failures without exposing request data or masking the original failure."""

import logging
import traceback
from uuid import uuid4

from Main.services.error_logging import persist_error


class ErrorLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger("error_logger")

    def __call__(self, request):
        request.error_request_id = uuid4().hex
        request.error_recorded = False
        response = self.get_response(request)
        response["X-Request-ID"] = request.error_request_id
        if response.status_code >= 400 and not request.error_recorded:
            self.record(request, response.status_code)
        return response

    def record(self, request, status, exception=None):
        request.error_recorded = True
        match = getattr(request, "resolver_match", None)
        route = getattr(match, "view_name", None) or "unresolved"
        # Only route names are retained: raw paths can contain personal data.
        location = route[:255]
        line = None
        frames = []
        if exception is not None:
            for frame in traceback.extract_tb(exception.__traceback__):
                # Retain code locations, never source lines, local variables or exception text.
                filename = frame.filename.replace("\\", "/").rsplit("/", 1)[-1]
                frames.append(f"{filename}:{frame.lineno}:{frame.name}")
            if frames:
                location = frames[-1][:255]
                line = traceback.extract_tb(exception.__traceback__)[-1].lineno
        message = (
            f"request_id={request.error_request_id} status={status} route={route} "
            f"exception={type(exception).__name__ if exception is not None else 'none'}"
        )
        if frames:
            message += " frames=" + " > ".join(frames[-20:])
        self.logger.error("%s", message)
        persist_error(
            error_code=str(status),
            message=message,
            location=location,
            line_number=line,
        )

    def process_exception(self, request, exception):
        self.record(request, 500, exception)
        return None
