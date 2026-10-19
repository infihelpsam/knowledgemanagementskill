import json
import logging
import datetime


class JsonFormatter(logging.Formatter):
    def format(self, record):
        # Deliberately omit messages/tracebacks from upstream exceptions that may contain secrets.
        return json.dumps({'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'level': record.levelname, 'event': record.msg if isinstance(record.msg, str) and record.msg.replace('_', '').isalnum() else 'log_event', 'job_id': getattr(record, 'job_id', None), 'request_id': getattr(record, 'request_id', None), 'exception_type': record.exc_info[0].__name__ if record.exc_info else None})


def configure_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
