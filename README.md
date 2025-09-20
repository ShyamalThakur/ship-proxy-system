# Ship Proxy System

A cost-efficient proxy system designed for cruise ships that minimizes satellite internet costs by reusing a single TCP connection for all outbound HTTP/S requests.

## System Architecture

```
Browser/curl → Ship Proxy (8080) → Single TCP → Offshore Proxy (9999) → Internet
```

- **Ship Proxy (Client)**: Runs on the ship, accepts HTTP proxy connections, queues requests, and forwards them sequentially over a single TCP connection
- **Offshore Proxy (Server)**: Runs remotely, receives requests over TCP, forwards them to target servers, and sends responses back

## Features

- ✅ Single persistent TCP connection between ship and offshore proxy
- ✅ Sequential request processing to ensure reliability
- ✅ Support for all HTTP methods (GET, POST, PUT, DELETE, etc.)
- ✅ HTTPS support via CONNECT method tunneling
- ✅ Automatic reconnection on connection failures
- ✅ Docker support with multi-architecture builds
- ✅ Works with curl, browsers, and other HTTP clients

## Quick Start

### Using Docker Compose (Recommended)

1. Clone this repository
2. Run the entire system:

```bash
docker-compose up -d
```

3. Test with curl:

```bash
# HTTP request
curl -x http://localhost:8080 http://httpforever.com/

# HTTPS request
curl -x http://localhost:8080 https://httpbin.org/get

# POST request
curl -x http://localhost:8080 -X POST -d "test data" http://httpbin.org/post
```

### Using Docker Images

Run the offshore proxy:
```bash
docker run -p 9999:9999 your-username/offshore-proxy
```

Run the ship proxy:
```bash
docker run -p 8080:8080 -e OFFSHORE_HOST=localhost your-username/ship-proxy
```

### Manual Installation

#### Prerequisites
- Python 3.8+
- No additional dependencies (uses only standard library)

#### Running the Offshore Proxy

```bash
cd server
python server.py
```

#### Running the Ship Proxy

```bash
cd client
python client.py --offshore-host=localhost --offshore-port=9999
```

## Testing

### Basic HTTP Test
```bash
curl -x http://localhost:8080 http://httpforever.com/
```

### HTTPS Test
```bash
curl -x http://localhost:8080 https://httpbin.org/get
```

### Multiple HTTP Methods
```bash
# GET
curl -x http://localhost:8080 http://httpbin.org/get

# POST
curl -x http://localhost:8080 -X POST -d '{"key":"value"}' -H "Content-Type: application/json" http://httpbin.org/post

# PUT
curl -x
