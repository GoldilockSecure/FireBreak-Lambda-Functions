# Goldilock FireBreak AWS Lambda Functions

This repository contains AWS Lambda functions for interfacing with the Goldilock FireBreak API. These functions provide port status monitoring and control capabilities.

## Lambda Functions

### [`port_status.py`](lambda_functions/port_status.py) - Port Status Retrieval

**Purpose:** Retrieves the current activation status of all FireBreak ports.

**HTTP Method:** GET  
**Goldilock API Endpoint:** `https://{API_IP}/api/websocket/get-all-status`

**Event Payload:** No parameters required
```json
{}
```

**Response Format (body unescaped for readability):**
```json
{
  "statusCode": 200,
  "body": {
    "ports": [
      {"active": 0, "port": 0},
      {"active": 1, "port": 1},
      {"active": 0, "port": 2}
    ],
    "executionTimeMs": 245.67
  }
}
```

### [`port_control.py`](lambda_functions/port_control.py) - Port Control

**Purpose:** Activates or deactivates individual FireBreak ports.

**HTTP Method:** POST  
**Goldilock API Endpoint:** `https://{API_IP}/api/websocket/port-control`

**Event Payload:**

*Individual Port Control:*
```json
{
  "port": 5,
  "activate": true
}
```

*All Ports Control:*
```json
{
  "port": "all",
  "activate": true
}
```

**Parameters:**
- `port` (integer or string, required):
  - Port number for individual port control (range depends on PORT_OFFSET setting):
    - PORT_OFFSET=false: 0-11 (API numbering)
    - PORT_OFFSET=true: 1-12 (physical numbering)
  - `"all"` to control all ports simultaneously
- `activate` (boolean, required): `true` to activate, `false` to deactivate

**Response Format:**

*Individual Port Response (body unescaped):*
```json
{
  "statusCode": 200,
  "body": {
    "active": true,
    "port": 5,
    "executionTimeMs": 198.45
  }
}
```

*All Ports Response (body unescaped):*
```json
{
  "statusCode": 200,
  "body": {
    "ports": [
      {"active": 1, "port": 0},
      {"active": 1, "port": 1},
      {"active": 1, "port": 2}
    ],
    "executionTimeMs": 312.89
  }
}
```

## Environment Variables

Both Lambda functions require these environment variables:

| Variable | Description | Required | Example |
|----------|-------------|----------|---------|
| `API_IP` | Goldilock FireBreak device IP address | Yes | `192.168.1.100` |
| `API_TOKEN` | Bearer token for API authentication | Yes | `your-goldilock-firebreak-token` |
| `PORT_OFFSET` | Port numbering offset (see Port Numbering section) | No | `false` |
| `DISABLE_SSL_VERIFY` | Skip SSL verification (use `true` for development) | No | `true` |

## Port Numbering - IMPORTANT

**Physical vs API Port Numbering:**
- The **FireBreak device** physically numbers its ports starting from **1** (ports 1-12)
- The **FireBreak API** numbers its ports starting from **0** (ports 0-11)

The `PORT_OFFSET` environment variable controls how port numbers are handled:

### PORT_OFFSET=false (Default)
- Lambda functions expect **API numbering** (0-11)
- No conversion is performed
- Use this if you handle the numbering conversion in your application

**Example:**
- To control physical port 1, send `{"port": 0}`
- To control physical port 12, send `{"port": 11}`

### PORT_OFFSET=true
- Lambda functions expect **physical numbering** (1-12)
- Automatic conversion to API numbering (subtract 1)
- Response port numbers are converted back to physical numbering (add 1)
- Use this for user-friendly physical port numbering

**Example:**
- To control physical port 1, send `{"port": 1}`
- To control physical port 12, send `{"port": 12}`

**Note:** The "all" ports functionality is not affected by PORT_OFFSET setting.

## AWS Lambda Deployment

### 1. Environment Variables Setup

In AWS Lambda Console or via Infrastructure as Code:

**Standard Setup (API Numbering):**
```bash
API_IP=192.168.1.100
API_TOKEN=your-goldilock-firebreak-token
PORT_OFFSET=false
DISABLE_SSL_VERIFY=true
```

**User-Friendly Setup (Physical Numbering):**
```bash
API_IP=192.168.1.100
API_TOKEN=your-goldilock-firebreak-token
PORT_OFFSET=true
DISABLE_SSL_VERIFY=true
```

### 2. IAM Permissions

No special AWS permissions required - functions only make external HTTP requests.

## Invocation Examples

### AWS CLI

**Port Status:**
```bash
aws lambda invoke \
  --function-name goldilock-port-status \
  --payload '{}' \
  response.json
```

**Port Control (API Numbering - PORT_OFFSET=false):**
```bash
aws lambda invoke \
  --function-name goldilock-port-control \
  --payload '{"port": 2, "activate": false}' \
  response.json
```

**Port Control (Physical Numbering - PORT_OFFSET=true):**
```bash
aws lambda invoke \
  --function-name goldilock-port-control \
  --payload '{"port": 3, "activate": false}' \
  response.json
  
  # View the response
  cat response.json
  ```

  Console Output:
  ```json
  {
    "StatusCode": 200,
    "ExecutedVersion": "$LATEST"
  }
  ```

  response.json Content (body unescaped for readability):
  ```json
  {
    "statusCode": 200,
    "body": {
      "ports": [
        {"active": 0, "port": 0},
        {"active": 1, "port": 1},
        {"active": 0, "port": 2}
      ],
      "executionTimeMs": 245.67
    }
  }
  ```
  
  **Port Control - Individual Port (PORT_OFFSET=false):**
  ```bash
  aws lambda invoke \
    --function-name goldilock-port-control \
    --payload '{"port": 2, "activate": false}' \
    response.json

  # View the response
  cat response.json
  ```

  Console Output:
  ```json
  {
    "StatusCode": 200,
    "ExecutedVersion": "$LATEST"
  }
  ```
  
  response.json Content (body unescaped):
  ```json
  {
    "statusCode": 200,
    "body": {
      "active": false,
      "port": 2,
      "executionTimeMs": 198.45
    }
  }
  ```

  **Port Control - Individual Port (PORT_OFFSET=true):**
  ```bash
  aws lambda invoke \
    --function-name goldilock-port-control \
    --payload '{"port": 3, "activate": false}' \
    response.json

  # View the response
  cat response.json
  ```

  response.json Content (body unescaped):
  ```json
  {
    "statusCode": 200,
    "body": {
      "active": false,
      "port": 3,
      "executionTimeMs": 198.45
    }
  }
  ```
  
  **Port Control - All Ports:**
  ```bash
  aws lambda invoke \
    --function-name goldilock-port-control \
    --payload '{"port": "all", "activate": true}' \
    response.json
  
  # View the response
  cat response.json
  ```
  
  **Console Output:**
  ```json
  {
      "StatusCode": 200,
      "ExecutedVersion": "$LATEST"
  }
  ```
  
  response.json Content (body unescaped):
  ```json
  {
    "statusCode": 200,
    "body": {
      "ports": [
        {"active": 1, "port": 0},
        {"active": 1, "port": 1},
        {"active": 1, "port": 2},
        {"active": 1, "port": 3},
        {"active": 1, "port": 4},
        {"active": 1, "port": 5},
        {"active": 1, "port": 6},
        {"active": 1, "port": 7},
        {"active": 1, "port": 8},
        {"active": 1, "port": 9},
        {"active": 1, "port": 10},
        {"active": 1, "port": 11}
      ],
      "executionTimeMs": 312.89
    }
  }
  ```
  
  ### Error Response Example
  
  Console Output:
  ```json
  {
    "StatusCode": 200,
    "ExecutedVersion": "$LATEST"
  }
  ```
  
  response.json Content (body unescaped):
  ```json
  {
    "statusCode": 400,
    "body": {
      "error": "FireBreak port must be an integer (0-11) or 'all', got: 15",
      "executionTimeMs": 12.34
    }
  }
  ```
  
## Lambda Response Structure

AWS Lambda wraps your function’s invocation result metadata. The actual Lambda invocation metadata includes:

- **StatusCode**: AWS Lambda execution status (200 = successful invocation, even if your function returns an error)
- **ExecutedVersion**: Which version of the function was executed
- **LogResult**: Base64-encoded logs (if `--log-type Tail` is used)

The **response.json file** contains your Lambda function's actual response with:
- **statusCode**: HTTP status code from your function (200, 400, 500, etc.)
- **body**: JSON string containing the actual data or error message
- **executionTimeMs**: Time in ms how long it took to execute the function and receive response from FireBreak.

## Error Responses

### Common Error Codes

| Status Code | Description | Cause |
|-------------|-------------|-------|
| 400 | Bad Request | Invalid port number/value or missing parameters |
| 500 | Internal Server Error | Missing API_TOKEN or invalid JSON response |
| 502 | Bad Gateway | Cannot reach Goldilock FireBreak API |

### Error Response Format

All error responses include execution time for complete performance tracking:

```json
{
  "statusCode": 400,
  "body": "{\"error\": \"FireBreak port must be an integer (0-11) or 'all', got: 15\", \"executionTimeMs\": 12.34}"
}
```

## Goldilock FireBreak API Integration

### Port Status Response

The Lambda function wraps the Goldilock FireBreak API response with execution timing:
```json
{
  "ports": [
    {"active": 0, "port": 0},
    {"active": 1, "port": 1},
    {"active": 0, "port": 2},
    ...
  ],
  "executionTimeMs": 245.67
}
```

- `ports`: Array of port objects from Goldilock FireBreak API
- `active`: 0 (inactive) or 1 (active)
- `port`: Port number (range depends on PORT_OFFSET setting):
  - PORT_OFFSET=false: 0-11 (API numbering)
  - PORT_OFFSET=true: 1-12 (physical numbering)
- `executionTimeMs`: Function execution time in milliseconds

### Port Control Response

**Individual Port Control:**
The Lambda function wraps the Goldilock FireBreak API response with execution timing:
```json
{
  "active": true,
  "port": 5,
  "executionTimeMs": 198.45
}
```

**All Ports Control:**
The Lambda function wraps the Goldilock FireBreak API response with execution timing:
```json
{
  "ports": [
    {"active": 1, "port": 0},
    {"active": 1, "port": 1},
    {"active": 1, "port": 2},
    {"active": 1, "port": 3},
    {"active": 1, "port": 4},
    {"active": 1, "port": 5},
    {"active": 1, "port": 6},
    {"active": 1, "port": 7},
    {"active": 1, "port": 8},
    {"active": 1, "port": 9},
    {"active": 1, "port": 10},
    {"active": 1, "port": 11}
  ],
  "executionTimeMs": 312.89
}
```

**Execution Time Information:**
- All Lambda responses include `executionTimeMs` for performance monitoring
- Time is measured from function start to response completion
- Includes API call time, JSON processing, and Lambda overhead
- Useful for benchmarking and performance optimization

## Step Functions Integration

Example Step Function state for automated port control:

```json
{
  "Comment": "Control multiple FireBreak ports",
  "StartAt": "DeactivatePort1",
  "States": {
    "DeactivateAllPorts": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:region:account:function:goldilock-port-control",
      "Parameters": {
        "port": "all",
        "activate": false
      },
      "Next": "ActivatePort5"
    },
    "ActivatePort5": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:region:account:function:goldilock-port-control",
      "Parameters": {
        "port": 5,
        "activate": true
      },
      "End": true
    }
  }
}
```

## Testing
NOTE: The following tests are just for internal use. They are not required for running the scripts found in lambda_functions folder.

### Prerequisites
- Python 3.9 or higher
- No additional packages required (uses standard library only)

### Quick Testing

**Navigate to tests directory:**
```bash
cd tests
```

**Test Port Status Function:**
```bash
python demo_test.py
```

**Test Port Control Function:**
```bash
python demo_port_control.py
```

### Configuration

**Option 1: Use Default Test Configuration**
The tests include built-in configuration with sample values. No setup required for basic testing.

**Option 2: Use Real FireBreak API**
1. Copy the configuration template:
   ```bash
   cp test_config.json.example test_config.json
   ```
2. Edit `test_config.json` with your real FireBreak API details:
   ```json
   {
     "environments": {
       "local": {
         "API_IP": "your-firebreak-ip-address",
         "API_TOKEN": "your-firebreak-api-token",
         "PORT_OFFSET": "false",
         "DISABLE_SSL_VERIFY": "true"
       }
     }
   }
   ```

### Comprehensive Testing

**Test Port Status with different configurations:**
```bash
cd tests
python test_port_status.py mock              # Mock API server
python test_port_status.py mock_physical     # Mock API with PORT_OFFSET=true
python test_port_status.py local             # Real FireBreak API (if configured)
```

**Test Port Control with different configurations:**
```bash
cd tests
python test_port_control.py mock_port_control          # Mock API server
python test_port_control.py mock_port_control_physical # Mock API with PORT_OFFSET=true
python test_port_control.py local_port_control         # Real FireBreak API (if configured)
```

### Test Options

| Environment | Description |
|-------------|-------------|
| `mock` | Uses built-in mock server (no external API required) |
| `mock_physical` | Mock server with PORT_OFFSET=true (physical numbering 1-12) |
| `local` | Uses real FireBreak API with API numbering (0-11) |
| `local_physical` | Uses real FireBreak API with physical numbering (1-12) |

### Expected Output

**Successful Test Run:**
```
Goldilock FireBreak Port Control Lambda Function Demo
==================================================

Test 1/4: Activate FireBreak Port 5 (API Numbering)
----------------------------------------
Environment Override: {'PORT_OFFSET': 'false'}
Lambda function executed successfully!
HTTP Status: 200
Execution Time: 0.198s
Lambda Execution Time: 245.67ms
Response Type: object (Individual port control)
Result: FireBreak Port 5 ACTIVATED

All tests completed successfully!
```

### Troubleshooting

**ImportError:**
- Ensure you're running from the `tests/` directory
- Python 3.9+ is required

**Network Errors:**
- For mock tests: No network required, should always work
- For local tests: Check FireBreak device is reachable and API_TOKEN is valid

**SSL Errors:**
- Set `DISABLE_SSL_VERIFY=true` in test configuration for development testing

## Dependencies

- **Python Standard Library Only** - No external dependencies
- Compatible with AWS Lambda runtime
- No additional packages required in deployment package