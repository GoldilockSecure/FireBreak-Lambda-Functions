#!/usr/bin/env python3
"""
Comprehensive test suite for the Goldilock FireBreak portStatus Lambda function.

This script demonstrates various testing scenarios including:
- Successful Goldilock FireBreak API responses
- Error handling (missing token, network errors, invalid JSON)
- Different event types (API Gateway, scheduled events)
- Environment configuration testing

Usage:
    python test_port_status.py [environment_name]
    
Examples:
    python test_port_status.py local
    python test_port_status.py staging
    python test_port_status.py mock
"""

import sys
import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, List, Union, cast
from lambda_test_runner import LambdaTestRunner


class MockAPIServer(BaseHTTPRequestHandler):
    """Mock Goldilock FireBreak API server for testing without external dependencies."""
    
    def do_GET(self):
        """Handle GET requests to simulate the Goldilock FireBreak port status API."""
        # Check authorization header
        auth_header = self.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            self.send_error(401, 'Unauthorized')
            return
            
        token = auth_header.replace('Bearer ', '')
        
        # Simulate different responses based on token
        if token == 'mock-token':
            # Normal successful response matching Goldilock FireBreak API format
            response_data = [
                {"active": 0, "port": 0},
                {"active": 1, "port": 1},
                {"active": 0, "port": 2},
                {"active": 1, "port": 3},
                {"active": 0, "port": 4},
                {"active": 1, "port": 5},
                {"active": 0, "port": 6},
                {"active": 0, "port": 7},
                {"active": 1, "port": 8},
                {"active": 0, "port": 9},
                {"active": 1, "port": 10},
                {"active": 0, "port": 11}
            ]
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
            self.wfile.write(b'{"delayed": true}')
            
        else:
            self.send_error(403, 'Forbidden')
            
    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default logging to keep test output clean."""
        pass


def start_mock_server(port: int = 8080) -> HTTPServer:
    """Start a mock Goldilock FireBreak API server in a separate thread."""
    server = HTTPServer(('localhost', port), MockAPIServer)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    print(f"Mock Goldilock FireBreak API server started on http://localhost:{port}")
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


def create_test_cases(config: Dict[str, Any], environment: str = 'local') -> List[Dict[str, Any]]:
    """Create comprehensive test cases for the Goldilock FireBreak Lambda function."""
    env_config = config['environments'][environment]
    scenarios = config['test_scenarios']
    
    test_cases: List[Dict[str, Any]] = [
        # Test Case 1: Successful execution
        {
            'name': 'Successful Goldilock FireBreak API Request',
            'env_vars': env_config,
            'event': scenarios['basic_request']['event'],
            'expected_status': 200
        },
        
        # Test Case 2: Missing API token
        {
            'name': 'Missing Goldilock FireBreak API Token',
            'env_vars': {**env_config, 'API_TOKEN': ''},
            'event': scenarios['basic_request']['event'],
            'expected_status': 500
        },
        
        # Test Case 3: API Gateway request format
        {
            'name': 'API Gateway Request Format',
            'env_vars': env_config,
            'event': scenarios['api_gateway_request']['event'],
            'expected_status': 200
        },
        
        # Test Case 4: Scheduled CloudWatch event
        {
            'name': 'CloudWatch Scheduled Event',
            'env_vars': env_config,
            'event': scenarios['scheduled_event']['event'],
            'expected_status': 200
        },

        # Test Case 5: Host validation - valid IPv4
        {
            'name': 'Valid API_IP IPv4',
            'env_vars': {**env_config, 'API_IP': '192.168.1.10'},
            'event': scenarios['basic_request']['event'],
            'expected_status': 200
        },

        # Test Case 6: Host validation - valid localhost with port
        {
            'name': 'Valid API_IP localhost:8080',
            'env_vars': {**env_config, 'API_IP': 'localhost:8080'},
            'event': scenarios['basic_request']['event'],
            'expected_status': 200 if environment == 'mock' else 500
        },

        # Test Case 7: Host validation - valid DNS name
        {
            'name': 'Valid API_IP DNS name',
            'env_vars': {**env_config, 'API_IP': 'staging.goldilock-firebreak.com'},
            'event': scenarios['basic_request']['event'],
            'expected_status': 200 if environment in ('staging','production') else 500
        },

        # Test Case 8: Host validation - reject dangerous characters (@)
        {
            'name': 'Invalid API_IP with @ should fail fast',
            'env_vars': {**env_config, 'API_IP': '1.2.3.4@evil.com'},
            'event': scenarios['basic_request']['event'],
            'expect_import_error': True
        },

        # Test Case 9: Host validation - multiple colons
        {
            'name': 'Invalid API_IP multiple colons should fail fast',
            'env_vars': {**env_config, 'API_IP': '1.2.3.4:443:extra'},
            'event': scenarios['basic_request']['event'],
            'expect_import_error': True
        },

        # Test Case 10: Host validation - invalid port (0)
        {
            'name': 'Invalid API_IP port 0 should fail fast',
            'env_vars': {**env_config, 'API_IP': '10.0.0.1:0'},
            'event': scenarios['basic_request']['event'],
            'expect_import_error': True
        },

        # Test Case 11: Host validation - invalid port (non-numeric)
        {
            'name': 'Invalid API_IP non-numeric port should fail fast',
            'env_vars': {**env_config, 'API_IP': '10.0.0.1:notaport'},
            'event': scenarios['basic_request']['event'],
            'expect_import_error': True
        }
    ]
    
    # Add mock server specific test cases
    if environment == 'mock':
        mock_cases: List[Dict[str, Any]] = [
            {
                'name': 'Server Error (500)',
                'env_vars': {**env_config, 'API_TOKEN': 'error-token'},
                'event': scenarios['basic_request']['event'],
                'expected_status': 500
            },
            {
                'name': 'Unauthorized (403)',
                'env_vars': {**env_config, 'API_TOKEN': 'invalid-token'},
                'event': scenarios['basic_request']['event'],
                'expected_status': 403
            },
            {
                'name': 'Invalid JSON Response',
                'env_vars': {**env_config, 'API_TOKEN': 'invalid-json-token'},
                'event': scenarios['basic_request']['event'],
                'expected_status': 500
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
    print("TEST SUMMARY")
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
                
                # Show port status result details if successful
                if status_code == 200:
                    try:
                        body_str = lambda_response.get('body', '{}')
                        if isinstance(body_str, str):
                            response_data = json.loads(body_str)
                            if isinstance(response_data, dict) and 'ports' in response_data:
                                # New format with wrapped ports and execution time
                                response_body = cast(Dict[str, Any], response_data)
                                ports_list = response_body.get('ports', [])
                                execution_time = response_body.get('executionTimeMs', 0)
                                if isinstance(ports_list, list):
                                    ports_typed = cast(List[Dict[str, Any]], ports_list)
                                    active_count = sum(1 for p in ports_typed if p.get('active') == 1)
                                    print(f"    Result: {len(ports_typed)} FireBreak ports ({active_count} active)")
                                    print(f"    Lambda Execution Time: {execution_time}ms")
                            elif isinstance(response_data, list):
                                # Legacy format for backwards compatibility testing
                                legacy_ports = cast(List[Dict[str, Any]], response_data)
                                active_count = sum(1 for p in legacy_ports if p.get('active') == 1)
                                print(f"    Result: {len(legacy_ports)} FireBreak ports ({active_count} active) - Legacy Format")
                    except (json.JSONDecodeError, KeyError):
                        print("    Result: Unable to parse response body")
        else:
            error_type = result.get('error_type', 'Unknown')
            error_msg = result.get('error', 'No error message')
            print(f"    Error: {error_type}: {error_msg}")
        print()
    
    return successful_tests == total_tests


def run_integration_test(environment: str = 'local') -> bool:
    """Run integration tests for the portStatus Lambda function."""
    print("Goldilock FireBreak AWS Lambda Integration Test Suite")
    print("=" * 50)
    print(f"Environment: {environment}")
    print("Target Function: port_status.py")
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
    if environment == 'mock':
        mock_server = start_mock_server(8080)
        time.sleep(1)  # Give server time to start
    
    try:
        # Create test runner
        runner = LambdaTestRunner('../lambda_functions/port_status.py')
        
        # Create test cases
        test_cases = create_test_cases(config, environment)
        
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
            print("Mock Goldilock FireBreak API server stopped")


def main():
    """Main test execution function."""
    environment = 'local'
    
    if len(sys.argv) > 1:
        environment = sys.argv[1]
    
    # Run the integration test
    success = run_integration_test(environment)
    
    if success:
        print("\nAll tests passed! Your Goldilock FireBreak Lambda function is ready for deployment.")
        sys.exit(0)
    else:
        print("\nSome tests failed. Please review the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()