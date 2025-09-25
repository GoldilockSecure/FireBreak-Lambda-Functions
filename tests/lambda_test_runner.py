#!/usr/bin/env python3
"""Local AWS Lambda test runner for Goldilock FireBreak functions.

This script allows you to test your Goldilock FireBreak Lambda functions locally
without deploying to AWS. It provides a mock Lambda context and handles
environment variable configuration.
"""

import os
import sys
import json
import time
import uuid
from typing import Any, Dict, Optional, List, Union, Callable
from datetime import datetime


class MockLambdaContext:
    """Mock AWS Lambda context object for Goldilock FireBreak function testing.
    
    Mimics the real context object passed to Lambda functions, with attributes
    matching the official AWS Lambda context object specification:
    https://docs.aws.amazon.com/lambda/latest/dg/python-context.html
    """
    
    def __init__(self, function_name: str = "test-function", timeout_seconds: int = 30):
        self.function_name = function_name
        self.function_version = "$LATEST"
        self.invoked_function_arn = f"arn:aws:lambda:us-east-1:123456789012:function:{function_name}"
        self.memory_limit_in_mb = "128"
        self.remaining_time_in_millis = lambda: max(0, int((self._deadline - time.time()) * 1000))
        self.log_group_name = f"/aws/lambda/{function_name}"
        self.log_stream_name = f"{datetime.now().strftime('%Y/%m/%d')}/[$LATEST]{uuid.uuid4().hex}"
        self.aws_request_id = str(uuid.uuid4())
        self.client_context = None
        self.identity = None
        
        # Set deadline for timeout simulation
        self._deadline = time.time() + timeout_seconds
        
    def get_remaining_time_in_millis(self) -> int:
        """Get remaining execution time in milliseconds."""
        return max(0, int((self._deadline - time.time()) * 1000))


class LambdaTestRunner:
    """Test runner for Goldilock FireBreak AWS Lambda functions.
    
    Provides environment management, logging, and execution context for testing
    Goldilock FireBreak Lambda functions locally without AWS deployment.
    """
    
    def __init__(self, function_module_path: str) -> None:
        """Initialize the test runner for Goldilock FireBreak Lambda functions.
        
        Args:
            function_module_path: Path to the Python file containing the
                lambda_handler function for Goldilock FireBreak operations.
        """
        self.function_module_path = function_module_path
        self.original_env: Dict[str, Optional[str]] = {}
        
    def set_environment_variables(self, env_vars: Dict[str, str]) -> None:
        """Set environment variables for Goldilock FireBreak API testing.
        
        Backs up original values for restoration after testing.
        
        Args:
            env_vars: Dictionary of environment variable key-value pairs,
                typically including Goldilock FireBreak API credentials.
        """
        # Backup original environment variables
        for key in env_vars:
            if key in os.environ:
                self.original_env[key] = os.environ[key]
            else:
                self.original_env[key] = None
                
        # Set new environment variables
        for key, value in env_vars.items():
            os.environ[key] = value
            
    def restore_environment_variables(self) -> None:
        """Restore original environment variables."""
        for key, original_value in self.original_env.items():
            if original_value is None:
                if key in os.environ:
                    del os.environ[key]
            else:
                os.environ[key] = original_value
        self.original_env = {}
        
    def import_lambda_function(self) -> Callable[[Dict[str, Any], Any], Dict[str, Any]]:
        """Dynamically import the Goldilock FireBreak lambda_handler function.
        
        Returns:
            The lambda_handler function for Goldilock FireBreak operations.
        """
        # Handle different path formats
        if self.function_module_path.startswith('../'):
            # Path relative to current directory (e.g., '../lambda_functions/port_status.py')
            import importlib.util
            import os
            
            # Get absolute path
            abs_path = os.path.abspath(self.function_module_path)
            module_name = os.path.splitext(os.path.basename(abs_path))[0]
            
            # Load module from file path
            spec = importlib.util.spec_from_file_location(module_name, abs_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"Could not load module spec from {abs_path}")
                
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
        else:
            # Original behavior - module name without path
            module_name = self.function_module_path.replace('.py', '')
            
            # Add current directory to Python path if not already there
            if '.' not in sys.path:
                sys.path.insert(0, '.')
                
            try:
                # Import the module
                module = __import__(module_name)
            except ImportError as e:
                raise ImportError(f"Failed to import {module_name}: {e}")
            
        # Get the lambda_handler function
        if hasattr(module, 'lambda_handler'):
            return module.lambda_handler
        else:
            raise AttributeError(f"No lambda_handler function found in {self.function_module_path}")
            
    def run_test(self,
                 event: Dict[str, Any],
                 env_vars: Optional[Dict[str, str]] = None,
                 function_name: str = "test-function",
                 timeout_seconds: int = 30,
                 expect_import_error: bool = False) -> Dict[str, Union[bool, str, float, Any]]:
        """Run a Goldilock FireBreak Lambda function test.
        
        Executes the Lambda function with provided event and environment,
        typically for testing Goldilock FireBreak API interactions.
        
        Args:
            event: Lambda event object (dict) containing request data.
            env_vars: Environment variables including Goldilock FireBreak
                API credentials.
            function_name: Name of the function for context logging.
            timeout_seconds: Timeout in seconds for function execution.
            expect_import_error: When True, treat import-time exceptions
                (e.g., invalid/missing API_IP hard-fail) as a successful test.
            
        Returns:
            Dictionary containing test results, execution time, and metadata.
        """
        # Set up environment variables if provided
        if env_vars:
            self.set_environment_variables(env_vars)
            
        # Record start time
        start_time = time.time()
        
        try:
            # Import the lambda function (may hard-fail on invalid config)
            lambda_handler = self.import_lambda_function()
            
            # Create mock context
            context = MockLambdaContext(function_name, timeout_seconds)
            
            print(f"Running Lambda function: {function_name}")
            print(f"Event: {json.dumps(event, indent=2)}")
            print(f"Timeout: {timeout_seconds}s")
            print("-" * 50)
            
            # Execute the lambda function
            result = lambda_handler(event, context)
            
            # Calculate execution time
            execution_time = time.time() - start_time
            
            # Prepare test results
            test_result: Dict[str, Union[bool, str, float, Any]] = {
                "success": True,
                "result": result,
                "execution_time_seconds": round(execution_time, 3),
                "function_name": function_name,
                "remaining_time_ms": context.get_remaining_time_in_millis(),
                "aws_request_id": context.aws_request_id
            }
            
            print(f"Function completed successfully in {execution_time:.3f}s")
            print(f"Result: {json.dumps(result, indent=2)}")
            
            return test_result
            
        except Exception as e:
            execution_time = time.time() - start_time
            # If import/config failure was expected, treat as success while recording details
            if expect_import_error and isinstance(e, (ValueError, ImportError)):
                success_result: Dict[str, Union[bool, str, float, Any]] = {
                    "success": True,
                    "result": {  # using Any in the typing for flexibility
                        "statusCode": 0,
                        "body": json.dumps({"expected_import_failure": str(e)})
                    },
                    "execution_time_seconds": round(execution_time, 3),
                    "function_name": function_name
                }
                print(f"Expected import/config failure occurred: {type(e).__name__}: {str(e)}")
                return success_result

            error_result: Dict[str, Union[bool, str, float]] = {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "execution_time_seconds": round(execution_time, 3),
                "function_name": function_name
            }
            
            print(f"Function failed after {execution_time:.3f}s")
            print(f"Error: {type(e).__name__}: {str(e)}")
            
            return error_result
            
        finally:
            # Restore original environment variables
            if env_vars:
                self.restore_environment_variables()
                
    def run_multiple_tests(self, test_cases: List[Dict[str, Any]]) -> List[Dict[str, Union[bool, str, float, Any]]]:
        """Run multiple Goldilock FireBreak test cases sequentially.
        
        Args:
            test_cases: List of dictionaries, each containing test parameters.
                       Expected keys: event, env_vars (optional), name (optional)
                       
        Returns:
            List of test results for each Goldilock FireBreak test case.
        """
        results: List[Dict[str, Union[bool, str, float, Any]]] = []
        
        for i, test_case in enumerate(test_cases):
            test_name = test_case.get('name', f"Test Case {i+1}")
            print(f"\nRunning {test_name}")
            print("=" * 60)
            
            result = self.run_test(
                event=test_case['event'],
                env_vars=test_case.get('env_vars'),
                function_name=test_case.get('function_name', f"test-{i+1}"),
                timeout_seconds=test_case.get('timeout_seconds', 30),
                expect_import_error=test_case.get('expect_import_error', False)
            )
            
            result['test_name'] = test_name
            results.append(result)
            
        return results


def main() -> None:
    """Example usage of the Goldilock FireBreak Lambda test runner."""
    if len(sys.argv) < 2:
        print("Usage: python lambda_test_runner.py <lambda_module.py>")
        sys.exit(1)
        
    module_path = sys.argv[1]
    
    # Create test runner
    runner = LambdaTestRunner(module_path)
    
    # Example test event
    test_event: Dict[str, Any] = {
        "httpMethod": "GET",
        "path": "/port-status",
        "headers": {},
        "queryStringParameters": None,
        "body": None
    }
    
    # Example environment variables
    test_env: Dict[str, str] = {
        "API_IP": "10.0.69.15",
        "API_TOKEN": "your-test-token-here",
        "DISABLE_SSL_VERIFY": "true"
    }
    
    # Run the test
    result = runner.run_test(test_event, test_env)
    
    print("\n" + "=" * 60)
    print("FINAL RESULT:")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()