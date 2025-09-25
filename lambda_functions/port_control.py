"""AWS Lambda function to control Goldilock FireBreak port activation.

This function interfaces with the Goldilock FireBreak API to control the
activation status of individual FireBreak ports. It is designed to run in
AWS Lambda with no external dependencies beyond Python's standard library.

The function:
- Reads Goldilock FireBreak API IP address and token from environment variables
- Makes a POST request using urllib (standard library, no external deps)
- Sends JSON payload to activate/deactivate specific FireBreak ports
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

# Construct the specific endpoint URL for port control
API_URL: str = f"https://{API_IP}/api/websocket/port-control"

# Optional: allow skipping SSL verification (use with caution)
DISABLE_SSL_VERIFY: bool = os.environ.get("DISABLE_SSL_VERIFY", "true").lower() == "true"

# Optional: port number offset for physical vs API numbering
# When True: Physical ports 1-12 -> API ports 0-11
# When False (default): Use raw port numbers as provided
PORT_OFFSET: bool = os.environ.get("PORT_OFFSET", "false").lower() == "true"


def control_port(port: Union[int, str], activate: bool) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """Control FireBreak port activation through the Goldilock FireBreak API.

    Makes a POST request to the configured Goldilock FireBreak API endpoint
    to activate or deactivate specific FireBreak port(s).

    Args:
        port: FireBreak port number or "all" to control all ports.
              Port range depends on PORT_OFFSET setting:
              - PORT_OFFSET=true: 1-12 (physical numbering)
              - PORT_OFFSET=false: 0-11 (API numbering)
        activate: True to activate the FireBreak port(s), False to deactivate.

    Returns:
        For individual ports: A dictionary with keys 'active' (bool) and 'port' (int).
        For "all" ports: A list of dictionaries, each with 'active' and 'port' keys.
        Port numbers in response are adjusted based on PORT_OFFSET setting.

    Raises:
        urllib.error.URLError: If the HTTP request to Goldilock FireBreak
            API fails.
        json.JSONDecodeError: If the API response is not valid JSON.
        ValueError: If port is not in valid range or "all".
    """
    # Validate and convert port parameter
    if isinstance(port, int):
        if PORT_OFFSET:
            # Physical numbering: 1-12 -> API numbering: 0-11
            if port < 1 or port > 12:
                raise ValueError(f"FireBreak port must be an integer between 1 and 12 (physical numbering), got: {port}")
            api_port = port - 1  # Convert to API numbering
        else:
            # API numbering: 0-11
            if port < 0 or port > 11:
                raise ValueError(f"FireBreak port must be an integer between 0 and 11 (API numbering), got: {port}")
            api_port = port  # Use as-is
    elif port == "all":
        api_port = "all"  # Pass through unchanged
    else:
        port_range = "1-12" if PORT_OFFSET else "0-11"
        numbering = "physical" if PORT_OFFSET else "API"
        raise ValueError(f"FireBreak port must be an integer ({port_range}, {numbering} numbering) or 'all', got: {port}")

    # Prepare request payload with API port numbering
    payload: Dict[str, Any] = {
        "port": api_port,
        "activate": activate
    }
    
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }

    # Encode payload as JSON
    json_payload = json.dumps(payload).encode('utf-8')
    
    req = urllib.request.Request(API_URL, data=json_payload, headers=headers, method='POST')

    # Handle SSL context
    ssl_context = None
    if DISABLE_SSL_VERIFY:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

    with urllib.request.urlopen(req, context=ssl_context, timeout=10) as resp:
        body = resp.read().decode("utf-8")
        raw_response = json.loads(body)
        
        # Apply port offset to response if enabled (API numbering -> Physical numbering)
        if PORT_OFFSET:
            if isinstance(raw_response, dict) and 'port' in raw_response:
                # Individual port response: convert API port back to physical port
                response_dict = cast(Dict[str, Any], raw_response)
                response_dict['port'] = response_dict['port'] + 1
                return response_dict
            elif isinstance(raw_response, list):
                # All ports response: convert all API ports back to physical ports
                ports_list = cast(List[Dict[str, Any]], raw_response)
                for port_data in ports_list:
                    if 'port' in port_data:
                        port_data['port'] = port_data['port'] + 1
                return ports_list
        
        # Return raw response if no offset needed
        return cast(Union[Dict[str, Any], List[Dict[str, Any]]], raw_response)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda entry point for Goldilock FireBreak port control.

    Handles incoming Lambda events to control FireBreak port activation
    through the Goldilock FireBreak API. Returns responses suitable for
    API Gateway.

    Expected event structure:
    {
        "port": int (0-11) or "all",
        "activate": bool (true/false)
    }
    
    Or for API Gateway events, the port and activate values can be in:
    - event["body"] (JSON string)
    - event itself (direct parameters)

    Args:
        event: AWS Lambda event object containing request information.
        context: AWS Lambda context runtime information.

    Returns:
        A dictionary containing 'statusCode' (int) and 'body' (JSON string)
        with either the port control result or error information, including
        execution time in milliseconds.
    """
    start_time = time.time()
    
    logger.info(
        json.dumps(
            {
                "message": "Goldilock FireBreak Port Control Lambda invoked",
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
        # Extract port and activate parameters from event
        port = None
        activate = None
        
        # Try to get parameters from different event structures
        if "body" in event and event["body"]:
            # API Gateway event with JSON body
            try:
                body_data = json.loads(event["body"])
                port = body_data.get("port")
                activate = body_data.get("activate")
            except json.JSONDecodeError:
                return {
                    "statusCode": 400,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps({"error": "Invalid JSON in request body"}),
                }
        else:
            # Direct event parameters
            port = event.get("port")
            activate = event.get("activate")

        # Validate required parameters
        if port is None:
            execution_time_ms = round((time.time() - start_time) * 1000, 2)
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "error": "Missing required parameter: port",
                    "executionTimeMs": execution_time_ms
                }),
            }
            
        if activate is None:
            execution_time_ms = round((time.time() - start_time) * 1000, 2)
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "error": "Missing required parameter: activate",
                    "executionTimeMs": execution_time_ms
                }),
            }

        # Handle port parameter - can be integer (0-11) or string "all"
        if isinstance(port, str):
            if port.lower() == "all":
                port = "all"
            else:
                # Try to convert to integer
                try:
                    port = int(port)
                except ValueError:
                    execution_time_ms = round((time.time() - start_time) * 1000, 2)
                    return {
                        "statusCode": 400,
                        "headers": {"Content-Type": "application/json"},
                        "body": json.dumps({
                            "error": f"FireBreak port must be a number (0-11) or 'all', got: {port}",
                            "executionTimeMs": execution_time_ms
                        }),
                    }

        # Normalize 'activate' to a strict boolean
        try:
            activate = parse_bool(activate)
        except ValueError:
            execution_time_ms = round((time.time() - start_time) * 1000, 2)
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "error": "Invalid value for 'activate': expected boolean (true/false) or equivalent",
                    "executionTimeMs": execution_time_ms
                }),
            }
        
        logger.info(json.dumps({
            "message": "Controlling Goldilock FireBreak port",
            "port": port,
            "activate": activate
        }))

        # Make the API call
        result = control_port(port, activate)
        execution_time_ms = round((time.time() - start_time) * 1000, 2)
        
        logger.info(json.dumps({
            "message": "Goldilock FireBreak port control successful",
            "result": result,
            "executionTimeMs": execution_time_ms
        }))
        
        # Wrap result with execution time
        if isinstance(result, list):
            # All ports response
            all_ports_response: Dict[str, Union[List[Dict[str, Any]], float]] = {
                "ports": result,
                "executionTimeMs": execution_time_ms
            }
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(all_ports_response),
            }
        else:
            # Individual port response
            individual_port_response: Dict[str, Any] = {**result, "executionTimeMs": execution_time_ms}
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(individual_port_response),
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

    except ValueError as val_err:
        execution_time_ms = round((time.time() - start_time) * 1000, 2)
        logger.error(json.dumps({
            "error": "ValueError",
            "details": str(val_err),
            "executionTimeMs": execution_time_ms
        }))
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "error": str(val_err),
                "executionTimeMs": execution_time_ms
            }),
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
                "error": "Unexpected error occurred while controlling Goldilock FireBreak API",
                "executionTimeMs": execution_time_ms
            }),
        }

def parse_bool(value: Any) -> bool:
    """Parse value into a strict boolean.

    Accepts:
    - bool: returned as-is
    - int: 0 or 1 only
    - str: case-insensitive true/false equivalents:
      true, false, 1, 0, yes, no, y, n, on, off
    Raises:
        ValueError: for unsupported types or values.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value in (0, 1):
            return bool(value)
        raise ValueError(f"Invalid integer for boolean: {value}")
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("true", "1", "yes", "y", "on"):
            return True
        if v in ("false", "0", "no", "n", "off"):
            return False
        raise ValueError(f"Invalid string for boolean: {value!r}")
    raise ValueError(f"Unsupported type for boolean: {type(value).__name__}")