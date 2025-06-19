# Production Usage Guide for Lighter CPTY

This guide explains how to run the Lighter CPTY integration with Architect core in production.

## Prerequisites

1. Set environment variables:
```bash
export LIGHTER_URL="https://testnet.zklighter.elliot.ai"  # or mainnet URL
export LIGHTER_API_KEY_PRIVATE_KEY="your_private_key_here"
export LIGHTER_ACCOUNT_INDEX="0"  # Your account index
export LIGHTER_API_KEY_INDEX="1"  # Usually 1
```

2. Install dependencies:
```bash
cd architect-py
pip install grpcio grpcio-tools msgspec websockets lighter-python
```

## Running the Server

### 1. Start the Lighter CPTY Server

This server implements the Architect CPTY interface and connects to Lighter:

```bash
cd architect-py/examples
python run_lighter_cpty_server.py [port]
```

Default port is 50051. The server will:
- Initialize connection to Lighter using the SDK
- Accept gRPC connections from Architect core
- Handle order placement, cancellation, and streaming updates

Example output:
```
2024-01-01 12:00:00 - INFO - Lighter CPTY server started on port 50051
2024-01-01 12:00:00 - INFO - Using Lighter endpoint: https://testnet.zklighter.elliot.ai
2024-01-01 12:00:00 - INFO - Account index: 0
2024-01-01 12:00:00 - INFO - Server is ready to accept connections from Architect core
```

### 2. Configure Architect Core

In your Architect core configuration, point to the Lighter CPTY server:

```yaml
cpty:
  lighter:
    type: grpc
    address: localhost:50051
    protocol: json
```

## Client Usage

### 1. Send Orders via Command Line

Use the order sending script:

```bash
# Buy 0.1 ETH at $2700
python send_lighter_order.py \
  --symbol 0 \
  --side BUY \
  --price 2700.00 \
  --quantity 0.1 \
  --type LIMIT \
  --tif GTC

# Sell 0.05 BTC at $45000 with post-only
python send_lighter_order.py \
  --symbol 1 \
  --side SELL \
  --price 45000.00 \
  --quantity 0.05 \
  --type LIMIT \
  --post-only
```

Options:
- `--server`: Architect server address (default: localhost:50051)
- `--user`: User ID (default: trader)
- `--account`: Account ID/index (default: 0)
- `--symbol`: Market ID (0=ETH/USDC, 1=BTC/USDC, etc.)
- `--side`: BUY or SELL
- `--price`: Order price
- `--quantity`: Order quantity
- `--type`: LIMIT, MARKET, or LIMIT_MAKER
- `--tif`: GTC, IOC, or FOK
- `--order-id`: Custom order ID (auto-generated if not provided)
- `--reduce-only`: Reduce-only flag
- `--post-only`: Post-only flag

### 2. Monitor Orderflow

Monitor real-time updates:

```bash
# Monitor all accounts
python monitor_lighter_orderflow.py

# Monitor specific account
python monitor_lighter_orderflow.py --account 0
```

### 3. Programmatic Client

Use the client library in your Python code:

```python
import asyncio
from lighter_cpty_client import LighterCptyClient

async def main():
    client = LighterCptyClient("localhost:50051")
    await client.connect()
    
    # Login
    await client.login("my_user", "0")
    
    # Place order
    await client.place_order(
        cl_ord_id="order_001",
        symbol="0",
        side="BUY",
        price="2700.00",
        qty="0.1"
    )
    
    # Handle responses
    await client.handle_responses()
    
    await client.disconnect()

asyncio.run(main())
```

## Production Deployment

### 1. System Service (systemd)

Create `/etc/systemd/system/lighter-cpty.service`:

```ini
[Unit]
Description=Lighter CPTY Server for Architect
After=network.target

[Service]
Type=simple
User=architect
Group=architect
WorkingDirectory=/opt/architect/architect-py
Environment="LIGHTER_URL=https://mainnet.zklighter.elliot.ai"
Environment="LIGHTER_API_KEY_PRIVATE_KEY=your_key_here"
Environment="LIGHTER_ACCOUNT_INDEX=0"
Environment="LIGHTER_API_KEY_INDEX=1"
ExecStart=/usr/bin/python3 /opt/architect/architect-py/examples/run_lighter_cpty_server.py 50051
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable lighter-cpty
sudo systemctl start lighter-cpty
sudo systemctl status lighter-cpty
```

### 2. Docker Deployment

Create a Dockerfile:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY architect-py/ /app/architect-py/

# Environment variables
ENV LIGHTER_URL="https://mainnet.zklighter.elliot.ai"
ENV LIGHTER_ACCOUNT_INDEX="0"
ENV LIGHTER_API_KEY_INDEX="1"

# Expose gRPC port
EXPOSE 50051

# Run server
CMD ["python", "/app/architect-py/examples/run_lighter_cpty_server.py"]
```

Run with Docker:
```bash
docker build -t lighter-cpty .
docker run -d \
  --name lighter-cpty \
  -p 50051:50051 \
  -e LIGHTER_API_KEY_PRIVATE_KEY="your_key_here" \
  lighter-cpty
```

### 3. Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: lighter-cpty
spec:
  replicas: 1
  selector:
    matchLabels:
      app: lighter-cpty
  template:
    metadata:
      labels:
        app: lighter-cpty
    spec:
      containers:
      - name: lighter-cpty
        image: lighter-cpty:latest
        ports:
        - containerPort: 50051
        env:
        - name: LIGHTER_URL
          value: "https://mainnet.zklighter.elliot.ai"
        - name: LIGHTER_API_KEY_PRIVATE_KEY
          valueFrom:
            secretKeyRef:
              name: lighter-secrets
              key: api-key
        - name: LIGHTER_ACCOUNT_INDEX
          value: "0"
---
apiVersion: v1
kind: Service
metadata:
  name: lighter-cpty
spec:
  selector:
    app: lighter-cpty
  ports:
  - port: 50051
    targetPort: 50051
```

## Monitoring and Logging

### 1. Health Check

The server logs its status regularly. Monitor logs for:
- Connection status
- Order placement/cancellation confirmations
- WebSocket connectivity
- Error messages

### 2. Metrics

Consider adding Prometheus metrics for:
- Order success/failure rates
- Latency measurements
- WebSocket reconnection counts
- API rate limit usage

### 3. Alerts

Set up alerts for:
- Server disconnections
- Authentication failures
- High error rates
- WebSocket disconnections lasting > 1 minute

## Troubleshooting

### Common Issues

1. **Authentication Failed**
   - Verify LIGHTER_API_KEY_PRIVATE_KEY is correct
   - Check account index matches your Lighter account
   - Ensure API key has trading permissions

2. **Connection Refused**
   - Check server is running on correct port
   - Verify firewall rules allow gRPC traffic
   - Ensure Architect core points to correct address

3. **Orders Not Executing**
   - Verify market ID is correct (0=ETH/USDC, 1=BTC/USDC)
   - Check price is within valid range
   - Ensure sufficient balance in account

4. **WebSocket Disconnections**
   - Monitor network connectivity
   - Check for rate limiting
   - Verify WebSocket URL is correct

### Debug Mode

Enable debug logging:
```bash
export PYTHONUNBUFFERED=1
export GRPC_VERBOSITY=DEBUG
export GRPC_TRACE=all
python run_lighter_cpty_server.py
```

## Security Considerations

1. **API Key Protection**
   - Never commit API keys to version control
   - Use environment variables or secure key management
   - Rotate keys regularly

2. **Network Security**
   - Use TLS for production gRPC connections
   - Restrict server access to authorized clients only
   - Monitor for suspicious activity

3. **Order Validation**
   - Implement order size limits
   - Add price sanity checks
   - Monitor for unusual trading patterns

## Support

For issues:
- Lighter API: https://docs.lighter.xyz
- Architect: Consult Architect documentation
- This integration: Check logs and examples in architect-py/examples/