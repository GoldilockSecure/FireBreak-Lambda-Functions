#!/usr/bin/env python3
"""Local API Gateway simulator for testing Goldilock FireBreak AWS Lambda functions.

This script creates a local HTTP server that mimics AWS API Gateway behavior,
allowing you to test your Goldilock FireBreak Lambda functions with realistic
HTTP requests/responses.

Features:
- Simulates API Gateway request event structure
- Handles HTTP methods, headers, query parameters, and request bodies
- Provides proper Lambda context
- Returns formatted HTTP responses
- Supports CORS headers
- Request/response logging

Usage:
    python local_api_gateway.py [port] [lambda_module]
    
Examples:
    python local_api_gateway.py 3000 portStatus
    python local_api_gateway.py 8080 port_status.py
"""

import sys
import json
import time
import uuid
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Dict, Any, List, Callable, Optional, cast
from lambda_test_runner import MockLambdaContext


class APIGatewaySimulator(BaseHTTPRequestHandler):
    """HTTP request handler that simulates AWS API Gateway behavior."""
    
    def __init__(self, lambda_handler: Callable[[Dict[str, Any], Any], Dict[str, Any]], *args: Any, **kwargs: Any) -> None:
        """Initialize the handler with a Goldilock FireBreak Lambda function.
        
        Args:
            lambda_handler: The Goldilock FireBreak Lambda function to invoke.
        """
        self.lambda_handler = lambda_handler
        super().__init__(*args, **kwargs)
        
    @classmethod
    def create_handler(cls, lambda_handler: Callable[[Dict[str, Any], Any], Dict[str, Any]]) -> Callable[..., 'APIGatewaySimulator']:
        """Factory method to create a handler with the Lambda function."""
        def handler(*args: Any, **kwargs: Any) -> 'APIGatewaySimulator':
            return cls(lambda_handler, *args, **kwargs)
        return handler
        
    def do_GET(self) -> None:
        """Handle GET requests."""
        self.handle_request()
        
    def do_POST(self) -> None:
        """Handle POST requests."""
        self.handle_request()
        
    def do_PUT(self) -> None:
        """Handle PUT requests."""
        self.handle_request()
        
    def do_DELETE(self) -> None:
        """Handle DELETE requests."""
        self.handle_request()
        
    def do_PATCH(self) -> None:
        """Handle PATCH requests."""
        self.handle_request()
        
    def do_OPTIONS(self) -> None:
        """Handle OPTIONS requests (for CORS preflight)."""
        self.send_cors_response()
        
    def send_cors_response(self) -> None:
        """Send CORS preflight response."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, PATCH, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With')
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()
        
    def handle_request(self) -> None:
        """Process HTTP request and invoke Lambda function."""
        try:
            # Parse the request
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)
            
            # Convert multi-value query parameters to single values (for simplicity)
            single_value_params: Dict[str, Optional[str]] = {}
            multi_value_params: Dict[str, List[str]] = {}
            
            for key, values in query_params.items():
                single_value_params[key] = values[0] if values else None
                multi_value_params[key] = values
                
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            body: Optional[str] = None
            is_base64_encoded = False
            
            if content_length > 0:
                body_bytes = self.rfile.read(content_length)
                try:
                    # Try to decode as UTF-8 text
                    body = body_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    # If not UTF-8, base64 encode binary data
                    import base64
                    body = base64.b64encode(body_bytes).decode('utf-8')
                    is_base64_encoded = True
                    
            # Convert headers to the format expected by Lambda
            headers: Dict[str, str] = {}
            multi_value_headers: Dict[str, List[str]] = {}
            
            for key, value in self.headers.items():
                headers[key] = value
                multi_value_headers[key] = [value]
                
            # Create API Gateway event structure
            event: Dict[str, Any] = {
                'resource': parsed_url.path,
                'path': parsed_url.path,
                'httpMethod': self.command,
                'headers': headers,
                'multiValueHeaders': multi_value_headers,
                'queryStringParameters': single_value_params if single_value_params else None,
                'multiValueQueryStringParameters': multi_value_params if multi_value_params else None,
                'pathParameters': None,
                'stageVariables': None,
                'requestContext': {
                    'resourceId': str(uuid.uuid4())[:8],
                    'resourcePath': parsed_url.path,
                    'httpMethod': self.command,
                    'extendedRequestId': str(uuid.uuid4()),
                    'requestId': str(uuid.uuid4()),
                    'accountId': '123456789012',
                    'stage': 'local',
                    'requestTimeEpoch': int(time.time() * 1000),
                    'requestTime': datetime.now(timezone.utc).strftime('%d/%b/%Y:%H:%M:%S %z'),
                    'protocol': f'HTTP/{self.protocol_version}',
                    'identity': {
                        'cognitoIdentityPoolId': None,
                        'accountId': None,
                        'cognitoIdentityId': None,
                        'caller': None,
                        'sourceIp': self.client_address[0],
                        'principalOrgId': None,
                        'accessKey': None,
                        'cognitoAuthenticationType': None,
                        'cognitoAuthenticationProvider': None,
                        'userArn': None,
                        'userAgent': self.headers.get('User-Agent', ''),
                        'user': None
                    },
                    'domainName': 'localhost',
                    'apiId': 'local-api'
                },
                'body': body,
                'isBase64Encoded': is_base64_encoded
            }
            
            # Create Lambda context
            context = MockLambdaContext('local-api-gateway-function', 30)
            
            # Log the request
            self.log_api_request(event)
            
            # Invoke the Lambda function
            start_time = time.time()
            lambda_response = self.lambda_handler(event, context)
            execution_time = time.time() - start_time
            
            # Log the response
            self.log_api_response(lambda_response, execution_time)
            
            # Send HTTP response
            self.send_lambda_response(lambda_response)
            
        except Exception as e:
            # Handle any errors during request processing
            self.log_api_error(e)
            self.send_error_response(500, f"Internal server error: {str(e)}")
            
    def log_api_request(self, event: Dict[str, Any]) -> None:
        """Log incoming request details."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        method = event.get('httpMethod', 'UNKNOWN')
        path = event.get('path', '/')
        request_context = event.get('requestContext', {})
        if isinstance(request_context, dict):
            request_ctx = cast(Dict[str, Any], request_context)
            identity_data = request_ctx.get('identity', {})
            identity = cast(Dict[str, Any], identity_data) if identity_data else {}
            source_ip = str(identity.get('sourceIp', 'unknown'))
        else:
            source_ip = 'unknown'
        
        print(f"[{timestamp}] IN  {method} {path} - {source_ip}")
        
        # Log query parameters if present
        query_params = event.get('queryStringParameters')
        if query_params:
            print(f"    Query: {json.dumps(query_params)}")
            
        # Log important headers
        headers = event.get('headers', {})
        if isinstance(headers, dict):
            headers_dict = cast(Dict[str, Any], headers)
            important_headers = ['Authorization', 'Content-Type', 'User-Agent']
            for header in important_headers:
                if header in headers_dict:
                    header_value = headers_dict[header]
                    value = str(header_value) if header_value is not None else ''
                    # Mask Authorization header for security
                    if header == 'Authorization':
                        value = value[:10] + '...' if len(value) > 10 else value
                    print(f"    {header}: {value}")
                
    def log_api_response(self, response: Dict[str, Any], execution_time: float) -> None:
        """Log Lambda function response."""
        status_code = response.get('statusCode', 200)
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        print(f"[{timestamp}] OUT {status_code} ({execution_time:.3f}s)")
        
    def log_api_error(self, error: Exception) -> None:
        """Log errors that occur during request processing."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] ERROR: {type(error).__name__}: {str(error)}")
        
    def send_lambda_response(self, lambda_response: Dict[str, Any]) -> None:
        """Convert Lambda response to HTTP response."""
        # Extract response components
        status_code = lambda_response.get('statusCode', 200)
        headers = lambda_response.get('headers', {})
        body = lambda_response.get('body', '')
        is_base64_encoded = lambda_response.get('isBase64Encoded', False)
        
        # Send status code
        if isinstance(status_code, int):
            self.send_response(status_code)
        else:
            self.send_response(200)
        
        # Add CORS headers by default
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, PATCH, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With')
        
        # Send custom headers from Lambda response
        if isinstance(headers, dict):
            headers_dict = cast(Dict[str, Any], headers)
            for key, value in headers_dict.items():
                self.send_header(str(key), str(value))
            
            # If no content-type specified, default to JSON for API responses
            if 'Content-Type' not in headers:
                self.send_header('Content-Type', 'application/json')
        else:
            self.send_header('Content-Type', 'application/json')
            
        self.end_headers()
        
        # Send body
        if body:
            if is_base64_encoded and isinstance(body, str):
                import base64
                body_bytes = base64.b64decode(body)
                self.wfile.write(body_bytes)
            elif isinstance(body, str):
                self.wfile.write(body.encode('utf-8'))
                
    def send_error_response(self, status_code: int, message: str) -> None:
        """Send an error response."""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        error_body = json.dumps({'error': message})
        self.wfile.write(error_body.encode('utf-8'))
        
    def log_message(self, format: str, *args: Any) -> None:
        """Override default logging to use our custom format."""
        # We handle logging in our custom methods
        pass


def import_lambda_function(module_path: str) -> Callable[[Dict[str, Any], Any], Dict[str, Any]]:
    """Import the lambda_handler function from the specified module."""
    # Remove .py extension if present
    module_name = module_path.replace('.py', '')
    
    # Add lambda_functions directory to Python path
    import os
    lambda_functions_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lambda_functions')
    lambda_functions_dir = os.path.abspath(lambda_functions_dir)
    
    if lambda_functions_dir not in sys.path:
        sys.path.insert(0, lambda_functions_dir)
        
    # Also add current directory for backward compatibility
    if '.' not in sys.path:
        sys.path.insert(0, '.')
        
    try:
        # Import the module
        module = __import__(module_name)
        
        # Get the lambda_handler function
        if hasattr(module, 'lambda_handler'):
            return module.lambda_handler
        else:
            raise AttributeError(f"No lambda_handler function found in {module_name}")
            
    except ImportError as e:
        raise ImportError(f"Failed to import {module_name}: {e}")


def main() -> None:
    """Start the local API Gateway simulator for Goldilock FireBreak functions."""
    # Parse command line arguments
    port = 3000
    lambda_module = 'portStatus'
    
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("Invalid port number")
            sys.exit(1)
            
    if len(sys.argv) > 2:
        lambda_module = sys.argv[2]
        
    # Import the Lambda function
    try:
        lambda_handler = import_lambda_function(lambda_module)
        print(f"Successfully imported {lambda_module}.lambda_handler")
    except Exception as e:
        print(f"Failed to import Lambda function: {e}")
        sys.exit(1)
        
    # Create the handler class with the Lambda function
    handler_class = APIGatewaySimulator.create_handler(lambda_handler)
    
    # Start the server
    server = None
    try:
        server = HTTPServer(('localhost', port), handler_class)
        print("Local API Gateway simulator started")
        print(f"Server: http://localhost:{port}")
        print(f"Goldilock FireBreak Lambda Function: {lambda_module}")
        print("Press Ctrl+C to stop")
        print("-" * 50)
        
        server.serve_forever()
        
    except KeyboardInterrupt:
        print("\nServer stopped by user")
        if server:
            server.shutdown()
    except Exception as e:
        print(f"Server error: {e}")
        if server:
            server.shutdown()
        sys.exit(1)


if __name__ == "__main__":
    main()