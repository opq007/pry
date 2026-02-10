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

RESTful API for retrieving validated proxy servers.

## Features

- 🔄 Automatic proxy pool refresh
- 🔒 Bearer token authentication
- ⚡ Fast multi-threaded validation
- 🩺 Health check endpoint

## API Endpoints

| Endpoint | Auth | Description |
|----------|------|-------------|
| `GET /health` | No | Health check |
| `GET /api/proxies` | Yes | Get proxy list |

## Usage

```bash
# Health check
curl http://localhost:7860/health

# Get proxies (with token)
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:7860/api/proxies
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PROXY_API_TOKEN` | `dev_token_123` | Authentication token |
| `CHECK_INTERVAL` | `600` | Proxy refresh interval (seconds) |
| `HOST` | `0.0.0.0` | Server host |
| `PORT` | `7860` | Server port |

## License

MIT License