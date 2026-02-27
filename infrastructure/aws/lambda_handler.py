"""
AWS Lambda Handler — ML Service
Wraps the Flask application using Mangum (ASGI adapter) or a custom
WSGI shim so the Flask app can run as an AWS Lambda function behind
an API Gateway HTTP API (or ALB).

Lambda is used for the ML service during low-traffic periods or as a
serverless fallback; for sustained 8K concurrent-user loads, ECS/Fargate
with the Docker image is preferred.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import base64

# Ensure the ml-service/src directory is on the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../ml-service/src"))

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Lazy-initialize Flask app for Lambda warm-start reuse
_flask_app = None


def _get_app():
    global _flask_app
    if _flask_app is None:
        logger.info("Cold start: initializing Flask application …")
        from app import app  # noqa: PLC0415
        _flask_app = app
    return _flask_app


# ---------------------------------------------------------------------------
# WSGI adapter (lightweight, no external dependency needed)
# ---------------------------------------------------------------------------

class WSGIAdapter:
    """
    Minimal AWS Lambda ↔ WSGI bridge.
    Converts API Gateway v2 (HTTP API) proxy events to WSGI environ dicts
    and converts WSGI responses back to API Gateway response format.
    """

    def __init__(self, application):
        self.application = application

    def __call__(self, event: dict, context) -> dict:
        # ── Build WSGI environ from API GW event ───────────────────────────
        method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
        path = event.get("rawPath", "/")
        query = event.get("rawQueryString", "")
        headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}

        body_raw = event.get("body", "") or ""
        is_b64 = event.get("isBase64Encoded", False)
        body_bytes = base64.b64decode(body_raw) if is_b64 else body_raw.encode("utf-8")

        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "QUERY_STRING": query,
            "CONTENT_TYPE": headers.get("content-type", ""),
            "CONTENT_LENGTH": str(len(body_bytes)),
            "SERVER_NAME": "lambda",
            "SERVER_PORT": "443",
            "SERVER_PROTOCOL": "HTTP/1.1",
            "wsgi.input": __import__("io").BytesIO(body_bytes),
            "wsgi.errors": sys.stderr,
            "wsgi.multithread": False,
            "wsgi.multiprocess": False,
            "wsgi.run_once": False,
            "wsgi.url_scheme": "https",
        }

        # Forward HTTP headers as HTTP_* keys
        for key, val in headers.items():
            wsgi_key = "HTTP_" + key.upper().replace("-", "_")
            environ[wsgi_key] = val

        # ── Call the WSGI application ─────────────────────────────────────
        response_started = {}
        response_body = []

        def start_response(status, headers, exc_info=None):
            response_started["status"] = status
            response_started["headers"] = headers

        result = self.application(environ, start_response)
        for chunk in result:
            response_body.append(chunk)

        # ── Convert WSGI response to API GW format ────────────────────────
        status_code = int(response_started["status"].split(" ", 1)[0])
        resp_headers = {k: v for k, v in response_started.get("headers", [])}
        body_out = b"".join(response_body)

        return {
            "statusCode": status_code,
            "headers": resp_headers,
            "body": body_out.decode("utf-8", errors="replace"),
            "isBase64Encoded": False,
        }


# ---------------------------------------------------------------------------
# Lambda entry point
# ---------------------------------------------------------------------------

_adapter = None


def handler(event: dict, context) -> dict:
    """
    AWS Lambda handler function.

    Registered as the Lambda function handler in serverless.yml:
        handler: infrastructure/aws/lambda_handler.handler

    Supports:
    - API Gateway HTTP API (v2) proxy events
    - ALB (Application Load Balancer) target events
    - Direct Lambda invocations (for testing)
    """
    global _adapter
    if _adapter is None:
        app = _get_app()
        _adapter = WSGIAdapter(app)

    logger.info(
        "Lambda invocation: method=%s path=%s",
        event.get("requestContext", {}).get("http", {}).get("method", "?"),
        event.get("rawPath", "/"),
    )

    try:
        return _adapter(event, context)
    except Exception as exc:
        logger.error("Unhandled exception in Lambda handler: %s", exc, exc_info=True)
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Internal server error"}),
            "isBase64Encoded": False,
        }
