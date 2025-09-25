"""AWS Lambda function to query Goldilock FireBreak API for port status.

This function interfaces with the Goldilock FireBreak API to retrieve the
current activation status of all FireBreak ports. It is designed to run in
AWS Lambda with no external dependencies beyond Python's standard library.

The function:
- Reads Goldilock FireBreak API IP address and token from environment variables
- Makes a GET request using urllib (standard library, no external deps)
- Returns structured JSON with appropriate HTTP status codes

Environment Variables:
    API_IP: Goldilock FireBreak device IP address
    API_TOKEN: Bearer token for Goldilock FireBreak API authentication
    DISABLE_SSL_VERIFY: Optional flag to disable SSL verification
    PORT_OFFSET: Optional flag to enable physical port numbering (1-12)
"""

import os
import json
import ssl
import logging
import time
import urllib.request
import urllib.error
import re
from typing import Any, Dict, List, Union, cast

# Configure structured logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment configuration
API_IP: str = os.environ.get("API_IP", "")
API_TOKEN: str = os.environ.get("API_TOKEN", "")


def validate_api_ip(ip_str: str) -> bool:
    """Validate API host[:port] to prevent injection and SSRF.
    
    Accepts:
      - 'localhost' or DNS hostname (RFC 1123 subset)
      - IPv4 address
      - Optional ':port' where 1–65535
    Rejects:
      - Any of '@', '/', '\\', '?', '#'
      - Multiple ':' segments (only host:port supported)
    """
    if not ip_str:
        return False

    # Quick reject of dangerous characters
    if any(ch in ip_str for ch in ('@', '/', '\\', '?', '#')):
        return False

    try:
        parts = ip_str.split(':')
        if len(parts) > 2:
            return False

        host = parts[0]
        port_str = parts[1] if len(parts) == 2 else None

        # Validate host
        ipv4_pattern = r'^(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)$'
        dns_pattern = (
            r'^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?'
            r'(?:\.(?:[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?))*)$'
        )

        # Validate host against allowed patterns
        if not (
            host == 'localhost'
            or re.match(ipv4_pattern, host) is not None
            or re.match(dns_pattern, host) is not None
        ):
            return False

        # Validate optional port
        if port_str is not None:
            if not port_str.isdigit():
                return False
            port = int(port_str)
            if port < 1 or port > 65535:
                return False

        return True
    except Exception:
        return False


# Validate API_IP on module load
if not API_IP:
    raise ValueError("API_IP environment variable is missing")
if not validate_api_ip(API_IP):
    raise ValueError(f"Invalid API_IP environment variable: {API_IP}")

# Construct the specific endpoint URL for port status
API_URL: str = f"https://{API_IP}/api/websocket/get-all-status"

# Optional: allow skipping SSL verification (use with caution)
DISABLE_SSL_VERIFY: bool = os.environ.get("DISABLE_SSL_VERIFY", "true").lower() == "true"

# Optional: port number offset for physical vs API numbering
# When True: Physical ports 1-12 -> API ports 0-11
# When False (default): Use raw port numbers as provided
PORT_OFFSET: bool = os.environ.get("PORT_OFFSET", "false").lower() == "true"


def fetch_port_status() -> List[Dict[str, Any]]:
    """Fetch port status data from the Goldilock FireBreak API.

    Makes a GET request to the configured Goldilock FireBreak API endpoint
    to retrieve the activation status of all FireBreak ports.

    Returns:
        A list of dictionaries with keys 'active' (int, 0 or 1) and
        'port' (int) representing the status of each FireBreak port.
        Port numbers are adjusted based on PORT_OFFSET setting:
        - PORT_OFFSET=true: Returns ports 1-12 (physical numbering)
        - PORT_OFFSET=false: Returns ports 0-11 (API numbering)

    Raises:
        urllib.error.URLError: If the HTTP request to Goldilock FireBreak
            API fails.
        json.JSONDecodeError: If the API response is not valid JSON.
    """
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {API_TOKEN}",
    }

    req = urllib.request.Request(API_URL, headers=headers)

    # Handle SSL context
    ssl_context = None
    if DISABLE_SSL_VERIFY:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

    with urllib.request.urlopen(req, context=ssl_context, timeout=10) as resp:
        body = resp.read().decode("utf-8")
        raw_data = json.loads(body)
        
        # Apply port offset if enabled (API ports 0-11 -> Physical ports 1-12)
        if PORT_OFFSET and isinstance(raw_data, list):
            ports_list = cast(List[Dict[str, Any]], raw_data)
            for port_data in ports_list:
                if 'port' in port_data:
                    port_data['port'] = port_data['port'] + 1
            return ports_list
        
        # Return raw data if no offset or not a list
        return cast(List[Dict[str, Any]], raw_data)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda entry point for Goldilock FireBreak port status retrieval.

    Handles incoming Lambda events and returns port status data from the
    Goldilock FireBreak API in a format suitable for API Gateway responses.

    Args:
        event: AWS Lambda event object containing request information.
        context: AWS Lambda context runtime information.

    Returns:
        A dictionary containing 'statusCode' (int) and 'body' (JSON string)
        with either the port status data or error information, including
        execution time in milliseconds.
    """
    start_time = time.time()
    
    logger.info(
        json.dumps(
            {
                "message": "Lambda invoked",
                "event": event,
            }
        )
    )

    if not API_TOKEN:
        error_message = "API_TOKEN environment variable is missing"
        logger.error(error_message)
        execution_time_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "error": error_message,
                "executionTimeMs": execution_time_ms
            }),
        }

    try:
        data = fetch_port_status()
        execution_time_ms = round((time.time() - start_time) * 1000, 2)
        logger.info(json.dumps({
            "message": "Successfully fetched Goldilock FireBreak port status",
            "count": len(data),
            "executionTimeMs": execution_time_ms
        }))
        
        response_data: Dict[str, Union[List[Dict[str, Any]], float]] = {
            "ports": data,
            "executionTimeMs": execution_time_ms
        }
        
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(response_data),
        }

    except urllib.error.HTTPError as http_err:
        execution_time_ms = round((time.time() - start_time) * 1000, 2)
        logger.error(json.dumps({
            "error": "Goldilock FireBreak API HTTPError",
            "code": http_err.code,
            "reason": http_err.reason,
            "executionTimeMs": execution_time_ms
        }))
        return {
            "statusCode": http_err.code,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "error": f"Goldilock FireBreak API HTTP error: {http_err.reason}",
                "executionTimeMs": execution_time_ms
            }),
        }

    except urllib.error.URLError as url_err:
        execution_time_ms = round((time.time() - start_time) * 1000, 2)
        logger.error(json.dumps({
            "error": "Goldilock FireBreak API URLError",
            "reason": str(url_err),
            "executionTimeMs": execution_time_ms
        }))
        return {
            "statusCode": 502,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "error": f"Goldilock FireBreak API URL error: {url_err}",
                "executionTimeMs": execution_time_ms
            }),
        }

    except json.JSONDecodeError:
        execution_time_ms = round((time.time() - start_time) * 1000, 2)
        logger.error(json.dumps({
            "error": "Failed to decode Goldilock FireBreak API JSON response",
            "executionTimeMs": execution_time_ms
        }))
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "error": "Invalid JSON response from Goldilock FireBreak API",
                "executionTimeMs": execution_time_ms
            }),
        }

    except Exception as exc:  # Catch-all safeguard
        execution_time_ms = round((time.time() - start_time) * 1000, 2)
        logger.error(json.dumps({
            "error": "UnexpectedError",
            "details": str(exc),
            "executionTimeMs": execution_time_ms
        }))
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "error": "Unexpected error occurred while querying Goldilock FireBreak API",
                "executionTimeMs": execution_time_ms
            }),
        }
