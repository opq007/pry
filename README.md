---
title: FastAPI Proxy Service
emoji: 🚀
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
license: mit
---

# FastAPI Proxy Service

RESTful API for retrieving validated proxy servers and proxy forwarding service.

## Features

- 🔄 Automatic proxy pool refresh
- 🔒 Bearer token authentication
- ⚡ Fast multi-threaded validation
- 🌐 HTTP & SOCKS5 proxy support
- 🔀 Proxy forwarding with round-robin selection
- 🛡️ Fallback to direct request when pool is empty

## API Endpoints

| Endpoint | Methods | Auth | Description |
|----------|---------|------|-------------|
| `GET /health` | GET | No | Health check |
| `GET /api/proxies` | GET | Yes | Get proxy list |
| `GET /api/proxy/status` | GET | Yes | Get proxy pool status |
| `/api/proxy/forward` | GET/POST/PUT/DELETE/PATCH/HEAD/OPTIONS | Yes | Forward request through proxy |

## Authentication

Two authentication methods supported (use ONE of them):

| Method | Usage | Recommended |
|--------|-------|-------------|
| `X-Proxy-Authorization` Header | `-H "X-Proxy-Authorization: Bearer <token>"` | ✅ Yes |
| `proxy_token` Query Parameter | `?proxy_token=<token>` | For simple cases |

> **Note**: Use `X-Proxy-Authorization` header when the target URL also requires `Authorization` header, to avoid conflict.

## Usage Examples

### Health Check

```bash
curl http://localhost:7860/health
```

### Get Proxy List

```bash
# Using header
curl -H "X-Proxy-Authorization: Bearer dev_token_123" \
  http://localhost:7860/api/proxies

# Using query parameter
curl "http://localhost:7860/api/proxies?proxy_token=dev_token_123"
```

### Get Proxy Pool Status

```bash
curl -H "X-Proxy-Authorization: Bearer dev_token_123" \
  http://localhost:7860/api/proxy/status
```

### Proxy Forwarding

#### GET Request Example

```bash
# Basic GET request
curl -H "X-Proxy-Authorization: Bearer dev_token_123" \
  "http://localhost:7860/api/proxy/forward?url=http://ip-api.com/json"

# With proxy type (http or socks5)
curl -H "X-Proxy-Authorization: Bearer dev_token_123" \
  "http://localhost:7860/api/proxy/forward?url=http://ip-api.com/json&proxy_type=socks5"

# With custom timeout
curl -H "X-Proxy-Authorization: Bearer dev_token_123" \
  "http://localhost:7860/api/proxy/forward?url=http://ip-api.com/json&timeout=60"
```

#### POST Request Example

```bash
# POST with JSON body
curl -X POST \
  -H "X-Proxy-Authorization: Bearer dev_token_123" \
  -H "Content-Type: application/json" \
  -d '{"name": "test", "value": 123}' \
  "http://localhost:7860/api/proxy/forward?url=https://httpbin.org/post"

# POST with form data
curl -X POST \
  -H "X-Proxy-Authorization: Bearer dev_token_123" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "field1=value1&field2=value2" \
  "http://localhost:7860/api/proxy/forward?url=https://httpbin.org/post"

# POST to API that requires Authorization (using header-based proxy auth)
curl -X POST \
  -H "X-Proxy-Authorization: Bearer dev_token_123" \
  -H "Authorization: Bearer target_api_token" \
  -H "Content-Type: application/json" \
  -d '{"key": "value"}' \
  "http://localhost:7860/api/proxy/forward?url=https://api.example.com/endpoint"
```

#### PUT/DELETE Request Example

```bash
# PUT request
curl -X PUT \
  -H "X-Proxy-Authorization: Bearer dev_token_123" \
  -H "Content-Type: application/json" \
  -d '{"id": 1, "name": "updated"}' \
  "http://localhost:7860/api/proxy/forward?url=https://httpbin.org/put"

# DELETE request
curl -X DELETE \
  -H "X-Proxy-Authorization: Bearer dev_token_123" \
  "http://localhost:7860/api/proxy/forward?url=https://httpbin.org/delete"
```

### Response Headers

| Header | Description |
|--------|-------------|
| `X-Proxy-Used` | Proxy address used (e.g., `1.2.3.4:8080`) or `DIRECT` if fallback |

### Query Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `url` | Yes | - | Target URL to forward request to |
| `proxy_type` | No | `http` | Proxy type: `http` or `socks5` |
| `timeout` | No | `30` | Request timeout in seconds |
| `proxy_token` | No* | - | Authentication token (alternative to header) |

*Either `proxy_token` or `X-Proxy-Authorization` header is required.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PROXY_API_TOKEN` | `dev_token_123` | Authentication token |
| `CHECK_INTERVAL` | `600` | Proxy refresh interval (seconds) |
| `FORWARD_TIMEOUT` | `30` | Forward request timeout (seconds) |
| `FORWARD_MAX_RETRIES` | `3` | Max retry attempts with different proxies |
| `FORWARD_MAX_BODY_SIZE` | `10485760` | Max request body size (10MB) |
| `HOST` | `0.0.0.0` | Server host |
| `PORT` | `7860` | Server port |

## Running

```bash
# Install dependencies
pip install -r requirements.txt

# Run with default settings
python run.py

# Or with custom environment
set PROXY_API_TOKEN=your_secure_token
set PORT=8080
python run.py
```

## Docker

```bash
# Build
docker build -t proxy-service .

# Run
docker run -p 7860:7860 -e PROXY_API_TOKEN=your_token proxy-service
```

## License

MIT License
