# Getting Started with WebStore Monitoring Example

**Read this first!** This guide will get you up and running in 5 minutes.

## What You'll Learn

This project teaches you modern observability practices through a real-world e-commerce application with:
- OpenTelemetry instrumentation across multiple languages (Python, Go, C#, Node.js)
- Distributed tracing with Grafana Tempo
- Metrics collection with Prometheus
- Log aggregation with Loki
- Visualization with Grafana dashboards
- Alerting and SLO tracking

## Prerequisites

Before you begin, make sure you have:
- **Docker Desktop** installed and running with at least **8GB RAM** allocated
- **Python 3.8+** for traffic generation scripts
- **4 CPU cores** available
- **20GB disk space** (50GB recommended for SSD)

## Quick Start in 3 Steps

### Step 1: Start All Services (2-3 minutes)

```bash
# Clone the repository (if you haven't already)
git clone <repository-url>
cd monitoring-example

# Start everything
./start.sh
```

Or use one of these alternatives:
```bash
# Using Docker Compose directly
docker-compose up -d

# Using Make
make start
```

**Wait 2-3 minutes** for all services to initialize. PostgreSQL and other services need time to start.

### Step 2: Verify Services Are Running

```bash
# Check service status
docker-compose ps

# Or use the health check script
./health-check-dependencies.sh
```

All services should show "Up" status.

### Step 3: Generate Traffic and Explore

```bash
# Generate realistic traffic
cd scripts
python3 generate-traffic.py --users 5 --duration 60
```

While traffic is generating, open these in your browser:

1. **WebStore App**: http://localhost:3001
   - Click "Login" (uses demo token)
   - Browse products, add to cart, checkout

2. **Grafana**: http://localhost:3000
   - Navigate to: Dashboards → WebStore folder
   - View real-time metrics

## What's Running?

After startup, you'll have 15 services running:

**Application Services** (7):
- Frontend (React) - Port 3001
- Main Service (Python/FastAPI) - Port 8000
- Payments Service (Go) - Port 8081
- Promotions Service (C#/.NET) - Port 8082
- Payment Provider (Node.js) - Port 3001
- CRM System (Node.js) - Port 3002
- Inventory System (Node.js) - Port 3003

**Observability Stack** (8):
- PostgreSQL - Port 5432
- Redis - Port 6379
- OpenTelemetry Collector - Ports 4317 (gRPC), 4318 (HTTP)
- Prometheus - Port 9090
- Grafana Tempo - Port 3200
- Grafana Loki - Port 3100
- Alertmanager - Port 9093
- Grafana - Port 3000

## Your First Exploration

### 1. View Business Metrics

Open Grafana → Dashboards → WebStore → **WebStore Overview**

You'll see:
- Cart additions by country
- Checkout rates and conversion
- Payment success/failure rates
- Active shopping carts
- Country-specific performance

### 2. Explore Distributed Traces

Open Grafana → Explore → Select **Tempo** data source

1. Click **Search**
2. Select service: `main-service`
3. Click **Run query**
4. Click any trace to see the complete request flow through all services

You'll see how a single checkout request flows:
```
Frontend → Main Service → Payments Service → Payment Provider
                      ↓
                  Inventory System
                      ↓
                  CRM System
```

### 3. View Correlated Logs

Open Grafana → Explore → Select **Loki** data source

Try these queries:
```logql
# All logs from main service
{service_name="main-service"}

# Failed payment logs
{service_name="payments-service"} |= "failed"

# Checkout events
{service_name="main-service"} |= "checkout"
```

**Pro tip**: Click on a `trace_id` in logs to jump directly to the trace!

### 4. Check Alerts

Open Prometheus → Alerts: http://localhost:9090/alerts

You'll see 18 configured alert rules monitoring:
- Error rates
- Latency (P95, P99)
- Payment failures
- Resource usage
- SLO violations

## Test the API Directly

### Browse Products (No Auth Required)

```bash
curl http://localhost:8000/products | jq
```

### Add Item to Cart (Auth Required)

```bash
curl -X POST http://localhost:8000/cart/add \
  -H "Authorization: Bearer user-token-123" \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": 1,
    "quantity": 1,
    "country": "US"
  }' | jq
```

### Complete a Checkout

```bash
curl -X POST http://localhost:8000/checkout \
  -H "Authorization: Bearer user-token-123" \
  -H "Content-Type: application/json" \
  -d '{
    "payment_method": "credit_card",
    "country": "US"
  }' | jq
```

After running these commands:
1. Go to Grafana → Explore → Tempo
2. Search for recent traces
3. You'll see the complete trace showing all service calls!

## Demo Authentication Tokens

The app uses hardcoded tokens for demo purposes:
- `user-token-123`
- `admin-token-456`
- `test-token-789`

## Common First-Time Issues

### Services Keep Restarting

**Cause**: Not enough memory allocated to Docker

**Solution**: Increase Docker Desktop memory to at least 8GB:
- Docker Desktop → Settings → Resources → Memory

### Port Already in Use

**Cause**: Another application is using required ports

**Solution**: Find and stop the conflicting service:
```bash
# Check what's using port 8000
lsof -i :8000

# Kill the process or change ports in docker-compose.yml
```

### Services Not Ready

**Cause**: Services can take 2-3 minutes to fully start

**Solution**: Wait a bit longer, then check logs:
```bash
docker-compose logs -f main-service
```

### No Metrics Showing

**Cause**: No traffic has been generated yet

**Solution**: Run the traffic generator:
```bash
cd scripts
python3 generate-traffic.py --users 5 --duration 60
```

## Useful Commands

```bash
# View logs
docker-compose logs -f                    # All services
docker-compose logs -f main-service       # Specific service
make logs-main                            # Using Make

# Restart a service
docker-compose restart main-service

# Stop everything
docker-compose down

# Stop and remove all data
docker-compose down -v

# Rebuild after code changes
docker-compose up -d --build main-service
```

## Next Steps

Now that you have everything running, continue your learning:

1. **[Understanding the Architecture](02_ARCHITECTURE_OVERVIEW.md)** - Learn how services communicate
2. **[OpenTelemetry Instrumentation](03_OPENTELEMETRY_INSTRUMENTATION.md)** - See how observability works
3. **[Metrics and Dashboards](04_METRICS_AND_DASHBOARDS.md)** - Understand the metrics being collected
4. **[Distributed Tracing](05_DISTRIBUTED_TRACING.md)** - Deep dive into traces
5. **[Logs and Correlation](06_LOGGING_AND_CORRELATION.md)** - Learn structured logging
6. **[Alerting and SLOs](07_ALERTING_AND_SLOS.md)** - Understand the alerting system

## Need Help?

- Check the [Troubleshooting Guide](09_TROUBLESHOOTING.md)
- Review the main [README](../README.md)
- Examine service logs: `docker-compose logs <service-name>`
- Use the health check: `./health-check-dependencies.sh`

## Clean Up

When you're done exploring:

```bash
# Stop services (keeps data)
docker-compose down

# Stop and remove all data
docker-compose down -v

# Remove images too
docker-compose down -v --rmi all
```

---

**Ready to dive deeper?** Continue to [Architecture Overview](02_ARCHITECTURE_OVERVIEW.md) →
