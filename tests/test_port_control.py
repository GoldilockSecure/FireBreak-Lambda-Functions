#!/usr/bin/env python3
"""
Comprehensive test suite for the Goldilock FireBreak portControl Lambda function.

This script demonstrates various testing scenarios including:
- Successful FireBreak port activation/deactivation
- Parameter validation (FireBreak port range, data types)
- Error handling (missing parameters, invalid JSON, network errors)
- Different event types (API Gateway, direct invocation)
- Environment configuration testing

Usage:
    python test_port_control.py [environment_name]
    
Examples:
    python test_port_control.py local_port_control
    python test_port_control.py mock_port_control
"""

import sys
import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, List, Union, cast
from lambda_test_runner import LambdaTestRunner


class MockPortControlServer(BaseHTTPRequestHandler):
    """Mock Goldilock FireBreak API server for testing port control without external dependencies."""
    
    def do_POST(self):
        """Handle POST requests to simulate the Goldilock FireBreak port control API."""
        # Check authorization header
        auth_header = self.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            self.send_error(401, 'Unauthorized')
            return
            
        token = auth_header.replace('Bearer ', '')
        
        # Read request body
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            self.send_error(400, 'Empty request body')
            return
            
        try:
            body_bytes = self.rfile.read(content_length)
            request_data = json.loads(body_bytes.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_error(400, 'Invalid JSON in request body')
            return
        
        # Validate required fields
        if 'port' not in request_data:
            self.send_error(400, 'Missing required field: port')
            return
            
        if 'activate' not in request_data:
            self.send_error(400, 'Missing required field: activate')
            return
            
        port = request_data['port']
        activate = request_data['activate']
        
        # Validate FireBreak port range (including "all" option)
        if isinstance(port, str) and port.lower() == "all":
            # Handle "all" ports control
            all_ports_response: List[Dict[str, Union[int, bool]]] = []
            for port_num in range(12):
                all_ports_response.append({
                    "active": 1 if activate else 0,
                    "port": port_num
                })
            
            if token == 'mock-token':
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(all_ports_response).encode())
                return
            elif token == 'error-token':
                self.send_error(500, 'Internal Server Error')
                return
            elif token == 'invalid-json-token':
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'invalid json response')
                return
            else:
                self.send_error(403, 'Forbidden - Invalid token')
                return
        elif not isinstance(port, int) or port < 0 or port > 11:
            self.send_error(400, f'FireBreak port must be integer between 0-11 or "all", got: {port}')
            return
            
        # Validate activate type
        if not isinstance(activate, bool):
            self.send_error(400, f'Activate must be boolean, got: {type(activate).__name__}')
            return
        
        # Simulate different responses based on token
        if token == 'mock-token':
            # Normal successful response matching Goldilock FireBreak API format
            response_data: Dict[str, Union[bool, int]] = {
                "active": activate,  # Return the requested activation state
                "port": port
            }
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode())
            
        elif token == 'error-token':
            # Simulate server error
            self.send_error(500, 'Internal Server Error')
            
        elif token == 'invalid-json-token':
            # Simulate invalid JSON response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'invalid json response')
            
        elif token == 'timeout-token':
            # Simulate timeout by sleeping
            time.sleep(15)  # Longer than typical Lambda timeout
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"delayed": True}).encode())
            
        else:
            self.send_error(403, 'Forbidden - Invalid token')
            
    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default logging to keep test output clean."""
        pass


def start_mock_control_server(port: int = 8080) -> HTTPServer:
    """Start a mock Goldilock FireBreak port control API server in a separate thread."""
    server = HTTPServer(('localhost', port), MockPortControlServer)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    print(f"Mock Goldilock FireBreak Port Control API server started on http://localhost:{port}")
    return server


def load_test_config() -> Dict[str, Any]:
    """Load test configuration from test_config.json."""
    try:
        with open('test_config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("test_config.json not found. Please run from the project directory.")
        sys.exit(1)
    except json.JSONDecodeError:
        print("Invalid JSON in test_config.json")
        sys.exit(1)


def create_port_control_test_cases(config: Dict[str, Any], environment: str = 'local_port_control') -> List[Dict[str, Any]]:
    """Create comprehensive test cases for the Goldilock FireBreak port control Lambda function."""
    env_config = config['environments'][environment]
    
    test_cases: List[Dict[str, Any]] = [
        # Host validation: valid IPv4
        {
            'name': 'Valid API_IP IPv4 (port control)',
            'env_vars': {**env_config, 'API_IP': '192.168.1.10'},
            'event': {
                'port': 5,
                'activate': True
            }
        },

        # Host validation: valid DNS
        {
            'name': 'Valid API_IP DNS name (port control)',
            'env_vars': {**env_config, 'API_IP': 'staging.goldilock-firebreak.com'},
            'event': {
                'port': 5,
                'activate': True
            }
        },

        # Host validation: valid localhost with port (works in mock environments)
        {
            'name': 'Valid API_IP localhost:8080 (port control)',
            'env_vars': {**env_config, 'API_IP': 'localhost:8080'},
            'event': {
                'port': 5,
                'activate': True
            }
        },

        # Host validation negative cases (should fail fast at import)
        {
            'name': 'Invalid API_IP with @ should fail fast (port control)',
            'env_vars': {**env_config, 'API_IP': '1.2.3.4@evil.com'},
            'event': {
                'port': 5,
                'activate': True
            }
        },
        {
            'name': 'Invalid API_IP multiple colons should fail fast (port control)',
            'env_vars': {**env_config, 'API_IP': '1.2.3.4:443:extra'},
            'event': {
                'port': 5,
                'activate': True
            }
        },
        {
            'name': 'Invalid API_IP non-numeric port should fail fast (port control)',
            'env_vars': {**env_config, 'API_IP': '10.0.0.1:notaport'},
            'event': {
                'port': 5,
                'activate': True
            }
        },
        {
            'name': 'Invalid API_IP port 0 should fail fast (port control)',
            'env_vars': {**env_config, 'API_IP': '10.0.0.1:0'},
            'event': {
                'port': 5,
                'activate': True
            }
        },
        # Test Case 1: Successful port activation
        {
            'name': 'Activate FireBreak Port 5',
            'env_vars': env_config,
            'event': {
                'port': 5,
                'activate': True
            }
        },
        
        # Test Case 2: Control All FireBreak Ports (Activate)
        {
            'name': 'Activate All FireBreak Ports',
            'env_vars': env_config,
            'event': {
                'port': "all",
                'activate': True
            }
        },
        
        # Test Case 3: Control All FireBreak Ports (Deactivate)
        {
            'name': 'Deactivate All FireBreak Ports',
            'env_vars': env_config,
            'event': {
                'port': "all",
                'activate': False
            }
        },
        
        # Test Case 4: Successful port deactivation
        {
            'name': 'Deactivate FireBreak Port 3',
            'env_vars': env_config,
            'event': {
                'port': 3,
                'activate': False
            }
        },
        
        # Test Case 5: API Gateway event format
        {
            'name': 'API Gateway Request Format',
            'env_vars': env_config,
            'event': {
                'httpMethod': 'POST',
                'path': '/port-control',
                'headers': {
                    'Content-Type': 'application/json'
                },
                'body': json.dumps({
                    'port': 7,
                    'activate': True
                })
            }
        },
        
        # Test Case 6: API Gateway "all" ports format
        {
            'name': 'API Gateway All Ports Format',
            'env_vars': env_config,
            'event': {
                'httpMethod': 'POST',
                'path': '/port-control',
                'headers': {
                    'Content-Type': 'application/json'
                },
                'body': json.dumps({
                    'port': "all",
                    'activate': True
                })
            }
        },
        
        # Test Case 7: Edge case - Port 0
        {
            'name': 'Control FireBreak Port 0 (Edge Case)',
            'env_vars': env_config,
            'event': {
                'port': 0,
                'activate': True
            }
        },
        
        # Test Case 8: Edge case - Port 11
        {
            'name': 'Control FireBreak Port 11 (Edge Case)',
            'env_vars': env_config,
            'event': {
                'port': 11,
                'activate': False
            }
        },
        
        # Test Case 9: PORT_OFFSET=true Physical Port 1 (API Port 0)
        {
            'name': 'Physical Port 1 with PORT_OFFSET=true',
            'env_vars': {**env_config, 'PORT_OFFSET': 'true'},
            'event': {
                'port': 1,
                'activate': True
            }
        },
        
        # Test Case 10: PORT_OFFSET=true Physical Port 12 (API Port 11)
        {
            'name': 'Physical Port 12 with PORT_OFFSET=true',
            'env_vars': {**env_config, 'PORT_OFFSET': 'true'},
            'event': {
                'port': 12,
                'activate': False
            }
        },
        
        # Test Case 11: Missing API token
        {
            'name': 'Missing Goldilock FireBreak API Token',
            'env_vars': {**env_config, 'API_TOKEN': ''},
            'event': {
                'port': 5,
                'activate': True
            }
        },
        
        # Test Case 12: Missing port parameter
        {
            'name': 'Missing FireBreak Port Parameter',
            'env_vars': env_config,
            'event': {
                'activate': True
            }
        },
        
        # Test Case 13: Missing activate parameter
        {
            'name': 'Missing Activate Parameter',
            'env_vars': env_config,
            'event': {
                'port': 5
            }
        },
        
        # Test Case 14: Invalid port range (negative, PORT_OFFSET=false)
        {
            'name': 'Invalid FireBreak Port Range (Negative, API numbering)',
            'env_vars': {**env_config, 'PORT_OFFSET': 'false'},
            'event': {
                'port': -1,
                'activate': True
            }
        },
        
        # Test Case 15: Invalid port range (too high, PORT_OFFSET=false)
        {
            'name': 'Invalid FireBreak Port Range (>11, API numbering)',
            'env_vars': {**env_config, 'PORT_OFFSET': 'false'},
            'event': {
                'port': 12,
                'activate': True
            }
        },
        
        # Test Case 16: Invalid port range (zero, PORT_OFFSET=true)
        {
            'name': 'Invalid FireBreak Port Range (0, Physical numbering)',
            'env_vars': {**env_config, 'PORT_OFFSET': 'true'},
            'event': {
                'port': 0,
                'activate': True
            }
        },
        
        # Test Case 17: Invalid port range (>12, PORT_OFFSET=true)
        {
            'name': 'Invalid FireBreak Port Range (>12, Physical numbering)',
            'env_vars': {**env_config, 'PORT_OFFSET': 'true'},
            'event': {
                'port': 13,
                'activate': True
            }
        },
        
        # Test Case 18: Invalid port type (not int or "all")
        {
            'name': 'Invalid FireBreak Port Type',
            'env_vars': env_config,
            'event': {
                'port': "invalid",
                'activate': True
            }
        }
    ]
    
    # Add mock server specific test cases
    if 'mock' in environment:
        # For localhost:8080 to be reachable, ensure API_IP is correctly set in env_vars
        mock_cases: List[Dict[str, Any]] = [
            {
                'name': 'Server Error (500)',
                'env_vars': {**env_config, 'API_TOKEN': 'error-token'},
                'event': {
                    'port': 5,
                    'activate': True
                }
            },
            {
                'name': 'Unauthorized (403)',
                'env_vars': {**env_config, 'API_TOKEN': 'invalid-token'},
                'event': {
                    'port': 5,
                    'activate': True
                }
            },
            {
                'name': 'Invalid JSON Response',
                'env_vars': {**env_config, 'API_TOKEN': 'invalid-json-token'},
                'event': {
                    'port': 5,
                    'activate': True
                }
            }
        ]
        test_cases.extend(mock_cases)
    
    return test_cases


def analyze_test_results(results: List[Dict[str, Union[bool, str, float, Any]]]) -> bool:
    """Analyze and summarize test results."""
    total_tests = len(results)
    successful_tests = sum(1 for r in results if r.get('success', False))
    failed_tests = total_tests - successful_tests
    
    print("\n" + "=" * 80)
    print("GOLDILOCK FIREBREAK PORT CONTROL TEST SUMMARY")
    print("=" * 80)
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {successful_tests}")
    print(f"Failed: {failed_tests}")
    print(f"Success Rate: {successful_tests/total_tests*100:.1f}%")
    
    # Detailed results
    print("\nDETAILED RESULTS:")
    print("-" * 80)
    
    for result in results:
        status_icon = "[PASS]" if result['success'] else "[FAIL]"
        test_name = result.get('test_name', 'Unknown Test')
        execution_time = result.get('execution_time_seconds', 0)
        
        print(f"{status_icon} {test_name} ({execution_time:.3f}s)")
        
        success = result.get('success', False)
        if isinstance(success, bool) and success:
            # Check HTTP status code if available
            lambda_result = result.get('result')
            if isinstance(lambda_result, dict):
                lambda_response = cast(Dict[str, Any], lambda_result)
                status_code = lambda_response.get('statusCode', 0)
                print(f"    HTTP Status: {status_code}")
                
                # Show port control result if successful
                if status_code == 200:
                    try:
                        body_str = lambda_response.get('body', '{}')
                        if isinstance(body_str, str):
                            response_data = json.loads(body_str)
                            
                            if isinstance(response_data, dict):
                                response_body = cast(Dict[str, Any], response_data)
                                execution_time = response_body.get('executionTimeMs', 0)
                                print(f"    Lambda Execution Time: {execution_time}ms")
                                
                                if 'ports' in response_body:
                                    # All ports control response
                                    ports_list = response_body.get('ports', [])
                                    if isinstance(ports_list, list):
                                        ports_typed = cast(List[Dict[str, Any]], ports_list)
                                        active_count = sum(1 for p in ports_typed if p.get('active') == 1)
                                        total_ports = len(ports_typed)
                                        print(f"    Result: All {total_ports} FireBreak ports controlled ({active_count} active)")
                                else:
                                    # Individual port control response
                                    active = response_body.get('active')
                                    port = response_body.get('port')
                                    if active is not None and port is not None:
                                        status = "ACTIVATED" if active else "DEACTIVATED"
                                        print(f"    Result: FireBreak Port {port} {status}")
                    except (json.JSONDecodeError, KeyError):
                        print("    Result: Unable to parse response body")
        else:
            error_type = result.get('error_type', 'Unknown')
            error_msg = result.get('error', 'No error message')
            print(f"    Error: {error_type}: {error_msg}")
        print()
    
    return successful_tests == total_tests


def run_port_control_integration_test(environment: str = 'local_port_control') -> bool:
    """Run integration tests for the portControl Lambda function."""
    print("Goldilock FireBreak AWS Lambda Port Control Integration Test Suite")
    print("=" * 60)
    print(f"Environment: {environment}")
    print("Target Function: port_control.py")
    print()
    
    # Load configuration
    config = load_test_config()
    
    if environment not in config['environments']:
        print(f"Environment '{environment}' not found in config")
        available_envs = list(config['environments'].keys())
        print(f"Available environments: {', '.join(available_envs)}")
        return False
    
    # Start mock server if using mock environment
    mock_server = None
    if 'mock' in environment:
        mock_server = start_mock_control_server(8080)
        time.sleep(1)  # Give server time to start
    
    try:
        # Create test runner
        runner = LambdaTestRunner('../lambda_functions/port_control.py')
        
        # Create test cases
        test_cases = create_port_control_test_cases(config, environment)
        
        # Run tests
        results = runner.run_multiple_tests(test_cases)
        
        # Analyze results
        all_passed = analyze_test_results(results)
        
        return all_passed
        
    except Exception as e:
        print(f"Test execution failed: {e}")
        return False
        
    finally:
        if mock_server:
            mock_server.shutdown()
            print("Mock Goldilock FireBreak Port Control server stopped")


def main():
    """Main test execution function."""
    environment = 'local_port_control'
    
    if len(sys.argv) > 1:
        environment = sys.argv[1]
    
    # Run the integration test
    success = run_port_control_integration_test(environment)
    
    if success:
        print("\nAll Goldilock FireBreak port control tests passed! Your Lambda function is ready for deployment.")
        sys.exit(0)
    else:
        print("\nSome tests failed. Please review the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()