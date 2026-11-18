"""WSGI handler that never writes request details or exception text to logs."""
import sys
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer


def _emit(code):
    try:
        if sys.stderr is not None:
            sys.stderr.write(code + '\n')
    except (OSError, ValueError):
        pass


class _SafeErrorStream:
    def __init__(self):
        self._reported = False

    def write(self, value):
        if not self._reported:
            self._reported = True
            _emit('OCR2_HTTP_ERROR')
        return len(value)

    def flush(self):
        return None

    def writelines(self, values):
        for value in values:
            self.write(value)


class SafeWSGIRequestHandler(WSGIRequestHandler):
    def log_message(self, format, *args):
        # Standard access logging includes the full request path and query.
        return None

    def get_stderr(self):
        # WSGI tracebacks can include document text and identifiers.
        return _SafeErrorStream()


class SafeWSGIServer(WSGIServer):
    def handle_error(self, request, client_address):
        _emit('OCR2_HTTP_HANDLER_ERROR')
