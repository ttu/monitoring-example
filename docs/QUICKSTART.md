# Quick Start Guide

Get up and running in 5 minutes!

## Prerequisites

- Docker Desktop installed and running
- 8GB+ RAM available
- Python 3.8+ (for traffic generation)

## Step 1: Start the Application (2 minutes)

```bash
# Option 1: Using the start script (recommended)
chmod +x start.sh
./start.sh

# Option 2: Using Docker Compose directly
docker-compose up -d

# Option 3: Using Make
make start
```

Wait 2-3 minutes for all services to initialize.

## Step 2: Verify Services Are Running

Check all services are healthy:

```bash
docker-compose ps
```

All services should show "Up" status.

## Step 3: Access the Application

Open these URLs in your browser:

1. **WebStore Frontend**: http://localhost:3001
   - Click "Login" button (uses demo token)
   - Browse products
   - Add items to cart
   - Click "Checkout"

2. **Grafana Dashboards**: http://localhost:3000
   - Go to Dashboards → WebStore → WebStore Overview
   - Watch metrics update in real-time

## Step 4: Generate Traffic (Optional but Recommended)

Generate realistic traffic to populate dashboards:

```bash
# Install Python requests library (if not already installed)
pip install requests

# Generate traffic with 5 concurrent users
cd scripts
python3 generate-traffic.py --users 5 --duration 60
```

Leave this running in a separate terminal.

## Step 5: Explore Observability Features

### View Metrics (Prometheus)

Open http://localhost:9090 and try these queries:

```promql
# Cart additions per second
rate(webstore_cart_additions_total[1m])

# Payment success rate
rate(payments_processed_total{status="success"}[5m]) / rate(payments_processed_total[5m])

# Active carts by country
webstore_active_carts
```

### View Traces (Tempo via Grafana)

1. Open Grafana: http://localhost:3000
2. Click "Explore" (compass icon)
3. Select "Tempo" data source
4. Click "Search"
5. Select service: `main-service`
6. Click "Run query"
7. Click on any trace to see the full distributed trace

### View Logs (Loki via Grafana)

1. In Grafana Explore
2. Select "Loki" data source
3. Try these queries:

```logql
# All logs from main service
{service_name="main-service"}

# Failed payments
{service_name="payments-service"} |= "failed"

# Checkout events
{service_name="main-service"} |= "checkout"
```

### View Profiles (Pyroscope)

Open http://localhost:4040
- Select application: `main-service`
- View CPU flame graphs

## Common First-Time Issues

### "Service not ready" errors

**Solution**: Wait a bit longer. Services can take 2-3 minutes to fully start, especially on first run.

```bash
# Check service logs
docker-compose logs -f main-service
```

### Port already in use

**Solution**: Another application is using the required ports.

```bash
# Find what's using port 8000
lsof -i :8000

# Stop the conflicting service or change ports in docker-compose.yml
```

### Out of memory

**Solution**: Increase Docker memory allocation in Docker Desktop settings to at least 8GB.

### Services keep restarting

**Solution**: Check logs for errors:

```bash
docker-compose logs
```

## Basic Operations

### Stop Everything

```bash
docker-compose down
```

### Stop and Remove All Data

```bash
docker-compose down -v
```

### Restart a Specific Service

```bash
docker-compose restart main-service
```

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f payments-service
```

### Update a Service

After making code changes:

```bash
docker-compose up -d --build main-service
```

## Test the API Directly

### Get Products (No Authentication)

```bash
curl http://localhost:8000/products
```

### Add to Cart (Requires Authentication)

```bash
curl -X POST http://localhost:8000/cart/add \
  -H "Authorization: Bearer user-token-123" \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": 1,
    "quantity": 1,
    "country": "US"
  }'
```

### View Cart

```bash
curl http://localhost:8000/cart \
  -H "Authorization: Bearer user-token-123"
```

### Checkout

```bash
curl -X POST http://localhost:8000/checkout \
  -H "Authorization: Bearer user-token-123" \
  -H "Content-Type: application/json" \
  -d '{
    "payment_method": "credit_card",
    "country": "US"
  }'
```

## Demo Scenario: Complete Purchase Flow

Run these commands in sequence to simulate a complete purchase:

```bash
# 1. Browse products
curl http://localhost:8000/products

# 2. Add laptop to cart
curl -X POST http://localhost:8000/cart/add \
  -H "Authorization: Bearer user-token-123" \
  -H "Content-Type: application/json" \
  -d '{"product_id": 1, "quantity": 1, "country": "US"}'

# 3. Add smartphone to cart
curl -X POST http://localhost:8000/cart/add \
  -H "Authorization: Bearer user-token-123" \
  -H "Content-Type: application/json" \
  -d '{"product_id": 2, "quantity": 1, "country": "US"}'

# 4. View cart
curl http://localhost:8000/cart \
  -H "Authorization: Bearer user-token-123"

# 5. Checkout
curl -X POST http://localhost:8000/checkout \
  -H "Authorization: Bearer user-token-123" \
  -H "Content-Type: application/json" \
  -d '{"payment_method": "credit_card", "country": "US"}'

# 6. View orders
curl http://localhost:8000/orders \
  -H "Authorization: Bearer user-token-123"
```

After running these commands:
1. Open Grafana: http://localhost:3000
2. Go to Explore → Tempo
3. Search for recent traces
4. You'll see the complete trace spanning all services!

## What to Look For

### In Grafana Dashboards

- **Cart Additions Rate**: Should increase when you add items
- **Checkout Rate**: Should increase after checkout
- **Payment Failure Rate**: Around 5-15% (simulated failures)
- **Active Carts**: Shows current shopping sessions

### In Traces

- Full request path across all services
- Service dependencies (Service Graph)
- Slow operations highlighted
- Failed requests marked in red
- Exact timing of each operation

### In Logs

- Structured JSON logs with trace IDs
- Click trace ID to jump to the trace
- Filter by service, level, or content

## Next Steps

1. ✅ Check out the [README.md](README.md) for detailed information
2. ✅ Read [ARCHITECTURE.md](ARCHITECTURE.md) for system design
3. ✅ Explore Grafana dashboards
4. ✅ Try different countries and see failure rates vary
5. ✅ Look for correlation between metrics, traces, and logs

## Getting Help

- Check [README.md](README.md) for full documentation
- Review [ARCHITECTURE.md](ARCHITECTURE.md) for system details
- Look at service logs: `docker-compose logs <service>`
- Verify service health: `make health` or check http://localhost:8000/health

## Clean Up

When you're done:

```bash
# Stop services but keep data
docker-compose down

# Stop services and remove all data
docker-compose down -v

# Remove images too
docker-compose down -v --rmi all
```

---

**Enjoy exploring modern observability! 🚀**
