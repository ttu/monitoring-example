# Health Check Architecture - Technical Reference

> **Note**: For an introduction to health checks, see [08_DOCKER_AND_DEPLOYMENT.md](08_DOCKER_AND_DEPLOYMENT.md#health-checks-and-dependencies) and [09_TROUBLESHOOTING.md](09_TROUBLESHOOTING.md).
> This document provides **detailed technical specifications** and deep-dive information on the health check system.

## Architecture

### Layered Health Check Model

```
┌─────────────────────────────────────────────────────────┐
│ Layer 5: Frontend                                       │
│ └─ frontend (React SPA)                                 │
│    Depends on: main-service                             │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│ Layer 4: External Integration Services                  │
│ ├─ payment-provider (simulated external)               │
│ ├─ crm-system (simulated external)                     │
│ └─ inventory-system (simulated external)               │
│    Depends on: main-service, payments-service           │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│ Layer 3: Core Application Services (CRITICAL)           │
│ ├─ main-service (FastAPI/Python)                       │
│ ├─ payments-service (Go)                               │
│ └─ promotions-service (C#/.NET)                        │
│    Depends on: PostgreSQL, Redis, OTEL-Collector       │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│ Layer 2: Observability Infrastructure                   │
│ ├─ OTEL-Collector (telemetry aggregation)             │
│ ├─ Prometheus (metrics storage)                        │
│ ├─ Tempo (trace storage)                               │
│ ├─ Loki (log aggregation)                              │
│ ├─ Alertmanager (alert routing)                        │
│ └─ Grafana (visualization)                             │
│    Note: Non-critical for app operation                │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│ Layer 1: Core Infrastructure (CRITICAL)                 │
│ ├─ PostgreSQL (persistent data)                        │
│ └─ Redis (caching, sessions)                           │
│    Note: Application cannot function without these      │
└─────────────────────────────────────────────────────────┘
```

## Complete Service Health Check Matrix

### Application Services

| Service | Health Endpoint | Port | Response Format | Expected Response | Dependencies | Critical |
|---------|----------------|------|-----------------|-------------------|--------------|----------|
| main-service | `/health` | 8000 | JSON | `{"status": "healthy"}` | PostgreSQL, Redis, OTEL | ✓ Yes |
| payments-service | `/health` | 8081 | JSON | `{"status": "healthy"}` | payment-provider, OTEL | ✓ Yes |
| promotions-service | `/health` | 8082 | HTTP Status | HTTP 200 OK | OTEL | No |
| frontend | `/` | 3001 | HTTP Status | HTTP 200 OK | main-service | No |

### External Services

| Service | Health Endpoint | Port | Response Format | Expected Response | Purpose | Critical |
|---------|----------------|------|-----------------|-------------------|---------|----------|
| payment-provider | `/health` | 3001 | JSON | `{"status": "ok"}` | Payment processing | No* |
| crm-system | `/health` | 3002 | JSON | `{"status": "ok"}` | Customer data | No |
| inventory-system | `/health` | 3003 | JSON | `{"status": "ok"}` | Stock management | No |

*Payment-provider failure affects payments-service but app can degrade gracefully

### Infrastructure Services

| Service | Health Check Method | Port | Command/Endpoint | Expected | Critical |
|---------|-------------------|------|------------------|----------|----------|
| PostgreSQL | CLI Command | 5432 | `pg_isready -U webstore` | "accepting connections" | ✓ Yes |
| Redis | CLI Command | 6379 | `redis-cli ping` | "PONG" | ✓ Yes |
| OTEL-Collector | HTTP | 13133 | `GET /` | HTTP 200 | Yes* |
| Prometheus | HTTP | 9090 | Port check or `/-/ready` | HTTP 200 | No |
| Tempo | TCP | 3200 | Port check or `/ready` | HTTP 200 | No |
| Loki | HTTP | 3100 | `/ready` | HTTP 200 | No |
| Alertmanager | HTTP | 9093 | `/-/healthy` | HTTP 200 | No |
| Grafana | TCP | 3000 | Port check | Connection success | No |

*OTEL Collector is critical for observability but not for application functionality

## Health Check Script Implementation Details

### Script Usage

```bash
# Standard health check with verbose output
./health-check-dependencies.sh

# Quiet mode (errors only)
./health-check-dependencies.sh --quiet

# JSON output (for automation)
./health-check-dependencies.sh --json

# Custom timeout
./health-check-dependencies.sh --timeout 10

# Check specific layer only
./health-check-dependencies.sh --layer infrastructure
./health-check-dependencies.sh --layer application
```

### Exit Codes

| Code | Meaning | Description |
|------|---------|-------------|
| `0` | Success | All critical services healthy |
| `1` | Critical Failure | One or more critical services unhealthy |
| `2` | Warning | Non-critical services unhealthy |
| `3` | Timeout | Health check timed out |
| `4` | Invalid Argument | Invalid command line argument |

**Critical services**: PostgreSQL, Redis, main-service, payments-service

### Implementation Patterns

**Port Check Function**:
```bash
check_port() {
    local host=$1
    local port=$2
    local timeout=${3:-5}

    if timeout $timeout bash -c "cat < /dev/null > /dev/tcp/$host/$port" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}
```

**HTTP Health Check Function**:
```bash
check_http() {
    local url=$1
    local timeout=${2:-5}
    local expected_status=${3:-200}

    status=$(curl -s -o /dev/null -w "%{http_code}" \
        --connect-timeout $timeout \
        --max-time $timeout \
        "$url")

    if [ "$status" -eq "$expected_status" ]; then
        return 0
    else
        return 1
    fi
}
```

**JSON Health Check Function**:
```bash
check_json_health() {
    local url=$1
    local timeout=${2:-5}

    response=$(curl -s --connect-timeout $timeout \
        --max-time $timeout "$url")

    status=$(echo "$response" | jq -r '.status // empty')

    if [ "$status" = "healthy" ] || [ "$status" = "ok" ]; then
        return 0
    else
        return 1
    fi
}
```

### Output Format

#### Verbose Mode

```
========================================
  WebStore Health Check with Dependencies
========================================

[Layer 1] Core Infrastructure (Critical):
  Checking PostgreSQL (localhost:5432)... ✓ OK (15ms)
  Checking Redis (localhost:6379)... ✓ OK (12ms)

[Layer 2] Observability Infrastructure:
  Checking OTEL-Collector... ✓ OK (145ms)
  Checking Prometheus (localhost:9090)... ✓ OK (8ms)
  ...

[Layer 3] Core Application Services:
  Checking main-service... ✓ OK (234ms)
  Checking payments-service... ✓ OK (189ms)
  ...

Overall Status: ✓ HEALTHY
```

#### JSON Mode

```json
{
  "overall_status": "healthy",
  "timestamp": "2025-10-19T17:00:00Z",
  "duration_seconds": 2,
  "services": {
    "PostgreSQL": {
      "status": "healthy",
      "response_time_ms": 15,
      "error": "none"
    },
    "main-service": {
      "status": "healthy",
      "response_time_ms": 234,
      "error": "none"
    }
  },
  "dependency_graph": {
    "layer1_infrastructure": ["PostgreSQL", "Redis"],
    "layer2_observability": [...],
    "layer3_core_services": {
      "services": ["main-service", "payments-service"],
      "depends_on": ["PostgreSQL", "Redis"]
    }
  }
}
```

## Dependency Matrix

### Service Dependencies

| Service | Direct Dependencies | Impact if Down |
|---------|-------------------|----------------|
| **PostgreSQL** | None | 🔴 Critical - All services fail |
| **Redis** | None | 🔴 Critical - Session/cache loss |
| **OTEL-Collector** | None | 🟡 Warning - Telemetry loss |
| **main-service** | PostgreSQL, Redis, OTEL | 🔴 Critical - Core API unavailable |
| **payments-service** | payment-provider, OTEL | 🔴 Critical - Payments fail |
| **promotions-service** | OTEL | 🟡 Warning - Discounts unavailable |
| **payment-provider** | None | 🟡 Warning - Payments degraded |
| **crm-system** | None | 🟢 Info - Analytics affected |
| **inventory-system** | None | 🟢 Info - Stock checks affected |
| **frontend** | main-service | 🟡 Warning - UI unavailable |

### Health Check Order

Health checks are performed in dependency order to avoid false negatives:

1. **Infrastructure first** (PostgreSQL, Redis)
   - If these fail, we expect app services to fail
   - Warns about expected failures

2. **Observability second** (OTEL, Prometheus, etc.)
   - Non-critical for app operation
   - Failures don't affect overall status

3. **Core services third** (main, payments, promotions)
   - Depend on infrastructure
   - Critical for application

4. **External services fourth**
   - Depend on core services
   - Non-critical (can degrade gracefully)

5. **Frontend last**
   - Depends on everything
   - Non-critical for API operation

## Integration with Monitoring

### Prometheus Metrics

Health check results can be exposed as Prometheus metrics:

```yaml
# prometheus-alerts.yml
- alert: ServiceUnhealthy
  expr: up{job="main-service"} == 0
  for: 2m
  labels:
    severity: critical
  annotations:
    summary: "Service {{ $labels.job }} is unhealthy"
```

### Docker Healthchecks

Services can use Docker's built-in healthcheck:

```yaml
# docker-compose.yml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

### Kubernetes Probes

For Kubernetes deployments:

```yaml
# Liveness probe - restart if fails
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10

# Readiness probe - remove from load balancer if fails
readinessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
```

## Enhanced Health Checks (Future)

### Current Implementation

Basic health checks return simple status:

```json
{"status": "healthy"}
```

### Enhanced Health Check Response

For production systems, consider enhanced responses:

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2025-10-19T17:00:00Z",
  "checks": {
    "database": {
      "status": "healthy",
      "response_time_ms": 15,
      "connection_pool": {
        "active": 5,
        "idle": 10,
        "max": 20
      }
    },
    "redis": {
      "status": "healthy",
      "response_time_ms": 8,
      "memory_usage_mb": 125
    },
    "external_services": {
      "payment_provider": {
        "status": "healthy",
        "last_check": "2025-10-19T16:59:00Z"
      }
    }
  },
  "metrics": {
    "requests_per_second": 100,
    "error_rate": 0.01,
    "p95_latency_ms": 250
  }
}
```

### Implementation Example (Python)

```python
from fastapi import FastAPI
from datetime import datetime
import asyncio

@app.get("/health")
async def health():
    """Enhanced health check with dependency verification."""

    checks = {}

    # Check database
    try:
        db_start = time.time()
        await database.execute("SELECT 1")
        db_time = (time.time() - db_start) * 1000

        pool_stats = await database.pool_stats()
        checks["database"] = {
            "status": "healthy",
            "response_time_ms": round(db_time, 2),
            "connection_pool": pool_stats
        }
    except Exception as e:
        checks["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }

    # Check Redis
    try:
        redis_start = time.time()
        await redis.ping()
        redis_time = (time.time() - redis_start) * 1000

        checks["redis"] = {
            "status": "healthy",
            "response_time_ms": round(redis_time, 2)
        }
    except Exception as e:
        checks["redis"] = {
            "status": "unhealthy",
            "error": str(e)
        }

    # Determine overall status
    overall_status = "healthy"
    for check in checks.values():
        if check["status"] != "healthy":
            overall_status = "unhealthy"
            break

    return {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "checks": checks
    }
```

## Best Practices

### DO ✅

- **Check dependencies in order** - Infrastructure → Services → Frontend
- **Set appropriate timeouts** - Don't wait too long for unhealthy services
- **Distinguish critical from non-critical** - Not all failures are equal
- **Include response times** - Track health check latency
- **Automate health checks** - Run periodically, alert on failures
- **Document dependencies** - Keep dependency graph up-to-date
- **Use proper HTTP status codes** - 200 for healthy, 503 for unhealthy

### DON'T ❌

- **Don't perform heavy operations** - Health checks should be lightweight
- **Don't expose sensitive data** - Keep health responses minimal
- **Don't ignore non-critical failures** - Log them for investigation
- **Don't check everything simultaneously** - Respect dependency order
- **Don't use health checks for monitoring** - Use proper metrics instead
- **Don't make external calls** - Cache external service status

## Advanced Troubleshooting Patterns

### All Services Appear Unhealthy

**Diagnostic procedure:**

1. **Verify Docker is running:**
   ```bash
   docker info
   docker-compose ps  # Should show containers
   ```

2. **Check network connectivity:**
   ```bash
   docker network inspect monitoring-example_default
   docker-compose exec main-service ping postgres
   docker-compose exec main-service ping payments-service
   ```

3. **Verify DNS resolution:**
   ```bash
   docker-compose exec main-service nslookup postgres
   docker-compose exec main-service nslookup redis
   ```

4. **Check service startup order:**
   ```bash
   # Services should start in dependency order
   docker-compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
   ```

5. **Resource constraints:**
   ```bash
   docker stats --no-stream
   # Check if containers are being OOMKilled
   docker inspect monitoring-example-main-service-1 | jq '.[0].State'
   ```

### Intermittent Health Check Failures

**Root cause analysis:**

**Pattern 1: Timeout Issues**
```bash
# Measure actual response time
time curl -s http://localhost:8000/health

# If > 5s consistently, increase timeout
# If sporadic, check resource contention
docker stats
```

**Pattern 2: Service Startup Race Conditions**
```bash
# Check if service is ready
docker-compose logs main-service | grep -i "ready"
docker-compose logs main-service | grep -i "listening"

# Verify health check start_period is sufficient
docker inspect monitoring-example-main-service-1 | \
  jq '.[0].Config.Healthcheck'
```

**Pattern 3: Database Connection Pool Exhaustion**
```bash
# Check PostgreSQL connection count
docker-compose exec postgres psql -U webstore -c \
  "SELECT count(*) FROM pg_stat_activity;"

# Check connection pool settings in application
docker-compose logs main-service | grep -i "pool"
```

**Solutions with retry logic:**
```bash
#!/bin/bash
# Health check with exponential backoff
check_with_retry() {
    local url=$1
    local max_attempts=5
    local attempt=1
    local delay=1

    while [ $attempt -le $max_attempts ]; do
        if curl -sf --max-time 5 "$url" >/dev/null; then
            return 0
        fi

        echo "Attempt $attempt failed, retrying in ${delay}s..."
        sleep $delay
        delay=$((delay * 2))
        attempt=$((attempt + 1))
    done

    return 1
}
```

### False Positives and Flaky Health Checks

**Scenario 1: Service is functional but slow**
```bash
# Check if service is processing requests despite slow health check
docker-compose logs main-service --tail=50 | grep -v health

# Increase health check timeout in docker-compose.yml:
healthcheck:
  interval: 30s
  timeout: 10s  # Increased from 5s
  retries: 3
  start_period: 60s  # Give more time on startup
```

**Scenario 2: Health check endpoint itself has issues**
```python
# Enhanced health check endpoint with timeout
@app.get("/health")
async def health(request: Request):
    """Health check with database verification."""
    health_timeout = 2  # seconds

    try:
        # Quick database ping (with timeout)
        await asyncio.wait_for(
            database.execute("SELECT 1"),
            timeout=health_timeout
        )

        return {"status": "healthy"}
    except asyncio.TimeoutError:
        return {"status": "degraded", "reason": "db_timeout"}
    except Exception as e:
        return {"status": "unhealthy", "reason": str(e)}
```

**Scenario 3: Cached failures (Circuit Breaker Pattern)**
```bash
# Reset circuit breaker state
docker-compose restart main-service

# Or implement circuit breaker reset endpoint
curl -X POST http://localhost:8000/admin/reset-circuit-breaker
```

## Related Documentation

- **[08_DOCKER_AND_DEPLOYMENT.md](08_DOCKER_AND_DEPLOYMENT.md#health-checks-and-dependencies)**: Health check configuration in Docker Compose
- **[09_TROUBLESHOOTING.md](09_TROUBLESHOOTING.md)**: Common health check issues and solutions
- **[ARCHITECTURE.md](ARCHITECTURE.md)**: System architecture and service dependencies
- **[docker-compose.yml](../docker-compose.yml)**: Service health check configuration

---

**Last Updated**: 2025-10-19
