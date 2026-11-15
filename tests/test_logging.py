import json
import logging

from app.log_config import setup_logging


def test_log_line_is_json(capsys):
    setup_logging("INFO")

    logging.getLogger("app.test").warning("hello")

    line = capsys.readouterr().out.strip().splitlines()[-1]
    record = json.loads(line)
    assert record["level"] == "WARNING"
    assert record["logger"] == "app.test"
    assert record["message"] == "hello"
    assert "timestamp" in record


def test_health_check_requests_are_not_logged(capsys):
    setup_logging("INFO")

    access = logging.getLogger("uvicorn.access")
    access.info('1.2.3.4 - "GET /healthz/live HTTP/1.1" 200')
    access.info('1.2.3.4 - "GET /api/version HTTP/1.1" 200')

    output = capsys.readouterr().out
    assert "/healthz/live" not in output
    assert "/api/version" in output
